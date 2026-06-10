"""Shared base entity for all Meteo Tracker platforms."""

from __future__ import annotations

from typing import Any

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import ATTRIBUTION, DOMAIN, MANUFACTURER, MODEL
from .coordinator import MeteoTrackerCoordinator


class MeteoTrackerEntity(CoordinatorEntity[MeteoTrackerCoordinator]):
    """Base class binding an entity to a single tracked person (device_tracker)."""

    _attr_has_entity_name = True
    _attr_attribution = ATTRIBUTION

    def __init__(
        self, coordinator: MeteoTrackerCoordinator, tracker_id: str
    ) -> None:
        super().__init__(coordinator)
        self._tracker_id = tracker_id
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"{coordinator.entry.entry_id}_{tracker_id}")},
            name=self._tracker_data.get("name", tracker_id),
            manufacturer=MANUFACTURER,
            model=MODEL,
        )

    @property
    def _tracker_data(self) -> dict[str, Any]:
        """This person's slice of the coordinator payload (never ``None``)."""
        return self.coordinator.data.get("trackers", {}).get(self._tracker_id, {})

    @property
    def _onecall(self) -> dict[str, Any] | None:
        return self._tracker_data.get("onecall")

    @property
    def _air(self) -> dict[str, Any] | None:
        return self._tracker_data.get("air")

    @property
    def available(self) -> bool:
        return (
            super().available
            and bool(self._tracker_data.get("available"))
        )
