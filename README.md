<p align="center">
  <img src="images/icon.png" width="120" alt="Meteo Tracker" />
</p>

<h1 align="center">🌦️ Meteo Tracker — per-person weather for Home Assistant</h1>

<p align="center">
  <a href="https://github.com/hacs/integration"><img src="https://img.shields.io/badge/HACS-Custom-41BDF5.svg" alt="HACS Custom"></a>
  <img src="https://img.shields.io/badge/Home%20Assistant-2024.12%2B-41BDF5.svg" alt="HA min version">
  <a href="CHANGELOG.md"><img src="https://img.shields.io/badge/version-0.1.0-blue.svg" alt="Version"></a>
  <img src="https://img.shields.io/badge/License-MIT-green.svg" alt="License: MIT">
</p>

A **complete, professional** weather integration that gives **each person their own
weather**, based on where they actually are. You pick one or more `device_tracker`
entities; Meteo Tracker follows each person's live GPS position and pulls a full
weather picture from **OpenWeather One Call API 3.0** — refreshed **every 5 minutes**.

> 🇮🇹 *Versione italiana più in basso → [Italiano](#-italiano).*

---

## ✨ Features

- 👥 **Multi-person / multi-user** — follow as many people as you like. Each tracker
  becomes its own Home Assistant **device** with a weather entity + sensors.
- 📍 **Location-aware** — weather is fetched at each person's *current* coordinates,
  so it updates as they travel.
- 🌡️ **Every nuance** — temperature & feels-like, min/max, pressure, humidity, dew
  point, UV index, cloud cover, visibility, wind speed/gust/bearing/direction,
  rain & snow, precipitation probability, daily human-readable summary.
- 🌅 **Sun & moon** — sunrise, sunset, moonrise, moonset, named moon phase.
- 🫁 **Air quality** — AQI plus PM2.5, PM10, O₃, NO₂, SO₂, CO, NO, NH₃.
- ⚠️ **Government weather alerts** — exposed as a binary sensor with full details.
- 📈 **Full forecasts** — hourly (48 h), daily (8 days) and twice-daily, via the
  modern Home Assistant forecast API (works with the Weather Forecast card).
- ⏱️ **5-minute refresh** by default, configurable 1–60 min.
- 💰 **Call-budget friendly** — people standing in the same spot share a single API
  call (coordinates are de-duplicated to ~11 m).

---

## 📋 Requirements

- Home Assistant **2024.12** or newer.
- At least one **GPS-based `device_tracker`** (HA Companion App, Owntracks, Traccar,
  iCloud, Life360, etc.).
- An **OpenWeather One Call API 3.0** key (free tier available — see below).

### Getting an API key

1. Create a free account at [openweathermap.org](https://openweathermap.org/).
2. Go to **API keys** and copy your key.
3. Subscribe to **“One Call by Call”** (the plan that powers One Call API 3.0).
   It is **free up to 1,000 calls/day** — to stay free, open
   *Billing plans → set a “calls per day” limit of 1000* so you are never charged.

> A brand-new key can take **a couple of hours** to activate. If setup fails with
> “invalid API key” right after creating it, wait and try again.

#### 💰 Call-budget cheat sheet

Each distinct location costs **1 One Call request** per refresh (air quality uses a
**separate free API** and does *not* count against the 1,000/day budget).

| Refresh interval | Calls/day per location | Distinct locations within 1,000/day |
|---|---|---|
| 5 min (default) | 288 | up to **3** |
| 10 min | 144 | up to **6** |
| 15 min | 96 | up to **10** |

People in the same place share one call, so a whole family at home counts as **one**
location. If you follow many people in different cities, raise the interval.

---

## 📦 Installation

### Option A — HACS (recommended)

1. HACS → **⋮** → **Custom repositories**.
2. Add `https://github.com/ProtossBlaster/ha-meteo-tracker` as an **Integration**.
3. Install **Meteo Tracker**, then **restart** Home Assistant.

### Option B — Manual

Copy `custom_components/meteo_tracker/` into your HA `config/custom_components/`
folder and restart.

---

## ⚙️ Configuration

Everything is configured from the UI — no YAML.

**Settings → Devices & Services → Add Integration → “Meteo Tracker”.**

| Field | Description |
|---|---|
| **Name** | A label for this integration instance. |
| **OpenWeather API key** | Your One Call 3.0 key. |
| **People to follow** | One or more `device_tracker` entities. |
| **Refresh interval** | Minutes between updates (default **5**). |
| **Language** | Language of the textual weather descriptions. |

You can change trackers, interval and language any time via the integration's
**Configure** (⚙️) button.

---

## 🧭 Entities

For **each** person you follow, Meteo Tracker creates a device with:

### Weather entity
A full `weather.<person>` entity with current conditions and **hourly / daily /
twice-daily** forecasts.

### Sensors

| Group | Sensors |
|---|---|
| **Temperature** | Temperature, Apparent temperature, Min today, Max today, Dew point |
| **Atmosphere** | Pressure, Humidity, Cloud coverage, Visibility, UV index |
| **Wind** | Wind speed, Wind gust, Wind bearing (°), Wind direction (compass) |
| **Precipitation** | Last hour, Next hour, Probability, Rain today, Snow today |
| **Descriptive** | Condition, Weather description, Daily summary |
| **Sun & moon** | Sunrise, Sunset, Moonrise, Moonset, Moon phase |
| **Air quality** | AQI (index + label), PM2.5, PM10, O₃, NO₂, SO₂, CO, NO, NH₃ |
| **Diagnostic** | Location, Last measured, Moon phase value |

### Binary sensors

- **Weather alert** — `on` when a government alert is active; the alert details
  (event, sender, start/end, description, tags) are in the entity attributes.
- **Precipitation expected** — `on` when rain/snow is expected within the next hour.

---

## ❓ How does it find each person's location?

For every tracker, in order:

1. The tracker's own `latitude` / `longitude` attributes (GPS trackers).
2. If the tracker reads `home`, your Home Assistant home coordinates.
3. If it reads a zone name, that zone's coordinates.

If none of these are available (e.g. a non-GPS router tracker that's away), that
person's entities become *unavailable* until coordinates are known again.

---

## 🛠️ Troubleshooting

- **“Invalid API key”** right after creating the key → wait up to ~2 h for activation.
- **Entities unavailable** → the tracker has no coordinates (see above), or the
  daily call limit was hit. Lower the refresh frequency or check OpenWeather usage.
- **Diagnostics** → the integration's *Download diagnostics* redacts your API key
  and exact coordinates.

---

## 🤝 Contributing

Issues and PRs welcome. Pure helper logic is unit-tested:

```bash
pip install pytest
pytest tests/
```

---

## 🇮🇹 Italiano

**Meteo Tracker** dà a **ogni persona il proprio meteo**, in base a dove si trova
davvero. Scegli uno o più `device_tracker`: il componente segue la posizione GPS di
ciascuno e scarica un quadro meteo completo da **OpenWeather One Call API 3.0**,
aggiornato **ogni 5 minuti**.

**Caratteristiche**

- 👥 **Multi-utente**: segui quante persone vuoi, ognuna con il proprio dispositivo,
  entità meteo e sensori.
- 📍 Meteo sempre sulla **posizione attuale** di ogni persona.
- 🌡️ **Tutte le sfumature**: temperatura e percepita, min/max, pressione, umidità,
  punto di rugiada, indice UV, nuvolosità, visibilità, vento (velocità/raffica/
  direzione), pioggia e neve, probabilità di precipitazioni, riepilogo giornaliero.
- 🌅 Alba, tramonto, sorgere/tramonto della luna, **fase lunare**.
- 🫁 **Qualità dell'aria**: AQI + PM2.5, PM10, O₃, NO₂, SO₂, CO, NO, NH₃.
- ⚠️ **Allerte meteo ufficiali** come sensore binario con tutti i dettagli.
- 📈 Previsioni **orarie (48 h)**, **giornaliere (8 gg)** e bigiornaliere.

**Requisiti**: Home Assistant 2024.12+, un `device_tracker` GPS e una chiave
**OpenWeather One Call 3.0** (gratis fino a 1000 chiamate/giorno impostando il tetto).

**Budget chiamate**: a 5 minuti servono ~288 chiamate/giorno per ogni posizione
distinta → fino a **3 posizioni** restano gratis. Persone nello stesso luogo
condividono una sola chiamata. Per molte persone in città diverse, alza l'intervallo.

**Installazione**: HACS → *Custom repositories* → aggiungi questo repo come
*Integration*, installa, riavvia. Poi *Impostazioni → Dispositivi e servizi →
Aggiungi integrazione → “Meteo Tracker”*.

---

## 📄 License

[MIT](LICENSE) © 2026 Silvio Bressani.

Weather data by [OpenWeather](https://openweathermap.org/). This project is not
affiliated with OpenWeather.
