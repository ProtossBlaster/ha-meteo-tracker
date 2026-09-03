"""The Meteo Tracker integration: per-person OpenWeather from device_trackers."""

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import OpenWeatherClient
from .const import (
    CONF_API_KEY,
    CONF_API_VERSION,
    CONF_LANGUAGE,
    CONF_SCAN_INTERVAL_MINUTES,
    CONF_TRACKERS,
    DEFAULT_API_VERSION,
    DEFAULT_LANGUAGE,
    DEFAULT_SCAN_INTERVAL_MINUTES,
    DOMAIN,
    min_interval_for,
)
from .coordinator import MeteoTrackerCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [
    Platform.WEATHER,
    Platform.SENSOR,
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
]

MeteoTrackerConfigEntry = ConfigEntry[MeteoTrackerCoordinator]


def _opt(entry: ConfigEntry, key: str, default):
    """Read a value preferring options, falling back to entry data."""
    return entry.options.get(key, entry.data.get(key, default))


async def async_setup_entry(
    hass: HomeAssistant, entry: MeteoTrackerConfigEntry
) -> bool:
    """Set up Meteo Tracker from a config entry."""
    session = async_get_clientsession(hass)
    # Entries written before 4.0 support existed carry no version, and they are
    # all 3.0 — that is the only product that was on sale when they were made.
    api_version = _opt(entry, CONF_API_VERSION, DEFAULT_API_VERSION)
    client = OpenWeatherClient(
        session,
        entry.data[CONF_API_KEY],
        language=_opt(entry, CONF_LANGUAGE, DEFAULT_LANGUAGE),
        units="metric",
        api_version=api_version,
    )

    trackers: list[str] = list(_opt(entry, CONF_TRACKERS, []))
    if not trackers:
        _LOGGER.warning("Meteo Tracker entry %s has no trackers configured", entry.title)

    # The floor is held here too, not just in the UI: an entry edited by hand
    # or carried over from 3.0 must not be able to bill six calls every minute.
    floor = min_interval_for(api_version)
    interval = int(_opt(entry, CONF_SCAN_INTERVAL_MINUTES, DEFAULT_SCAN_INTERVAL_MINUTES))
    if interval < floor:
        _LOGGER.warning(
            "Refresh interval of %d min is below the %d min One Call %s needs; "
            "using %d min",
            interval,
            floor,
            api_version,
            floor,
        )
        interval = floor

    coordinator = MeteoTrackerCoordinator(hass, entry, client, trackers, interval)

    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_reload_entry))
    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: MeteoTrackerConfigEntry
) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def _async_reload_entry(
    hass: HomeAssistant, entry: MeteoTrackerConfigEntry
) -> None:
    """Reload the entry when its options change."""
    await hass.config_entries.async_reload(entry.entry_id)
