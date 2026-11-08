"""Polls the SENEC unit for all entities at once."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import SenecClient, SenecError
from .const import DOMAIN, SCAN_INTERVAL

_LOGGER = logging.getLogger(__name__)

type SenecConfigEntry = ConfigEntry[SenecCoordinator]


class SenecCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """One request every SCAN_INTERVAL, shared by every sensor."""

    config_entry: SenecConfigEntry

    def __init__(
        self, hass: HomeAssistant, entry: SenecConfigEntry, client: SenecClient
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=SCAN_INTERVAL,
        )
        self.client = client

    async def _async_update_data(self) -> dict[str, Any]:
        try:
            return await self.client.async_get_data()
        except SenecError as err:
            raise UpdateFailed(str(err)) from err
