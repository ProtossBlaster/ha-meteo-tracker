# Changelog

All notable changes to **Meteo Tracker** are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

The version in `custom_components/meteo_tracker/manifest.json` always matches the
latest released git tag (`vX.Y.Z`).

## [Unreleased]

## [0.2.0] - 2026-09-03

### Added
- **One Call API 4.0 support.** OpenWeather stopped offering One Call 3.0 to newly
  created accounts, which left new users unable to finish setup at all. The version
  a key can reach is now detected during configuration and stored on the entry;
  existing entries keep 3.0, which is still served and still cheaper. On 4.0 the six
  endpoints are fetched and reassembled into the 3.0 payload shape, so every entity
  behaves exactly as before.

### Added
- **Recovery when OpenWeather stops accepting a key.** The integration had no
  reauthentication step, so a key that stopped working left the entry broken with
  no way back: Home Assistant asks the config flow for `async_step_reauth`, and
  without it the recovery never starts. The only escape was deleting and re-adding
  the integration — and because every entity's unique ID derives from the entry
  id, that lost all of their history. There is now a reauth step that re-probes
  the key, carries the entry to whichever One Call version the key still reaches,
  raises the refresh interval if the new version needs it, and **updates the
  existing entry**, so entities and history survive. This is the path every 3.0
  user would take on the day OpenWeather stops serving 3.0.
- **Move an existing entry between One Call versions.** The version is now a field
  in the integration's options. Detection still picks it when the entry is created,
  but a user who later subscribes to the other product can switch without deleting
  anything — which was impossible before, since detection ran once and always
  preferred 3.0 while 3.0 kept working. The move is checked against OpenWeather
  before it is saved, so an unbought version is refused with its reason rather than
  breaking the entry.

### Changed
- **Refresh interval has a 10-minute floor on One Call 4.0.** One refresh costs six
  requests there instead of one, and OpenWeather only updates the 4.0 model every ten
  minutes — a shorter interval would pay full price for identical data. 3.0 entries
  are untouched.
- **A refused key now explains itself.** OpenWeather's own reason for a 401 (most
  often a missing "One Call by Call" subscription, or a key created in the last
  couple of hours) is written to the log instead of being replaced with a bare
  "Invalid API key", and the setup form says where to look.
- README, in-app help and the call-budget table now cover both versions.

### Measured against the live One Call 4.0 API on 2026-09-03
- **Full parity with 3.0.** Both versions were fetched for the same point in the
  same minute and pushed through all 40 sensors: **no sensor loses a value on 4.0**.
  The four that differ do so only by model precision (4.0 runs OpenWeather's OWHL
  model), e.g. a maximum of 32.39 °C against 32.92 °C.
- **Alerts arrive better, not worse.** OpenWeather's own migration guide lists
  `tags` as gone from 4.0 — it is not: the live endpoint returns it, identical to
  3.0, and it is passed through. The alert `description` arrives as a per-language
  list, so an Italian install now reads its alerts **in Italian**, where 3.0
  answered in English.
- **Alert `event` can come back empty.** For a live Meteoalarm alert that 3.0
  titled *Yellow High-temperature Warning*, 4.0 returned an empty `event`. Rather
  than draw a nameless alert, the alert's own tag stands in (*Extreme high
  temperature*); with no tag either, the field is omitted rather than emptied.
  Observed on one alert, so it may not be universal.
- When more than 10 alerts are active at one point, only the first 10 are fetched
  (each costs a request on 4.0); the count is logged.

## [0.1.3] - 2026-06-11

### Changed
- **Daily summary is now localised.** OpenWeather's own `summary` text is
  English-only, so the `daily_summary` weather attribute and the *Daily summary*
  sensor are now composed from the (translated) day description + temperature
  range + rain probability, using symbols — e.g. `Nubi sparse · 14–24° · 🌧️ 20%`.
  Reads correctly in any language, with no extra API calls.

## [0.1.2] - 2026-06-11

### Added
- **Refresh button** per tracked person (`button.<person>_refresh`): forces an
  immediate OpenWeather update without waiting for the refresh interval. It is
  always pressable, so it doubles as a manual retry when data is stale.

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

[Unreleased]: https://github.com/ProtossBlaster/ha-meteo-tracker/compare/v0.1.3...HEAD
[0.1.3]: https://github.com/ProtossBlaster/ha-meteo-tracker/releases/tag/v0.1.3
[0.1.2]: https://github.com/ProtossBlaster/ha-meteo-tracker/releases/tag/v0.1.2
[0.1.1]: https://github.com/ProtossBlaster/ha-meteo-tracker/releases/tag/v0.1.1
[0.1.0]: https://github.com/ProtossBlaster/ha-meteo-tracker/releases/tag/v0.1.0
