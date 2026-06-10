"""Weather platform: one rich weather entity per tracked person."""

from __future__ import annotations

from typing import Any

from homeassistant.components.weather import (
    Forecast,
    WeatherEntity,
    WeatherEntityFeature,
)
from homeassistant.const import (
    UnitOfLength,
    UnitOfPrecipitationDepth,
    UnitOfPressure,
    UnitOfSpeed,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import dt as dt_util

from . import MeteoTrackerConfigEntry
from .entity import MeteoTrackerEntity
from .weather_codes import map_condition


async def async_setup_entry(
    hass: HomeAssistant,
    entry: MeteoTrackerConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Create one weather entity per tracked person."""
    coordinator = entry.runtime_data
    async_add_entities(
        MeteoTrackerWeather(coordinator, tracker_id)
        for tracker_id in coordinator.trackers
    )


def _precip(block: dict[str, Any]) -> float | None:
    """Total liquid-equivalent precipitation (mm) from a rain/snow block."""
    rain = (block.get("rain") or {})
    snow = (block.get("snow") or {})
    total = 0.0
    seen = False
    for src, field in ((rain, "1h"), (snow, "1h")):
        if isinstance(src, dict) and field in src:
            total += float(src[field])
            seen = True
        elif isinstance(src, (int, float)):
            total += float(src)
            seen = True
    return round(total, 2) if seen else None


def _utc_iso(ts: int | None) -> str | None:
    if ts is None:
        return None
    return dt_util.utc_from_timestamp(ts).isoformat()


class MeteoTrackerWeather(MeteoTrackerEntity, WeatherEntity):
    """A weather entity backed by OpenWeather One Call 3.0 for one person."""

    _attr_name = None  # take the device (person) name
    _attr_native_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_native_pressure_unit = UnitOfPressure.HPA
    _attr_native_wind_speed_unit = UnitOfSpeed.METERS_PER_SECOND
    _attr_native_visibility_unit = UnitOfLength.KILOMETERS
    _attr_native_precipitation_unit = UnitOfPrecipitationDepth.MILLIMETERS
    _attr_supported_features = (
        WeatherEntityFeature.FORECAST_DAILY
        | WeatherEntityFeature.FORECAST_HOURLY
        | WeatherEntityFeature.FORECAST_TWICE_DAILY
    )

    def __init__(self, coordinator, tracker_id: str) -> None:
        super().__init__(coordinator, tracker_id)
        self._attr_unique_id = f"{coordinator.entry.entry_id}_{tracker_id}_weather"

    @callback
    def _handle_coordinator_update(self) -> None:
        # Refresh the current conditions and push fresh forecasts to any card
        # subscribed via the websocket forecast API.
        self.async_write_ha_state()
        self.hass.async_create_task(
            self.async_update_listeners(["daily", "hourly", "twice_daily"])
        )

    @property
    def _current(self) -> dict[str, Any]:
        onecall = self._onecall or {}
        return onecall.get("current") or {}

    @property
    def condition(self) -> str | None:
        weather = (self._current.get("weather") or [{}])[0]
        if not weather:
            return None
        return map_condition(weather.get("id"), weather.get("icon"))

    @property
    def native_temperature(self) -> float | None:
        return self._current.get("temp")

    @property
    def native_apparent_temperature(self) -> float | None:
        return self._current.get("feels_like")

    @property
    def native_pressure(self) -> float | None:
        return self._current.get("pressure")

    @property
    def humidity(self) -> float | None:
        return self._current.get("humidity")

    @property
    def native_dew_point(self) -> float | None:
        return self._current.get("dew_point")

    @property
    def native_wind_speed(self) -> float | None:
        return self._current.get("wind_speed")

    @property
    def native_wind_gust_speed(self) -> float | None:
        return self._current.get("wind_gust")

    @property
    def wind_bearing(self) -> float | None:
        return self._current.get("wind_deg")

    @property
    def cloud_coverage(self) -> float | None:
        return self._current.get("clouds")

    @property
    def uv_index(self) -> float | None:
        return self._current.get("uvi")

    @property
    def native_visibility(self) -> float | None:
        visibility = self._current.get("visibility")
        if visibility is None:
            return None
        return round(visibility / 1000, 2)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Surface the fine-grained wording HA's 15-state ``condition`` can't hold.

        ``detailed_description`` carries OpenWeather's precise, localised phrase
        (e.g. "Temporale con pioggia forte"); the daily summary and any active
        government alert are exposed here too, right on the weather entity.
        """
        onecall = self._onecall or {}
        weather = (self._current.get("weather") or [{}])[0]
        daily = onecall.get("daily") or []
        alerts = onecall.get("alerts") or []
        description = weather.get("description")
        return {
            "detailed_description": description.capitalize() if description else None,
            "openweather_id": weather.get("id"),
            "daily_summary": daily[0].get("summary") if daily else None,
            "alert_active": bool(alerts),
            "alert": alerts[0].get("event") if alerts else None,
            "alert_count": len(alerts),
        }

    # ---- Forecasts -------------------------------------------------------

    def _hourly(self) -> list[Forecast] | None:
        hours = (self._onecall or {}).get("hourly")
        if not hours:
            return None
        out: list[Forecast] = []
        for hour in hours:
            weather = (hour.get("weather") or [{}])[0]
            pop = hour.get("pop")
            out.append(
                {
                    "datetime": _utc_iso(hour.get("dt")),
                    "condition": map_condition(
                        weather.get("id"), weather.get("icon")
                    ),
                    "native_temperature": hour.get("temp"),
                    "native_apparent_temperature": hour.get("feels_like"),
                    "native_pressure": hour.get("pressure"),
                    "humidity": hour.get("humidity"),
                    "native_dew_point": hour.get("dew_point"),
                    "cloud_coverage": hour.get("clouds"),
                    "native_wind_speed": hour.get("wind_speed"),
                    "native_wind_gust_speed": hour.get("wind_gust"),
                    "wind_bearing": hour.get("wind_deg"),
                    "uv_index": hour.get("uvi"),
                    "precipitation_probability": (
                        round(pop * 100) if pop is not None else None
                    ),
                    "native_precipitation": _precip(hour),
                }
            )
        return out

    def _daily(self) -> list[Forecast] | None:
        days = (self._onecall or {}).get("daily")
        if not days:
            return None
        out: list[Forecast] = []
        for day in days:
            weather = (day.get("weather") or [{}])[0]
            temp = day.get("temp") or {}
            feels = day.get("feels_like") or {}
            pop = day.get("pop")
            out.append(
                {
                    "datetime": _utc_iso(day.get("dt")),
                    "condition": map_condition(
                        weather.get("id"), weather.get("icon")
                    ),
                    "native_temperature": temp.get("max"),
                    "native_templow": temp.get("min"),
                    "native_apparent_temperature": feels.get("day"),
                    "native_pressure": day.get("pressure"),
                    "humidity": day.get("humidity"),
                    "native_dew_point": day.get("dew_point"),
                    "cloud_coverage": day.get("clouds"),
                    "native_wind_speed": day.get("wind_speed"),
                    "native_wind_gust_speed": day.get("wind_gust"),
                    "wind_bearing": day.get("wind_deg"),
                    "uv_index": day.get("uvi"),
                    "precipitation_probability": (
                        round(pop * 100) if pop is not None else None
                    ),
                    "native_precipitation": _precip(day),
                }
            )
        return out

    def _twice_daily(self) -> list[Forecast] | None:
        days = (self._onecall or {}).get("daily")
        if not days:
            return None
        out: list[Forecast] = []
        for day in days:
            weather = (day.get("weather") or [{}])[0]
            temp = day.get("temp") or {}
            condition = map_condition(weather.get("id"), weather.get("icon"))
            pop = day.get("pop")
            precip = _precip(day)
            prob = round(pop * 100) if pop is not None else None
            out.append(
                {
                    "datetime": _utc_iso(day.get("dt")),
                    "is_daytime": True,
                    "condition": condition,
                    "native_temperature": temp.get("max"),
                    "native_templow": temp.get("min"),
                    "precipitation_probability": prob,
                    "native_precipitation": precip,
                    "native_wind_speed": day.get("wind_speed"),
                    "wind_bearing": day.get("wind_deg"),
                }
            )
            out.append(
                {
                    "datetime": _utc_iso(day.get("sunset") or day.get("dt")),
                    "is_daytime": False,
                    "condition": condition,
                    "native_temperature": temp.get("night"),
                    "precipitation_probability": prob,
                    "native_precipitation": precip,
                    "native_wind_speed": day.get("wind_speed"),
                    "wind_bearing": day.get("wind_deg"),
                }
            )
        return out

    async def async_forecast_hourly(self) -> list[Forecast] | None:
        return self._hourly()

    async def async_forecast_daily(self) -> list[Forecast] | None:
        return self._daily()

    async def async_forecast_twice_daily(self) -> list[Forecast] | None:
        return self._twice_daily()
