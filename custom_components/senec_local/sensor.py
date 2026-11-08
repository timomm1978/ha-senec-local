"""Sensors for a SENEC unit: live values plus energy totals for the dashboard."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from homeassistant.components.sensor import (
    RestoreSensor,
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    PERCENTAGE,
    EntityCategory,
    UnitOfElectricCurrent,
    UnitOfElectricPotential,
    UnitOfEnergy,
    UnitOfFrequency,
    UnitOfPower,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util

from .const import DOMAIN, MANUFACTURER
from .coordinator import SenecConfigEntry, SenecCoordinator

# A gap longer than this (the unit was unreachable, Home Assistant was off)
# is not filled in: nobody knows what flowed meanwhile.
MAX_INTEGRATION_GAP_SECONDS = 300


@dataclass(frozen=True, kw_only=True)
class SenecSensorDescription(SensorEntityDescription):
    """A live value: `key` is the field in the coordinator data."""


def _power(key: str, **kwargs: Any) -> SenecSensorDescription:
    return SenecSensorDescription(
        key=key,
        translation_key=key,
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.WATT,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
        **kwargs,
    )


def _measure(key: str, kind: str, **kwargs: Any) -> SenecSensorDescription:
    device_class, unit, precision = {
        "voltage": (SensorDeviceClass.VOLTAGE, UnitOfElectricPotential.VOLT, 1),
        "current": (SensorDeviceClass.CURRENT, UnitOfElectricCurrent.AMPERE, 2),
        "temperature": (SensorDeviceClass.TEMPERATURE, UnitOfTemperature.CELSIUS, 1),
    }[kind]
    return SenecSensorDescription(
        key=key,
        translation_key=key,
        device_class=device_class,
        native_unit_of_measurement=unit,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=precision,
        **kwargs,
    )


DIAG = {"entity_category": EntityCategory.DIAGNOSTIC}
HIDDEN = {"entity_category": EntityCategory.DIAGNOSTIC, "entity_registry_enabled_default": False}

LIVE_SENSORS: tuple[SenecSensorDescription, ...] = (
    _power("house_power"),
    _power("solar_power"),
    _power("grid_power"),
    _power("grid_import_power"),
    _power("grid_export_power"),
    _power("battery_power"),
    _power("battery_charge_power"),
    _power("battery_discharge_power"),
    SenecSensorDescription(
        key="battery_soc",
        translation_key="battery_soc",
        device_class=SensorDeviceClass.BATTERY,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
    ),
    SenecSensorDescription(
        key="system_state",
        translation_key="system_state",
        icon="mdi:home-battery",
    ),
    _measure("battery_voltage", "voltage", **DIAG),
    _measure("battery_current", "current", **DIAG),
    SenecSensorDescription(
        key="grid_frequency",
        translation_key="grid_frequency",
        device_class=SensorDeviceClass.FREQUENCY,
        native_unit_of_measurement=UnitOfFrequency.HERTZ,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
        **DIAG,
    ),
    SenecSensorDescription(
        key="power_ratio",
        translation_key="power_ratio",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
        icon="mdi:solar-power-variant",
        **DIAG,
    ),
    _measure("battery_temperature", "temperature", **DIAG),
    _measure("case_temperature", "temperature", **DIAG),
    _measure("mcu_temperature", "temperature", **HIDDEN),
    *(_power(f"l{n}_power", **DIAG) for n in (1, 2, 3)),
    *(_measure(f"l{n}_voltage", "voltage", **HIDDEN) for n in (1, 2, 3)),
    *(_measure(f"l{n}_current", "current", **HIDDEN) for n in (1, 2, 3)),
    *(_power(f"mpp{n}_power", **DIAG) for n in (1, 2, 3)),
    *(_measure(f"mpp{n}_voltage", "voltage", **HIDDEN) for n in (1, 2, 3)),
    *(_measure(f"mpp{n}_current", "current", **HIDDEN) for n in (1, 2, 3)),
)

# Energy totals, added up from the matching power value. The unit keeps no
# totals of its own on this firmware.
ENERGY_SENSORS: dict[str, str] = {
    "solar_energy": "solar_power",
    "house_energy": "house_power",
    "grid_import_energy": "grid_import_power",
    "grid_export_energy": "grid_export_power",
    "battery_charge_energy": "battery_charge_power",
    "battery_discharge_energy": "battery_discharge_power",
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SenecConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    coordinator = entry.runtime_data
    data = coordinator.data
    # Only what this unit actually reports (e.g. fewer MPP trackers).
    entities: list[SensorEntity] = [
        SenecSensor(coordinator, description)
        for description in LIVE_SENSORS
        if data.get(description.key) is not None
    ]
    entities += [
        SenecEnergySensor(coordinator, key, source)
        for key, source in ENERGY_SENSORS.items()
        if data.get(source) is not None
    ]
    async_add_entities(entities)


class SenecEntity(CoordinatorEntity[SenecCoordinator]):
    _attr_has_entity_name = True

    def __init__(self, coordinator: SenecCoordinator, key: str) -> None:
        super().__init__(coordinator)
        entry = coordinator.config_entry
        serial = entry.unique_id or entry.entry_id
        self._attr_unique_id = f"{serial}_{key}"
        data = coordinator.data
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, serial)},
            manufacturer=MANUFACTURER,
            model="SENEC.Home",
            model_id=str(data.get("system_type")) if data.get("system_type") is not None else None,
            name="SENEC",
            serial_number=data.get("device_id"),
            sw_version=data.get("firmware"),
            configuration_url=f"https://{coordinator.client.host}/",
        )


class SenecSensor(SenecEntity, SensorEntity):
    entity_description: SenecSensorDescription

    def __init__(
        self, coordinator: SenecCoordinator, description: SenecSensorDescription
    ) -> None:
        super().__init__(coordinator, description.key)
        self.entity_description = description

    @property
    def native_value(self) -> Any:
        return self.coordinator.data.get(self.entity_description.key)

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        if self.entity_description.key == "system_state":
            return {"code": self.coordinator.data.get("system_state_code")}
        return None


class SenecEnergySensor(SenecEntity, RestoreSensor):
    """kWh total of a power value (trapezoidal rule), kept across restarts."""

    _attr_device_class = SensorDeviceClass.ENERGY
    _attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
    _attr_state_class = SensorStateClass.TOTAL_INCREASING
    _attr_suggested_display_precision = 2

    def __init__(self, coordinator: SenecCoordinator, key: str, source: str) -> None:
        super().__init__(coordinator, key)
        self._attr_translation_key = key
        self._source = source
        self._total = 0.0
        self._last_power: float | None = None
        self._last_time: datetime | None = None

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        if (last := await self.async_get_last_sensor_data()) is not None:
            try:
                self._total = float(last.native_value or 0)
            except (TypeError, ValueError):
                self._total = 0.0
        # The first poll happened before this entity existed: start from it.
        if (power := self.coordinator.data.get(self._source)) is not None:
            self._last_power, self._last_time = power, dt_util.utcnow()
        self._attr_native_value = round(self._total, 4)

    @callback
    def _handle_coordinator_update(self) -> None:
        power = self.coordinator.data.get(self._source)
        now = dt_util.utcnow()
        if power is None or not self.coordinator.last_update_success:
            # Unknown period: start over at the next good reading.
            self._last_power = self._last_time = None
        else:
            if self._last_power is not None and self._last_time is not None:
                seconds = (now - self._last_time).total_seconds()
                if 0 < seconds <= MAX_INTEGRATION_GAP_SECONDS:
                    average_watts = (self._last_power + power) / 2
                    self._total += max(average_watts, 0.0) * seconds / 3_600_000
            self._last_power, self._last_time = power, now
        self._attr_native_value = round(self._total, 4)
        super()._handle_coordinator_update()

    @property
    def available(self) -> bool:
        # A total stays meaningful while the unit is briefly unreachable.
        return True
