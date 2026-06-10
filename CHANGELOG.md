# Changelog

All notable changes to **Meteo Tracker** are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

The version in `custom_components/meteo_tracker/manifest.json` always matches the
latest released git tag (`vX.Y.Z`).

## [Unreleased]

## [0.1.1] - 2026-06-11

### Added
- The `weather` entity now exposes OpenWeather's precise, **localised description**
  as state attributes — the fine wording HA's 15-state `condition` cannot hold:
  - `detailed_description` (e.g. *"Temporale con pioggia forte"*),
  - `daily_summary` (human-readable day summary),
  - `alert`, `alert_active`, `alert_count` (active government weather alert),
  - `openweather_id` (raw OpenWeather condition code, for templating).

## [0.1.0] - 2026-06-11

Initial release. 🎉

### Added
- **Per-person weather**: pick one or more `device_tracker` entities; each becomes
  its own Home Assistant device with a `weather.<person>` entity that follows that
  person's live location.
- **Multi-user**: follow as many people as you like from a single config entry.
- **OpenWeather One Call API 3.0** backend: current conditions plus **hourly (48 h)**,
  **daily (8 days)** and **twice-daily** forecasts via the modern HA forecast API.
- **40 sensors per person**: temperature / apparent / min / max / dew point,
  pressure, humidity, UV index, cloud coverage, visibility, wind
  (speed / gust / bearing / compass direction), precipitation
  (last hour / next hour / probability / rain today / snow today), condition,
  weather description, daily summary, sunrise / sunset / moonrise / moonset,
  moon phase, and air quality (AQI + PM2.5, PM10, O₃, NO₂, SO₂, CO, NO, NH₃).
- **2 binary sensors per person**: government **weather alert** (with full alert
  details in attributes) and **precipitation expected** within the next hour.
- **5-minute refresh** by default, configurable 1–60 minutes via the options flow.
- **Call-budget friendly**: identical coordinates are de-duplicated (~11 m), so
  people in the same place share a single API call.
- **UI config & options flow** (no YAML); **bilingual EN / IT**.
- **Diagnostics** download with the API key and exact coordinates redacted.
- App **icon** and CI (HACS + hassfest + unit tests).

[Unreleased]: https://github.com/ProtossBlaster/ha-meteo-tracker/compare/v0.1.1...HEAD
[0.1.1]: https://github.com/ProtossBlaster/ha-meteo-tracker/releases/tag/v0.1.1
[0.1.0]: https://github.com/ProtossBlaster/ha-meteo-tracker/releases/tag/v0.1.0
