# Drone Detector — Design Spec

**Date:** 2026-05-23
**Author:** deardevx (NBTC Thailand)
**Status:** Approved for planning

## 1. Purpose

A Python tool that detects nearby DJI drones by decoding the DJI DroneID broadcast embedded in WiFi beacon frames, for use in NBTC Thailand spectrum / drone-operations enforcement.

Each detection yields drone serial, drone GPS position, altitude, velocity, pilot GPS position, home point, and flight session UUID — written to stdout in real time and appended to a JSONL evidence log.

## 2. Scope

### In scope (v1)

- Decode **DJI DroneID v2** broadcast in WiFi beacon vendor-specific IE (OUI `60:60:1F`, OUI-type `09`).
- Two capture modes:
  - **Live** capture from a monitor-mode WiFi interface (Linux only).
  - **Replay** of a `.pcap` file (cross-platform — primary dev mode on macOS).
- CLI tool with stdout output and JSONL log file output.
- Channel-hopping helper for covering both 2.4 GHz and 5 GHz bands.

### Out of scope (v1, explicit YAGNI)

- Web UI / map view
- Database storage (JSONL is enough)
- Bluetooth RemoteID
- ASTM F3411 over WiFi NaN or WiFi Beacon
- Multi-drone correlation / alerting / no-fly-zone enforcement
- Non-DJI drone protocols
- Authentication / multi-user features

## 3. Hardware & platform

