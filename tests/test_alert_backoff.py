"""Tests for progressive backoff of inaccessible One Call 4.0 alerts."""

import asyncio
import logging
import sys
import types
from itertools import pairwise
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

pytest.importorskip("aiohttp")
component = Path(__file__).resolve().parents[1] / "custom_components" / "meteo_tracker"
# Load the API as a package without executing the Home Assistant integration entrypoint.
pkg = types.ModuleType("meteo_tracker")
pkg.__path__ = [str(component)]
sys.modules.setdefault("meteo_tracker", pkg)
from meteo_tracker.api import OpenWeatherClient, OpenWeatherError, OpenWeatherHTTPError


def test_404_backoff_and_recovery(caplog):
    async def run():
        client = OpenWeatherClient(None, "test", api_version="4.0")
        current = {"data": [{"alerts": ["A", "B"]}]}
        calls = []
        async def fetch(url, params):
            calls.append(url)
            if url.endswith("/A") and len([u for u in calls if u.endswith("/A")]) <= 4:
                raise OpenWeatherHTTPError(404, '{"message":"Internal error"}')
            return {"id": url.rsplit("/", 1)[-1], "event": "Wind", "start": 1, "end": 2}
        client._get = fetch
        clock = [0.0]
        with (
            patch("meteo_tracker.api.time.monotonic", side_effect=lambda: clock[0]),
            caplog.at_level(logging.DEBUG),
        ):
            for when, expected_attempts in [(0, 1), (100, 1), (300, 2), (900, 3), (2100, 4), (4499, 4), (4500, 5)]:
                clock[0] = when
                await client._alerts_v4(current)
                assert sum(u.endswith("/A") for u in calls) == expected_attempts
            assert sum("Could not read alert A (HTTP 404)" in r.message for r in caplog.records) == 1
            assert sum("Alert A still unavailable" in r.message for r in caplog.records) == 3
            assert sum("Previously unavailable alert A retrieved" in r.message for r in caplog.records) == 1
            assert "A" not in client._alert_404_failures



    asyncio.run(run())

def test_transient_disappearance_retains_backoff(caplog):
    async def run():
        client = OpenWeatherClient(None, "test", api_version="4.0")
        client._get = AsyncMock(side_effect=OpenWeatherHTTPError(404, "missing"))
        active = {"data": [{"alerts": ["A"]}]}
        absent = {"data": [{"alerts": []}]}
        clock = [0.0]
        with (
            patch("meteo_tracker.api.time.monotonic", side_effect=lambda: clock[0]),
            caplog.at_level(logging.DEBUG),
        ):
            await client._alerts_v4(active)
            clock[0] = 600
            await client._alerts_v4(absent)
            assert "A" in client._alert_404_failures
            clock[0] = 660
            await client._alerts_v4(active)
            assert client._get.await_count == 2
            assert client._alert_404_failures["A"][0] == 2
            assert sum("Could not read alert A (HTTP 404)" in r.message for r in caplog.records) == 1
            assert any("attempt 2; retry in 10 minutes" in r.message for r in caplog.records)

    asyncio.run(run())


def test_absent_alert_expires_without_recovery_log(caplog):
    async def run():
        client = OpenWeatherClient(None, "test", api_version="4.0")
        client._get = AsyncMock(side_effect=OpenWeatherHTTPError(404, "missing"))
        clock = [0.0]
        with (
            patch("meteo_tracker.api.time.monotonic", side_effect=lambda: clock[0]),
            caplog.at_level(logging.INFO),
        ):
            await client._alerts_v4({"data": [{"alerts": ["A"]}]})
            clock[0] = 3599
            await client._alerts_v4({"data": [{"alerts": []}]})
            assert "A" in client._alert_404_failures
            clock[0] = 3600
            await client._alerts_v4({"data": [{"alerts": []}]})
        assert not client._alert_404_failures
        assert not any("retrieved" in r.message for r in caplog.records)

    asyncio.run(run())


def test_reappearance_refreshes_absence_expiry():
    async def run():
        client = OpenWeatherClient(None, "test", api_version="4.0")
        client._get = AsyncMock(side_effect=OpenWeatherHTTPError(404, "missing"))
        clock = [0.0]
        active = {"data": [{"alerts": ["A"]}]}
        absent = {"data": [{"alerts": []}]}
        with patch("meteo_tracker.api.time.monotonic", side_effect=lambda: clock[0]):
            await client._alerts_v4(active)
            clock[0] = 3500
            await client._alerts_v4(active)
            clock[0] = 3601
            await client._alerts_v4(absent)
            assert "A" in client._alert_404_failures
            clock[0] = 7100
            await client._alerts_v4(absent)
            assert not client._alert_404_failures

    asyncio.run(run())


