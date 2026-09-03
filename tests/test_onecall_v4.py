"""Unit tests for rebuilding a One Call 3.0 payload out of 4.0 responses.

The rest of the integration only ever reads the 3.0 shape, so these tests are
the contract: if the reassembly drifts, every platform silently loses data.
"""

import onecall_v4 as v4


def page(*records, **top):
    """A 4.0 response: records under ``data``, with the usual header fields."""
    return {"lat": 45.46, "lon": 9.19, "timezone": "Europe/Rome",
            "timezone_offset": 7200, "data": list(records), **top}


def hours(start, count, step=v4.HOUR):
    return [{"dt": start + i * step, "temp": 20 + i} for i in range(count)]


class TestRecords:
    def test_reads_the_data_array(self):
        assert v4.records(page({"dt": 1}, {"dt": 2})) == [{"dt": 1}, {"dt": 2}]

    def test_survives_anything_that_is_not_a_response(self):
        for junk in (None, [], "boom", {}, {"data": None}, {"data": "no"}):
            assert v4.records(junk) == []

    def test_skips_non_dict_entries(self):
        assert v4.records({"data": [{"dt": 1}, "junk", None]}) == [{"dt": 1}]


class TestMergePages:
    def test_orders_by_time_and_drops_repeats(self):
        first = page(*hours(1000, 3))
        # A second page that overlaps the first must not show an hour twice.
        second = page(*hours(1000 + 2 * v4.HOUR, 3))
        merged = v4.merge_pages([first, second], limit=10)
        assert [r["dt"] for r in merged] == [
            1000 + i * v4.HOUR for i in range(5)
        ]

    def test_honours_the_limit(self):
        merged = v4.merge_pages([page(*hours(0, 60))], limit=v4.WANT_HOURS)
        assert len(merged) == 48

    def test_drops_records_without_a_timestamp(self):
        assert v4.merge_pages([page({"temp": 9})], limit=5) == []

    def test_strips_the_alert_ids_4_0_adds_to_every_record(self):
        merged = v4.merge_pages([page({"dt": 1, "temp": 3, "alerts": ["a"]})], limit=5)
        assert merged == [{"dt": 1, "temp": 3}]


class TestNextStart:
    def test_a_short_page_ends_the_timeline(self):
        # Fewer records than the endpoint's maximum means the data ran out.
        assert v4.next_start(page(*hours(0, 5)), v4.HOUR, v4.HOURLY_PAGE) is None

    def test_a_full_page_asks_for_the_hour_after_the_last(self):
        full = page(*hours(1000, v4.HOURLY_PAGE))
        last = 1000 + (v4.HOURLY_PAGE - 1) * v4.HOUR
        assert v4.next_start(full, v4.HOUR, v4.HOURLY_PAGE) == last + v4.HOUR

    def test_a_full_page_of_untimed_records_stops_rather_than_loops(self):
        full = page(*[{"temp": 1} for _ in range(v4.HOURLY_PAGE)])
        assert v4.next_start(full, v4.HOUR, v4.HOURLY_PAGE) is None


class TestAlertIds:
    def test_collects_in_order_without_repeats(self):
        current = page({"dt": 1, "alerts": ["b", "a", "b"]})
        assert v4.alert_ids(current) == ["b", "a"]

    def test_no_alerts_is_an_empty_list(self):
        assert v4.alert_ids(page({"dt": 1})) == []

    def test_ignores_entries_that_are_not_identifiers(self):
        assert v4.alert_ids(page({"dt": 1, "alerts": [None, "", 7, "ok"]})) == ["ok"]


