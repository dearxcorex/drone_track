# drone-detector

DJI DroneID decoder for NBTC Thailand. Decodes DJI's WiFi-beacon vendor IE
into drone GPS, pilot GPS, serial, and flight session UUID.

## Install (dev)

```bash
uv sync
```

## Usage

Replay a captured `.pcap` (works on any OS):
```bash
uv run drone-detector replay capture.pcap --out detections.jsonl
```

Live capture (Linux only, requires monitor-mode interface):
```bash
sudo uv run drone-detector listen --iface wlan0mon --out detections.jsonl
```

Channel hopping (separate terminal):
```bash
sudo uv run drone-detector hop --iface wlan0mon --channels 1,6,11,36,149
```

Version:
```bash
uv run drone-detector version
```

## Hardware

- Tenda U10 (Realtek RTL8811CU). On Linux, install the
  `morrownr/8821cu-20210916` driver and enable monitor mode with
  `sudo airmon-ng start wlan1`.

## Docs

- Design spec: `docs/superpowers/specs/2026-05-23-drone-detector-design.md`
- DJI DroneID v2 byte layout: `docs/dji_droneid_v2_format.md`

## Test

```bash
uv run pytest --cov
uv run ruff check .
uv run mypy src
```
