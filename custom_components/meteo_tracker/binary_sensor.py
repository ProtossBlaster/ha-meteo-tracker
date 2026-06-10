"""Binary sensor platform: weather alerts and imminent precipitation."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import dt as dt_util

from . import MeteoTrackerConfigEntry
from .entity import MeteoTrackerEntity


def _alerts(d: dict) -> list[dict]:
    return (d.get("onecall") or {}).get("alerts") or []


def _alerts_on(d: dict) -> bool | None:
    if not d.get("onecall"):
        return None
    return bool(_alerts(d))


def _alerts_attrs(d: dict) -> dict[str, Any]:
    alerts = _alerts(d)
    return {
        "count": len(alerts),
        "alerts": [
            {
                "event": a.get("event"),
                "sender": a.get("sender_name"),
                "start": _iso(a.get("start")),
                "end": _iso(a.get("end")),
                "description": a.get("description"),
                "tags": a.get("tags"),
            }
            for a in alerts
        ],
    }


def _iso(ts: int | None) -> str | None:
    return dt_util.utc_from_timestamp(ts).isoformat() if ts is not None else None


def _precip_soon(d: dict) -> bool | None:
    onecall = d.get("onecall") or {}
    minutely = onecall.get("minutely") or []
    if minutely:
        return any((m.get("precipitation") or 0) > 0 for m in minutely)
    hourly = onecall.get("hourly") or []
    if hourly:
        pop = hourly[0].get("pop")
        return pop is not None and pop >= 0.5
    return None


@dataclass(frozen=True, kw_only=True)
class MeteoBinaryDescription(BinarySensorEntityDescription):
    """Binary sensor description with a value extractor and optional attrs."""

    value_fn: Callable[[dict], bool | None]
    attrs_fn: Callable[[dict], dict[str, Any]] | None = None


BINARY_SENSORS: tuple[MeteoBinaryDescription, ...] = (
    MeteoBinaryDescription(
        key="weather_alert",
        device_class=BinarySensorDeviceClass.SAFETY,
        value_fn=_alerts_on,
        attrs_fn=_alerts_attrs,
    ),
    MeteoBinaryDescription(
        key="precipitation_expected",
        icon="mdi:weather-pouring",
        value_fn=_precip_soon,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: MeteoTrackerConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Create the binary sensors for every tracked person."""
    coordinator = entry.runtime_data
    async_add_entities(
        MeteoTrackerBinarySensor(coordinator, tracker_id, description)
        for tracker_id in coordinator.trackers
        for description in BINARY_SENSORS
    )


class MeteoTrackerBinarySensor(MeteoTrackerEntity, BinarySensorEntity):
    """A per-person weather binary sensor."""

    entity_description: MeteoBinaryDescription

    def __init__(self, coordinator, tracker_id: str, description) -> None:
        super().__init__(coordinator, tracker_id)
        self.entity_description = description
        self._attr_translation_key = description.key
        self._attr_unique_id = (
            f"{coordinator.entry.entry_id}_{tracker_id}_{description.key}"
        )

    @property
    def is_on(self) -> bool | None:
        try:
            return self.entity_description.value_fn(self._tracker_data)
        except (TypeError, ValueError, IndexError, KeyError, AttributeError):
            return None

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        if self.entity_description.attrs_fn is None:
            return None
        try:
            return self.entity_description.attrs_fn(self._tracker_data)
        except (TypeError, ValueError, IndexError, KeyError, AttributeError):
            return None
