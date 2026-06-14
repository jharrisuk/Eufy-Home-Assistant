#!/usr/bin/env bash
# Start the eufy -> go2rtc RTSP bridge. Serves rtsp://THIS_HOST:8554/eufy_garage (+ eufy_ch1/2/3) on demand.
cd "$(dirname "$0")"
exec ./bin/go2rtc -config go2rtc.yaml
