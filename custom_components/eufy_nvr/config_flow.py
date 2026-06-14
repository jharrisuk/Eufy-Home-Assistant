"""Config flow: ask for the bridge host + the go2rtc stream names."""
from __future__ import annotations

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult

from .const import (
    CONF_HOST,
    CONF_PORT,
    CONF_STREAMS,
    DEFAULT_PORT,
    DEFAULT_STREAMS,
    DOMAIN,
)


class EufyNvrConfigFlow(ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input=None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            host = user_input[CONF_HOST].strip()
            await self.async_set_unique_id(f"{host}:{user_input[CONF_PORT]}")
            self._abort_if_unique_id_configured()
            return self.async_create_entry(title=f"Eufy NVR ({host})", data=user_input)

        schema = vol.Schema(
            {
                vol.Required(CONF_HOST): str,  # IP/host of the machine running the bridge's go2rtc
                vol.Required(CONF_PORT, default=DEFAULT_PORT): int,
                vol.Required(CONF_STREAMS, default=DEFAULT_STREAMS): str,
            }
        )
        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)