- **WiFi adapter:** Tenda U10 (Realtek RTL8811CU chipset).
- **Capture host:** Linux (Raspberry Pi 4/5 or Ubuntu laptop) with `morrownr/8821cu-20210916` driver installed. macOS cannot do monitor mode with this chipset.
- **Dev host:** macOS — uses FilePcapSource for replay-based development and testing.
- **Python:** 3.11+, managed via `uv` (per user's global standard).

## 4. Architecture

Three clean layers communicating via Protocols, so any layer can be swapped without touching the others.

```
┌─────────────────────────────────────────────────────────────┐
│  CLI  (typer)                                               │
│  drone-detector listen --iface wlan0mon                     │
│  drone-detector replay capture.pcap                         │
└──────────────────────┬──────────────────────────────────────┘
                       │
        ┌──────────────┴──────────────┐
        │                             │
        ▼                             ▼
┌─────────────────┐          ┌─────────────────┐
│ Source layer    │          │ Sink layer      │
│ - LivePcapSource│          │ - StdoutSink    │
│ - FilePcapSource│          │ - JsonlFileSink │
│ (uses scapy)    │          │ (later: HTTP/DB)│
└────────┬────────┘          └────────▲────────┘
         │ raw 802.11 frames          │ DroneIDReport
         ▼                            │
┌─────────────────────────────────────┴───────┐
│ Decoder layer                                │
│ - WifiBeaconFilter (picks frames w/ DJI IE) │
│ - DjiDroneIdParser (binary → DroneIDReport) │
└──────────────────────────────────────────────┘
```

**Why this shape:**

- The Source abstraction lets us develop on macOS (FilePcapSource over a `.pcap`) and deploy on Linux (LivePcapSource over `wlan0mon`) with zero parser changes.
- The Decoder has zero I/O — pure functions taking `bytes → DroneIDReport`. Trivially unit-testable from fixture frames.
- The Sink abstraction is where v2 features (map UI, DB writes, NBTC alerts) plug in without touching anything else.

## 5. Data model

```python
from dataclasses import dataclass
from datetime import datetime

@dataclass(frozen=True)
class DroneIDReport:
    captured_at: datetime          # UTC, time we received the frame
    rssi: int | None               # signal strength from radiotap header (dBm)
    drone_serial: str              # DJI serial, e.g. "1581F..."
    drone_lat: float               # WGS84 decimal degrees
    drone_lon: float
    drone_altitude_m: float        # above takeoff point
    drone_height_m: float          # AGL barometric
    drone_speed_ns_mps: float      # north/south velocity, m/s
    drone_speed_ew_mps: float      # east/west velocity, m/s
    drone_speed_ud_mps: float      # up/down velocity, m/s
    drone_yaw_deg: float
    pilot_lat: float | None        # None if not yet acquired by the drone
    pilot_lon: float | None
    home_lat: float | None         # takeoff point
    home_lon: float | None
    uuid_len: int                  # DJI flight session UUID length
    uuid: str                      # flight session ID (hex)
    raw_frame_hex: str             # full frame hex, kept for forensic / NBTC evidence
```

## 6. Decoder pipeline (pure functions, no I/O)

1. **`extract_dji_ie(frame: bytes) -> bytes | None`**
   Walk the 802.11 beacon's Information Elements. Find the IE with OUI `60:60:1F` (DJI) and OUI-type `09` (DroneID v2). Return the payload, or `None` if absent.

2. **`parse_dji_droneid(ie_payload: bytes) -> DroneIDReport`**
   Binary-unpack per the published DJI DroneID v2 layout:
   - Frame header (state flags, version)
   - Serial (64 bytes, null-padded ASCII)
   - Lat/Lon int32 scaled by 1e7
   - Altitudes int16 scaled by 10
   - Velocities int16 scaled by 100
   - Yaw int16 scaled by 100
   - Pilot lat/lon int32 scaled by 1e7
   - Home lat/lon int32 scaled by 1e7
   - UUID length + UUID bytes
   All offsets/scales live in one module — `dji_droneid_v2.py` — with named constants, not magic numbers. The byte-level reference layout is documented in `docs/dji_droneid_v2_format.md`.

   **"Not yet acquired" convention:** DJI broadcasts `lat=0, lon=0` for `pilot` and `home` before the drone has a GPS lock on the pilot / before takeoff. The parser converts the exact pair `(0, 0)` to `None` for `pilot_lat/lon` and `home_lat/lon`. Drone position itself is always treated as real (drone won't broadcast at all without its own GPS lock).

3. **`parse_radiotap(packet) -> RadioTapMeta`**
   Pulls RSSI, channel, MCS from the radiotap header that scapy already parses.

**Error handling rule:** unrecognized or malformed IE → log at DEBUG, drop frame, never crash. The capture loop must survive bad frames indefinitely.

## 7. Sources and sinks

### Source Protocol

```python
from typing import Protocol, Iterator

class FrameSource(Protocol):
    def __iter__(self) -> Iterator["ScapyPacket"]: ...
    def close(self) -> None: ...
```

- **`LivePcapSource(iface: str)`** — uses `scapy.sendrecv.AsyncSniffer` on a monitor-mode interface (Linux only). Yields packets as they arrive. Clean shutdown on Ctrl+C.
- **`FilePcapSource(path: Path)`** — uses `scapy.utils.PcapReader` to stream a `.pcap` file frame-by-frame. Same interface as Live — the rest of the code can't tell the difference. Primary macOS dev mode.

### Sink Protocol

```python
class ReportSink(Protocol):
    def write(self, report: DroneIDReport) -> None: ...
    def close(self) -> None: ...
```

- **`StdoutSink`** — colored, one-line-per-drone via `rich`. Deduplicated by `(serial, 5-second bucket)` so a drone broadcasting at 2 Hz doesn't spam, but a stationary drone still produces a log line every 5 seconds to prove continued presence.
  Format: `HH:MM:SS  SERIAL  drone=(lat,lon) pilot=(lat,lon) RSSI=-XXdBm`
- **`JsonlFileSink(path)`** — appends one JSON object per detection. NBTC-grade evidence trail; same dedup window as stdout.
- Both sinks run simultaneously by default (stdout AND file).

## 8. CLI

```
drone-detector listen --iface wlan0mon [--out detections.jsonl] [--channels 1,6,11,36,149]
drone-detector replay PATH.pcap [--out detections.jsonl]
drone-detector hop --iface wlan0mon --channels 1,6,11,36,149 --dwell-ms 500
   # background helper that rotates the monitor interface through channels
drone-detector version
```

- `listen` and `replay` share the same pipeline (only the Source differs).
- `hop` is a separate utility because channel hopping uses `iw dev` (OS-level), not Python.
- Default channels: `1,6,11,36,149` (covers Thai DJI usage in both bands).
- Default JSONL output path: `./detections.jsonl`.

## 9. Project layout

```
drone_detector/
├── pyproject.toml              # uv-managed, Python 3.11+
├── README.md
├── src/drone_detector/
│   ├── __init__.py
│   ├── cli.py                  # typer entrypoint
│   ├── models.py               # DroneIDReport dataclass
│   ├── decoder/
│   │   ├── __init__.py
│   │   ├── dji_droneid_v2.py   # binary layout constants + parse_dji_droneid()
│   │   ├── ie_extract.py       # extract_dji_ie()
│   │   └── radiotap.py         # parse_radiotap()
│   ├── sources/
│   │   ├── __init__.py
│   │   ├── base.py             # FrameSource Protocol
│   │   ├── live_pcap.py        # LivePcapSource (Linux only)
│   │   └── file_pcap.py        # FilePcapSource (cross-platform)
│   ├── sinks/
│   │   ├── __init__.py
│   │   ├── base.py             # ReportSink Protocol
│   │   ├── stdout_sink.py
│   │   └── jsonl_sink.py
│   └── pipeline.py             # wires Source → decoder → Sink loop
├── tests/
│   ├── fixtures/
│   │   ├── beacons/            # raw .bin frames, one per case
│   │   └── pcaps/              # sample captures (sanitized)
│   ├── test_dji_droneid_v2.py  # offset-by-offset parser tests
│   ├── test_ie_extract.py
│   ├── test_file_source.py
│   ├── test_sinks.py
│   └── test_pipeline.py
└── docs/
    ├── superpowers/specs/2026-05-23-drone-detector-design.md
    └── dji_droneid_v2_format.md  # documented byte layout (our reference)
```

## 10. Dependencies

| Package | Purpose |
|---|---|
| `scapy` | 802.11 parsing, PCAP read, live sniffing |
| `typer` | CLI framework |
| `rich` | Colored stdout for StdoutSink |
| `pytest` + `pytest-cov` | Test runner & coverage |
| `ruff` + `mypy` | Lint & type-check |

All installed via `uv add` per the user's global Python convention.

## 11. Testing strategy

TDD throughout, per the superpowers stack.

- **Unit (fast, cross-platform):** every decoder function gets fixture-based tests. We commit small `.bin` files containing known-good DJI IE payloads with hand-checked expected `DroneIDReport` values. Coverage target ≥ 80%, decoder module at ~100%.
- **Integration (cross-platform):** `FilePcapSource → pipeline → JsonlFileSink` over a real sanitized PCAP, asserting JSONL output matches a golden file. To stay deterministic, the test injects a fixed clock (so `captured_at` is reproducible) and compares JSON object-by-object rather than byte-for-byte.
- **Live capture (Linux only):** smoke-test marked `@pytest.mark.live`. Confirms `LivePcapSource` doesn't crash on a short sniff of a dummy/test interface. Skipped on macOS.

## 12. Deployment notes

For the Linux capture host (RPi 4/5 or Ubuntu laptop):

1. Install Realtek driver: `morrownr/8821cu-20210916` (DKMS).
2. Put adapter in monitor mode: `sudo airmon-ng start wlan1` (creates `wlan1mon`).
3. Optionally start channel hopping in another terminal: `drone-detector hop --iface wlan1mon --channels 1,6,11,36,149`.
4. Run listener: `sudo drone-detector listen --iface wlan1mon --out /var/log/nbtc/detections.jsonl`.

Alternatively, set `CAP_NET_RAW` + `CAP_NET_ADMIN` capabilities on the Python interpreter to avoid `sudo`.

## 13. References

- Schiller et al., "Drone Security and the Mysterious Case of DJI's DroneID", WiSec 2023 — public reverse-engineering of DJI DroneID v2.
- `proto17/dji_droneid` (GitHub) — Python reference for byte layout. Used as a documentation source, not a runtime dependency.
- ASTM F3411-22a — RemoteID standard (out of scope for v1 but informs future extensions).

## 14. Future extensions (post-v1, not implemented now)

- Bluetooth 4/5 RemoteID via a separate BT dongle (new Source).
- ASTM F3411 over WiFi Beacon (new Decoder module, reuses Source).
- Web dashboard with map view (new Sink + small FastAPI server).
- SQLite or Postgres storage (new Sink).
- No-fly-zone alerts (new pipeline stage between decoder and sinks).