def test_people_under_the_same_alert_share_its_wait():
    """The detail request carries no location: a 404 is the alert's, whoever is under it."""
    async def run():
        client = OpenWeatherClient(None, "test", api_version="4.0")
        asked = []

        async def fetch(url, params):
            if url.endswith("/current"):
                return {"data": [{"alerts": ["A"]}]}
            if "/alert/" in url:
                asked.append(url.rsplit("/", 1)[-1])
                raise OpenWeatherHTTPError(404, "missing")
            raise OpenWeatherError("no timeline in this test")

        client._get = fetch
        with patch(
            "meteo_tracker.api.onecall_v4.build_onecall",
            side_effect=lambda current, **parts: parts["alerts"],
        ):
            # One refresh, two people 30 km apart under the same alert.
            await client.async_one_call(43.66, 4.06)
            await client.async_one_call(43.93, 4.06)
        assert asked == ["A"]

    asyncio.run(run())


def test_an_alert_someone_still_sees_is_kept():
    """Missing from one person's response is not gone: the hour starts when nobody sees it."""
    async def run():
        client = OpenWeatherClient(None, "test", api_version="4.0")
        client._get = AsyncMock(side_effect=OpenWeatherHTTPError(404, "missing"))
        here = {"data": [{"alerts": ["A"]}]}
        elsewhere = {"data": [{"alerts": []}]}
        clock = [0.0]
        with patch("meteo_tracker.api.time.monotonic", side_effect=lambda: clock[0]):
            for minute in range(0, 130, 10):  # two hours of 10-minute refreshes
                clock[0] = minute * 60
                await client._alerts_v4(here)
                await client._alerts_v4(elsewhere)
            assert "A" in client._alert_404_failures

    asyncio.run(run())


def test_the_wait_grows_to_an_hour_and_stays_there():
    """5, 10, 20 and 40 minutes, then hourly: a day of it is 27 requests, not 144."""
    async def run():
        client = OpenWeatherClient(None, "test", api_version="4.0")
        client._get = AsyncMock(side_effect=OpenWeatherHTTPError(404, "missing"))
        current = {"data": [{"alerts": ["A"]}]}
        clock = [0.0]
        asked = []
        with patch("meteo_tracker.api.time.monotonic", side_effect=lambda: clock[0]):
            for minute in range(0, 24 * 60, 10):  # a day of 10-minute refreshes
                clock[0] = minute * 60
                before = client._get.await_count
                await client._alerts_v4(current)
                if client._get.await_count > before:
                    asked.append(minute)
        gaps = [later - earlier for earlier, later in pairwise(asked)]
        assert gaps[:5] == [10, 10, 20, 40, 60]
        assert set(gaps[4:]) == {60}
        assert len(asked) == 27

    asyncio.run(run())


def test_non_404_errors_do_not_enter_backoff():
    async def run():
        client = OpenWeatherClient(None, "test", api_version="4.0")
        client._get = AsyncMock(side_effect=OpenWeatherHTTPError(500, "server error"))
        current = {"data": [{"alerts": ["A"]}]}
        await client._alerts_v4(current)
        await client._alerts_v4(current)
        assert client._get.await_count == 2
        assert not client._alert_404_failures

    asyncio.run(run())


def test_invalid_api_key_is_propagated():
    from meteo_tracker.api import InvalidApiKey

    async def run():
        client = OpenWeatherClient(None, "test", api_version="4.0")
        client._get = AsyncMock(side_effect=InvalidApiKey("Invalid key"))

        with pytest.raises(InvalidApiKey):
            await client._alerts_v4({"data": [{"alerts": ["A"]}]})

        assert not client._alert_404_failures

    asyncio.run(run())


def test_multiple_successful_alerts():
    async def run():
        client = OpenWeatherClient(None, "test", api_version="4.0")
        client._get = AsyncMock(
            side_effect=[
                {"event": "Wind", "start": 1, "end": 2},
                {"event": "Rain", "start": 1, "end": 2},
            ]
        )

        alerts = await client._alerts_v4(
            {"data": [{"alerts": ["A", "B"]}]}
        )

        assert [alert["event"] for alert in alerts] == ["Wind", "Rain"]
        assert client._get.await_count == 2

    asyncio.run(run())


def test_alert_limit_preserves_backoff(caplog):
    from meteo_tracker.const import MAX_V4_ALERTS

    async def run():
        client = OpenWeatherClient(None, "test", api_version="4.0")
        client._get = AsyncMock(
            return_value={"event": "Wind", "start": 1, "end": 2}
        )

        ids = [f"alert-{i}" for i in range(MAX_V4_ALERTS + 1)]

        with caplog.at_level(logging.WARNING):
            alerts = await client._alerts_v4(
                {"data": [{"alerts": ids}]}
            )

        assert len(alerts) == MAX_V4_ALERTS
        assert client._get.await_count == MAX_V4_ALERTS
        assert any(
            "skipping" in record.message
            for record in caplog.records
        )

    asyncio.run(run())


def test_alert_normalisation_returns_none():
    async def run():
        client = OpenWeatherClient(None, "test", api_version="4.0")
        client._get = AsyncMock(return_value={})

        with patch(
            "meteo_tracker.api.onecall_v4.normalise_alert",
            return_value=None,
        ):
            alerts = await client._alerts_v4(
                {"data": [{"alerts": ["A"]}]}
            )

        assert alerts == []
        assert client._get.await_count == 1

    asyncio.run(run())
