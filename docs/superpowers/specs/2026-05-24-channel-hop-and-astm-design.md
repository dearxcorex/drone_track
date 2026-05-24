# Channel Hopping + ASTM F3411 Coverage — Design Spec

**Date:** 2026-05-24
**Status:** Approved (pending user review of this document)
**Prior spec:** `2026-05-23-drone-detector-design.md` (the original DJI DroneID v2 build)

## 1. Background

The v0.1.0 build (tagged) decodes DJI DroneID v2 from WiFi beacons (OUI `60:60:1F`, type `0x09`) and runs end-to-end on a Raspberry Pi with a Tenda U10 (RTL8811CU) adapter.

Field test against a DJI Air 3S on 2026-05-23 produced zero packets across all swept channels — both for DJI's OUI and for ASTM's `FA:0B:BC`. The legacy BLE scan also produced no RemoteID payload (only the QuickTransfer name advert).

Follow-up research found two distinct causes:

1. **DJI Air 3S only broadcasts RemoteID when motors are spinning.** Per DJI's FAA compliance FAQ: the drone must be "in flight (propellers turning)". Power-on alone produces nothing. The previous bench test never armed the drone, so zero packets was expected behavior, not a bug.
2. **DJI parks DroneID beacons on the current OcuSync video channel**, which moves. A single-channel listener misses the broadcast even when the drone is transmitting. Aggressive hopping across 2.4 GHz channels 1/6/11 and 5 GHz UNII-1/UNII-3 with ~200ms dwell is required.

Bluetooth is not a transport DJI uses on the Air 3S (or any modern DJI consumer drone since Mini 3 Pro). The BT line of investigation is closed.

## 2. Goals

- Detect DJI Air 3S and other modern DJI drones reliably during flight on the Pi
- Add ASTM F3411 (OpenDroneID) coverage so non-DJI drones (Parrot, Autel, ESP32-based modules) are also caught
- Preserve the existing replay/CLI/dedup pipeline — no rewrite of working code
- Maintain TDD discipline and the 80% coverage gate

## 3. Non-goals

- Bluetooth RemoteID support (separate effort; needs a BT5-capable USB dongle like Sonoff CC2652P + Sniffle)
- DJI OcuSync decoding (proprietary protocol; out of scope, needs SDR + reverse-engineered libraries like `proto17/dji_droneid`)
- WiFi NAN transport (rarely used in the wild; can be added later)
- A web UI (CLI + JSONL output remains the interface; downstream consumers can layer a UI)

## 4. Hardware

| Component | Detail |
|---|---|
| SBC | **Raspberry Pi 5** (8 GB recommended, 4 GB acceptable) |
| WiFi adapter | Tenda U10 (RTL8811CU, in-kernel `rtw88_8821cu` driver) — confirmed working in monitor mode |
| Dev machine | macOS — code only; tests run on the Pi |

The Pi 5's CPU and per-port USB controllers give ample headroom for one-process hopping + sniffing + decoding (<10% of one core expected).

## 5. Architecture

Single Python process with three threads inside the `listen` subcommand:

```
                    ┌─────────────────────┐
                    │   listen subcommand │
                    └──────────┬──────────┘
                               │
              ┌────────────────┼────────────────┐
              │                │                │
        ┌─────▼─────┐    ┌─────▼─────┐    ┌─────▼─────┐
        │  Hopper   │    │  Sniffer  │    │ Decoder + │
        │  thread   │    │  thread   │    │  Sinks    │
        │           │    │           │    │ (main)    │
        │ iw set    │    │ scapy     │    │           │
        │ channel @ │    │ Async-    │    │ frame →   │
        │ N ms      │    │ Sniffer   │    │ IE extract│
        │           │    │ → queue   │◄───┤ → parser  │
        └───────────┘    └─────┬─────┘    │ → report  │
                               │          │ → sinks   │
                               └──────────►           │
                                          └───────────┘
```

The hopper and sniffer share only the interface name. Communication is through a bounded thread-safe queue (drop-oldest on full). The main loop drains the queue, dispatches frames to the right protocol decoder, and fans reports out to sinks. Per-frame and per-sink exception isolation from the existing `pipeline.run_pipeline()` is preserved.

