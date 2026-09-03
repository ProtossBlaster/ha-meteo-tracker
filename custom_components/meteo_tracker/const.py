"""Constants for the Meteo Tracker integration."""

from __future__ import annotations

DOMAIN = "meteo_tracker"

# Config / option keys.
CONF_API_KEY = "api_key"
CONF_TRACKERS = "trackers"
CONF_SCAN_INTERVAL_MINUTES = "scan_interval_minutes"
CONF_LANGUAGE = "language"
CONF_API_VERSION = "api_version"

# Which One Call product a key can reach. OpenWeather stopped offering 3.0 to
# new accounts, so fresh installs land on 4.0 while existing keys keep 3.0.
API_V3 = "3.0"
API_V4 = "4.0"
# Entries created before 4.0 support existed carry no version and are all 3.0.
DEFAULT_API_VERSION = API_V3

# Defaults.
DEFAULT_NAME = "Meteo Tracker"
DEFAULT_SCAN_INTERVAL_MINUTES = 5
MIN_SCAN_INTERVAL_MINUTES = 1
MAX_SCAN_INTERVAL_MINUTES = 60
DEFAULT_LANGUAGE = "en"

# One Call 4.0 splits the old single response into six endpoints, so one refresh
# costs six requests instead of one and the 1,000/day free tier is reached far
# sooner. Polling faster than the model updates would only buy duplicate data at
# full price: OpenWeather refreshes 4.0 every 10 minutes and recommends the same
# interval, so that is the floor we hold callers to.
MIN_SCAN_INTERVAL_MINUTES_V4 = 10

# Network.
ONECALL_URL = "https://api.openweathermap.org/data/3.0/onecall"
ONECALL_V4_BASE = "https://api.openweathermap.org/data/4.0/onecall"
AIR_POLLUTION_URL = "https://api.openweathermap.org/data/2.5/air_pollution"
REQUEST_TIMEOUT = 30

# A single point can in theory carry many simultaneous alerts, and each one
# costs its own request on 4.0. Beyond this many we stop fetching and say so,
# rather than letting one stormy afternoon empty the call budget.
MAX_V4_ALERTS = 10

# Rounding used to deduplicate API calls when several trackers share a spot.
# 4 decimal degrees ~= 11 m, well below OpenWeather's grid resolution.
COORD_PRECISION = 4

# OpenWeather languages we expose in the options flow (a curated subset of the
# full list at https://openweathermap.org/api/one-call-3#multi ).
SUPPORTED_LANGUAGES = [
    "en", "it", "de", "fr", "es", "pt", "nl", "pl", "ro", "ru",
    "tr", "uk", "cz", "sv", "da", "fi", "no", "el", "hu", "pt_br",
    "zh_cn", "ja", "ar",
]

# Manufacturer / model shown on each per-person device.
ATTRIBUTION = "Weather data provided by OpenWeather"
MANUFACTURER = "OpenWeather"


def model_for_version(api_version: str | None) -> str:
    """Device model line — it names the API actually answering for this entry."""
    return f"One Call API {api_version or DEFAULT_API_VERSION}"


def min_interval_for(api_version: str | None) -> int:
    """Smallest refresh interval allowed on the given One Call version."""
    if api_version == API_V4:
        return MIN_SCAN_INTERVAL_MINUTES_V4
    return MIN_SCAN_INTERVAL_MINUTES
