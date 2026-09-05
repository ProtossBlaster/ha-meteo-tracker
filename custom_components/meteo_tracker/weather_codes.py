"""Pure, Home-Assistant-free helpers for translating OpenWeather data.

Everything in this module is deliberately free of any ``homeassistant`` import so
it can be unit-tested in isolation (see ``tests/test_weather_codes.py``).
"""

from __future__ import annotations

# Home Assistant weather conditions (the only strings the frontend understands).
ATTR_CONDITION_CLEAR_NIGHT = "clear-night"
ATTR_CONDITION_CLOUDY = "cloudy"
ATTR_CONDITION_EXCEPTIONAL = "exceptional"
ATTR_CONDITION_FOG = "fog"
ATTR_CONDITION_HAIL = "hail"
ATTR_CONDITION_LIGHTNING = "lightning"
ATTR_CONDITION_LIGHTNING_RAINY = "lightning-rainy"
ATTR_CONDITION_PARTLYCLOUDY = "partlycloudy"
ATTR_CONDITION_POURING = "pouring"
ATTR_CONDITION_RAINY = "rainy"
ATTR_CONDITION_SNOWY = "snowy"
ATTR_CONDITION_SNOWY_RAINY = "snowy-rainy"
ATTR_CONDITION_SUNNY = "sunny"
ATTR_CONDITION_WINDY = "windy"
ATTR_CONDITION_WINDY_VARIANT = "windy-variant"

# Explicit per-id overrides where a whole hundreds-band is too coarse.
# https://openweathermap.org/weather-conditions
_ID_OVERRIDES: dict[int, str] = {
    # Thunderstorm without rain -> dry lightning.
    210: ATTR_CONDITION_LIGHTNING,
    211: ATTR_CONDITION_LIGHTNING,
    212: ATTR_CONDITION_LIGHTNING,
    221: ATTR_CONDITION_LIGHTNING,
    # Heavy / very heavy rain.
    502: ATTR_CONDITION_POURING,
    503: ATTR_CONDITION_POURING,
    504: ATTR_CONDITION_POURING,
    522: ATTR_CONDITION_POURING,
    531: ATTR_CONDITION_POURING,
    # Freezing rain / sleet behave like a rain-snow mix.
    511: ATTR_CONDITION_SNOWY_RAINY,
    611: ATTR_CONDITION_SNOWY_RAINY,
    612: ATTR_CONDITION_SNOWY_RAINY,
    613: ATTR_CONDITION_SNOWY_RAINY,
    615: ATTR_CONDITION_SNOWY_RAINY,
    616: ATTR_CONDITION_SNOWY_RAINY,
    620: ATTR_CONDITION_SNOWY_RAINY,
    621: ATTR_CONDITION_SNOWY_RAINY,
    622: ATTR_CONDITION_SNOWY,
    # Atmosphere band nuances.
    701: ATTR_CONDITION_FOG,  # mist
    711: ATTR_CONDITION_FOG,  # smoke
    721: ATTR_CONDITION_FOG,  # haze
    731: ATTR_CONDITION_FOG,  # sand/dust whirls
    741: ATTR_CONDITION_FOG,  # fog
    751: ATTR_CONDITION_FOG,  # sand
    761: ATTR_CONDITION_FOG,  # dust
    762: ATTR_CONDITION_FOG,  # volcanic ash
    771: ATTR_CONDITION_WINDY,  # squalls
    781: ATTR_CONDITION_EXCEPTIONAL,  # tornado
    # Clouds.
    801: ATTR_CONDITION_PARTLYCLOUDY,  # few clouds 11-25%
    802: ATTR_CONDITION_PARTLYCLOUDY,  # scattered 25-50%
    803: ATTR_CONDITION_CLOUDY,  # broken 51-84%
    804: ATTR_CONDITION_CLOUDY,  # overcast 85-100%
}


def map_condition(weather_id: int | None, icon: str | None = None) -> str:
    """Map an OpenWeather ``weather[].id`` to a Home Assistant condition.

    ``icon`` (ending in ``d``/``n``) is used to split a clear sky into
    ``sunny`` vs ``clear-night``.
    """
    if weather_id is None:
        return ATTR_CONDITION_EXCEPTIONAL

    if weather_id in _ID_OVERRIDES:
        return _ID_OVERRIDES[weather_id]

    if 200 <= weather_id < 300:
        return ATTR_CONDITION_LIGHTNING_RAINY
    if 300 <= weather_id < 400:
        return ATTR_CONDITION_RAINY  # drizzle
    if 500 <= weather_id < 600:
        return ATTR_CONDITION_RAINY
    if 600 <= weather_id < 700:
        return ATTR_CONDITION_SNOWY
    if 700 <= weather_id < 800:
        return ATTR_CONDITION_FOG
    if weather_id == 800:
        if icon and icon.endswith("n"):
            return ATTR_CONDITION_CLEAR_NIGHT
        return ATTR_CONDITION_SUNNY
    if 800 < weather_id < 900:
        return ATTR_CONDITION_CLOUDY

    return ATTR_CONDITION_EXCEPTIONAL


