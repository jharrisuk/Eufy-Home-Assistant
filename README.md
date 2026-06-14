# Eufy S4 / PoE NVR → Home Assistant (local live video, no cloud media, no Frigate)

Pull a **local, LAN-direct live video stream** from a **eufy PoE NVR (S4 Max / model `T8N00`)** and its PoE
cameras into **Home Assistant** — as a standard RTSP/WebRTC stream you can drop straight onto a dashboard.

No eufy cloud relay for the video. No Frigate. No flashing the cameras. Just Home Assistant's built-in
**go2rtc** and a small bridge that speaks the NVR's (previously undocumented) WebRTC protocol.

> ⚠️ This is independent interoperability/reverse-engineering work for use with **your own** hardware. It is not
> affiliated with or endorsed by Anker/eufy. Use it on devices you own.

---

## TL;DR

```
eufy NVR  ──WebRTC (DTLS/SCTP, LAN-direct)──►  bridge (this repo)  ──RTSP──►  Home Assistant (go2rtc)
192.168.1.152                                  Python + Node + ffmpeg + go2rtc          dashboard / cameras
```

1. Run the **bridge** on any always-on machine on your LAN (Windows or Linux) that has Python, Node and ffmpeg.
2. It serves `rtsp://<bridge-ip>:8554/eufy_garage` (and `eufy_ch1/2/3`).
3. Point Home Assistant at those RTSP URLs (via go2rtc or the Generic Camera integration). Done.

Live 1080p H.265, ~15–25 fps, pulled **directly over your LAN** (the only thing that touches eufy's cloud is a
one-time session token for signaling — the pixels never leave your network).

---

## Why this exists — what we found

