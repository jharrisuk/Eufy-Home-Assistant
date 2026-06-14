"""Camera entities that pull RTSP from the bridge's go2rtc."""
from __future__ import annotations

from homeassistant.components.camera import Camera, CameraEntityFeature
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import CONF_HOST, CONF_PORT, CONF_STREAMS, DOMAIN


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    host = entry.data[CONF_HOST]
    port = entry.data[CONF_PORT]
    names = [s.strip() for s in str(entry.data[CONF_STREAMS]).split(",") if s.strip()]
    async_add_entities(EufyNvrCamera(host, port, name) for name in names)


class EufyNvrCamera(Camera):
    _attr_supported_features = CameraEntityFeature.STREAM
    _attr_has_entity_name = False

    def __init__(self, host: str, port: int, stream: str) -> None:
        super().__init__()
        self._url = f"rtsp://{host}:{port}/{stream}"
        self._attr_name = stream.replace("_", " ").title()
        self._attr_unique_id = f"{DOMAIN}_{host}_{port}_{stream}"

    async def stream_source(self) -> str:
        return self._url

    async def async_camera_image(self, width=None, height=None):
        # grab a still from the RTSP stream via HA's bundled ffmpeg
        from homeassistant.components.ffmpeg import async_get_image

        return await async_get_image(self.hass, self._url, width=width, height=height)
