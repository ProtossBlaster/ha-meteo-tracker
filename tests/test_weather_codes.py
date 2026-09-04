"""Unit tests for the pure OpenWeather -> Home Assistant helpers."""

import weather_codes as wc


class TestMapCondition:
    def test_clear_day_vs_night(self):
        assert wc.map_condition(800, "01d") == "sunny"
        assert wc.map_condition(800, "01n") == "clear-night"
        # No icon defaults to the daytime variant.
        assert wc.map_condition(800) == "sunny"

    def test_cloud_bands(self):
        assert wc.map_condition(801) == "partlycloudy"
        assert wc.map_condition(802) == "partlycloudy"
        assert wc.map_condition(803) == "cloudy"
        assert wc.map_condition(804) == "cloudy"

    def test_rain_and_pouring(self):
        assert wc.map_condition(500) == "rainy"
        assert wc.map_condition(501) == "rainy"
        assert wc.map_condition(502) == "pouring"
        assert wc.map_condition(503) == "pouring"

    def test_thunderstorm(self):
        assert wc.map_condition(200) == "lightning-rainy"
        assert wc.map_condition(211) == "lightning"  # dry thunderstorm

    def test_snow_and_sleet(self):
        assert wc.map_condition(600) == "snowy"
        assert wc.map_condition(511) == "snowy-rainy"  # freezing rain
        assert wc.map_condition(615) == "snowy-rainy"

    def test_atmosphere(self):
        assert wc.map_condition(741) == "fog"
        assert wc.map_condition(781) == "exceptional"  # tornado
        assert wc.map_condition(771) == "windy"  # squalls

    def test_none_is_exceptional(self):
        assert wc.map_condition(None) == "exceptional"


class TestWindCardinal:
    def test_cardinals(self):
        assert wc.wind_cardinal(0) == "N"
        assert wc.wind_cardinal(90) == "E"
        assert wc.wind_cardinal(180) == "S"
        assert wc.wind_cardinal(270) == "W"

    def test_wraps_360(self):
        assert wc.wind_cardinal(360) == "N"
        assert wc.wind_cardinal(348.75) == "N"  # just inside the N sector

    def test_intercardinal(self):
        assert wc.wind_cardinal(45) == "NE"
        assert wc.wind_cardinal(225) == "SW"

    def test_none(self):
        assert wc.wind_cardinal(None) is None


class TestAqiLabel:
    def test_scale(self):
        assert wc.aqi_label(1) == "good"
        assert wc.aqi_label(3) == "moderate"
        assert wc.aqi_label(5) == "very_poor"

    def test_unknown(self):
        assert wc.aqi_label(0) is None
        assert wc.aqi_label(None) is None


class TestCompactSummary:
    def test_full(self):
        day = {
            "weather": [{"description": "nubi sparse"}],
            "temp": {"min": 14.2, "max": 23.8},
            "pop": 0.2,
        }
        assert wc.compact_summary(day) == "Nubi sparse · 14–24° · 🌧️ 20%"

    def test_dry_day_omits_rain(self):
        day = {"weather": [{"description": "cielo sereno"}], "temp": {"min": 10, "max": 20}, "pop": 0}
        assert wc.compact_summary(day) == "Cielo sereno · 10–20°"

    def test_partial(self):
        assert wc.compact_summary({"temp": {"min": 5, "max": 9}}) == "5–9°"

    def test_empty(self):
        assert wc.compact_summary(None) is None
        assert wc.compact_summary({}) is None


class TestMoonPhase:
    def test_principal_phases(self):
        assert wc.moon_phase_name(0) == "new_moon"
        assert wc.moon_phase_name(0.25) == "first_quarter"
        assert wc.moon_phase_name(0.5) == "full_moon"
        assert wc.moon_phase_name(0.75) == "last_quarter"
        assert wc.moon_phase_name(1.0) == "new_moon"

    def test_intermediate(self):
        assert wc.moon_phase_name(0.1) == "waxing_crescent"
        assert wc.moon_phase_name(0.4) == "waxing_gibbous"
        assert wc.moon_phase_name(0.6) == "waning_gibbous"
        assert wc.moon_phase_name(0.9) == "waning_crescent"

    def test_none(self):
        assert wc.moon_phase_name(None) is None


class TestAlertTag:
    """`tags[0]` of the first alert that has one — the state of the alert-type sensor.

    `tags` rather than `event` because `event` comes back empty on One Call 4.0:
    measured 2026-09-04 against live alerts, 14 out of 14, six national services.
    """

    def test_first_tag_of_the_first_alert(self):
        alerts = [
            {"sender_name": "METEO-FRANCE", "tags": ["Extreme high temperature"]},
            {"sender_name": "METEO-FRANCE", "tags": ["Wind"]},
        ]
        assert wc.alert_tag(alerts) == "Extreme high temperature"

    def test_no_alerts(self):
        assert wc.alert_tag([]) is None
        assert wc.alert_tag(None) is None

    def test_an_alert_without_tags_does_not_hide_one_that_has_them(self):
        """4.0 omits `tags` on an alert that carries none; the next alert still counts."""
        alerts = [{"sender_name": "DWD", "event": ""}, {"tags": ["Wind"]}]
        assert wc.alert_tag(alerts) == "Wind"

    def test_empty_and_blank_tags_are_not_a_state(self):
        assert wc.alert_tag([{"tags": []}]) is None
        assert wc.alert_tag([{"tags": ["   "]}]) is None
        assert wc.alert_tag([{"tags": [""]}, {"tags": ["Flood"]}]) == "Flood"

    def test_a_malformed_payload_never_raises(self):
        assert wc.alert_tag([{"tags": "Wind"}]) is None      # string, not a list
        assert wc.alert_tag([None, {"tags": ["Fog"]}]) == "Fog"
        assert wc.alert_tag("nonsense") is None

    def test_a_non_string_tag_is_read_as_text(self):
        assert wc.alert_tag([{"tags": [42]}]) == "42"