The eufy S4 generation was widely assumed to use the classic eufy/ThroughTek **P2P** transport (the AES-128-ECB
"start livestream" path that [bropat/eufy-security-client](https://github.com/bropat/eufy-security-client) and the
[fuatakgun/eufy-security](https://github.com/fuatakgun/eufy-security) HACS integration implement). **It doesn't.**

We captured the official web client (`security.eufy.com` / `nvr.eufy.com`) and reversed the protocol. The findings:

1. **It's WebRTC, not P2P.** The NVR's cloud provisioning has empty `p2p_conn`/`app_conn` and instead lists
   `signaling_servers` + `webrtc_sdk_version`. bropat/eufy-security-client has **no** WebRTC support, which is
   exactly why this NVR is "experimental"/non-working there.
2. **Signaling is cloud, media is local.** A small JSON handshake over a cloud WebSocket
   (`security-smart.eufylife.com`) exchanges SDP/ICE. The winning ICE pair is your host ↔ the NVR's LAN IP
   (`192.168.1.152 typ host`) — **media flows LAN-direct over DTLS/SCTP**, not through eufy's TURN relay.
3. **There is an extra framing layer.** The 6 WebRTC DataChannels carry an *inner* eufy reliable transport
   (magic `"PTCS"`, with FEC + retransmission) implemented in a WebAssembly module (`libsctp`,
   `sctp_frame_manager_web.c`). App messages are wrapped in a 16-byte `XZYH` header and fragmented into PTCS
   packets. We run eufy's **exact WASM** as a framing oracle (in Node) so we don't have to reimplement FEC.
4. **`openLive` is a red herring; `startStream` is the trigger.** The command that *returns camera params*
   (`cmd 1103`) does **not** start video. Live video only begins after a separate **`startStream` command
   (`cmd 1003`)** with a `chn_list` payload. This single fact was the whole ballgame.
5. **Video = H.265.** Each video DataChannel message is `[16-byte XZYH header][22-byte media header][Annex-B
   HEVC NAL]`. Strip 38 bytes → a clean H.265 elementary stream (VPS/SPS/PPS/IDR + P-frames, 1080p).

Full technical write-up: [`docs/PROTOCOL.md`](docs/PROTOCOL.md).

---

## Architecture

The heavy lifting (WebRTC + DTLS + the libsctp WASM + H.265 extraction) runs in the **bridge**. It needs Python,
Node and ffmpeg, so it runs on a normal machine on your LAN — **not** inside Home Assistant OS (which can't run
those). The bridge exposes plain RTSP via a local **go2rtc**; Home Assistant simply pulls it.

```
                         ┌──────────────────── bridge host (a PC/NUC on the LAN) ───────────────────┐
 eufy NVR  WebRTC        │  eufy_stream.py (aiortc)  ──►  sctp_oracle.js (eufy libsctp WASM, Node)  │
 T8N00 ───────────────►  │        │  startStream cmd 1003 + heartbeat                                │
 (LAN-direct DTLS/SCTP)  │        ▼  H.265 Annex-B                                                    │
                         │     ffmpeg ──►  go2rtc ──►  rtsp://<bridge>:8554/eufy_garage (+ ch1/2/3)   │
                         └─────────────────────────────────────────────────────────────────────────┘
                                                       │ RTSP pull (LAN)
                                                       ▼
                              Home Assistant (built-in go2rtc)  ──►  WebRTC/HLS on your dashboard
```

**On-demand:** go2rtc only spawns the bridge while something is actually watching, so the NVR's single live
session isn't held 24/7 (important — the NVR allows one active stream at a time).

---

## Requirements

On the **bridge host** (Windows or Linux, always-on, same LAN as the NVR):
- **Python 3.11+** with `aiortc av websockets aiohttp pycryptodome` (see `bridge/requirements.txt`)
- **Node 18+** (runs the libsctp WASM oracle)
- **ffmpeg** and **go2rtc** (the included `bridge/fetch_deps` script downloads both, plus eufy's WASM)
- A **eufy account** that owns the NVR (for the one-time cloud signaling token)

On the **Home Assistant** side: HA 2024.11+ (ships with go2rtc). Nothing else — **Frigate is not required.**

---

## Install

### 1) Set up the bridge

```bash
git clone https://github.com/HallyAus/Eufy-Home-Assistant
cd Eufy-Home-Assistant/bridge

pip install -r requirements.txt        # Python deps (aiortc, etc.)
node fetch_deps.js                     # downloads ffmpeg, go2rtc, and eufy's libsctp WASM (from eufy's CDN)
node get_auth.js                       # one-time: log into the eufy web portal -> writes auth.json (gitignored)
```

Edit `go2rtc.yaml` if your NVR isn't `192.168.1.152` or you want different channel names, then start it:

```bash
# Windows:  start_bridge.cmd          Linux:  ./start_bridge.sh
```

Verify locally (any RTSP player):
```bash
ffplay rtsp://127.0.0.1:8554/eufy_garage
```

### 2) Wire it into Home Assistant (no Frigate)

Pick whichever you prefer — both use HA's built-in go2rtc/camera stack:

**A. Add the streams to HA's go2rtc** (`/config/go2rtc.yaml`):
```yaml
streams:
  eufy_garage:  [ rtsp://BRIDGE_IP:8554/eufy_garage ]
  eufy_front:   [ rtsp://BRIDGE_IP:8554/eufy_ch1 ]
  # ...one line per camera...
```
Reload go2rtc, then **Settings → Devices & Services → Add Integration → Generic Camera** → Stream Source:
`rtsp://BRIDGE_IP:8554/eufy_garage`. You get low-latency WebRTC live view on dashboards out of the box.

**B. HACS (optional convenience integration):** add this repo as a custom repository in HACS (type: Integration),
install **Eufy NVR**, and enter your bridge's IP — it creates the camera entities for all channels for you. (The
bridge from step 1 still does the actual streaming; the integration just wires up the entities.)

---

## "I'm not a fan of Frigate" — you don't need it

The bridge emits **standard RTSP / H.265**, so any of these work with zero extra infrastructure:

- **Home Assistant native (recommended):** built-in **go2rtc** gives you sub-second WebRTC live view on
  dashboards — no add-ons, no NVR software.
- **HA Generic Camera** integration (RTSP) for a simple camera entity.
- **Recording / events (only if you want them):** [Scrypted](https://github.com/koush/scrypted),
  [Blue Iris](https://blueirissoftware.com/), [MediaMTX](https://github.com/bluenviron/mediamtx), or go2rtc
  itself. Frigate is *one* option, not a requirement.
- **Anything that speaks RTSP** (VLC, ffmpeg, a browser via go2rtc's WebRTC).

---

## Status & roadmap

**Working today:** LAN-direct connect, `startStream`, libsctp reassembly, H.265 extraction, sustained ~18–25 fps
1080p, served as RTSP via go2rtc. Channels 0–3.

**Roadmap:**
- [ ] Replace the browser-based auth (`get_auth.js`) with a pure-Python eufy login (email/password → token), so the
      bridge is fully headless.
- [ ] Audio (`1301`) and two-way talk.
- [ ] Package the bridge as a **Home Assistant add-on** (Docker) so it can run on the HA host itself (no separate
      machine) — the cleanest end-state for HAOS users.
- [ ] Auto-reconnect/keep-alive hardening; per-camera substream/quality selection (`streamtype`).

## Notes / limits

- The NVR allows **one** active live session; rapid reconnects can briefly put it into a timeout state. The
  on-demand design avoids holding the session when nobody's watching.
- Signaling needs a eufy cloud session token; the **video itself is LAN-local**.
- Your eufy credentials and session tokens are **gitignored** — never commit them.

## Credits

Protocol reversed from the official eufy web client. Built with
[aiortc](https://github.com/aiortc/aiortc), [go2rtc](https://github.com/AlexxIT/go2rtc), ffmpeg, and eufy's own
`libsctp` WASM (loaded at runtime from eufy's CDN, not redistributed here).
