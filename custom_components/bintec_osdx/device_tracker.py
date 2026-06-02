"""Device tracker: one ScannerEntity per associated WLAN client."""

from __future__ import annotations

from homeassistant.components.device_tracker import ScannerEntity, SourceType
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import BintecOsdxConfigEntry
from .const import DOMAIN
from .coordinator import BintecOsdxCoordinator
from .entity import BintecOsdxEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: BintecOsdxConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up trackers and add new ones as clients appear."""
    coordinator = entry.runtime_data
    tracked: set[str] = set()

    @callback
    def _discover() -> None:
        new = [
            BintecOsdxScannerEntity(coordinator, mac)
            for mac in coordinator.data["stations"]
            if mac not in tracked
        ]
        for entity in new:
            tracked.add(entity.mac_address)
        if new:
            async_add_entities(new)

    entry.async_on_unload(coordinator.async_add_listener(_discover))
    _discover()


class BintecOsdxScannerEntity(BintecOsdxEntity, ScannerEntity):
    """Presence of a single WLAN client (associated = home)."""

    _attr_has_entity_name = False

    def __init__(self, coordinator: BintecOsdxCoordinator, mac: str) -> None:
        super().__init__(coordinator)
        self._mac = mac
        self._attr_unique_id = f"{DOMAIN}_{mac}"
        self._attr_name = f"Bintec {mac}"

    @property
    def _station(self) -> dict | None:
        return self.coordinator.data["stations"].get(self._mac)

    @property
    def source_type(self) -> SourceType:
        return SourceType.ROUTER

    @property
    def is_connected(self) -> bool:
        return self._station is not None

    @property
    def mac_address(self) -> str:
        return self._mac

    @property
    def ip_address(self) -> str | None:
        station = self._station
        return station.get("ip") if station else None

    @property
    def extra_state_attributes(self) -> dict:
        station = self._station or {}
        return {
            "rssi": station.get("rssi"),
            "vap": station.get("vap"),
            "uptime": station.get("uptime"),
        }