## 6. Components

### New modules

| Module | Purpose |
|---|---|
| `decoder/astm_f3411.py` | Wraps `libopendroneid.{so,dylib}` via `ctypes`. Exposes `parse_astm(payload, *, captured_at, rssi, raw_frame_hex) -> DroneReport`. Raises `MalformedAstmError`. |
| `decoder/registry.py` | Tiny dispatch: `{protocol_tag → parser fn}`. ~20 lines. Not a plugin system. |
| `capture/hopper.py` | `ChannelHopper(iface, channels, dwell_ms, set_channel_fn)` — daemon thread. Mock-injectable `set_channel_fn` for unit tests. |
| `capture/iw_backend.py` | Linux-only adapter: `subprocess.run(["iw", "dev", iface, "set", "channel", str(ch)])`. |
| `_lib/` (build artifact) | Holds the built `libopendroneid.{so,dylib}` produced during install. |

### Modified modules

| Module | Change |
|---|---|
| `decoder/ie_extract.py` | Walk IE list and match BOTH `(60:60:1F, 0x09)` → `"dji_v2"` AND `(FA:0B:BC, 0x0D)` → `"astm_f3411"`. Return `(protocol_tag, payload)` instead of bare bytes. |
| `models.py` | Rename `DroneIDReport` → `DroneReport`. Add `protocol: Literal["dji_v2", "astm_f3411"]`, `operator_id`, `astm_message_type`. Make DJI-only fields (`pilot_*`, `home_*`) nullable. |
| `cli.py` | `listen` gains `--hop / --no-hop` (default: hop), `--channels 1,6,11,36,40,44,149,153,157,161`, `--dwell-ms 200`. `hop` subcommand stays as a manual one-shot for debugging. |

### Build integration

- `vendor/opendroneid-core-c/` as git submodule, pinned to a tagged release
- `pyproject.toml` adds a `hatchling` custom build hook (the project already uses `hatchling.build`) that runs `cmake --build` and copies `libopendroneid.{so,dylib}` into `src/drone_detector/_lib/`
- `ctypes.CDLL` loads from the package-relative path — no system-wide install
- Builds on both macOS (`.dylib`) and Linux (`.so`)

## 7. Data model

```python
@dataclass(frozen=True)
class DroneReport:
    # Common
    captured_at: datetime          # UTC
    rssi: int | None               # dBm
    protocol: Literal["dji_v2", "astm_f3411"]
    raw_frame_hex: str

    # Identity
    drone_serial: str              # DJI: 16-byte serial; ASTM: Basic ID UAS ID
    operator_id: str | None        # ASTM Operator ID; None for DJI

    # Drone telemetry
    drone_lat: float | None
    drone_lon: float | None
    drone_altitude_m: float | None
    drone_height_m: float | None
    drone_speed_ns_mps: float | None
    drone_speed_ew_mps: float | None
    drone_speed_ud_mps: float | None
    drone_yaw_deg: float | None

    # Pilot / home (DJI only)
    pilot_lat: float | None
    pilot_lon: float | None
    home_lat: float | None
    home_lon: float | None

    # ASTM-specific
    astm_message_type: int | None   # 0=Basic ID, 1=Location, 2=Auth, 3=Self-ID, 4=System, 5=Operator, 0xF=Pack
    uuid_len: int | None
    uuid: str | None
```

Both specs report lat/lon/alt/speed/heading in compatible units, so they collapse into shared nullable fields. The `(0, 0)` → `(None, None)` "not yet acquired" convention from the v0.1.0 spec is preserved for both protocols.

## 8. Data flow (listen mode)

