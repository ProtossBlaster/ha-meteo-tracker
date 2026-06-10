"""Button platform: a manual 'refresh now' button per tracked person."""

from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import MeteoTrackerConfigEntry
from .entity import MeteoTrackerEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: MeteoTrackerConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Create a refresh button for every tracked person."""
    coordinator = entry.runtime_data
    async_add_entities(
        MeteoTrackerRefreshButton(coordinator, tracker_id)
        for tracker_id in coordinator.trackers
    )


class MeteoTrackerRefreshButton(MeteoTrackerEntity, ButtonEntity):
    """Forces an immediate OpenWeather refresh (instead of waiting the interval)."""

    _attr_translation_key = "refresh"
    _attr_icon = "mdi:refresh"

    def __init__(self, coordinator, tracker_id: str) -> None:
        super().__init__(coordinator, tracker_id)
        self._attr_unique_id = (
            f"{coordinator.entry.entry_id}_{tracker_id}_refresh"
        )

    @property
    def available(self) -> bool:
        # Always pressable — so you can force a retry even when data is stale
        # or the last update failed.
        return True

    async def async_press(self) -> None:
        """Refresh all tracked people now (the coordinator is shared)."""
        await self.coordinator.async_request_refresh()
