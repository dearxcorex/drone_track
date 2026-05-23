# DJI DroneID v2 — WiFi Beacon Vendor IE byte layout

This document is the implementation reference for `src/drone_detector/decoder/dji_droneid_v2.py`.

## Source

- Schiller et al., "Drone Security and the Mysterious Case of DJI's DroneID", WiSec 2023.
- `proto17/dji_droneid` (GitHub) — Python reference parser.
- `Alex-PK/DJI-DroneID-RID` — additional reverse-engineering notes.

## Outer wrapping (handled before we get the payload)

An 802.11 beacon contains Information Elements (IEs). Each IE is:

```
[Element ID = 0xDD (221, vendor-specific)] [Length] [OUI (3 bytes)] [OUI-type (1 byte)] [Payload ...]
```

The DJI DroneID IE has:
- OUI = `60:60:1F` (DJI)
- OUI-type = `0x09` (DroneID v2)

`extract_dji_ie()` (Task 4) returns the **Payload** bytes only.

## Payload layout (offsets are within the IE payload)

| Offset | Length | Field             | Type / Scale                       | Notes |
|-------:|-------:|-------------------|------------------------------------|-------|
| 0      | 1      | Frame type        | u8                                 | Always `0x10` for DroneID v2 telemetry. |
| 1      | 1      | Version           | u8                                 | Typically `0x00` or `0x01`. |
| 2      | 1      | Seq               | u8                                 | Sequence counter. |
| 3      | 1      | State flags       | u8                                 | Bit0: motors on. Bit2: takeoff done. |
| 4      | 1      | Serial length     | u8                                 | Almost always `0x40` (64). |
| 5      | N      | Serial (ASCII)    | bytes, null-padded                 | N = serial length. Decode as ASCII, strip nulls. |
| 5+N    | 4      | Drone lon         | int32 LE, scale × 1e7              | WGS84. |
| 5+N+4  | 4      | Drone lat         | int32 LE, scale × 1e7              | WGS84. |
| 5+N+8  | 2      | Altitude (takeoff)| int16 LE, scale × 10 → metres       | Signed. |
| 5+N+10 | 2      | Height (AGL baro) | int16 LE, scale × 10 → metres       | Signed. |
| 5+N+12 | 2      | Velocity N/S      | int16 LE, scale × 100 → m/s         | Positive = north. |
| 5+N+14 | 2      | Velocity E/W      | int16 LE, scale × 100 → m/s         | Positive = east. |
| 5+N+16 | 2      | Velocity U/D      | int16 LE, scale × 100 → m/s         | Positive = up. |
| 5+N+18 | 2      | Yaw               | int16 LE, scale × 100 → degrees     | 0..360. |
| 5+N+20 | 8      | Timestamp         | u64 LE, milliseconds                | DJI internal. Ignored in v1. |
| 5+N+28 | 4      | Pilot lat         | int32 LE, scale × 1e7              | `0` → unknown → emit None. |
| 5+N+32 | 4      | Pilot lon         | int32 LE, scale × 1e7              | `0` → unknown → emit None. |
| 5+N+36 | 4      | Home lat          | int32 LE, scale × 1e7              | `0` → unknown → emit None. |
| 5+N+40 | 4      | Home lon          | int32 LE, scale × 1e7              | `0` → unknown → emit None. |
| 5+N+44 | 1      | UUID length       | u8                                 | Often 8 or 16. |
| 5+N+45 | M      | UUID              | raw bytes                          | Emit as hex string. |

All multi-byte integers are little-endian.

## Conventions

- "Pilot/home unknown" pairs: parser converts `(lat=0, lon=0)` to `(None, None)`.
- Lengths smaller than expected: raise `MalformedDroneIDError` so the caller can drop the frame.
- Drone position is always returned as-is (drone won't broadcast without a GPS lock).
