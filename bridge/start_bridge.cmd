@echo off
REM Start the eufy -> go2rtc RTSP bridge. Serves rtsp://THIS_HOST:8554/eufy_garage (+ eufy_ch1/2/3) on demand.
cd /d %~dp0
bin\go2rtc.exe -config go2rtc.yaml
