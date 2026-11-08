"""The sensors Home Assistant shows."""

from datetime import timedelta

import pytest
from freezegun.api import FrozenDateTimeFactory
from homeassistant.const import CONF_HOST, STATE_UNAVAILABLE
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    async_fire_time_changed,
)

from custom_components.senec_local.api import SenecError
from custom_components.senec_local.const import DOMAIN


async def _setup(hass):
    entry = MockConfigEntry(
        domain=DOMAIN, unique_id="20316761110462487540422709", data={CONF_HOST: "192.168.178.154"}
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


async def test_live_values(hass, mock_client):
    await _setup(hass)
    house = hass.states.get("sensor.senec_house_consumption")
    assert float(house.state) == pytest.approx(3063.41, abs=0.01)
    assert house.attributes["unit_of_measurement"] == "W"
    assert hass.states.get("sensor.senec_battery_charge").state == "1.0"
    state = hass.states.get("sensor.senec_system_state")
    assert state.state == "AKKU LEER"
    assert state.attributes["code"] == 15
    assert float(hass.states.get("sensor.senec_phase_l2_power").state) == pytest.approx(1903.93, abs=0.01)
    # Rarely needed details exist but start disabled.
    registry = er.async_get(hass)
    assert registry.async_get("sensor.senec_string_1_voltage").disabled_by is not None
    assert hass.states.get("sensor.senec_string_1_voltage") is None


async def test_energy_total(hass, mock_client, reply, freezer: FrozenDateTimeFactory):
    await _setup(hass)
    entity = "sensor.senec_grid_import_energy"
    assert float(hass.states.get(entity).state) == 0.0
    # 2768.25 W for 10 s = 0.00769 kWh.
    freezer.tick(timedelta(seconds=10))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert float(hass.states.get(entity).state) == pytest.approx(2768.25 * 10 / 3_600_000, abs=1e-4)
    assert hass.states.get(entity).attributes["state_class"] == "total_increasing"


async def test_unreachable_unit(hass, mock_client, freezer: FrozenDateTimeFactory):
    await _setup(hass)
    mock_client.side_effect = SenecError("gone")
    freezer.tick(timedelta(seconds=10))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert hass.states.get("sensor.senec_house_consumption").state == STATE_UNAVAILABLE
    # Totals keep their value instead of dropping out of the statistics.
    assert hass.states.get("sensor.senec_grid_import_energy").state != STATE_UNAVAILABLE


async def test_unload(hass, mock_client):
    entry = await _setup(hass)
    assert await hass.config_entries.async_unload(entry.entry_id)
