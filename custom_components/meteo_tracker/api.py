"""Async client for the OpenWeather One Call (3.0 and 4.0) and Air Pollution APIs.

Callers only ever see the One Call 3.0 payload shape. When an entry is on 4.0
the six endpoints are fetched and reassembled here (see :mod:`onecall_v4`), so
the coordinator and every platform stay version-agnostic.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any
from urllib.parse import quote

from aiohttp import ClientError, ClientSession

from . import onecall_v4
from .const import (
    AIR_POLLUTION_URL,
    API_V3,
    API_V4,
    DEFAULT_API_VERSION,
    MAX_V4_ALERTS,
    ONECALL_URL,
    ONECALL_V4_BASE,
    REQUEST_TIMEOUT,
)

_LOGGER = logging.getLogger(__name__)

# Guard against a timeline that never reports itself finished. Even the longest
# thing we ask for (48 hours at 20 records a page) needs three requests.
_MAX_PAGES = 4


class OpenWeatherError(Exception):
    """Generic OpenWeather error."""


class InvalidApiKey(OpenWeatherError):
    """The API key was rejected (HTTP 401)."""


class RateLimited(OpenWeatherError):
    """The daily/per-minute call budget was exceeded (HTTP 429)."""


class OpenWeatherClient:
    """Minimal client wrapping the OpenWeather endpoints we use."""

    def __init__(
        self,
        session: ClientSession,
        api_key: str,
        *,
        language: str = "en",
        units: str = "metric",
        api_version: str = DEFAULT_API_VERSION,
    ) -> None:
        self._session = session
        self._api_key = api_key
        self._language = language
        self._units = units
        self._api_version = api_version

    @property
    def api_version(self) -> str:
        return self._api_version

    async def _get(self, url: str, params: dict[str, Any]) -> dict[str, Any]:
        full_params = {**params, "appid": self._api_key}
        try:
            async with asyncio.timeout(REQUEST_TIMEOUT):
                async with self._session.get(url, params=full_params) as resp:
                    if resp.status == 401:
                        # OpenWeather explains *why* it refused — most often the
                        # key is fine but the One Call plan was never subscribed.
                        # Passing that on beats replacing it with "invalid key".
                        raise InvalidApiKey(await _reason(resp))
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
        if self._api_version == API_V4:
            return await self._one_call_v4(lat, lon)
        return await self._get(
            ONECALL_URL,
            {
                "lat": lat,
                "lon": lon,
                "units": self._units,
                "lang": self._language,
            },
        )

    # ------------------------------------------------------------------ 4.0 --

    async def _timeline(
        self,
        path: str,
        params: dict[str, Any],
        *,
        want: int,
        page_size: int,
        step: int,
    ) -> list[dict[str, Any]]:
        """Fetch one 4.0 timeline, paging until we hold ``want`` records."""
        url = f"{ONECALL_V4_BASE}/{path}"
        pages: list[dict[str, Any]] = []
        start: int | None = None

        for _ in range(_MAX_PAGES):
            page = await self._get(
                url, params if start is None else {**params, "start": start}
            )
            pages.append(page)
            if len(onecall_v4.merge_pages(pages, want)) >= want:
                break
            nxt = onecall_v4.next_start(page, step, page_size)
            # A non-advancing cursor would loop forever at a call apiece.
            if nxt is None or (start is not None and nxt <= start):
                break
            start = nxt

        return pages

    async def _one_call_v4(self, lat: float, lon: float) -> dict[str, Any]:
        params = {
            "lat": lat,
            "lon": lon,
            "units": self._units,
            "lang": self._language,
        }

        current, minutely, hourly, daily = await asyncio.gather(
            self._get(f"{ONECALL_V4_BASE}/current", params),
            self._timeline(
                "timeline/1min",
                params,
                want=onecall_v4.WANT_MINUTES,
                page_size=onecall_v4.MINUTELY_PAGE,
                step=60,
            ),
            self._timeline(
                "timeline/1h",
                params,
                want=onecall_v4.WANT_HOURS,
                page_size=onecall_v4.HOURLY_PAGE,
                step=onecall_v4.HOUR,
            ),
            self._timeline(
                "timeline/1day",
                params,
                want=onecall_v4.WANT_DAYS,
                page_size=onecall_v4.DAILY_PAGE,
                step=onecall_v4.DAY,
            ),
            return_exceptions=True,
        )

        # A rejected key must always surface, whichever leg hit it first.
        for outcome in (current, minutely, hourly, daily):
            if isinstance(outcome, InvalidApiKey):
                raise outcome
        if isinstance(current, BaseException):
            raise current

        return onecall_v4.build_onecall(
            current,
            minutely_pages=_or_empty(minutely, "minute-by-minute forecast"),
            hourly_pages=_or_empty(hourly, "hourly forecast"),
            daily_pages=_or_empty(daily, "daily forecast"),
            alerts=await self._alerts_v4(current),
        )

    async def _alerts_v4(self, current: Any) -> list[dict[str, Any]]:
        """Resolve the alert IDs 4.0 returns into full 3.0-shaped alert entries."""
        ids = onecall_v4.alert_ids(current)
        if not ids:
            return []
        if len(ids) > MAX_V4_ALERTS:
            _LOGGER.warning(
                "%d weather alerts are active here; fetching the first %d, "
                "skipping %d to protect the API call budget",
                len(ids),
                MAX_V4_ALERTS,
                len(ids) - MAX_V4_ALERTS,
            )
            ids = ids[:MAX_V4_ALERTS]

        details = await asyncio.gather(
            *(
                self._get(f"{ONECALL_V4_BASE}/alert/{quote(aid, safe='')}", {})
                for aid in ids
            ),
            return_exceptions=True,
        )

        alerts: list[dict[str, Any]] = []
        for aid, detail in zip(ids, details):
            if isinstance(detail, InvalidApiKey):
                raise detail
            if isinstance(detail, BaseException):
                _LOGGER.warning("Could not read alert %s: %s", aid, detail)
                continue
            alert = onecall_v4.normalise_alert(
                detail, language=self._language
            )
            if alert:
                alerts.append(alert)
        return alerts

    # ---------------------------------------------------------------- other --

    async def async_air_pollution(self, lat: float, lon: float) -> dict[str, Any]:
        """Fetch the current air-quality reading for a location."""
        return await self._get(AIR_POLLUTION_URL, {"lat": lat, "lon": lon})

    async def async_validate(self, lat: float, lon: float) -> None:
        """Probe the API key with a single One Call request.

        Raises :class:`InvalidApiKey`, :class:`RateLimited` or
        :class:`OpenWeatherError` on failure; returns ``None`` on success.
        """
        if self._api_version == API_V4:
            # The cheapest 4.0 endpoint: one request, one record.
            await self._get(
                f"{ONECALL_V4_BASE}/current", {"lat": lat, "lon": lon}
            )
            return
        await self.async_one_call(lat, lon)


async def _reason(resp: Any) -> str:
    """OpenWeather's own explanation for a refusal, when it sent one."""
    try:
        body = await resp.json(content_type=None)
        message = body.get("message") if isinstance(body, dict) else None
    except Exception:  # noqa: BLE001 - a body we cannot parse is not fatal here
        message = None
    if not message:
        return "OpenWeather rejected the API key"
    return str(message)[:300]


def _or_empty(outcome: Any, what: str) -> list[dict[str, Any]]:
    """Keep a partial refresh alive when one optional timeline failed."""
    if isinstance(outcome, BaseException):
        _LOGGER.warning("One Call 4.0: %s unavailable this cycle: %s", what, outcome)
        return []
    return outcome


async def async_detect_api_version(
    session: ClientSession, api_key: str, lat: float, lon: float
) -> str:
    """Return the One Call version this key can actually reach.

    3.0 is tried first: a key that reaches both should stay on 3.0, because the
    whole picture costs one request there and six on 4.0. Only when 3.0 refuses
    the key — the state every account created after OpenWeather stopped selling
    3.0 is in — do we fall through to 4.0.
    """
    refusal: InvalidApiKey | None = None
    for version in (API_V3, API_V4):
        client = OpenWeatherClient(session, api_key, api_version=version)
        try:
            await client.async_validate(lat, lon)
        except InvalidApiKey as err:
            refusal = err
            continue
        return version
    raise refusal or InvalidApiKey("OpenWeather rejected the API key")