```
WiFi packet on ch N
   │
   ▼
[Sniffer thread] scapy AsyncSniffer
   │  (Dot11 frame + Radiotap header)
   ▼
Queue (bounded, drop-oldest on full)
   │
   ▼
[Main thread] decoder loop
   ├─► parse_radiotap() → rssi
   ├─► extract_ie(frame_body)
   │       ├─ (60:60:1F, 0x09)  → tag="dji_v2"
   │       ├─ (FA:0B:BC, 0x0D)  → tag="astm_f3411"
   │       └─ no match          → drop
   │
   ├─► registry.dispatch(tag)
   │       ├─ "dji_v2"      → parse_dji_droneid(payload, ...)
   │       └─ "astm_f3411"  → parse_astm(payload, ...)
   │
   ├─► DroneReport(protocol=tag, ...)
   │
   └─► for sink in sinks: sink.write(report)   # per-sink exception isolation
                                               # per-(serial, 5s) dedup
```

The hopper runs independently:

```
[Hopper thread] every dwell_ms:
   ch = next(channel_iter)
   set_channel_fn(iface, ch)   # iw dev wlan1 set channel <ch>
```

## 9. Channel hop strategy

| Setting | Default | Rationale |
|---|---|---|
| Channels | `[1, 6, 11, 36, 40, 44, 149, 153, 157, 161]` | DJI OcuSync parks on 2.4 GHz ch 1/6/11 at startup, moves to 5 GHz UNII-1/UNII-3 once linked |
| Dwell | 200 ms | DJI DroneID beacon interval is typically 600ms; 200ms dwell across 10 channels = 2s full sweep, catches at least one beacon per channel within ~3s |
| Both flags | Configurable via `--channels` and `--dwell-ms` | Allows narrowing to a known band during testing |

## 10. Error handling

| Layer | Failure mode | Behavior |
|---|---|---|
| Sniffer thread | scapy raises on malformed 802.11 frame | Catch, counter++, continue |
| IE extractor | Bytes shorter than declared length | Return `None`, drop packet |
| DJI parser | `MalformedDroneIDError` | Log at DEBUG, drop, counter++ |
| ASTM parser | `MalformedAstmError` | Log at DEBUG, drop, counter++ |
| Hopper thread | `iw` returns non-zero | Log at WARN, retry same channel next tick |
| Sink | Any exception | Caught per-sink, other sinks still receive the report |
| `libopendroneid` segfault | C-level memory bug | Cannot catch in Python — mitigated by strict input length check **before** the ctypes call, and by pinning the library to a tagged release |

### `libopendroneid` wrapping safety

- Pre-call length check against ASTM minimum frame size (25 bytes)
- All ctypes structures mirror the C structs by name, with field-by-field projection into `DroneReport` in Python
- No C pointers escape the wrapper function
- Library pinned to a tagged release, not master
- Byte-exact fixture tests pin the wrapper to known good inputs

### Library loader

```python
def _resolve_lib_path() -> str:
    pkg_lib = Path(__file__).parent.parent / "_lib"
    candidates = [pkg_lib / "libopendroneid.so", pkg_lib / "libopendroneid.dylib"]
    for p in candidates:
        if p.exists():
            return str(p)
    raise RuntimeError(
        "libopendroneid not found. Run `uv pip install -e .` to build the vendored C library."
    )
```

### Driver-wedge mitigation

The `rtw88_8821cu` driver occasionally stalls after rapid channel changes (observed during the v0.1.0 field test). The hopper exposes a `--reset-on-stall N` flag (default 20) that performs `ip link set down/up` after N consecutive empty hops. Set to 0 to disable.

## 11. CLI

| Command | Change |
|---|---|
| `drone-detector version` | unchanged |
| `drone-detector replay <pcap> [--jsonl <path>]` | unchanged (now emits unified `DroneReport`) |
| `drone-detector listen --iface <name>` | **new flags:** `--hop / --no-hop` (default hop), `--channels 1,6,11,36,40,44,149,153,157,161`, `--dwell-ms 200`, `--reset-on-stall 20` (0 to disable) |
| `drone-detector hop --iface <name> --channel <n>` | unchanged (one-shot manual channel set, useful for debugging) |

## 12. Testing

| Layer | Where | How |
|---|---|---|
| Unit (IE extractor, registry, hopper logic, ctypes wrapper, DroneReport mapping) | Mac edit → Pi run | `pytest` |
| Integration (PCAP replay → JSONL golden) | Mac edit → Pi run | `pytest` |
| End-to-end (live capture with Air 3S + motors armed) | Pi only | Manual `listen` invocation |
| Smoke (channel hop loop without packets, verify via `iw dev wlan1 info`) | Pi only | Shell script in `scripts/` |

