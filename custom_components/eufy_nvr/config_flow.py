"""Config flow for Eufy NVR (local).

The user supplies only where go2rtc lives (host + ports). Cameras are discovered
automatically afterwards by the coordinator — no channel names, no per-camera
entry. The flow validates that go2rtc's REST API answers before creating the
entry, so misconfiguration is caught immediately.
"""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
from aiohttp import ClientError
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import (
    API_STREAMS_PATH,
    CONF_API_PORT,
    CONF_HOST,
    CONF_RTSP_PORT,
    DEFAULT_API_PORT,
    DEFAULT_HOST,
    DEFAULT_RTSP_PORT,
    DOMAIN,
    REQUEST_TIMEOUT,
    STREAM_PREFIX,
)

_LOGGER = logging.getLogger(__name__)


async def _validate_go2rtc(hass, host: str, api_port: int) -> int:
    """Probe go2rtc's /api/streams. Return the eufy_* stream count.

    Raises ``CannotConnect`` if go2rtc cannot be reached or replies with an error.
    """
    session = async_get_clientsession(hass)
    url = f"http://{host}:{api_port}{API_STREAMS_PATH}"
    try:
        async with session.get(url, timeout=REQUEST_TIMEOUT) as resp:
            resp.raise_for_status()
            payload = await resp.json(content_type=None)
    except (ClientError, TimeoutError, ValueError) as err:
        _LOGGER.debug("go2rtc validation failed for %s: %s", url, err)
        raise CannotConnect from err

    if isinstance(payload, dict) and isinstance(payload.get("streams"), dict):
        payload = payload["streams"]
    if not isinstance(payload, dict):
        raise CannotConnect

    return sum(
        1 for name in payload if isinstance(name, str) and name.startswith(STREAM_PREFIX)
    )


def _schema(defaults: dict[str, Any]) -> vol.Schema:
    """Build the form schema with the given defaults."""
    return vol.Schema(
        {
            vol.Required(
                CONF_HOST, default=defaults.get(CONF_HOST, DEFAULT_HOST)
            ): str,
            vol.Required(
                CONF_API_PORT, default=defaults.get(CONF_API_PORT, DEFAULT_API_PORT)
            ): int,
            vol.Required(
                CONF_RTSP_PORT, default=defaults.get(CONF_RTSP_PORT, DEFAULT_RTSP_PORT)
            ): int,
        }
    )


class EufyNvrConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle the config + reconfigure flow."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Initial setup step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            host = user_input[CONF_HOST].strip()
            api_port = user_input[CONF_API_PORT]
            rtsp_port = user_input[CONF_RTSP_PORT]

            # One entry per go2rtc API endpoint.
            await self.async_set_unique_id(f"{host}:{api_port}")
            self._abort_if_unique_id_configured()

            try:
                count = await _validate_go2rtc(self.hass, host, api_port)
            except CannotConnect:
                errors["base"] = "cannot_connect"
            else:
                _LOGGER.debug("go2rtc at %s:%s exposes %d eufy stream(s)", host, api_port, count)
                return self.async_create_entry(
                    title=f"Eufy NVR ({host})",
                    data={
                        CONF_HOST: host,
                        CONF_API_PORT: api_port,
                        CONF_RTSP_PORT: rtsp_port,
                    },
                )

        return self.async_show_form(
            step_id="user",
            data_schema=_schema(user_input or {}),
            errors=errors,
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Allow editing host/ports of an existing entry."""
        entry = self._get_reconfigure_entry()
        errors: dict[str, str] = {}

        if user_input is not None:
            host = user_input[CONF_HOST].strip()
            api_port = user_input[CONF_API_PORT]
            try:
                await _validate_go2rtc(self.hass, host, api_port)
            except CannotConnect:
                errors["base"] = "cannot_connect"
            else:
                return self.async_update_reload_and_abort(
                    entry,
                    data_updates={
                        CONF_HOST: host,
                        CONF_API_PORT: api_port,
                        CONF_RTSP_PORT: user_input[CONF_RTSP_PORT],
                    },
                )

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=_schema(dict(entry.data)),
            errors=errors,
        )


class CannotConnect(Exception):
    """Raised when go2rtc's REST API is unreachable."""