# 16-point compass, 22.5 deg per sector, offset by half a sector.
_COMPASS = (
    "N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE",
    "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW",
)


def wind_cardinal(degrees: float | int | None) -> str | None:
    """Return the 16-point compass label for a wind bearing in degrees."""
    if degrees is None:
        return None
    index = int((float(degrees) % 360) / 22.5 + 0.5) % 16
    return _COMPASS[index]


# OpenWeather AQI is a 1-5 index. Labels follow OpenWeather's own scale.
_AQI_LABELS = {
    1: "good",
    2: "fair",
    3: "moderate",
    4: "poor",
    5: "very_poor",
}


def aqi_label(aqi: int | None) -> str | None:
    """Return a slug label for an OpenWeather air-quality index (1-5)."""
    if aqi is None:
        return None
    return _AQI_LABELS.get(int(aqi))


def compact_summary(day: dict | None) -> str | None:
    """Build a language-neutral compact daily summary from a ``daily[]`` entry.

    OpenWeather's own ``summary`` text is English-only, but the per-day
    ``weather[].description`` *is* translated by the ``lang`` parameter. So we
    compose our own line from that localised description plus the temperature
    range and rain probability, using symbols instead of words — it then reads
    correctly in any language. Example: ``"Nubi sparse · 14–24° · 🌧️ 20%"``.
    """
    if not day:
        return None
    parts: list[str] = []
    description = (day.get("weather") or [{}])[0].get("description")
    if isinstance(description, str) and description:
        parts.append(description.capitalize())
    temp = day.get("temp") or {}
    tmin, tmax = temp.get("min"), temp.get("max")
    if tmin is not None and tmax is not None:
        parts.append(f"{round(tmin)}–{round(tmax)}°")
    pop = day.get("pop")
    if pop:
        parts.append(f"🌧️ {round(pop * 100)}%")
    return " · ".join(parts) if parts else None


# Eight named lunar phases keyed off OpenWeather ``moon_phase`` (0..1).
def moon_phase_name(value: float | None) -> str | None:
    """Map an OpenWeather ``moon_phase`` (0=new, 0.5=full, 1=new) to a slug."""
    if value is None:
        return None
    v = float(value) % 1.0
    if v < 0.0625 or v >= 0.9375:
        return "new_moon"
    if v < 0.1875:
        return "waxing_crescent"
    if v < 0.3125:
        return "first_quarter"
    if v < 0.4375:
        return "waxing_gibbous"
    if v < 0.5625:
        return "full_moon"
    if v < 0.6875:
        return "waning_gibbous"
    if v < 0.8125:
        return "last_quarter"
    return "waning_crescent"


ALERT_TYPE_SLUGS = {
    "Coastal event": "coastal_event",
    "Extreme low temperature": "extreme_low_temperature",
    "Extreme high temperature": "extreme_high_temperature",
    "Wind": "wind",
    "Flood": "flood",
    "Sand dust": "sand_dust",
    "Rain": "rain",
    "Fire warning": "fire_warning",
    "Marine event": "marine_event",
    "Avalanches": "avalanches",
    "Fog": "fog",
    "Air quality": "air_quality",
    "Tornado": "tornado",
    "Cyclone": "cyclone",
    "Snow ice": "snow_ice",
    "Thunderstorm": "thunderstorm",
    "Hail": "hail",
}


def alert_type_state(alerts: object) -> str | None:
    """Translate known tags to stable state keys; preserve any future tags."""
    raw = alert_tag(alerts)
    return ALERT_TYPE_SLUGS.get(raw, raw)


def alert_tag(alerts: object) -> str | None:
    """The kind of weather alert in force: ``tags[0]`` of the first alert carrying one.

    ``tags`` and not ``event``, on purpose. Measured against the live API on
    2026-09-04: on One Call **4.0** ``event`` comes back empty — 14 live alerts,
    six national services, every one of them — while the same alerts on 3.0 are
    named. ``tags`` is the one field that arrives present, identical and
    identically shaped on both versions and from every service seen so far
    (``["Wind"]``, ``["Extreme high temperature"]``).

    This raw accessor preserves the provider value for the sensor's raw_type
    attribute. The state accessor maps known tags separately, leaving future
    tags unchanged rather than restricting them to an enum. An alert whose
    ``tags`` is absent or empty is skipped rather than blanking the state, since
    a second alert may well carry one.
    """
    if not isinstance(alerts, (list, tuple)):
        return None
    for alert in alerts:
        if not isinstance(alert, dict):
            continue
        tags = alert.get("tags")
        if not isinstance(tags, (list, tuple)):
            continue
        for tag in tags:
            text = str(tag).strip()
            if text:
                return text
    return None
