"""DataUpdateCoordinator that polls go2rtc for the list of eufy_* streams.

The coordinator is the single source of truth for "which cameras exist and are
they reachable". The camera platform listens to it: when go2rtc gains a new
``eufy_*`` stream the coordinator picks it up and the platform adds a new camera
entity automatically — no YAML, no re-config.
"""
from __future__ import annotations

import logging
from typing import Any

from aiohttp import ClientError, ClientResponseError
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    API_STREAMS_PATH,
    CONF_API_PORT,
    CONF_HOST,
    DOMAIN,
    REQUEST_TIMEOUT,
    STREAM_PREFIX,
    UPDATE_INTERVAL,
)

_LOGGER = logging.getLogger(__name__)


class EufyNvrCoordinator(DataUpdateCoordinator[dict[str, dict[str, Any]]]):
    """Fetch and cache the set of eufy_* streams advertised by go2rtc.

    ``data`` is a mapping of ``{stream_name: stream_info}`` where ``stream_info``
    is the raw object go2rtc returns for that stream. Presence of a key means the
    stream exists; that is what camera availability is derived from.
    """

    config_entry: ConfigEntry

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialise the coordinator from a config entry."""
        self.host: str = entry.data[CONF_HOST]
        self.api_port: int = entry.data[CONF_API_PORT]
        self._session = async_get_clientsession(hass)
        self._url = f"http://{self.host}:{self.api_port}{API_STREAMS_PATH}"

        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN} ({self.host})",
            update_interval=UPDATE_INTERVAL,
            config_entry=entry,
        )

    async def _async_update_data(self) -> dict[str, dict[str, Any]]:
        """Query go2rtc and return only the eufy_* streams.

        Raises ``UpdateFailed`` on transport/HTTP/parse errors so HA marks every
        dependent entity unavailable until go2rtc is reachable again.
        """
        try:
            async with self._session.get(
                self._url, timeout=REQUEST_TIMEOUT
            ) as resp:
                resp.raise_for_status()
                payload = await resp.json(content_type=None)
        except ClientResponseError as err:
            raise UpdateFailed(
                f"go2rtc returned HTTP {err.status} from {self._url}"
            ) from err
        except (ClientError, TimeoutError) as err:
            raise UpdateFailed(
                f"Cannot reach go2rtc at {self._url}: {err}"
            ) from err
        except ValueError as err:  # invalid JSON
            raise UpdateFailed(
                f"go2rtc returned invalid JSON from {self._url}: {err}"
            ) from err

        # go2rtc's /api/streams returns a dict keyed by stream name. Some builds
        # wrap it as {"streams": {...}}; tolerate both shapes.
        if isinstance(payload, dict) and "streams" in payload and isinstance(
            payload["streams"], dict
        ):
            payload = payload["streams"]

        if not isinstance(payload, dict):
            raise UpdateFailed(
                f"Unexpected go2rtc /api/streams shape: {type(payload).__name__}"
            )

        streams: dict[str, dict[str, Any]] = {
            name: (info if isinstance(info, dict) else {})
            for name, info in payload.items()
            if isinstance(name, str) and name.startswith(STREAM_PREFIX)
        }

        _LOGGER.debug(
            "Discovered %d eufy stream(s) from %s: %s",
            len(streams),
            self._url,
            ", ".join(sorted(streams)) or "(none)",
        )
        return streams
