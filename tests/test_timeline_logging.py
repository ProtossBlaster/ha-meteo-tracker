"""Regression tests for One Call 4.0 timeline failure logging."""

import asyncio
import logging
import sys
import types
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

pytest.importorskip("aiohttp")
component = Path(__file__).resolve().parents[1] / "custom_components" / "meteo_tracker"
pkg = types.ModuleType("meteo_tracker")
pkg.__path__ = [str(component)]
sys.modules.setdefault("meteo_tracker", pkg)

from meteo_tracker.api import OpenWeatherClient, OpenWeatherError


def test_timeline_failure_levels_and_recovery(caplog):
    client = OpenWeatherClient(None, "test", api_version="4.0")
    error = OpenWeatherError("timeout")
    with caplog.at_level(logging.DEBUG):
        assert client._timeline_or_empty(error, "daily forecast", (45.0, 5.0)) == []
        assert client._timeline_or_empty(error, "daily forecast", (45.0, 5.0)) == []
        assert client._timeline_or_empty(error, "daily forecast", (45.0, 5.0)) == []
        assert client._timeline_or_empty([{"data": []}], "daily forecast", (45.0, 5.0)) == [{"data": []}]
        assert client._timeline_or_empty([{"data": []}], "daily forecast", (45.0, 5.0)) == [{"data": []}]
        assert client._timeline_or_empty(error, "daily forecast", (45.0, 5.0)) == []
    events = [(r.levelno, r.message) for r in caplog.records]
    assert [level for level, _ in events] == [
        logging.WARNING, logging.DEBUG, logging.DEBUG, logging.INFO, logging.WARNING
    ]
    assert "timeout" in events[0][1]
    assert "attempt 2" in events[1][1]
    assert "attempt 3" in events[2][1]
    assert "after 3 failed attempts" in events[3][1]
    assert client._timeline_failures[(45.0, 5.0, "daily forecast")] == 1


def test_timelines_and_clients_have_independent_counters(caplog):
    first = OpenWeatherClient(None, "test", api_version="4.0")
    second = OpenWeatherClient(None, "test", api_version="4.0")
    failure = OpenWeatherError("HTTP 500")
    with caplog.at_level(logging.DEBUG):
        first._timeline_or_empty(failure, "hourly forecast", (45.0, 5.0))
        first._timeline_or_empty(failure, "daily forecast", (45.0, 5.0))
        first._timeline_or_empty(failure, "hourly forecast", (45.0, 5.0))
        second._timeline_or_empty(failure, "hourly forecast", (45.0, 5.0))
        first._timeline_or_empty([], "hourly forecast", (45.0, 5.0))
    assert first._timeline_failures == {(45.0, 5.0, "daily forecast"): 1}
    assert second._timeline_failures == {(45.0, 5.0, "hourly forecast"): 1}
    warnings = [r for r in caplog.records if r.levelno == logging.WARNING]
    assert len(warnings) == 3
    assert any("after 2 failed attempts" in r.message for r in caplog.records)


def test_partial_refresh_still_queries_every_timeline(caplog):
    async def run():
        client = OpenWeatherClient(None, "test", api_version="4.0")
        paths = []

        async def fetch(url, params):
            paths.append(url)
            if url.endswith("/current"):
                return {"data": [{"dt": 1, "temp": 20}]}
            if url.endswith("/timeline/1day"):
                raise OpenWeatherError("daily timeout")
            return {"data": [{"dt": 1, "temp": 21}]}

        client._get = AsyncMock(side_effect=fetch)
        with caplog.at_level(logging.DEBUG):
            first = await client.async_one_call(45.0, 5.0)
            second = await client.async_one_call(45.0, 5.0)
        assert first["current"]["temp"] == second["current"]["temp"] == 20
        assert first["daily"] == second["daily"] == []
        assert first["hourly"] and second["hourly"]
        assert first["minutely"] and second["minutely"]
        assert sum(url.endswith("/timeline/1day") for url in paths) == 2
        assert sum("daily forecast unavailable this cycle" in r.message for r in caplog.records) == 1
        assert any("daily forecast still unavailable (attempt 2)" in r.message for r in caplog.records)

    asyncio.run(run())


def test_two_locations_do_not_reset_each_others_failures(caplog):
    """Three refreshes: A fails daily, B succeeds, then A recovers."""
    async def run():
        client = OpenWeatherClient(None, "test", api_version="4.0")

        async def fetch(url, params):
            if url.endswith("/current"):
                return {"data": [{"dt": 1, "temp": 20}]}
            if url.endswith("/timeline/1day") and params["lat"] == 45.0:
                raise OpenWeatherError("daily timeout")
            return {"data": [{"dt": 1, "temp": 21}]}

        client._get = AsyncMock(side_effect=fetch)
        with caplog.at_level(logging.DEBUG):
            for _ in range(3):
                await client.async_one_call(45.0, 5.0)
                await client.async_one_call(46.0, 6.0)
        warnings = [r for r in caplog.records if r.levelno == logging.WARNING]
        recoveries = [r for r in caplog.records if r.levelno == logging.INFO and "recovered" in r.message]
        assert len(warnings) == 1
        assert not recoveries
        assert client._timeline_failures[(45.0, 5.0, "daily forecast")] == 3

        async def recovered(url, params):
            if url.endswith("/current"):
                return {"data": [{"dt": 1, "temp": 20}]}
            return {"data": [{"dt": 1, "temp": 21}]}

        client._get = AsyncMock(side_effect=recovered)
        await client.async_one_call(45.0, 5.0)
        assert sum("daily forecast recovered after 3 failed attempts" in r.message for r in caplog.records) == 1

    asyncio.run(run())
