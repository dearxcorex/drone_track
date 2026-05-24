# drone-detector

DJI DroneID decoder for NBTC Thailand. Decodes DJI's WiFi-beacon vendor IE
into drone GPS, pilot GPS, serial, and flight session UUID. Also decodes
ASTM F3411 / OpenDroneID frames, so it catches FAA-mandated RemoteID from
any compliant drone.

## Install (dev)

Clone with submodules (the OpenDroneID C library lives in `vendor/`):
```bash
git clone --recurse-submodules <repo>
cd drone_detector
uv pip install -e .
```

The install builds `libopendroneid` via CMake — make sure `cmake` is on
your `PATH` before running `uv pip install`.

For an existing clone that's missing the submodule:
```bash
git submodule update --init --recursive
uv pip install -e .
```

## Usage

Replay a captured `.pcap` (works on any OS):
```bash
uv run drone-detector replay capture.pcap --out detections.jsonl
```

Live capture with channel hopping (Linux only, requires monitor-mode
interface). `--hop` is ON by default:
```bash
sudo uv run drone-detector listen --iface wlan1 \
    --hop --channels 1,6,11,36,40,44,149,153,157,161 \
    --dwell-ms 200 \
    --reset-on-stall 20 \
    --out detections.jsonl
```

- `--no-hop` disables channel rotation (stays on whatever channel the
  adapter is already on).
- `--reset-on-stall N` brings the interface down/up after N consecutive
  empty hops to recover from driver wedges; `--reset-on-stall 0` disables
  this mitigation.

Version:
```bash
uv run drone-detector version
```

## Protocols supported

| Protocol | WiFi vendor IE OUI | Type byte | Notes |
|---|---|---|---|
| DJI DroneID v2 | `60:60:1F` | `0x09` | Most DJI consumer drones (Air 3S, Mavic 3, Mini 4 Pro) |
| ASTM F3411 / OpenDroneID | `FA:0B:BC` | `0x0D` | Parrot, Autel, ESP32-based modules, any FAA-mandated RemoteID over WiFi Beacon |

**Out of scope:** Bluetooth RemoteID (needs a BT5-capable sniffer), DJI
OcuSync (proprietary, needs SDR), WiFi NAN (rare).

## Hardware

- **Pi 5 + Tenda U10 (Realtek RTL8811CU)** is the tested combination.
  On Linux, install the `morrownr/8821cu-20210916` driver and put the
  adapter into monitor mode with:
  ```bash
  sudo ip link set wlan1 down
  sudo iw dev wlan1 set type monitor
  sudo ip link set wlan1 up
  ```
  Avoid `airmon-ng check kill` over SSH — it kills `wpa_supplicant`
  globally and drops the session if you're connected over WiFi.

## Field testing

DJI drones (**Air 3S, Mavic 3, Mini 4 Pro**) only broadcast RemoteID
when **motors are spinning** per DJI's FAA compliance implementation.

- Power-on + RC-linked is **not enough** — you must arm the drone
  outdoors.
- The drone parks DroneID on the current OcuSync video channel, which
  moves as the RC negotiates — that's why `--hop` matters.

## Docs

- Design spec: `docs/superpowers/specs/2026-05-23-drone-detector-design.md`
- DJI DroneID v2 byte layout: `docs/dji_droneid_v2_format.md`

## Test

```bash
uv run pytest --cov=drone_detector --cov-fail-under=80
uv run ruff check .
uv run mypy src
```

Smoke-test channel hopping on the Pi before a live capture session:
```bash
scripts/pi_hop_smoke.sh wlan1
```

This cycles through channels 1, 6, 11, 36, and 149 and verifies each
`iw dev info` report matches the requested channel. Catches driver-wedge
and regulatory-domain issues before you take the hardware to the field.
