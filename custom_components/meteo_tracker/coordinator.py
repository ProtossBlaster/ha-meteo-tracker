"""Data update coordinator: resolves each tracker's location and polls OpenWeather."""

from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, State
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import slugify

from .api import InvalidApiKey, OpenWeatherClient, OpenWeatherError
from .const import COORD_PRECISION, DOMAIN

_LOGGER = logging.getLogger(__name__)


def resolve_coords(
    hass: HomeAssistant, state: State | None
) -> tuple[float, float] | None:
    """Best-effort (lat, lon) for a device_tracker state.

    Order of preference:
      1. GPS attributes on the tracker itself.
      2. The home zone, when the tracker reads ``home``.
      3. A matching ``zone.<slug>`` when the tracker reads a zone name.
    Returns ``None`` when no coordinates can be determined.
    """
    if state is None:
        return None

    lat = state.attributes.get("latitude")
    lon = state.attributes.get("longitude")
    if lat is not None and lon is not None:
        return float(lat), float(lon)

    value = (state.state or "").lower()
    if value in ("home", "casa"):
        return hass.config.latitude, hass.config.longitude

    zone = hass.states.get(f"zone.{slugify(value)}")
    if zone is not None:
        zlat = zone.attributes.get("latitude")
        zlon = zone.attributes.get("longitude")
        if zlat is not None and zlon is not None:
            return float(zlat), float(zlon)

    return None


def _tracker_name(hass: HomeAssistant, tracker_id: str, state: State | None) -> str:
    if state is not None and state.name:
        return state.name
    return tracker_id.split(".", 1)[-1].replace("_", " ").title()


class MeteoTrackerCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Polls OpenWeather once per cycle for every tracked person."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        client: OpenWeatherClient,
        trackers: list[str],
        scan_interval_minutes: int,
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(minutes=scan_interval_minutes),
        )
        self.entry = entry
        self.client = client
        self.trackers = trackers
        # How many distinct places the last cycle actually paid for. People
        # standing together share one fetch, so this is below the tracker count
        # whenever a household is at home — and it is what the call budget rides
        # on, which is why the options screen reads it rather than guessing.
        self.location_count = 0

    async def _async_update_data(self) -> dict[str, Any]:
        result: dict[str, Any] = {}
        # Cache responses per rounded coordinate so two people standing together
        # only cost one One Call request.
        cache: dict[tuple[float, float], dict[str, Any]] = {}
        successes = 0
        coordful = 0
        last_error: Exception | None = None

        for tracker_id in self.trackers:
            state = self.hass.states.get(tracker_id)
            name = _tracker_name(self.hass, tracker_id, state)
            coords = resolve_coords(self.hass, state)

            if coords is None:
                result[tracker_id] = {
                    "name": name,
                    "available": False,
                    "latitude": None,
                    "longitude": None,
                }
                continue

            coordful += 1
            lat, lon = coords
            key = (round(lat, COORD_PRECISION), round(lon, COORD_PRECISION))

            if key not in cache:
                try:
                    onecall = await self.client.async_one_call(lat, lon)
                    try:
                        air = await self.client.async_air_pollution(lat, lon)
                    except OpenWeatherError as err:
                        # Air quality is a bonus; never let it sink the whole row.
                        _LOGGER.debug("Air pollution fetch failed for %s: %s", name, err)
                        air = None
                    cache[key] = {"onecall": onecall, "air": air}
                except InvalidApiKey as err:
                    raise ConfigEntryAuthFailed(str(err)) from err
                except OpenWeatherError as err:
                    last_error = err
                    _LOGGER.warning("Weather fetch failed for %s: %s", name, err)
                    result[tracker_id] = {
                        "name": name,
                        "available": False,
                        "latitude": lat,
                        "longitude": lon,
                    }
                    continue

            successes += 1
            result[tracker_id] = {
                "name": name,
                "available": True,
                "latitude": lat,
                "longitude": lon,
                **cache[key],
            }

        self.location_count = len(cache)

        # Only fail the whole coordinator when every coordful tracker errored,
        # so a single flaky location degrades gracefully instead of blanking all.
        if coordful and successes == 0 and last_error is not None:
            raise UpdateFailed(str(last_error))

        return {"trackers": result}
