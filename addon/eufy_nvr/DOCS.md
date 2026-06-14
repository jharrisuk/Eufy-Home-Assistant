# Eufy NVR Local — Home Assistant add-on (experimental)

Runs the whole eufy WebRTC -> RTSP engine **on your Home Assistant host**, so you don't need a
separate always-on PC. It auto-discovers your NVR's cameras and serves them as RTSP/WebRTC via a
bundled, pinned go2rtc. No cloud media, no Frigate — only the signaling handshake touches eufy's
cloud; the video itself is pulled LAN-direct from the NVR.

> **Status: experimental / foundation.** Container + engine + auto-discovery + supervise/restart are
> production-grade. Two convenience pieces are still on the roadmap: (1) headless email/password login
> (v0.3 still needs a one-time token), and (2) a companion integration to auto-create the camera
> entities. See the repo roadmap.

## What it runs

- A Debian-based container (HA `*-base-debian:bookworm`) with python3 + aiortc/av/pycryptodome,
  nodejs (the libsctp WASM framing oracle), ffmpeg, and a pinned go2rtc.
- `run.sh` (bashio): builds `auth.json` from your options, auto-discovers cameras, generates
  `go2rtc.yaml`, then supervises go2rtc with restart-on-crash and capped backoff.

## Install

1. Home Assistant -> **Settings -> Add-ons -> Add-on Store -> ⋮ -> Repositories** -> add
   `https://github.com/HallyAus/Eufy-Home-Assistant` -> **Add**.
2. Find and install **Eufy NVR Local (experimental)**. (First build is slow: it compiles/links the
   WebRTC stack and downloads go2rtc.)
3. **Get a session token (one-time, until v0.4 headless login lands):** on any PC with Node + Chrome,
   from the repo run:
   ```
   cd bridge
   npm i playwright-core
   node get_auth.js
   ```
   Log into your eufy account in the window that opens and open the NVR live view once. This writes
   `bridge/auth.json` with `authToken`, `gtoken`, `userId` (your account id), and `stationSn`.
4. **Configuration tab** of the add-on — paste those four values and set `region`:
   - `auth_token`  <- `authToken`
   - `gtoken`      <- `gtoken`
   - `user_id`     <- `userId`
   - `station_sn`  <- `stationSn`
   - `region`      -> `US` or `EU`
   - `log_level`   -> `info` (raise to `debug` only when troubleshooting)

   Credentials are written to an in-container `auth.json` (chmod 600) and are never printed to the log.
5. **Start** the add-on and watch the **Log** tab. It discovers your cameras, generates the stream
   list, and starts go2rtc. Click **Open Web UI** (go2rtc on port 1984) to see/test the streams.

> The NVR allows **one** active live session and one signed-in app session at a time. Avoid running
> `get_auth.js` or the eufy app at the same moment the add-on is discovering/streaming.

## Use the cameras in Home Assistant

On the HA host the add-on serves:

- RTSP: `rtsp://127.0.0.1:8554/eufy_<camera>`
- go2rtc UI / API: `http://<ha-ip>:1984/`

Stream names are slugified from your camera names (e.g. "Garage" -> `eufy_garage`); the exact list is
printed in the add-on log and shown in the go2rtc UI. Until the companion integration lands, surface
them with either:

- **Generic Camera** integration -> *Stream Source* `rtsp://127.0.0.1:8554/eufy_garage` (one per camera), or
- add them to HA's own `/config/go2rtc.yaml` and reference from a `camera:` / WebRTC card.

Streams are **on-demand**: the engine only connects to the NVR while something is actually pulling a
stream, so the single live session is freed when nobody is watching.

## Ports

| Port      | Purpose                                                        |
|-----------|---------------------------------------------------------------|
| 8554/tcp  | RTSP — HA pulls cameras from here                             |
| 1984/tcp  | go2rtc API + web UI (also the Supervisor watchdog endpoint)   |
| 8555/tcp+udp | WebRTC candidates                                          |

The add-on runs with `host_network: true` (required: LAN-direct media to the NVR + same-host RTSP to
HA), so these ports are opened directly on the host.

## Reliability

- **Supervisor watchdog** polls `tcp://[HOST]:1984`; if go2rtc's API stops answering, the container
  is restarted automatically.
- **In-process supervise loop** in `run.sh` restarts go2rtc on a plain crash with exponential backoff
  (2s -> 60s cap), recovering faster than a full container bounce and without hammering the NVR.
- A Docker `HEALTHCHECK` hits the same API endpoint.

## Troubleshooting

- **"No auth_token set"** — fill in the Configuration tab (step 3–4).
- **"Discovery failed" / streams never start** — almost always an **expired session token**. Re-run
  `get_auth.js` and re-paste the four values. Also confirm `region` matches your account (US/EU) and
  `station_sn` is your NVR's serial.
- **`libsctp_*.wasm is missing` warning** — eufy bumped the libsctp version; the build's
  `fetch_deps.js` couldn't grab the matching worker files. Update the versions in
  `bridge/fetch_deps.js` + `bridge/sctp_oracle.js` and rebuild.
- **No video but discovery worked** — raise `log_level` to `debug`, restart, and check the log for the
  go2rtc `exec` line failing (python/ffmpeg/node path) or a non-200 from `ws/sign`.

## Notes

- This is independent interoperability work for **your own hardware**; not affiliated with Anker/eufy.
- Video is pulled LAN-direct; only the signaling token uses eufy's cloud.
