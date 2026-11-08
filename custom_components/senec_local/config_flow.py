"""Set up a SENEC unit from the UI: enter its address, done."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import SenecClient, SenecError
from .const import DOMAIN

SCHEMA = vol.Schema({vol.Required(CONF_HOST): str})


class SenecConfigFlow(ConfigFlow, domain=DOMAIN):
    """Asks for the host and checks that a SENEC unit answers there."""

    VERSION = 1

    async def _probe(self, host: str) -> tuple[dict[str, Any] | None, dict[str, str]]:
        client = SenecClient(async_get_clientsession(self.hass, verify_ssl=False), host)
        try:
            return await client.async_get_data(), {}
        except SenecError:
            return None, {"base": "cannot_connect"}

    @staticmethod
    def _clean(host: str) -> str:
        # Accept a pasted "https://192.168.178.154/" as well.
        return host.strip().removeprefix("https://").removeprefix("http://").rstrip("/")

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            host = self._clean(user_input[CONF_HOST])
            data, errors = await self._probe(host)
            if data is not None:
                # The serial number identifies the unit, so a new IP address
                # does not create a second one.
                await self.async_set_unique_id(data.get("device_id") or host)
                self._abort_if_unique_id_configured(updates={CONF_HOST: host})
                return self.async_create_entry(title=f"SENEC {host}", data={CONF_HOST: host})
        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(SCHEMA, user_input),
            errors=errors,
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Change the address of a unit that is already set up."""
        entry = self._get_reconfigure_entry()
        errors: dict[str, str] = {}
        if user_input is not None:
            host = self._clean(user_input[CONF_HOST])
            data, errors = await self._probe(host)
            if data is not None:
                await self.async_set_unique_id(data.get("device_id") or host)
                self._abort_if_unique_id_mismatch(reason="wrong_device")
                return self.async_update_reload_and_abort(
                    entry, title=f"SENEC {host}", data_updates={CONF_HOST: host}
                )
        return self.async_show_form(
            step_id="reconfigure",
            data_schema=self.add_suggested_values_to_schema(
                SCHEMA, user_input or entry.data
            ),
            errors=errors,
        )
