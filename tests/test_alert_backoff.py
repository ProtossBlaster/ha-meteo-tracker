"""Tests for progressive backoff of inaccessible One Call 4.0 alerts."""

import asyncio
import logging
from unittest.mock import AsyncMock, patch

import importlib
import sys
import types
from pathlib import Path

import pytest

pytest.importorskip("aiohttp")
component = Path(__file__).resolve().parents[1] / "custom_components" / "meteo_tracker"
# Load the API as a package without executing the Home Assistant integration entrypoint.
pkg = types.ModuleType("meteo_tracker")
pkg.__path__ = [str(component)]
sys.modules.setdefault("meteo_tracker", pkg)
from meteo_tracker.api import OpenWeatherClient, OpenWeatherHTTPError


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
        with patch("meteo_tracker.api.time.monotonic", side_effect=lambda: clock[0]):
            with caplog.at_level(logging.DEBUG):
                for when, expected_attempts in [(0, 1), (100, 1), (300, 2), (900, 3), (2100, 4), (3900, 5)]:
                    clock[0] = when
                    await client._alerts_v4(current)
                    assert sum(u.endswith("/A") for u in calls) == expected_attempts
                assert sum("Could not read alert A (HTTP 404)" in r.message for r in caplog.records) == 1
                assert sum("Alert A still unavailable" in r.message for r in caplog.records) == 3
                assert sum("Previously unavailable alert A retrieved" in r.message for r in caplog.records) == 1
                assert "A" not in client._alert_404_failures



    asyncio.run(run())

def test_disappeared_alert_clears_failure_without_recovery_log(caplog):
    async def run():
        client = OpenWeatherClient(None, "test", api_version="4.0")
        client._get = AsyncMock(side_effect=OpenWeatherHTTPError(404, "missing"))
        with caplog.at_level(logging.INFO):
            await client._alerts_v4({"data": [{"alerts": ["A"]}]})
            await client._alerts_v4({"data": [{"alerts": []}]})
        assert not client._alert_404_failures
        assert not any("retrieved" in r.message for r in caplog.records)

    asyncio.run(run())