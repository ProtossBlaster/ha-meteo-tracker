# Meteo Tracker

Per-person weather for Home Assistant, powered by the **OpenWeather One Call API** (3.0 or 4.0 — whichever your key can reach; detected at setup).

Pick one or more `device_tracker` entities and Meteo Tracker gives each person their
own weather entity plus a full set of sensors (temperature, wind, UV, precipitation,
sun & moon, **air quality**, government weather alerts…), always following wherever
that person currently is. Refreshes every 5 minutes by default.

See the [README](https://github.com/ProtossBlaster/ha-meteo-tracker) for setup.