### New fixtures

- `tests/fixtures/beacons/sample_astm_basic_id.bin` — hand-crafted ASTM Basic ID message
- `tests/fixtures/beacons/sample_astm_location.bin` — Location message
- `tests/fixtures/beacons/sample_astm_pack.bin` — Message Pack container
- `tests/fixtures/pcaps/mixed_protocols.pcap` — DJI + ASTM + plain beacon
- `tests/fixtures/golden/mixed_protocols.expected.jsonl` — expected JSONL output

### Coverage gate

- 80% on `src/drone_detector/**` (existing)
- `capture/iw_backend.py` excluded on macOS coverage runs (Linux-only); covered on Pi runs

### Validation milestone

Field test on the Pi with the Air 3S:

1. SSH to Pi, start `drone-detector listen --iface wlan1 --hop --channels 1,6,11,36,40,44,149,153,157,161`
2. Power on Air 3S + RC, **arm the drone (motors spinning)** outdoors
3. Confirm `DroneReport` with `protocol="dji_v2"` and a non-null serial appears in JSONL within ~2 seconds
4. Optional: borrow a Parrot Anafi or ESP32 ASTM transmitter to validate the `astm_f3411` path

## 13. Project layout (delta from v0.1.0)

```
drone_detector/
├── vendor/
│   └── opendroneid-core-c/          # NEW: git submodule
├── src/drone_detector/
│   ├── _lib/                        # NEW: built library artifacts
│   │   └── libopendroneid.{so,dylib}
│   ├── capture/                     # NEW package
│   │   ├── __init__.py
│   │   ├── hopper.py
│   │   └── iw_backend.py
│   ├── decoder/
│   │   ├── astm_f3411.py            # NEW
│   │   ├── registry.py              # NEW
│   │   ├── ie_extract.py            # MODIFIED
│   │   └── dji_droneid_v2.py        # unchanged
│   ├── models.py                    # MODIFIED (rename + new fields)
│   └── cli.py                       # MODIFIED (listen flags)
└── tests/
    ├── fixtures/
    │   ├── beacons/sample_astm_*.bin
    │   ├── pcaps/mixed_protocols.pcap
    │   └── golden/mixed_protocols.expected.jsonl
    └── test_astm_parser.py          # NEW
    └── test_hopper.py               # NEW
    └── test_registry.py             # NEW
```

## 14. Dev loop

- Mac: edit, `uv run pytest` for import-level sanity, commit locally (per memory: local commits OK, no push without permission)
- Pi: `git pull`, `uv pip install -e .` (rebuilds `libopendroneid`), `pytest`, then `listen`
- Optional tight iteration: `rsync --exclude .git src/ deardevx@192.168.0.128:~/drone_detector/src/`

## 15. References

- `opendroneid/opendroneid-core-c` — C library, Apache-2.0, the source of truth for ASTM F3411 parsing
- `opendroneid/receiver-android` — ground-truth oracle for cross-validation
- `opendroneid/wireshark-dissector` — offline pcap dissector for debugging
- `proto17/dji_droneid` — DJI DroneID reference (DJI v2 only, not used directly but consulted for spec corners)
- `alphafox02/droneid-go` — Go-based unified receiver for cross-checking
- ASTM F3411-22a-RID-B — the Remote ID standard
- DJI FAA Remote ID Compliance FAQ — "drone in flight, propellers turning" requirement
- SkySafe blog: *Drone Manufacturers Fail FAA Remote ID Requirements* — context on DJI's choices

## 16. Future extensions (out of scope)

- Bluetooth RemoteID (Sonoff CC2652P + Sniffle for BT5 Coded PHY)
- WiFi NAN transport
- DJI OcuSync decoding (SDR + `proto17/dji_droneid`)
- Multi-adapter parallel band scanning (Pi 5 has the headroom; saved as approach C from brainstorming)
- Map UI / web dashboard
