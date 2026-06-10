# Development & maintenance notes

Internal map of the integration so any future change is quick to locate, build
and validate. (User-facing docs live in the [README](../README.md); the version
history is in the [CHANGELOG](../CHANGELOG.md).)

Domain: `meteo_tracker` · Backend: OpenWeather **One Call API 3.0** + **Air Pollution API**.

---

## 1. File map — where each thing lives

| File | Responsibility |
|---|---|
| `custom_components/meteo_tracker/manifest.json` | Integration metadata; **`version` must equal the released git tag** `vX.Y.Z`. |
| `const.py` | All constants: URLs, defaults (refresh = 5 min), `SUPPORTED_LANGUAGES`, coordinate-dedup precision, attribution/model. |
| `weather_codes.py` | **Pure** (no HA imports) — OpenWeather→HA condition mapping, wind compass, AQI label, moon phase. Unit-tested. |
| `api.py` | Async OpenWeather client (`async_one_call`, `async_air_pollution`, `async_validate`) + typed errors. |
| `coordinator.py` | `DataUpdateCoordinator`: resolves each tracker's lat/lon, **dedupes** by rounded coords, fetches per location. |
| `__init__.py` | Setup/unload, builds client + coordinator, forwards platforms, options-reload listener. |
| `config_flow.py` | UI config (api_key + trackers + interval + language) and options flow. Initial values go in `entry.data`; options override. |
| `entity.py` | `MeteoTrackerEntity` base: per-person device, availability, `_onecall`/`_air` accessors. |
| `weather.py` | `weather.<person>` entity: current props + hourly/daily/twice-daily forecasts. |
| `sensor.py` | `SENSORS` descriptor table (40 sensors) + entity. Each has a `value_fn(tracker_data)`. |
| `binary_sensor.py` | `BINARY_SENSORS` (weather alert, precipitation expected). |
| `diagnostics.py` | Config-entry diagnostics; **redacts** api_key + coordinates. |
| `strings.json` + `translations/{en,it}.json` | UI + entity names + enum state labels. `en.json` is a copy of `strings.json`. |
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

- **Location resolution** (`coordinator.resolve_coords`): tracker GPS attrs → home
  zone (state `home`/`casa`) → `zone.<slug>`. No coords ⇒ that person unavailable.
- **Dedup**: coords rounded to `COORD_PRECISION` (4 dp ≈ 11 m) → one One Call per
  unique spot. Air Pollution is a **separate free API** (doesn't count vs the 1000/day).
- **Forecast push**: `weather._handle_coordinator_update` writes state and schedules
  `async_update_listeners(["daily","hourly","twice_daily"])` so cards refresh.
- **Units**: OWM requested in `metric`; entity exposes native °C / hPa / m·s⁻¹ / km / mm.
- **Call budget @5 min**: 288/day per distinct location → ≤3 locations stay free.

---

## 4. Validate before every release

Pure-logic tests (no HA needed):
```bash
python3 - <<'PY'
import sys, pathlib; sys.path.insert(0, "custom_components/meteo_tracker"); sys.path.insert(0, "tests")
import test_weather_codes as t
for c in [getattr(t,n) for n in dir(t) if n.startswith("Test")]:
    i=c(); [getattr(i,m)() for m in dir(i) if m.startswith("test_")]
print("pure tests OK")
PY
```

Import + data-flow against the **real HA image** (catches every device-class / unit /
API drift):
```bash
docker run --rm -i --entrypoint python -e PYTHONPATH=/pkg \
  -v "$PWD/custom_components:/pkg" ghcr.io/home-assistant/home-assistant:stable - <<'PY'
import importlib
for m in ["meteo_tracker","meteo_tracker.weather","meteo_tracker.sensor",
          "meteo_tracker.binary_sensor","meteo_tracker.config_flow",
          "meteo_tracker.coordinator","meteo_tracker.diagnostics"]:
    importlib.import_module(m); print("OK", m)
from meteo_tracker.sensor import SENSORS; print("sensors:", len(SENSORS))
PY
# clean up root-owned __pycache__ the mount leaves behind:
docker run --rm --entrypoint sh -v "$PWD/custom_components:/pkg" \
  ghcr.io/home-assistant/home-assistant:stable -c 'find /pkg -name __pycache__ -prune -exec rm -rf {} +'
```

CI runs the same spirit on every push: **HACS + hassfest + pytest**
(`.github/workflows/validate.yml`). `ignore: brands` stays until the brands PR lands.

---

## 5. Release checklist (versioning history)

1. Bump `version` in `manifest.json` (SemVer, = the new tag).
2. Add a dated section to `CHANGELOG.md` and update the version badge in `README.md`.
3. Run the validation in §4 (green).
4. `git commit` → `git push` (with Silvio's OK).
5. `gh release create vX.Y.Z --target main --title "…" --notes "…"` (creates the tag;
   HACS then serves it to users).
6. Confirm CI green on the tag.

---

## 6. Backlog / ideas

- [ ] **v0.1.1** — expose the detailed OpenWeather description (Italian) + active alert
      as `extra_state_attributes` on the `weather` entity (so the fine wording shows
      where users look, despite the 15-state `condition` limit).
- [ ] `home-assistant/brands` PR (assets ready in `brand/`) → icon shows in HA, drop
      `ignore: brands`. **External public PR — needs Silvio's explicit OK.**
- [ ] README screenshots (capture from a live HA once Silvio finishes testing).
- [ ] Optional: submit to **HACS default** so it installs without a custom repo.
- [ ] Optional hail heuristic (thunderstorm + cues) since OWM has no hail code.
- [ ] Watch for a real OTA/alert payload shape to refine the alert binary sensor.
