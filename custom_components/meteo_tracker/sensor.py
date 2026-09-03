"""Sensor platform: a rich set of per-person weather & air-quality sensors."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    DEGREE,
    PERCENTAGE,
    UnitOfLength,
    UnitOfPrecipitationDepth,
    UnitOfPressure,
    UnitOfSpeed,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import dt as dt_util

from . import MeteoTrackerConfigEntry
from .entity import MeteoTrackerEntity
from .weather import _precip
from .weather_codes import (
    aqi_label,
    compact_summary,
    map_condition,
    moon_phase_name,
    wind_cardinal,
)

MEASUREMENT = SensorStateClass.MEASUREMENT
try:  # HA 2026.7+
    from homeassistant.const import UnitOfDensity

    MICROGRAMS = UnitOfDensity.MICROGRAMS_PER_CUBIC_METER
except ImportError:  # HA < 2026.7, where UnitOfDensity does not exist yet
    from homeassistant.const import (  # noqa: F401
        CONCENTRATION_MICROGRAMS_PER_CUBIC_METER as MICROGRAMS,
    )

MOON_PHASES = [
    "new_moon", "waxing_crescent", "first_quarter", "waxing_gibbous",
    "full_moon", "waning_gibbous", "last_quarter", "waning_crescent",
]
AQI_LABELS = ["good", "fair", "moderate", "poor", "very_poor"]
# Lowercase slugs so they are valid Home Assistant enum/translation keys.
COMPASS_POINTS = [
    "n", "nne", "ne", "ene", "e", "ese", "se", "sse",
    "s", "ssw", "sw", "wsw", "w", "wnw", "nw", "nnw",
]


# ---- safe accessors over the per-tracker payload --------------------------


def _cur(d: dict) -> dict:
    return ((d.get("onecall") or {}).get("current") or {})


def _today(d: dict) -> dict:
    daily = (d.get("onecall") or {}).get("daily") or []
    return daily[0] if daily else {}


def _hour0(d: dict) -> dict:
    hourly = (d.get("onecall") or {}).get("hourly") or []
    return hourly[0] if hourly else {}


def _air_main(d: dict) -> dict:
    lst = (d.get("air") or {}).get("list") or []
    return (lst[0].get("main") if lst else {}) or {}


def _air_comp(d: dict) -> dict:
    lst = (d.get("air") or {}).get("list") or []
    return (lst[0].get("components") if lst else {}) or {}


def _ts(ts: int | None) -> datetime | None:
    return dt_util.utc_from_timestamp(ts) if ts is not None else None


def _km(meters: float | None) -> float | None:
    return round(meters / 1000, 2) if meters is not None else None


def _pct(value: float | None) -> float | None:
    return round(value * 100) if value is not None else None


def _location(d: dict) -> str | None:
    lat, lon = d.get("latitude"), d.get("longitude")
    if lat is None or lon is None:
        return None
    return f"{lat:.4f}, {lon:.4f}"


def _condition(d: dict) -> str | None:
    weather = (_cur(d).get("weather") or [{}])[0]
    return map_condition(weather.get("id"), weather.get("icon")) if weather else None


def _description(d: dict) -> str | None:
    weather = (_cur(d).get("weather") or [{}])[0]
    desc = weather.get("description")
    return desc.capitalize() if isinstance(desc, str) else None


def _wind_dir(d: dict) -> str | None:
    cardinal = wind_cardinal(_cur(d).get("wind_deg"))
    return cardinal.lower() if cardinal else None


def _minutely_sum(d: dict) -> float | None:
    minutely = (d.get("onecall") or {}).get("minutely") or []
    if not minutely:
        return None
    return round(sum(m.get("precipitation", 0) or 0 for m in minutely), 2)


@dataclass(frozen=True, kw_only=True)
class MeteoSensorDescription(SensorEntityDescription):
    """A sensor description carrying its value extractor."""

    value_fn: Callable[[dict], Any]


SENSORS: tuple[MeteoSensorDescription, ...] = (
    # --- core current weather ---------------------------------------------
    MeteoSensorDescription(
        key="temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=MEASUREMENT,
        value_fn=lambda d: _cur(d).get("temp"),
    ),
    MeteoSensorDescription(
        key="apparent_temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=MEASUREMENT,
        value_fn=lambda d: _cur(d).get("feels_like"),
    ),
    MeteoSensorDescription(
        key="temp_min_today",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        value_fn=lambda d: (_today(d).get("temp") or {}).get("min"),
    ),
    MeteoSensorDescription(
        key="temp_max_today",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        value_fn=lambda d: (_today(d).get("temp") or {}).get("max"),
    ),
    MeteoSensorDescription(
        key="pressure",
        device_class=SensorDeviceClass.ATMOSPHERIC_PRESSURE,
        native_unit_of_measurement=UnitOfPressure.HPA,
        state_class=MEASUREMENT,
        value_fn=lambda d: _cur(d).get("pressure"),
    ),
    MeteoSensorDescription(
        key="humidity",
        device_class=SensorDeviceClass.HUMIDITY,
        native_unit_of_measurement=PERCENTAGE,
        state_class=MEASUREMENT,
        value_fn=lambda d: _cur(d).get("humidity"),
    ),
    MeteoSensorDescription(
        key="dew_point",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=MEASUREMENT,
        value_fn=lambda d: _cur(d).get("dew_point"),
    ),
    MeteoSensorDescription(
        key="uv_index",
        icon="mdi:weather-sunny-alert",
        state_class=MEASUREMENT,
        value_fn=lambda d: _cur(d).get("uvi"),
    ),
    MeteoSensorDescription(
        key="cloud_coverage",
        icon="mdi:cloud-percent",
        native_unit_of_measurement=PERCENTAGE,
        state_class=MEASUREMENT,
        value_fn=lambda d: _cur(d).get("clouds"),
    ),
    MeteoSensorDescription(
        key="visibility",
        device_class=SensorDeviceClass.DISTANCE,
        native_unit_of_measurement=UnitOfLength.KILOMETERS,
        state_class=MEASUREMENT,
        value_fn=lambda d: _km(_cur(d).get("visibility")),
    ),
    MeteoSensorDescription(
        key="wind_speed",
        device_class=SensorDeviceClass.WIND_SPEED,
        native_unit_of_measurement=UnitOfSpeed.METERS_PER_SECOND,
        state_class=MEASUREMENT,
        value_fn=lambda d: _cur(d).get("wind_speed"),
    ),
    MeteoSensorDescription(
        key="wind_gust",
        device_class=SensorDeviceClass.WIND_SPEED,
        native_unit_of_measurement=UnitOfSpeed.METERS_PER_SECOND,
        state_class=MEASUREMENT,
        value_fn=lambda d: _cur(d).get("wind_gust"),
    ),
    MeteoSensorDescription(
        key="wind_bearing",
        icon="mdi:compass",
        native_unit_of_measurement=DEGREE,
        state_class=MEASUREMENT,
        value_fn=lambda d: _cur(d).get("wind_deg"),
    ),
    MeteoSensorDescription(
        key="wind_direction",
        icon="mdi:compass-outline",
        device_class=SensorDeviceClass.ENUM,
        options=COMPASS_POINTS,
        value_fn=_wind_dir,
    ),
    MeteoSensorDescription(
        key="precipitation_1h",
        device_class=SensorDeviceClass.PRECIPITATION,
        native_unit_of_measurement=UnitOfPrecipitationDepth.MILLIMETERS,
        state_class=MEASUREMENT,
        value_fn=lambda d: _precip(_cur(d)),
    ),
    MeteoSensorDescription(
        key="precipitation_probability",
        icon="mdi:weather-rainy",
        native_unit_of_measurement=PERCENTAGE,
        state_class=MEASUREMENT,
        value_fn=lambda d: _pct(_hour0(d).get("pop")),
    ),
    MeteoSensorDescription(
        key="precipitation_next_hour",
        icon="mdi:weather-pouring",
        device_class=SensorDeviceClass.PRECIPITATION,
        native_unit_of_measurement=UnitOfPrecipitationDepth.MILLIMETERS,
        value_fn=_minutely_sum,
    ),
    MeteoSensorDescription(
        key="rain_today",
        device_class=SensorDeviceClass.PRECIPITATION,
        native_unit_of_measurement=UnitOfPrecipitationDepth.MILLIMETERS,
        value_fn=lambda d: _today(d).get("rain"),
    ),
    MeteoSensorDescription(
        key="snow_today",
        device_class=SensorDeviceClass.PRECIPITATION,
        native_unit_of_measurement=UnitOfPrecipitationDepth.MILLIMETERS,
        value_fn=lambda d: _today(d).get("snow"),
    ),
    # --- descriptive ------------------------------------------------------
    MeteoSensorDescription(
        key="condition",
        icon="mdi:weather-partly-cloudy",
        value_fn=_condition,
    ),
    MeteoSensorDescription(
        key="weather_description",
        icon="mdi:text-short",
        value_fn=_description,
    ),
    MeteoSensorDescription(
        key="weather_summary",
        icon="mdi:text-long",
        value_fn=lambda d: compact_summary(_today(d)),
    ),
    # --- sun & moon -------------------------------------------------------
    MeteoSensorDescription(
        key="sunrise",
        device_class=SensorDeviceClass.TIMESTAMP,
        icon="mdi:weather-sunset-up",
        value_fn=lambda d: _ts(_cur(d).get("sunrise")),
    ),
    MeteoSensorDescription(
        key="sunset",
        device_class=SensorDeviceClass.TIMESTAMP,
        icon="mdi:weather-sunset-down",
        value_fn=lambda d: _ts(_cur(d).get("sunset")),
    ),
    MeteoSensorDescription(
        key="moonrise",
        device_class=SensorDeviceClass.TIMESTAMP,
        icon="mdi:weather-night",
        value_fn=lambda d: _ts(_today(d).get("moonrise")),
    ),
    MeteoSensorDescription(
        key="moonset",
        device_class=SensorDeviceClass.TIMESTAMP,
        icon="mdi:weather-night",
        value_fn=lambda d: _ts(_today(d).get("moonset")),
    ),
    MeteoSensorDescription(
        key="moon_phase",
        icon="mdi:moon-waning-crescent",
        device_class=SensorDeviceClass.ENUM,
        options=MOON_PHASES,
        value_fn=lambda d: moon_phase_name(_today(d).get("moon_phase")),
    ),
    MeteoSensorDescription(
        key="moon_phase_value",
        icon="mdi:moon-full",
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=MEASUREMENT,
        value_fn=lambda d: _today(d).get("moon_phase"),
    ),
    # --- air quality ------------------------------------------------------
    MeteoSensorDescription(
        key="air_quality_index",
        device_class=SensorDeviceClass.AQI,
        state_class=MEASUREMENT,
        value_fn=lambda d: _air_main(d).get("aqi"),
    ),
    MeteoSensorDescription(
        key="air_quality_label",
        icon="mdi:air-filter",
        device_class=SensorDeviceClass.ENUM,
        options=AQI_LABELS,
        value_fn=lambda d: aqi_label(_air_main(d).get("aqi")),
    ),
    MeteoSensorDescription(
        key="pm25",
        device_class=SensorDeviceClass.PM25,
        native_unit_of_measurement=MICROGRAMS,
        state_class=MEASUREMENT,
        value_fn=lambda d: _air_comp(d).get("pm2_5"),
    ),
    MeteoSensorDescription(
        key="pm10",
        device_class=SensorDeviceClass.PM10,
        native_unit_of_measurement=MICROGRAMS,
        state_class=MEASUREMENT,
        value_fn=lambda d: _air_comp(d).get("pm10"),
    ),
    MeteoSensorDescription(
        key="ozone",
        device_class=SensorDeviceClass.OZONE,
        native_unit_of_measurement=MICROGRAMS,
        state_class=MEASUREMENT,
        value_fn=lambda d: _air_comp(d).get("o3"),
    ),
    MeteoSensorDescription(
        key="nitrogen_dioxide",
        device_class=SensorDeviceClass.NITROGEN_DIOXIDE,
        native_unit_of_measurement=MICROGRAMS,
        state_class=MEASUREMENT,
        value_fn=lambda d: _air_comp(d).get("no2"),
    ),
    MeteoSensorDescription(
        key="sulphur_dioxide",
        device_class=SensorDeviceClass.SULPHUR_DIOXIDE,
        native_unit_of_measurement=MICROGRAMS,
        state_class=MEASUREMENT,
        value_fn=lambda d: _air_comp(d).get("so2"),
    ),
    MeteoSensorDescription(
        key="carbon_monoxide",
        icon="mdi:molecule-co",
        native_unit_of_measurement=MICROGRAMS,
        state_class=MEASUREMENT,
        value_fn=lambda d: _air_comp(d).get("co"),
    ),
    MeteoSensorDescription(
        key="nitrogen_monoxide",
        icon="mdi:molecule",
        native_unit_of_measurement=MICROGRAMS,
        state_class=MEASUREMENT,
        value_fn=lambda d: _air_comp(d).get("no"),
    ),
    MeteoSensorDescription(
        key="ammonia",
        icon="mdi:molecule",
        native_unit_of_measurement=MICROGRAMS,
        state_class=MEASUREMENT,
        value_fn=lambda d: _air_comp(d).get("nh3"),
    ),
    # --- diagnostics ------------------------------------------------------
    MeteoSensorDescription(
        key="location",
        icon="mdi:map-marker",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=_location,
    ),
    MeteoSensorDescription(
        key="last_measured",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda d: _ts(_cur(d).get("dt")),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: MeteoTrackerConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Create the full sensor cluster for every tracked person."""
    coordinator = entry.runtime_data
    async_add_entities(
        MeteoTrackerSensor(coordinator, tracker_id, description)
        for tracker_id in coordinator.trackers
        for description in SENSORS
    )


class MeteoTrackerSensor(MeteoTrackerEntity, SensorEntity):
    """A single per-person weather or air-quality sensor."""

    entity_description: MeteoSensorDescription

    def __init__(self, coordinator, tracker_id: str, description) -> None:
        super().__init__(coordinator, tracker_id)
        self.entity_description = description
        self._attr_translation_key = description.key
        self._attr_unique_id = (
            f"{coordinator.entry.entry_id}_{tracker_id}_{description.key}"
        )

    @property
    def native_value(self) -> Any:
        try:
            return self.entity_description.value_fn(self._tracker_data)
        except (TypeError, ValueError, IndexError, KeyError, AttributeError):
            return None
