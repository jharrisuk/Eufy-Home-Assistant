#!/usr/bin/env python3
"""Generate go2rtc.yaml from auto-discovered cameras.json (run `python eufy_stream.py --discover` first).

Turns the discovered channel->name list into friendly, on-demand go2rtc streams, e.g.
  Garage (ch 0) -> stream "eufy_garage" -> rtsp://<bridge>:8554/eufy_garage
Also prints the block to paste into Home Assistant's /config/go2rtc.yaml (HA pulls from this bridge host).
"""
import json, os, re, sys

ROOT = os.path.dirname(os.path.abspath(__file__))   # bridge/
BRIDGE_IP = os.environ.get("BRIDGE_IP", sys.argv[1] if len(sys.argv) > 1 else "BRIDGE_IP")
cams = json.load(open(os.path.join(ROOT, "cameras.json")))

def slug(name, ch):
    s = re.sub(r"[^a-z0-9]+", "_", (name or f"ch{ch}").lower()).strip("_")
    return "eufy_" + (s or f"ch{ch}")

named = [(slug(c["name"], c["channel"]), c) for c in cams["cameras"]]

lines = [f'# Auto-generated from cameras.json (eufy NVR {cams.get("nvr_sn","")}). On-demand streams.', "streams:"]
for name, c in named:
    note = "  # offline at discovery" if c.get("status") == 0 else ""
    lines.append(f"  {name}: \"exec:python eufy_stream.py {c['channel']} --rtsp {{output}}\"{note}")
lines += ["", "rtsp:", '  listen: ":8554"', "", "api:", '  listen: ":1984"', "", "log:", "  level: info", ""]
open(os.path.join(ROOT, "go2rtc.yaml"), "w").write("\n".join(lines))
print("wrote", os.path.join(ROOT, "go2rtc.yaml"))

print("\n# --- paste into Home Assistant /config/go2rtc.yaml (set BRIDGE_IP) ---\nstreams:")
for name, c in named:
    print(f"  {name}:\n  - rtsp://{BRIDGE_IP}:8554/{name}")
