# Development & maintenance notes

Internal map of the integration so any future change is quick to locate, build
and validate. (User-facing docs live in the [README](../README.md); the version
history is in the [CHANGELOG](../CHANGELOG.md).)

Domain: `meteo_tracker` · Backend: OpenWeather **One Call API 3.0 or 4.0** + **Air Pollution API**.
Everything above `api.py` only ever sees the **3.0 payload shape**: on 4.0 the six
endpoints are fetched and reassembled in `onecall_v4.py`, so no platform knows the difference.

---

## 1. File map — where each thing lives

| File | Responsibility |
|---|---|
| `custom_components/meteo_tracker/manifest.json` | Integration metadata; **`version` must equal the released git tag** `vX.Y.Z`. |
| `const.py` | All constants: URLs, defaults (refresh = 5 min), `SUPPORTED_LANGUAGES`, coordinate-dedup precision, attribution/model. |
| `weather_codes.py` | **Pure** (no HA imports) — OpenWeather→HA condition mapping, wind compass, AQI label, moon phase. Unit-tested. |
| `api.py` | Async OpenWeather client (`async_one_call`, `async_air_pollution`, `async_validate`), One Call 3.0/4.0 dispatch, `async_detect_api_version`, typed errors. |
| `onecall_v4.py` | **Pure** (no HA, no aiohttp) — rebuilds the 3.0 payload shape out of One Call 4.0's six endpoints. Unit-tested in CI. |
| `coordinator.py` | `DataUpdateCoordinator`: resolves each tracker's lat/lon, **dedupes** by rounded coords, fetches per location. |
| `__init__.py` | Setup/unload, builds client + coordinator, forwards platforms, options-reload listener. |
| `config_flow.py` | UI config (api_key + trackers + interval + language), **reauth** (re-probes the key, carries the entry across One Call versions, keeps the entry id so history survives) and options flow (incl. changing the One Call version). Initial values go in `entry.data`; options override. |
| `entity.py` | `MeteoTrackerEntity` base: per-person device, availability, `_onecall`/`_air` accessors. |
| `weather.py` | `weather.<person>` entity: current props + hourly/daily/twice-daily forecasts. |
| `sensor.py` | `SENSORS` descriptor table (40 sensors) + entity. Each has a `value_fn(tracker_data)`. |
| `binary_sensor.py` | `BINARY_SENSORS` (weather alert, precipitation expected). |
| `button.py` | Per-person **Refresh** button → `coordinator.async_request_refresh()`. Adding a platform also means editing `PLATFORMS` in `__init__.py`. |
| `diagnostics.py` | Config-entry diagnostics; **redacts** api_key + coordinates. |
| `strings.json` + `translations/{en,it,fr}.json` | UI + entity names + state labels. `en.json` is a copy of `strings.json`. |
| `brand/` | App icon/logo (256/512). Source for a future `home-assistant/brands` PR. |

---

## 2. Common changes — cookbook

- **Tweak a weather-condition mapping** → `weather_codes.py::map_condition`. Output
  **must** be one of HA's 15 conditions. Currently 13/15 are reachable; `hail` and
  `windy-variant` are never emitted because OpenWeather has no matching code.
- **Add a sensor** → add a `MeteoSensorDescription` to `SENSORS` in `sensor.py`
  (with a `value_fn`), then add its `key` under `entity.sensor` in `strings.json`,
  `translations/en.json` **and** `translations/it.json`. Re-copy `strings.json`→`en.json`.
- **Add a binary sensor** → `BINARY_SENSORS` in `binary_sensor.py` + translations.
- **Change default refresh / call-budget constants** → `const.py`.
- **Add a config/option field** → `config_flow.py` (both `async_step_user` and
  `async_step_init`) + a key in `const.py` + labels in the 3 translation files.
- **Add a language to the dropdown** → `const.py::SUPPORTED_LANGUAGES`.
- **Enum sensor states** (e.g. moon phase, AQI, wind direction) → slugs must be
  **lowercase** `[a-z0-9-_]` (hassfest enforces this) and listed in both `options=`
  and the translation `state` block.

---

## 3. Behaviour reference

