"""Config and options flow for Meteo Tracker."""

from __future__ import annotations

import logging
from collections.abc import Mapping
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.core import callback
from homeassistant.helpers import selector
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import (
    InvalidApiKey,
    OpenWeatherClient,
    OpenWeatherError,
    RateLimited,
    async_detect_api_version,
)
from .const import (
    API_V3,
    API_V4,
    CONF_API_KEY,
    CONF_API_VERSION,
    CONF_LANGUAGE,
    CONF_SCAN_INTERVAL_MINUTES,
    CONF_TRACKERS,
    DEFAULT_API_VERSION,
    DEFAULT_LANGUAGE,
    DEFAULT_NAME,
    DEFAULT_SCAN_INTERVAL_MINUTES,
    DOMAIN,
    MAX_SCAN_INTERVAL_MINUTES,
    MIN_SCAN_INTERVAL_MINUTES,
    SUPPORTED_LANGUAGES,
    min_interval_for,
)

_LOGGER = logging.getLogger(__name__)

CONF_NAME = "name"


def _language_selector() -> selector.SelectSelector:
    return selector.SelectSelector(
        selector.SelectSelectorConfig(
            options=SUPPORTED_LANGUAGES,
            mode=selector.SelectSelectorMode.DROPDOWN,
        )
    )


def _trackers_selector() -> selector.EntitySelector:
    return selector.EntitySelector(
        selector.EntitySelectorConfig(domain="device_tracker", multiple=True)
    )


def _interval_selector(api_version: str | None = None) -> selector.NumberSelector:
    # Once the entry's One Call version is known the picker starts at the
    # cheapest interval that version can afford, so the value cannot be wrong.
    return selector.NumberSelector(
        selector.NumberSelectorConfig(
            min=min_interval_for(api_version) if api_version else MIN_SCAN_INTERVAL_MINUTES,
            max=MAX_SCAN_INTERVAL_MINUTES,
            step=1,
            unit_of_measurement="min",
            mode=selector.NumberSelectorMode.BOX,
        )
    )


async def _detect_version(hass, api_key: str) -> tuple[str | None, str | None]:
    """Return ``(one_call_version, error_slug)`` for this key.

    Which One Call product a key can reach is not something the user can be
    expected to know — OpenWeather sells 3.0 to nobody new, so the same key that
    works for one account is refused for another. Probing settles it here, and
    the answer is stored so no refresh ever has to guess.
    """
    try:
        version = await async_detect_api_version(
            async_get_clientsession(hass),
            api_key,
            hass.config.latitude,
            hass.config.longitude,
        )
    except InvalidApiKey as err:
        # The form can only show a fixed sentence, but OpenWeather's own wording
        # is what tells the user whether the key is wrong, unsubscribed or just
        # too new — so it goes in the log, where the form sends them looking.
        _LOGGER.warning("OpenWeather refused the API key: %s", err)
        return None, "invalid_auth"
    except RateLimited:
        return None, "rate_limited"
    except OpenWeatherError as err:
        _LOGGER.warning("Could not reach OpenWeather to check the key: %s", err)
        return None, "cannot_connect"
    _LOGGER.debug("OpenWeather key accepted by One Call %s", version)
    return version, None


def _version_selector() -> selector.SelectSelector:
    return selector.SelectSelector(
        selector.SelectSelectorConfig(
            options=[API_V3, API_V4],
            mode=selector.SelectSelectorMode.DROPDOWN,
        )
    )


async def _key_reaches(hass, api_key: str, api_version: str) -> str | None:
    """Check the key against one chosen version. Error slug, or ``None`` if it works.

    Used when someone moves an existing entry between versions: the answer must
    come from OpenWeather, not from what was true the day the entry was made.
    """
    client = OpenWeatherClient(
        async_get_clientsession(hass), api_key, api_version=api_version
    )
    try:
        await client.async_validate(hass.config.latitude, hass.config.longitude)
    except InvalidApiKey as err:
        _LOGGER.warning(
            "OpenWeather refused this key for One Call %s: %s", api_version, err
        )
        return "version_unavailable"
    except RateLimited:
        return "rate_limited"
    except OpenWeatherError as err:
        _LOGGER.warning("Could not reach OpenWeather: %s", err)
        return "cannot_connect"
    return None


def _interval_error(api_version: str | None, minutes: int) -> str | None:
    """Refuse an interval the chosen One Call version cannot afford."""
    if minutes < min_interval_for(api_version):
        return "interval_too_low_v4" if api_version == API_V4 else "interval_too_low"
    return None


class MeteoTrackerConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle the initial setup."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        default_lang = (
            self.hass.config.language
            if self.hass.config.language in SUPPORTED_LANGUAGES
            else DEFAULT_LANGUAGE
        )

        if user_input is not None:
            interval = int(user_input[CONF_SCAN_INTERVAL_MINUTES])
            version, error = await _detect_version(
                self.hass, user_input[CONF_API_KEY]
            )
            interval_error = _interval_error(version, interval)
            if error:
                errors["base"] = error
            elif not user_input.get(CONF_TRACKERS):
                errors[CONF_TRACKERS] = "no_trackers"
            elif interval_error:
                errors[CONF_SCAN_INTERVAL_MINUTES] = interval_error
            else:
                return self.async_create_entry(
                    title=user_input.get(CONF_NAME) or DEFAULT_NAME,
                    data={
                        CONF_API_KEY: user_input[CONF_API_KEY],
                        CONF_API_VERSION: version,
                        CONF_TRACKERS: user_input[CONF_TRACKERS],
                        CONF_SCAN_INTERVAL_MINUTES: interval,
                        CONF_LANGUAGE: user_input[CONF_LANGUAGE],
                    },
                )

        suggested = user_input or {}
        schema = vol.Schema(
            {
                vol.Optional(
                    CONF_NAME, default=suggested.get(CONF_NAME, DEFAULT_NAME)
                ): str,
                vol.Required(
                    CONF_API_KEY, default=suggested.get(CONF_API_KEY, "")
                ): selector.TextSelector(
                    selector.TextSelectorConfig(
                        type=selector.TextSelectorType.PASSWORD
                    )
                ),
                vol.Required(
                    CONF_TRACKERS, default=suggested.get(CONF_TRACKERS, [])
                ): _trackers_selector(),
                vol.Required(
                    CONF_SCAN_INTERVAL_MINUTES,
                    default=suggested.get(
                        CONF_SCAN_INTERVAL_MINUTES, DEFAULT_SCAN_INTERVAL_MINUTES
                    ),
                ): _interval_selector(),
                vol.Required(
                    CONF_LANGUAGE,
                    default=suggested.get(CONF_LANGUAGE, default_lang),
                ): _language_selector(),
            }
        )
        return self.async_show_form(
            step_id="user", data_schema=schema, errors=errors
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """OpenWeather stopped accepting the key this entry was set up with.

        This is the path every 3.0 user lands on the day OpenWeather stops
        serving 3.0, so it has to be able to carry the entry across to 4.0.
        """
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Re-probe the key and, if the version changed, move the entry to it.

        The existing entry is updated rather than replaced: every entity's unique
        ID is built from the entry id, so a new entry would hand all 40-odd
        entities new identities and start their history over.
        """
        entry = self._get_reauth_entry()
        errors: dict[str, str] = {}
        stored = entry.data.get(CONF_API_VERSION, DEFAULT_API_VERSION)

        if user_input is not None:
            api_key = user_input.get(CONF_API_KEY) or entry.data[CONF_API_KEY]
            version, error = await _detect_version(self.hass, api_key)
            if error:
                errors["base"] = error
            else:
                options = dict(entry.options)
                floor = min_interval_for(version)
                interval = int(
                    options.get(
                        CONF_SCAN_INTERVAL_MINUTES,
                        entry.data.get(
                            CONF_SCAN_INTERVAL_MINUTES,
                            DEFAULT_SCAN_INTERVAL_MINUTES,
                        ),
                    )
                )
                if version != stored:
                    _LOGGER.warning(
                        "Meteo Tracker entry %s moves from One Call %s to %s: "
                        "OpenWeather no longer accepts this key for %s",
                        entry.title,
                        stored,
                        version,
                        stored,
                    )
                if interval < floor:
                    # Raise it here as well as in setup, so the options screen
                    # shows the interval actually being used.
                    options[CONF_SCAN_INTERVAL_MINUTES] = floor
                    _LOGGER.warning(
                        "Refresh interval raised from %d to %d min, the minimum "
                        "One Call %s can afford",
                        interval,
                        floor,
                        version,
                    )
                return self.async_update_reload_and_abort(
                    entry,
                    data_updates={
                        CONF_API_KEY: api_key,
                        CONF_API_VERSION: version,
                    },
                    options=options,
                    reason="reauth_successful",
                )

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema(
                {
                    vol.Optional(CONF_API_KEY, default=""): selector.TextSelector(
                        selector.TextSelectorConfig(
                            type=selector.TextSelectorType.PASSWORD
                        )
                    )
                }
            ),
            errors=errors,
            description_placeholders={"version": stored},
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        return MeteoTrackerOptionsFlow()


class MeteoTrackerOptionsFlow(OptionsFlow):
    """Edit trackers, refresh interval and language after setup."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        # Initial values live in entry.data; options override them once edited.
        current = {**self.config_entry.data, **self.config_entry.options}

        stored_version = current.get(CONF_API_VERSION, DEFAULT_API_VERSION)

        if user_input is not None:
            interval = int(user_input[CONF_SCAN_INTERVAL_MINUTES])
            version = user_input.get(CONF_API_VERSION, stored_version)
            # Only spend a request when the version actually changes: the entry
            # is already proving every refresh that the current one works.
            version_error = (
                None
                if version == stored_version
                else await _key_reaches(
                    self.hass, self.config_entry.data[CONF_API_KEY], version
                )
            )
            interval_error = _interval_error(version, interval)

            if not user_input.get(CONF_TRACKERS):
                errors[CONF_TRACKERS] = "no_trackers"
            elif version_error:
                errors[CONF_API_VERSION] = version_error
            elif interval_error:
                errors[CONF_SCAN_INTERVAL_MINUTES] = interval_error
            else:
                return self.async_create_entry(
                    title="",
                    data={
                        CONF_TRACKERS: user_input[CONF_TRACKERS],
                        CONF_API_VERSION: version,
                        CONF_SCAN_INTERVAL_MINUTES: interval,
                        CONF_LANGUAGE: user_input[CONF_LANGUAGE],
                    },
                )

        schema = vol.Schema(
            {
                vol.Required(
                    CONF_TRACKERS,
                    default=current.get(CONF_TRACKERS, []),
                ): _trackers_selector(),
                vol.Required(
                    CONF_SCAN_INTERVAL_MINUTES,
                    default=current.get(
                        CONF_SCAN_INTERVAL_MINUTES, DEFAULT_SCAN_INTERVAL_MINUTES
                    ),
                ): _interval_selector(stored_version),
                vol.Required(
                    CONF_API_VERSION, default=stored_version
                ): _version_selector(),
                vol.Required(
                    CONF_LANGUAGE,
                    default=current.get(CONF_LANGUAGE, DEFAULT_LANGUAGE),
                ): _language_selector(),
            }
        )
        return self.async_show_form(
            step_id="init", data_schema=schema, errors=errors
        )
