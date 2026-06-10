"""Constants for the Meteo Tracker integration."""

from __future__ import annotations

DOMAIN = "meteo_tracker"

# Config / option keys.
CONF_API_KEY = "api_key"
CONF_TRACKERS = "trackers"
CONF_SCAN_INTERVAL_MINUTES = "scan_interval_minutes"
CONF_LANGUAGE = "language"

# Defaults.
DEFAULT_NAME = "Meteo Tracker"
DEFAULT_SCAN_INTERVAL_MINUTES = 5
MIN_SCAN_INTERVAL_MINUTES = 1
MAX_SCAN_INTERVAL_MINUTES = 60
DEFAULT_LANGUAGE = "en"

# Network.
ONECALL_URL = "https://api.openweathermap.org/data/3.0/onecall"
AIR_POLLUTION_URL = "https://api.openweathermap.org/data/2.5/air_pollution"
REQUEST_TIMEOUT = 30

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
MODEL = "One Call API 3.0"
