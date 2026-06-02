"""Shared base entity for Bintec OSDx."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, MANUFACTURER
from .coordinator import BintecOsdxCoordinator


class BintecOsdxEntity(CoordinatorEntity[BintecOsdxCoordinator]):
    """Base entity carrying the shared AP device info."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: BintecOsdxCoordinator) -> None:
        super().__init__(coordinator)
        host = coordinator.client.host
        status = (coordinator.data or {}).get("status", {})
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, host)},
            manufacturer=MANUFACTURER,
            name=f"Bintec AP ({host})",
            model="OSDx access point",
            sw_version=status.get("firmware"),
            serial_number=status.get("serial"),
            configuration_url=f"http://{host}",
        )
