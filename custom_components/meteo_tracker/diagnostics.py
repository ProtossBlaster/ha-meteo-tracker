"""Diagnostics support for Meteo Tracker (API key always redacted)."""

from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.core import HomeAssistant

from . import MeteoTrackerConfigEntry
from .const import CONF_API_KEY

TO_REDACT = {CONF_API_KEY, "lat", "lon", "latitude", "longitude"}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: MeteoTrackerConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator = entry.runtime_data
    return {
        "entry": {
            "title": entry.title,
            "data": async_redact_data(dict(entry.data), TO_REDACT),
            "options": async_redact_data(dict(entry.options), TO_REDACT),
        },
        "trackers": coordinator.trackers,
        "last_update_success": coordinator.last_update_success,
        "data": async_redact_data(coordinator.data or {}, TO_REDACT),
    }
