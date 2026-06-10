"""Thin async client for the OpenWeather One Call 3.0 and Air Pollution APIs."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from aiohttp import ClientError, ClientSession

from .const import AIR_POLLUTION_URL, ONECALL_URL, REQUEST_TIMEOUT

_LOGGER = logging.getLogger(__name__)


class OpenWeatherError(Exception):
    """Generic OpenWeather error."""


class InvalidApiKey(OpenWeatherError):
    """The API key was rejected (HTTP 401)."""


class RateLimited(OpenWeatherError):
    """The daily/per-minute call budget was exceeded (HTTP 429)."""


class OpenWeatherClient:
    """Minimal client wrapping the two OpenWeather endpoints we use."""

    def __init__(
        self,
        session: ClientSession,
        api_key: str,
        *,
        language: str = "en",
        units: str = "metric",
    ) -> None:
        self._session = session
        self._api_key = api_key
        self._language = language
        self._units = units

    async def _get(self, url: str, params: dict[str, Any]) -> dict[str, Any]:
        full_params = {**params, "appid": self._api_key}
        try:
            async with asyncio.timeout(REQUEST_TIMEOUT):
                async with self._session.get(url, params=full_params) as resp:
                    if resp.status == 401:
                        raise InvalidApiKey("OpenWeather rejected the API key")
                    if resp.status == 429:
                        raise RateLimited("OpenWeather call budget exceeded")
                    if resp.status >= 400:
                        body = await resp.text()
                        raise OpenWeatherError(
                            f"OpenWeather returned HTTP {resp.status}: {body[:200]}"
                        )
                    return await resp.json()
        except (ClientError, asyncio.TimeoutError) as err:
            raise OpenWeatherError(f"Error talking to OpenWeather: {err}") from err

    async def async_one_call(self, lat: float, lon: float) -> dict[str, Any]:
        """Fetch current + minutely + hourly + daily + alerts for a location."""
        return await self._get(
            ONECALL_URL,
            {
                "lat": lat,
                "lon": lon,
                "units": self._units,
                "lang": self._language,
            },
        )

    async def async_air_pollution(self, lat: float, lon: float) -> dict[str, Any]:
        """Fetch the current air-quality reading for a location."""
        return await self._get(AIR_POLLUTION_URL, {"lat": lat, "lon": lon})

    async def async_validate(self, lat: float, lon: float) -> None:
        """Probe the API key with a single One Call request.

        Raises :class:`InvalidApiKey`, :class:`RateLimited` or
        :class:`OpenWeatherError` on failure; returns ``None`` on success.
        """
        await self.async_one_call(lat, lon)
