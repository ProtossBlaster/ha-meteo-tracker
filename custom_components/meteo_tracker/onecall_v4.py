"""Rebuild a One Call 3.0-shaped payload out of One Call 4.0 responses.

One Call 4.0 replaced 3.0's single combined answer with six focused endpoints,
so the picture this integration needs — current conditions, the 60-minute
precipitation timeline, 48 hours, 8 days and the active alerts — now arrives in
pieces, and the long timelines arrive paginated. Everything downstream
(``coordinator``, ``weather``, ``sensor``, ``binary_sensor``) still speaks 3.0,
so the pieces are reassembled here and the rest of the integration never learns
which API answered.

This module imports neither Home Assistant nor aiohttp on purpose: it is pure
data shaping, which is the part most likely to be wrong, and it is what the
unit tests exercise in CI.
"""

from __future__ import annotations

from typing import Any

HOUR = 3600
DAY = 86400

# Maximum records One Call 4.0 puts in a single response, per endpoint.
MINUTELY_PAGE = 60
HOURLY_PAGE = 20
DAILY_PAGE = 10

# How much of each timeline we rebuild — the amount One Call 3.0 handed over in
# one request, so the entities see exactly what they saw before.
WANT_MINUTES = 60
WANT_HOURS = 48
WANT_DAYS = 8

# Keys 4.0 adds to every record that 3.0 never had. They are dropped so the
# assembled payload is the 3.0 shape and nothing else.
_V4_ONLY_KEYS = ("alerts",)


def records(payload: Any) -> list[dict[str, Any]]:
    """The ``data`` array of a 4.0 response, or ``[]`` when it is absent."""
    if not isinstance(payload, dict):
        return []
    data = payload.get("data")
    if not isinstance(data, list):
        return []
    return [rec for rec in data if isinstance(rec, dict)]


def _strip(rec: dict[str, Any]) -> dict[str, Any]:
    out = dict(rec)
    for key in _V4_ONLY_KEYS:
        out.pop(key, None)
    return out


def merge_pages(pages: Any, limit: int) -> list[dict[str, Any]]:
    """Flatten paged responses into one time-ordered, de-duplicated timeline.

    Pages are keyed by ``dt`` rather than concatenated, because a paginated
    request that overlaps the previous page would otherwise show the same hour
    twice.
    """
    out: list[dict[str, Any]] = []
    seen: set[Any] = set()
    for page in pages or ():
        for rec in records(page):
            when = rec.get("dt")
            if when is None or when in seen:
                continue
            seen.add(when)
            out.append(_strip(rec))
    out.sort(key=lambda rec: rec["dt"])
    return out[:limit]


def next_start(page: Any, step: int, page_size: int) -> int | None:
    """Unix time to request next, or ``None`` when this page ended the timeline.

    A page shorter than the endpoint's maximum means the data ran out, so there
    is nothing left to page to and asking again would just spend a call.
    """
    recs = records(page)
    if len(recs) < page_size:
        return None
    times = [rec["dt"] for rec in recs if isinstance(rec.get("dt"), int)]
    return max(times) + step if times else None


def alert_ids(current: Any) -> list[str]:
    """Alert IDs carried by the current-conditions record, in order, no repeats.

    4.0 hands back identifiers only; the text behind each one costs its own
    request, which is why the caller counts them before fetching.
    """
    out: list[str] = []
    seen: set[str] = set()
    for rec in records(current):
        for aid in rec.get("alerts") or ():
            if isinstance(aid, str) and aid and aid not in seen:
                seen.add(aid)
                out.append(aid)
    return out


def pick_description(value: Any, language: str) -> Any:
    """The alert text in the wanted language.

    3.0 sent one string. 4.0 sends a list of ``{language, description}`` — for a
    live Italian alert on 2026-09-03 it carried both ``en-GB`` and ``it-IT``, so
    on 4.0 an Italian install can finally read its alerts in Italian. Preference
    order: the exact code, then the same base language, then English, then
    whatever came first.
    """
    if value is None or isinstance(value, str):
        return value
    if not isinstance(value, list):
        return None
    entries = [v for v in value if isinstance(v, dict) and v.get("description")]
    if not entries:
        return None

    want = str(language or "en").lower().replace("_", "-")
    def code(entry: dict[str, Any]) -> str:
        return str(entry.get("language") or "").lower()

    for matches in (
        lambda e: code(e) == want,
        lambda e: code(e).split("-")[0] == want.split("-")[0],
        lambda e: code(e).split("-")[0] == "en",
    ):
        for entry in entries:
            if matches(entry):
                return entry["description"]
    return entries[0]["description"]


def normalise_alert(payload: Any, *, language: str = "en") -> dict[str, Any]:
    """One 4.0 alert-detail response as a 3.0 ``alerts[]`` entry.

    The documentation shows the alert fields both at the top level and under the
    common ``data`` wrapper; the live endpoint uses the top level, and both are
    accepted here.

    Two things the migration guide does not prepare you for, both measured
    against the live API on 2026-09-03:

    * ``tags`` **is** returned, identical to 3.0, although the guide lists it as
      gone. It is passed through when present.
    * ``event`` came back empty for an alert 3.0 titled "Yellow High-temperature
      Warning". An alert with no name is useless in a dashboard, so the alert's
      own tag stands in — and when there is no tag either, the key is left out
      rather than set to an empty string.
    """
    recs = records(payload)
    rec = recs[0] if recs else (payload if isinstance(payload, dict) else {})

    out: dict[str, Any] = {
        key: rec[key] for key in ("sender_name", "start", "end") if key in rec
    }

    description = pick_description(rec.get("description"), language)
    if description is not None:
        out["description"] = description

    tags = rec.get("tags")
    if tags is not None:
        out["tags"] = tags

    event = rec.get("event")
    if not event and isinstance(tags, list) and tags:
        event = str(tags[0])
    if event:
        out["event"] = event

    return out


def build_onecall(
    current: Any,
    *,
    minutely_pages: Any = (),
    hourly_pages: Any = (),
    daily_pages: Any = (),
    alerts: Any = (),
) -> dict[str, Any]:
    """Assemble the One Call 3.0 payload the rest of the integration reads."""
    cur_recs = records(current)
    cur = _strip(cur_recs[0]) if cur_recs else {}

    out: dict[str, Any] = {}
    for key in ("lat", "lon", "timezone", "timezone_offset"):
        for source in (current, hourly_pages, daily_pages, minutely_pages):
            candidates = source if isinstance(source, (list, tuple)) else (source,)
            found = next(
                (c[key] for c in candidates if isinstance(c, dict) and key in c),
                None,
            )
            if found is not None:
                out[key] = found
                break

    out["current"] = cur
    out["minutely"] = merge_pages(minutely_pages, WANT_MINUTES)
    out["hourly"] = merge_pages(hourly_pages, WANT_HOURS)
    out["daily"] = merge_pages(daily_pages, WANT_DAYS)

    # 3.0 omits ``alerts`` entirely when nothing is active; matching that keeps
    # the "is there an alert" test downstream identical for both versions.
    if alerts:
        out["alerts"] = list(alerts)
    return out
