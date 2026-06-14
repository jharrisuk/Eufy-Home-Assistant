"""Constants for the Eufy NVR (local) integration.

Cameras are auto-discovered from a go2rtc instance that the bridge/add-on runs.
The integration never talks to the eufy cloud or the NVR directly — it only reads
go2rtc's REST API to learn which ``eufy_*`` streams exist, then exposes each as a
Home Assistant camera that pulls ``rtsp://<host>:<rtsp_port>/<stream>``.
"""
from __future__ import annotations

from datetime import timedelta

DOMAIN = "eufy_nvr"

# --- config entry keys -------------------------------------------------------
CONF_HOST = "host"
CONF_API_PORT = "api_port"
CONF_RTSP_PORT = "rtsp_port"

# --- defaults ----------------------------------------------------------------
# 127.0.0.1 is the common case: the add-on runs on the same host as HA and uses
# host networking, so go2rtc is reachable on localhost.
DEFAULT_HOST = "127.0.0.1"
DEFAULT_API_PORT = 1984   # go2rtc REST API / web UI
DEFAULT_RTSP_PORT = 8554  # go2rtc RTSP server

# --- discovery ---------------------------------------------------------------
# Only streams whose name starts with this prefix are surfaced as cameras. The
# bridge names every NVR channel ``eufy_<camera>`` (see bridge/gen_go2rtc.py), so
# this cleanly ignores any unrelated streams a user may have added to go2rtc.
STREAM_PREFIX = "eufy_"

# go2rtc REST endpoint that lists all configured/active streams.
API_STREAMS_PATH = "/api/streams"

# How often the coordinator re-queries go2rtc so newly added cameras appear and
# availability is kept fresh. Cheap localhost call; 30s is responsive enough.
UPDATE_INTERVAL = timedelta(seconds=30)

# Network timeout for the go2rtc REST call.
REQUEST_TIMEOUT = 10

# DeviceInfo identity for the single "Eufy NVR" hub device the cameras hang off.
MANUFACTURER = "eufy"
MODEL = "PoE NVR (S4 / T8N00)"
DEVICE_NAME = "Eufy NVR"
