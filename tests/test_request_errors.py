"""A request that fails says why, even when the error carries no text (#8)."""

import asyncio
import sys
import types
from pathlib import Path
from unittest.mock import patch

import pytest

pytest.importorskip("aiohttp")
component = Path(__file__).resolve().parents[1] / "custom_components" / "meteo_tracker"
# Load the API as a package without executing the Home Assistant integration entrypoint.
pkg = types.ModuleType("meteo_tracker")
pkg.__path__ = [str(component)]
sys.modules.setdefault("meteo_tracker", pkg)
from meteo_tracker.api import OpenWeatherClient, OpenWeatherError


class _Slow:
    """A session whose answer never comes in time."""

    def get(self, url, params):
        return self

    async def __aenter__(self):
        await asyncio.sleep(1)

    async def __aexit__(self, *exc):
        return False


def test_a_timeout_says_it_is_one():
    async def run():
        client = OpenWeatherClient(_Slow(), "test", api_version="4.0")
        with (
            patch("meteo_tracker.api.REQUEST_TIMEOUT", 0.01),
            pytest.raises(OpenWeatherError) as raised,
        ):
            await client._get("https://example.invalid/timeline/1day", {})
        assert str(raised.value) == "Error talking to OpenWeather: no answer within 0.01 s"

    asyncio.run(run())
