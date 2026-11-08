"""SENEC.Home storage systems, read over the local network."""

from __future__ import annotations

from homeassistant.const import CONF_HOST, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import SenecClient
from .coordinator import SenecConfigEntry, SenecCoordinator

PLATFORMS = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: SenecConfigEntry) -> bool:
    """Connect to the unit and set up its sensors."""
    # The unit's certificate is self-signed.
    session = async_get_clientsession(hass, verify_ssl=False)
    coordinator = SenecCoordinator(hass, entry, SenecClient(session, entry.data[CONF_HOST]))
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: SenecConfigEntry) -> bool:
    """Remove the sensors."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