- **Alert type:** `weather_codes.alert_type_state` maps 17 known tags to stable
  slugs, leaving unknown tags verbatim. `alert_tag` supplies the sensor's `raw_type`
  attribute. Keep this sensor free of a closed ENUM/options list so future tags
  remain usable. Translate known states in EN/IT/FR; keep full alert text untouched.

- **Location resolution** (`coordinator.resolve_coords`): tracker GPS attrs → home
  zone (state `home`/`casa`) → `zone.<slug>`. No coords ⇒ that person unavailable.
- **Call cost**: one refresh of one location is **1 request on 3.0**, **6 on 4.0**
  (current + 1min + 3 pages of 1h, since it caps at 20 records + 1day), plus one per
  active alert. `const.calls_per_refresh()` derives that from `onecall_v4`'s page
  sizes rather than hard-coding it, so the figures the UI shows cannot drift from the
  requests actually made. The free 1,000/day is **per OpenWeather account**, so two
  installations sharing a key share the allowance and cannot see each other.

  | Refresh | 4.0, 1 install. | 2 | 3 |
  |---:|---:|---:|---:|
  | 10 min | 864 ✅ | 1728 ⚠️ | 2592 ⚠️ |
  | 20 min | 432 ✅ | 864 ✅ | 1296 ⚠️ |
  | 30 min | 288 ✅ | 576 ✅ | 864 ✅ |

- **Dedup**: coords rounded to `COORD_PRECISION` (4 dp ≈ 11 m) → one One Call per
  unique spot. Air Pollution is a **separate free API** (doesn't count vs the 1000/day).
- **Forecast push**: `weather._handle_coordinator_update` writes state and schedules
  `async_update_listeners(["daily","hourly","twice_daily"])` so cards refresh.
- **Units**: OWM requested in `metric`; entity exposes native °C / hPa / m·s⁻¹ / km / mm.
- **Call budget @5 min**: 288/day per distinct location → ≤3 locations stay free.

---

## 4. Validate before every release

Pure-logic tests (no HA needed; use an environment with pytest installed):
```bash
python3 -m pytest tests/ -q
```

Import check against the **real HA image** (catches import-time incompatibilities;
it does not replace runtime or UI testing):
```bash
docker run --rm -i --entrypoint python -e PYTHONPATH=/pkg -e PYTHONDONTWRITEBYTECODE=1 \
  -v "$PWD/custom_components:/pkg:ro" ghcr.io/home-assistant/home-assistant:stable - <<'PY'
import importlib
for m in ["meteo_tracker","meteo_tracker.weather","meteo_tracker.sensor",
          "meteo_tracker.binary_sensor","meteo_tracker.config_flow",
          "meteo_tracker.coordinator","meteo_tracker.diagnostics"]:
    importlib.import_module(m); print("OK", m)
from meteo_tracker.sensor import SENSORS; print("sensors:", len(SENSORS))
PY
```

CI runs the same spirit on every push: **HACS + hassfest + pytest**
(`.github/workflows/validate.yml`). `ignore: brands` stays until the brands PR lands.

---

## 5. Release checklist (versioning history)

1. Bump `version` in `manifest.json` (SemVer, = the new tag).
2. Add a dated section to `CHANGELOG.md` and update the version badge in `README.md`.
   Update `info.md` and add `docs/releases/vX.Y.Z.md` with compatibility, upgrade,
   validation and rollback notes; use these notes for the GitHub release.
3. Run the validation in §4 (green).
4. `git commit` → `git push` (with Silvio's OK).
5. `gh release create vX.Y.Z --target main --title "…" --notes "…"` (creates the tag;
   HACS then serves it to users).
6. Confirm CI green on the tag.

---

## 6. Backlog / ideas

- [x] **v0.1.1** — detailed OpenWeather description + daily summary + active alert
      exposed as `extra_state_attributes` on the `weather` entity (the fine wording
      the 15-state `condition` can't hold). _Shipped 2026-06-11._
- [ ] `home-assistant/brands` PR (assets ready in `brand/`) → icon shows in HA, drop
      `ignore: brands`. **External public PR — needs Silvio's explicit OK.**
- [ ] README screenshots (capture from a live HA once Silvio finishes testing).
- [ ] Optional: submit to **HACS default** so it installs without a custom repo.
- [ ] Optional hail heuristic (thunderstorm + cues) since OWM has no hail code.
- [ ] Watch for a real OTA/alert payload shape to refine the alert binary sensor.
