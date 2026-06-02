"""Sensors: AP health + connected-client counts."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from homeassistant.components.sensor import (
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import PERCENTAGE, EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import BintecOsdxConfigEntry
from .const import DOMAIN
from .entity import BintecOsdxEntity


@dataclass(frozen=True, kw_only=True)
class BintecSensorDescription(SensorEntityDescription):
    """Sensor description with a value extractor over coordinator data."""

    value_fn: Callable[[dict], int | str | None]


SENSORS: tuple[BintecSensorDescription, ...] = (
    BintecSensorDescription(
        key="cpu_percent",
        translation_key="cpu_percent",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:cpu-64-bit",
        value_fn=lambda data: data["status"].get("cpu_percent"),
    ),
    BintecSensorDescription(
        key="memory_percent",
        translation_key="memory_percent",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:memory",
        value_fn=lambda data: data["status"].get("memory_percent"),
    ),
    BintecSensorDescription(
        key="clients_total",
        translation_key="clients_total",
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:wifi",
        value_fn=lambda data: len(data["stations"]),
    ),
    BintecSensorDescription(
        key="uptime",
        translation_key="uptime",
        entity_category=EntityCategory.DIAGNOSTIC,
        icon="mdi:timer-outline",
        value_fn=lambda data: data["status"].get("uptime"),
    ),
    BintecSensorDescription(
        key="firmware",
        translation_key="firmware",
        entity_category=EntityCategory.DIAGNOSTIC,
        icon="mdi:chip",
        value_fn=lambda data: data["status"].get("firmware"),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: BintecOsdxConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator = entry.runtime_data
    async_add_entities(
        BintecOsdxSensor(coordinator, description) for description in SENSORS
    )


class BintecOsdxSensor(BintecOsdxEntity, SensorEntity):
    """A single AP sensor."""

    entity_description: BintecSensorDescription

    def __init__(self, coordinator, description: BintecSensorDescription) -> None:
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{DOMAIN}_{coordinator.client.host}_{description.key}"

    @property
    def native_value(self) -> int | str | None:
        return self.entity_description.value_fn(self.coordinator.data)

    @property
    def extra_state_attributes(self) -> dict | None:
        if self.entity_description.key == "clients_total":
            return {"radios": self.coordinator.data["status"].get("radios")}
        if self.entity_description.key == "memory_percent":
            return {"memory": self.coordinator.data["status"].get("memory")}
        return None
