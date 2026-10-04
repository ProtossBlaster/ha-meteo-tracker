"""Alert state compatibility and translation catalogue contract."""

import json
from pathlib import Path
import re

import weather_codes as wc


COMPONENT = Path(__file__).resolve().parents[1] / "custom_components/meteo_tracker"


def test_known_tags_use_stable_keys_and_preserve_raw_values():
    assert wc.alert_type_state([{"tags": ["Extreme high temperature"]}]) == "extreme_high_temperature"
    assert wc.alert_type_state([{"tags": ["Wind"]}]) == "wind"
    for raw, slug in wc.ALERT_TYPE_SLUGS.items():
        alerts = [{"tags": [raw]}]
        assert wc.alert_type_state(alerts) == slug
        assert wc.alert_tag(alerts) == raw


def test_future_tags_do_not_become_unknown_or_get_normalized():
    for raw in ("Future experimental hazard", "Unlisted-local-tag", "Canicule"):
        assert wc.alert_type_state([{"tags": [raw]}]) == raw


def test_no_alert_and_malformed_payloads():
    for alerts in (None, [], "invalid", [None], [{"tags": []}], [{"tags": "Wind"}]):
        assert wc.alert_type_state(alerts) is None
        assert wc.alert_tag(alerts) is None


def test_first_usable_tag_and_payload_are_preserved():
    alerts = [{"tags": []}, {"tags": ["Wind", "Rain"], "description": "Texte original"}]
    before = json.dumps(alerts)
    assert wc.alert_type_state(alerts) == "wind"
    assert wc.alert_tag(alerts) == "Wind"
    assert json.dumps(alerts) == before


def test_catalogues_have_valid_complete_translations():
    source = json.loads((COMPONENT / "strings.json").read_text())
    english = json.loads((COMPONENT / "translations/en.json").read_text())
    assert source == english
    assert len(wc.ALERT_TYPE_SLUGS) == 17
    for language in ("en", "it", "fr"):
        catalogue = json.loads((COMPONENT / f"translations/{language}.json").read_text())
        states = catalogue["entity"]["sensor"]["weather_alert_type"]["state"]
        assert set(states) == set(wc.ALERT_TYPE_SLUGS.values())
        for key, label in states.items():
            assert re.fullmatch(r"[a-z0-9]+(?:[a-z0-9_-]*[a-z0-9])?", key)
            assert isinstance(label, str) and label.strip()
