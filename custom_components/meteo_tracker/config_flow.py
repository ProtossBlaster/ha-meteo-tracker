"""Config and options flow for Meteo Tracker."""

from __future__ import annotations

import logging
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

from .api import InvalidApiKey, OpenWeatherClient, OpenWeatherError, RateLimited
from .const import (
    CONF_API_KEY,
    CONF_LANGUAGE,
    CONF_SCAN_INTERVAL_MINUTES,
    CONF_TRACKERS,
    DEFAULT_LANGUAGE,
    DEFAULT_NAME,
    DEFAULT_SCAN_INTERVAL_MINUTES,
    DOMAIN,
    MAX_SCAN_INTERVAL_MINUTES,
    MIN_SCAN_INTERVAL_MINUTES,
    SUPPORTED_LANGUAGES,
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


def _interval_selector() -> selector.NumberSelector:
    return selector.NumberSelector(
        selector.NumberSelectorConfig(
            min=MIN_SCAN_INTERVAL_MINUTES,
            max=MAX_SCAN_INTERVAL_MINUTES,
            step=1,
            unit_of_measurement="min",
            mode=selector.NumberSelectorMode.BOX,
        )
    )


async def _validate_key(hass, api_key: str) -> str | None:
    """Return an error slug, or ``None`` when the key works."""
    client = OpenWeatherClient(async_get_clientsession(hass), api_key)
    try:
        await client.async_validate(hass.config.latitude, hass.config.longitude)
    except InvalidApiKey:
        return "invalid_auth"
    except RateLimited:
        return "rate_limited"
    except OpenWeatherError:
        return "cannot_connect"
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
            error = await _validate_key(self.hass, user_input[CONF_API_KEY])
            if error:
                errors["base"] = error
            elif not user_input.get(CONF_TRACKERS):
                errors[CONF_TRACKERS] = "no_trackers"
            else:
                return self.async_create_entry(
                    title=user_input.get(CONF_NAME) or DEFAULT_NAME,
                    data={
                        CONF_API_KEY: user_input[CONF_API_KEY],
                        CONF_TRACKERS: user_input[CONF_TRACKERS],
                        CONF_SCAN_INTERVAL_MINUTES: int(
                            user_input[CONF_SCAN_INTERVAL_MINUTES]
                        ),
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

        if user_input is not None:
            if not user_input.get(CONF_TRACKERS):
                errors[CONF_TRACKERS] = "no_trackers"
            else:
                return self.async_create_entry(
                    title="",
                    data={
                        CONF_TRACKERS: user_input[CONF_TRACKERS],
                        CONF_SCAN_INTERVAL_MINUTES: int(
                            user_input[CONF_SCAN_INTERVAL_MINUTES]
                        ),
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
                ): _interval_selector(),
                vol.Required(
                    CONF_LANGUAGE,
                    default=current.get(CONF_LANGUAGE, DEFAULT_LANGUAGE),
                ): _language_selector(),
            }
        )
        return self.async_show_form(
            step_id="init", data_schema=schema, errors=errors
        )