class TestNormaliseAlert:
    """Shapes measured against the live One Call 4.0 endpoint on 2026-09-03.

    Two of them contradict OpenWeather's own migration guide, which is why they
    are pinned here.
    """

    # A real Meteoalarm alert, trimmed: description arrives as a per-language
    # list, `event` arrives empty, and `tags` is present despite the guide.
    live = {
        "id": "2.49.0.0.380.3.IT...",
        "sender_name": "Italian Air Force National Meteorological Service",
        "event": "",
        "start": 1788501600,
        "end": 1788544740,
        "description": [
            {"language": "en-GB", "description": "Moderate intensity expected"},
            {"language": "it-IT", "description": "Fenomeni di intensita moderata"},
        ],
        "tags": ["Extreme high temperature"],
    }

    def test_reads_the_top_level_form_the_live_endpoint_uses(self):
        assert v4.normalise_alert(self.live)["sender_name"].startswith("Italian")

    def test_reads_the_wrapped_form_too(self):
        # The documentation also shows the fields under `data`.
        assert v4.normalise_alert(page(self.live))["start"] == 1788501600

    def test_passes_tags_through_although_the_guide_calls_them_gone(self):
        got = v4.normalise_alert(self.live)
        assert got["tags"] == ["Extreme high temperature"]

    def test_omits_tags_when_the_server_really_sends_none(self):
        bare = {k: v for k, v in self.live.items() if k != "tags"}
        assert "tags" not in v4.normalise_alert(bare)

    def test_picks_the_description_in_the_configured_language(self):
        got = v4.normalise_alert(self.live, language="it")
        assert got["description"] == "Fenomeni di intensita moderata"

    def test_prefers_the_exact_variant_over_another_of_the_same_language(self):
        # pt_br and zh_cn are in SUPPORTED_LANGUAGES, and a base-language match
        # alone would hand a Brazilian user the European Portuguese text.
        both = dict(self.live, description=[
            {"language": "pt-PT", "description": "Portugal"},
            {"language": "pt-BR", "description": "Brasil"},
        ])
        assert v4.normalise_alert(both, language="pt_br")["description"] == "Brasil"

    def test_falls_back_to_english_for_a_language_not_offered(self):
        got = v4.normalise_alert(self.live, language="de")
        assert got["description"] == "Moderate intensity expected"

    def test_falls_back_to_the_first_entry_when_english_is_absent(self):
        only = dict(self.live, description=[
            {"language": "fr-FR", "description": "Phenomenes moderes"}])
        assert v4.normalise_alert(only, language="de")["description"] == "Phenomenes moderes"

    def test_a_plain_string_description_is_kept_as_is(self):
        # 3.0 sent a string; keep working if 4.0 ever does the same.
        plain = dict(self.live, description="Just text")
        assert v4.normalise_alert(plain)["description"] == "Just text"

    def test_an_empty_event_borrows_the_alerts_own_tag(self):
        # Measured: 4.0 returned "" for an alert 3.0 titled "Yellow
        # High-temperature Warning". A nameless alert is useless on a dashboard.
        assert v4.normalise_alert(self.live)["event"] == "Extreme high temperature"

    def test_a_real_event_name_is_never_overwritten_by_a_tag(self):
        named = dict(self.live, event="Yellow High-temperature Warning")
        assert v4.normalise_alert(named)["event"] == "Yellow High-temperature Warning"

    def test_event_is_omitted_when_there_is_neither_name_nor_tag(self):
        # Absent is not the same as an empty title.
        naked = {k: v for k, v in self.live.items() if k not in ("tags", "event")}
        assert "event" not in v4.normalise_alert(naked)

    def test_the_internal_id_is_not_leaked_into_the_3_0_shape(self):
        assert "id" not in v4.normalise_alert(self.live)


class TestBuildOnecall:
    def test_produces_the_3_0_shape(self):
        built = v4.build_onecall(
            page({"dt": 500, "temp": 21, "alerts": ["A1"]}),
            minutely_pages=[page(*[{"dt": i, "precipitation": 0} for i in range(60)])],
            hourly_pages=[page(*hours(1000, 20)), page(*hours(1000 + 20 * v4.HOUR, 20)),
                          page(*hours(1000 + 40 * v4.HOUR, 8))],
            daily_pages=[page(*[{"dt": i * v4.DAY, "temp": {"min": 3, "max": 9}}
                               for i in range(8)])],
            alerts=[{"event": "Vento forte"}],
        )
        assert built["lat"] == 45.46 and built["timezone"] == "Europe/Rome"
        assert built["current"] == {"dt": 500, "temp": 21}
        assert len(built["minutely"]) == 60
        assert len(built["hourly"]) == 48
        assert len(built["daily"]) == 8
        assert built["alerts"] == [{"event": "Vento forte"}]

    def test_current_never_carries_the_raw_alert_ids(self):
        built = v4.build_onecall(page({"dt": 1, "alerts": ["A1", "A2"]}))
        # 3.0's `current` has no alerts key; the full objects live at top level.
        assert "alerts" not in built["current"]

    def test_omits_alerts_entirely_when_none_are_active(self):
        # 3.0 leaves the key out, and downstream tests "is there an alert" by
        # its presence — so an empty list here would read as a live alert.
        assert "alerts" not in v4.build_onecall(page({"dt": 1}))

    def test_empty_timelines_are_lists_not_none(self):
        built = v4.build_onecall(page({"dt": 1}))
        assert built["minutely"] == [] and built["hourly"] == [] and built["daily"] == []

    def test_a_missing_current_response_does_not_explode(self):
        built = v4.build_onecall(None)
        assert built["current"] == {} and built["hourly"] == []
