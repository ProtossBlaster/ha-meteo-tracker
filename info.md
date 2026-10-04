# Meteo Tracker

**v0.3.0:** weather alert types now have English, Italian and French display labels.
Known technical states change, for example `Wind` → `wind`; the original tag is
available in `raw_type`. Update any automation comparing the previous state.
Entity IDs and configuration are preserved. See the
[upgrade guide](https://github.com/ProtossBlaster/ha-meteo-tracker/blob/v0.3.0/docs/releases/v0.3.0.md).

Per-person weather for Home Assistant, powered by the **OpenWeather One Call API**
(3.0 or 4.0 — whichever your key can reach; detected at setup).

Pick one or more `device_tracker` entities and Meteo Tracker gives each person their
own weather entity plus a full set of sensors (temperature, wind, UV, precipitation,
sun & moon, **air quality**, government weather alerts…), always following wherever
that person currently is. Refreshes every **10 minutes** by default.

## Before you set the refresh interval

OpenWeather no longer sells **One Call 3.0** to new accounts, so a key created today
reaches **4.0** — where one refresh costs **six requests** instead of one, plus one
per active weather alert. Hence a 10-minute minimum on 4.0.

The free **1,000 calls/day belongs to your OpenWeather account**, not to the
installation: a second Home Assistant draws from the same allowance, and the two
cannot see each other. Daily requests on 4.0, for one tracked location — ✅ free,
⚠️ over:

| Refresh | 1 installation | 2 | 3 |
|---:|---:|---:|---:|
| **10 min** | 864 ✅ | 1728 ⚠️ | 2592 ⚠️ |
| **15 min** | 576 ✅ | 1152 ⚠️ | 1728 ⚠️ |
| **20 min** | 432 ✅ | 864 ✅ | 1296 ⚠️ |
| **30 min** | 288 ✅ | 576 ✅ | 864 ✅ |
| **60 min** | 144 ✅ | 288 ✅ | 432 ✅ |

On One Call 3.0 divide these by six. Multiply by the distinct locations you follow —
people in the same place share one set of requests. The same grid, filled in with
your own numbers, is shown inside the integration when you add it and under
*Configure*.

See the [README](https://github.com/ProtossBlaster/ha-meteo-tracker) for setup.
