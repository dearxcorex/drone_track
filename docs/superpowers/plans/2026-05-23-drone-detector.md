# Drone Detector Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.
>
> **User policy reminder (from `~/.claude/CLAUDE.md`):** Do NOT push to GitHub without explicit user permission. Local `git commit` steps in this plan are fine to run, but never `git push`.

**Goal:** Build a Python CLI that decodes DJI DroneID broadcasts from WiFi beacon frames (live monitor-mode on Linux, or replay from a `.pcap` on any OS) and writes one detection per drone every 5 seconds to stdout and a JSONL evidence log.

**Architecture:** Three layers wired through Protocols — `Source` (live or file PCAP) → `Decoder` (pure functions over bytes) → `Sink` (stdout and JSONL). Source/Sink abstractions let macOS run the parser/tests against PCAPs while the real capture runs on Linux with the Tenda U10.

**Tech Stack:** Python 3.11+, uv, scapy, typer, rich, pytest, pytest-cov, ruff, mypy.

**Spec:** `docs/superpowers/specs/2026-05-23-drone-detector-design.md`

---

## Task 1: Project scaffolding

**Files:**
- Create: `pyproject.toml`
- Create: `README.md`
- Create: `.gitignore`
- Create: `src/drone_detector/__init__.py`
- Create: `tests/__init__.py`
- Create: `tests/conftest.py`

- [ ] **Step 1: Initialize git repo**

Run:
```bash
cd /Users/deardevx/Documents/my_stufF/fun/drone_detector
git init
git branch -M main
```

- [ ] **Step 2: Initialize uv project**

Run:
```bash
uv init --package --name drone-detector --python 3.11
```

This creates `pyproject.toml`, `src/drone_detector/`, and a `.python-version` file.

- [ ] **Step 3: Add runtime and dev dependencies**

Run:
```bash
uv add scapy typer rich
uv add --dev pytest pytest-cov ruff mypy
```

- [ ] **Step 4: Configure pytest, ruff, mypy, and coverage**

Edit `pyproject.toml` and append:

```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
addopts = "-ra --strict-markers"
markers = [
    "live: requires a real monitor-mode WiFi interface (Linux only)",
]

[tool.coverage.run]
source = ["src/drone_detector"]
branch = true

[tool.coverage.report]
fail_under = 80
show_missing = true
skip_covered = false

[tool.ruff]
line-length = 100
target-version = "py311"

[tool.ruff.lint]
select = ["E", "F", "I", "B", "UP"]

[tool.mypy]
python_version = "3.11"
strict = true
ignore_missing_imports = true   # scapy has no stubs
```

- [ ] **Step 5: Write `.gitignore`**

Create `.gitignore`:
```
.venv/
__pycache__/
*.pyc
.pytest_cache/
.coverage
htmlcov/
.ruff_cache/
.mypy_cache/
detections.jsonl
*.pcap
!tests/fixtures/pcaps/*.pcap
```

- [ ] **Step 6: Write `README.md` placeholder**

Create `README.md`:
```markdown
# drone-detector

DJI DroneID decoder for NBTC Thailand. Decodes DJI's WiFi beacon vendor IE
into drone GPS, pilot GPS, serial, and flight session UUID.

See `docs/superpowers/specs/2026-05-23-drone-detector-design.md` for the design.
```

- [ ] **Step 7: Create empty test scaffolding**

Create `tests/__init__.py` (empty file).
Create `tests/conftest.py`:
```python
from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def fixtures_dir() -> Path:
    return FIXTURES
```

- [ ] **Step 8: Verify tooling works**

Run:
```bash
uv run pytest -v
uv run ruff check .
uv run mypy src
```

Expected: pytest reports "no tests ran", ruff and mypy pass (no files to check).

- [ ] **Step 9: Commit**

```bash
git add .
git commit -m "chore: project scaffolding with uv, pytest, ruff, mypy"
```

---

## Task 2: `DroneIDReport` dataclass

**Files:**
- Create: `src/drone_detector/models.py`
- Create: `tests/test_models.py`

- [ ] **Step 1: Write failing test**

Create `tests/test_models.py`:
```python
from datetime import datetime, timezone

from drone_detector.models import DroneIDReport


def test_drone_id_report_is_frozen_and_holds_all_fields() -> None:
    report = DroneIDReport(
        captured_at=datetime(2026, 5, 23, 10, 0, 0, tzinfo=timezone.utc),
        rssi=-62,
        drone_serial="1581F5ABCDEF1234567890",
        drone_lat=13.7563,
        drone_lon=100.5018,
        drone_altitude_m=120.0,
        drone_height_m=45.5,
        drone_speed_ns_mps=1.2,
        drone_speed_ew_mps=-0.4,
        drone_speed_ud_mps=0.0,
        drone_yaw_deg=87.5,
        pilot_lat=13.7560,
        pilot_lon=100.5020,
        home_lat=13.7560,
        home_lon=100.5020,
        uuid_len=8,
        uuid="0102030405060708",
        raw_frame_hex="dead",
    )
    assert report.drone_serial == "1581F5ABCDEF1234567890"
    # frozen dataclass should reject mutation
    import dataclasses
    assert dataclasses.is_dataclass(report)
    try:
        report.drone_serial = "x"  # type: ignore[misc]
    except dataclasses.FrozenInstanceError:
        pass
    else:
        raise AssertionError("DroneIDReport must be frozen")


def test_pilot_and_home_default_to_none() -> None:
    report = DroneIDReport(
        captured_at=datetime(2026, 5, 23, 10, 0, 0, tzinfo=timezone.utc),
        rssi=None,
        drone_serial="X",
        drone_lat=0.0, drone_lon=0.0,
        drone_altitude_m=0.0, drone_height_m=0.0,
        drone_speed_ns_mps=0.0, drone_speed_ew_mps=0.0, drone_speed_ud_mps=0.0,
        drone_yaw_deg=0.0,
        pilot_lat=None, pilot_lon=None,
        home_lat=None, home_lon=None,
        uuid_len=0, uuid="",
        raw_frame_hex="",
    )
    assert report.pilot_lat is None
    assert report.home_lon is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_models.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'drone_detector.models'`.

- [ ] **Step 3: Implement `DroneIDReport`**

Create `src/drone_detector/models.py`:
```python
from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class DroneIDReport:
    captured_at: datetime
    rssi: int | None
    drone_serial: str
    drone_lat: float
    drone_lon: float
    drone_altitude_m: float
    drone_height_m: float
    drone_speed_ns_mps: float
    drone_speed_ew_mps: float
    drone_speed_ud_mps: float
    drone_yaw_deg: float
    pilot_lat: float | None
    pilot_lon: float | None
    home_lat: float | None
    home_lon: float | None
    uuid_len: int
    uuid: str
    raw_frame_hex: str
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_models.py -v`
Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
git add src/drone_detector/models.py tests/test_models.py
git commit -m "feat(models): add DroneIDReport frozen dataclass"
```

---

## Task 3: Document the DJI DroneID v2 byte layout

This is a docs-only task. The parser in Task 5 is implemented against this document, so the document is the single source of truth for byte offsets, scales, and field meanings. Writing it before the parser forces clarity.

**Files:**
- Create: `docs/dji_droneid_v2_format.md`

- [ ] **Step 1: Write the reference document**

Create `docs/dji_droneid_v2_format.md`:
```markdown
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
```

- [ ] **Step 2: Commit**

```bash
git add docs/dji_droneid_v2_format.md
git commit -m "docs: document DJI DroneID v2 byte layout"
```

---

## Task 4: IE extraction (`extract_dji_ie`)

**Files:**
- Create: `src/drone_detector/decoder/__init__.py`
- Create: `src/drone_detector/decoder/ie_extract.py`
- Create: `tests/decoder/__init__.py`
- Create: `tests/decoder/test_ie_extract.py`

- [ ] **Step 1: Write failing test**

Create `tests/decoder/__init__.py` (empty).
Create `tests/decoder/test_ie_extract.py`:
```python
from drone_detector.decoder.ie_extract import extract_dji_ie


def _build_ie(oui: bytes, oui_type: int, payload: bytes) -> bytes:
    body = oui + bytes([oui_type]) + payload
    return bytes([0xDD, len(body)]) + body


def test_extracts_payload_from_dji_droneid_ie() -> None:
    payload = bytes(range(20))
    frame = b"\x00\x01\x02" + _build_ie(b"\x60\x60\x1F", 0x09, payload) + b"\xFF\xFF"
    assert extract_dji_ie(frame) == payload


def test_returns_none_when_no_dji_ie_present() -> None:
    frame = _build_ie(b"\x00\x50\xF2", 0x04, b"\x01\x02")  # Microsoft WPS, not DJI
    assert extract_dji_ie(frame) is None


def test_skips_non_vendor_ies_and_finds_dji() -> None:
    ssid_ie = bytes([0x00, 4]) + b"test"
    rates_ie = bytes([0x01, 2]) + b"\x82\x84"
    dji = _build_ie(b"\x60\x60\x1F", 0x09, b"\xAA\xBB")
    frame = ssid_ie + rates_ie + dji
    assert extract_dji_ie(frame) == b"\xAA\xBB"


def test_returns_none_on_truncated_ie() -> None:
    # Length byte says 10 but only 2 bytes follow
    frame = bytes([0xDD, 10, 0x60, 0x60])
    assert extract_dji_ie(frame) is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/decoder/test_ie_extract.py -v`
Expected: FAIL — module not found.

- [ ] **Step 3: Implement**

Create `src/drone_detector/decoder/__init__.py` (empty).
Create `src/drone_detector/decoder/ie_extract.py`:
```python
"""Extract the DJI DroneID v2 vendor-specific IE payload from an 802.11 frame body."""

DJI_OUI = b"\x60\x60\x1F"
DJI_DRONEID_V2_OUI_TYPE = 0x09
VENDOR_SPECIFIC_ELEMENT_ID = 0xDD


def extract_dji_ie(frame_body: bytes) -> bytes | None:
    """Walk the IE list in `frame_body`; return the DJI DroneID payload or None."""
    i = 0
    n = len(frame_body)
    while i + 2 <= n:
        element_id = frame_body[i]
        length = frame_body[i + 1]
        start = i + 2
        end = start + length
        if end > n:
            return None  # truncated
        if element_id == VENDOR_SPECIFIC_ELEMENT_ID and length >= 4:
            oui = frame_body[start : start + 3]
            oui_type = frame_body[start + 3]
            if oui == DJI_OUI and oui_type == DJI_DRONEID_V2_OUI_TYPE:
                return bytes(frame_body[start + 4 : end])
        i = end
    return None
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/decoder/test_ie_extract.py -v`
Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add src/drone_detector/decoder/ tests/decoder/
git commit -m "feat(decoder): extract DJI DroneID v2 IE payload from 802.11 frame"
```

---

## Task 5: DJI DroneID v2 binary parser

**Files:**
- Create: `src/drone_detector/decoder/dji_droneid_v2.py`
- Create: `tests/decoder/test_dji_droneid_v2.py`
- Create: `tests/fixtures/beacons/sample_v2.bin` (built in Step 1)

- [ ] **Step 1: Build a fixture IE payload with known values**

Create a small helper script at `tests/_fixture_builders/build_sample_v2.py`:
```python
"""One-shot builder for tests/fixtures/beacons/sample_v2.bin. Run manually."""

import struct
from pathlib import Path


def build() -> bytes:
    serial = b"1581F5ABCDEF1234567890" + b"\x00" * (64 - 22)
    header = bytes([0x10, 0x00, 0x07, 0b101])  # frame type, version, seq, flags
    out = header
    out += bytes([0x40])  # serial length = 64
    out += serial
    # drone lon, lat (Bangkok-ish), scaled by 1e7
    out += struct.pack("<i", int(100.5018 * 1e7))   # lon
    out += struct.pack("<i", int(13.7563 * 1e7))    # lat
    # altitude 120.0 m -> 1200; height 45.5 m -> 455
    out += struct.pack("<h", 1200)
    out += struct.pack("<h", 455)
    # velocities m/s -> *100
    out += struct.pack("<h", 120)   # N/S +1.2
    out += struct.pack("<h", -40)   # E/W -0.4
    out += struct.pack("<h", 0)     # U/D
    out += struct.pack("<h", 8750)  # yaw 87.5
    out += struct.pack("<Q", 1716457800000)  # ts ms
    # pilot lat, lon
    out += struct.pack("<i", int(13.7560 * 1e7))
    out += struct.pack("<i", int(100.5020 * 1e7))
    # home lat, lon (unknown -> 0,0)
    out += struct.pack("<i", 0)
    out += struct.pack("<i", 0)
    # UUID
    uuid_bytes = bytes.fromhex("0102030405060708")
    out += bytes([len(uuid_bytes)]) + uuid_bytes
    return out


if __name__ == "__main__":
    p = Path(__file__).resolve().parents[1] / "fixtures" / "beacons" / "sample_v2.bin"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(build())
    print(f"wrote {p} ({p.stat().st_size} bytes)")
```

Run it:
```bash
uv run python tests/_fixture_builders/build_sample_v2.py
```
Expected: prints "wrote .../sample_v2.bin (...bytes)" and the file exists.

- [ ] **Step 2: Write failing tests**

Create `tests/decoder/test_dji_droneid_v2.py`:
```python
from datetime import datetime, timezone

import pytest

from drone_detector.decoder.dji_droneid_v2 import (
    MalformedDroneIDError,
    parse_dji_droneid,
)


CAPTURED = datetime(2026, 5, 23, 10, 0, 0, tzinfo=timezone.utc)


def test_parses_known_fixture(fixtures_dir):
    payload = (fixtures_dir / "beacons" / "sample_v2.bin").read_bytes()
    report = parse_dji_droneid(payload, captured_at=CAPTURED, rssi=-62, raw_frame_hex="dead")

    assert report.drone_serial == "1581F5ABCDEF1234567890"
    assert report.drone_lat == pytest.approx(13.7563, abs=1e-6)
    assert report.drone_lon == pytest.approx(100.5018, abs=1e-6)
    assert report.drone_altitude_m == pytest.approx(120.0)
    assert report.drone_height_m == pytest.approx(45.5)
    assert report.drone_speed_ns_mps == pytest.approx(1.2)
    assert report.drone_speed_ew_mps == pytest.approx(-0.4)
    assert report.drone_speed_ud_mps == pytest.approx(0.0)
    assert report.drone_yaw_deg == pytest.approx(87.5)
    assert report.pilot_lat == pytest.approx(13.7560, abs=1e-6)
    assert report.pilot_lon == pytest.approx(100.5020, abs=1e-6)
    assert report.home_lat is None
    assert report.home_lon is None
    assert report.uuid_len == 8
    assert report.uuid == "0102030405060708"
    assert report.rssi == -62
    assert report.captured_at == CAPTURED
    assert report.raw_frame_hex == "dead"


def test_raises_on_truncated_payload():
    with pytest.raises(MalformedDroneIDError):
        parse_dji_droneid(b"\x10\x00\x07\x05\x40" + b"\x00" * 10, captured_at=CAPTURED, rssi=None, raw_frame_hex="")
```

- [ ] **Step 3: Run tests to verify failure**

Run: `uv run pytest tests/decoder/test_dji_droneid_v2.py -v`
Expected: FAIL — module not found.

- [ ] **Step 4: Implement the parser**

Create `src/drone_detector/decoder/dji_droneid_v2.py`:
```python
"""Parse the payload of a DJI DroneID v2 vendor IE into a DroneIDReport.

Byte layout is documented in docs/dji_droneid_v2_format.md (the single source of truth).
All multi-byte fields are little-endian.
"""

import struct
from datetime import datetime

from drone_detector.models import DroneIDReport

LAT_LON_SCALE = 1e7
ALT_SCALE = 10.0
SPEED_SCALE = 100.0
YAW_SCALE = 100.0

HEADER_LEN = 4   # frame type, version, seq, state flags
SERIAL_LEN_BYTE = 1


class MalformedDroneIDError(ValueError):
    """Raised when a DroneID payload is too short or otherwise malformed."""


def _none_if_zero_pair(lat: float, lon: float) -> tuple[float | None, float | None]:
    if lat == 0.0 and lon == 0.0:
        return None, None
    return lat, lon


def parse_dji_droneid(
    payload: bytes,
    *,
    captured_at: datetime,
    rssi: int | None,
    raw_frame_hex: str,
) -> DroneIDReport:
    """Decode a DJI DroneID v2 IE payload (without OUI/OUI-type) into a DroneIDReport."""
    if len(payload) < HEADER_LEN + SERIAL_LEN_BYTE:
        raise MalformedDroneIDError("payload shorter than header+serial-length")

    serial_len = payload[HEADER_LEN]
    cursor = HEADER_LEN + SERIAL_LEN_BYTE
    fixed_after_serial = 4 + 4 + 2 + 2 + 2 + 2 + 2 + 2 + 8 + 4 + 4 + 4 + 4 + 1
    min_total = cursor + serial_len + fixed_after_serial
    if len(payload) < min_total:
        raise MalformedDroneIDError(
            f"payload {len(payload)}B shorter than minimum {min_total}B for serial_len={serial_len}"
        )

    serial = payload[cursor : cursor + serial_len].rstrip(b"\x00").decode("ascii", errors="replace")
    cursor += serial_len

    drone_lon_i, drone_lat_i = struct.unpack_from("<ii", payload, cursor)
    cursor += 8
    alt_i, height_i, ns_i, ew_i, ud_i, yaw_i = struct.unpack_from("<hhhhhh", payload, cursor)
    cursor += 12
    _ts_ms, = struct.unpack_from("<Q", payload, cursor)
    cursor += 8
    pilot_lat_i, pilot_lon_i, home_lat_i, home_lon_i = struct.unpack_from("<iiii", payload, cursor)
    cursor += 16

    uuid_len = payload[cursor]
    cursor += 1
    if cursor + uuid_len > len(payload):
        raise MalformedDroneIDError("uuid extends past payload")
    uuid_hex = payload[cursor : cursor + uuid_len].hex()

    pilot_lat, pilot_lon = _none_if_zero_pair(pilot_lat_i / LAT_LON_SCALE, pilot_lon_i / LAT_LON_SCALE)
    home_lat, home_lon = _none_if_zero_pair(home_lat_i / LAT_LON_SCALE, home_lon_i / LAT_LON_SCALE)

    return DroneIDReport(
        captured_at=captured_at,
        rssi=rssi,
        drone_serial=serial,
        drone_lat=drone_lat_i / LAT_LON_SCALE,
        drone_lon=drone_lon_i / LAT_LON_SCALE,
        drone_altitude_m=alt_i / ALT_SCALE,
        drone_height_m=height_i / ALT_SCALE,
        drone_speed_ns_mps=ns_i / SPEED_SCALE,
        drone_speed_ew_mps=ew_i / SPEED_SCALE,
        drone_speed_ud_mps=ud_i / SPEED_SCALE,
        drone_yaw_deg=yaw_i / YAW_SCALE,
        pilot_lat=pilot_lat,
        pilot_lon=pilot_lon,
        home_lat=home_lat,
        home_lon=home_lon,
        uuid_len=uuid_len,
        uuid=uuid_hex,
        raw_frame_hex=raw_frame_hex,
    )
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest tests/decoder/test_dji_droneid_v2.py -v`
Expected: 2 passed.

- [ ] **Step 6: Commit**

```bash
git add src/drone_detector/decoder/dji_droneid_v2.py tests/decoder/test_dji_droneid_v2.py tests/_fixture_builders/build_sample_v2.py tests/fixtures/beacons/sample_v2.bin
git commit -m "feat(decoder): parse DJI DroneID v2 IE payload"
```

---

## Task 6: Radiotap metadata extractor

**Files:**
- Create: `src/drone_detector/decoder/radiotap.py`
- Create: `tests/decoder/test_radiotap.py`

- [ ] **Step 1: Write failing test**

Create `tests/decoder/test_radiotap.py`:
```python
from scapy.layers.dot11 import RadioTap

from drone_detector.decoder.radiotap import RadioTapMeta, parse_radiotap


def test_parses_rssi_when_present() -> None:
    rt = RadioTap(present="dBm_AntSignal", dBm_AntSignal=-67)
    meta = parse_radiotap(rt)
    assert meta == RadioTapMeta(rssi=-67)


def test_returns_none_rssi_when_absent() -> None:
    rt = RadioTap()  # no signal field
    meta = parse_radiotap(rt)
    assert meta.rssi is None
```

- [ ] **Step 2: Run test to verify failure**

Run: `uv run pytest tests/decoder/test_radiotap.py -v`
Expected: FAIL — module not found.

- [ ] **Step 3: Implement**

Create `src/drone_detector/decoder/radiotap.py`:
```python
"""Extract metadata (RSSI today; channel/MCS later) from scapy's RadioTap layer."""

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class RadioTapMeta:
    rssi: int | None


def parse_radiotap(packet: Any) -> RadioTapMeta:
    rssi = getattr(packet, "dBm_AntSignal", None)
    return RadioTapMeta(rssi=int(rssi) if rssi is not None else None)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/decoder/test_radiotap.py -v`
Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
git add src/drone_detector/decoder/radiotap.py tests/decoder/test_radiotap.py
git commit -m "feat(decoder): extract RSSI from RadioTap header"
```

---

## Task 7: `FrameSource` Protocol + `FilePcapSource`

**Files:**
- Create: `src/drone_detector/sources/__init__.py`
- Create: `src/drone_detector/sources/base.py`
- Create: `src/drone_detector/sources/file_pcap.py`
- Create: `tests/sources/__init__.py`
- Create: `tests/sources/test_file_pcap.py`
- Create: `tests/fixtures/pcaps/two_beacons.pcap` (built in Step 1)

- [ ] **Step 1: Build a tiny test PCAP**

Create `tests/_fixture_builders/build_two_beacons_pcap.py`:
```python
"""Builds tests/fixtures/pcaps/two_beacons.pcap with two beacons:
- one with a DJI DroneID IE (payload from sample_v2.bin)
- one without
"""

from pathlib import Path

from scapy.all import wrpcap
from scapy.layers.dot11 import Dot11, Dot11Beacon, Dot11Elt, RadioTap

ROOT = Path(__file__).resolve().parents[1]
BEACONS_DIR = ROOT / "fixtures" / "beacons"
PCAP_PATH = ROOT / "fixtures" / "pcaps" / "two_beacons.pcap"

DJI_OUI_AND_TYPE = b"\x60\x60\x1F\x09"


def build() -> None:
    dji_payload = (BEACONS_DIR / "sample_v2.bin").read_bytes()
    dji_ie = Dot11Elt(ID=221, info=DJI_OUI_AND_TYPE + dji_payload)
    dji_beacon = (
        RadioTap(present="dBm_AntSignal", dBm_AntSignal=-60)
        / Dot11(type=0, subtype=8, addr1="ff:ff:ff:ff:ff:ff",
                addr2="aa:bb:cc:dd:ee:ff", addr3="aa:bb:cc:dd:ee:ff")
        / Dot11Beacon(cap=0x0411)
        / Dot11Elt(ID=0, info=b"NBTC-TEST")
        / dji_ie
    )
    plain_beacon = (
        RadioTap()
        / Dot11(type=0, subtype=8, addr1="ff:ff:ff:ff:ff:ff",
                addr2="11:22:33:44:55:66", addr3="11:22:33:44:55:66")
        / Dot11Beacon(cap=0x0411)
        / Dot11Elt(ID=0, info=b"OtherAP")
    )
    PCAP_PATH.parent.mkdir(parents=True, exist_ok=True)
    wrpcap(str(PCAP_PATH), [dji_beacon, plain_beacon])
    print(f"wrote {PCAP_PATH}")


if __name__ == "__main__":
    build()
```

Run it:
```bash
uv run python tests/_fixture_builders/build_two_beacons_pcap.py
```
Expected: prints "wrote .../two_beacons.pcap" and the file exists.

- [ ] **Step 2: Write failing test**

Create `tests/sources/__init__.py` (empty).
Create `tests/sources/test_file_pcap.py`:
```python
from drone_detector.sources.file_pcap import FilePcapSource


def test_file_pcap_source_yields_all_packets(fixtures_dir) -> None:
    pcap = fixtures_dir / "pcaps" / "two_beacons.pcap"
    with FilePcapSource(pcap) as source:
        packets = list(source)
    assert len(packets) == 2


def test_file_pcap_source_is_idempotent_on_close(fixtures_dir) -> None:
    pcap = fixtures_dir / "pcaps" / "two_beacons.pcap"
    source = FilePcapSource(pcap)
    list(source)
    source.close()
    source.close()  # second call must not raise
```

- [ ] **Step 3: Run test to verify failure**

Run: `uv run pytest tests/sources/test_file_pcap.py -v`
Expected: FAIL — module not found.

- [ ] **Step 4: Implement Protocol and FilePcapSource**

Create `src/drone_detector/sources/__init__.py` (empty).
Create `src/drone_detector/sources/base.py`:
```python
"""Source Protocol for raw 802.11 frames."""

from typing import Iterator, Protocol, runtime_checkable


@runtime_checkable
class FrameSource(Protocol):
    def __iter__(self) -> Iterator: ...
    def close(self) -> None: ...
```

Create `src/drone_detector/sources/file_pcap.py`:
```python
"""Stream 802.11 frames from a .pcap file. Cross-platform; primary macOS dev mode."""

from __future__ import annotations

from pathlib import Path
from typing import Iterator

from scapy.utils import PcapReader


class FilePcapSource:
    def __init__(self, path: Path) -> None:
        self._path = Path(path)
        self._reader: PcapReader | None = None

    def __enter__(self) -> "FilePcapSource":
        self._reader = PcapReader(str(self._path))
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    def __iter__(self) -> Iterator:
        if self._reader is None:
            self._reader = PcapReader(str(self._path))
        yield from self._reader

    def close(self) -> None:
        if self._reader is not None:
            self._reader.close()
            self._reader = None
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest tests/sources/test_file_pcap.py -v`
Expected: 2 passed.

- [ ] **Step 6: Commit**

```bash
git add src/drone_detector/sources/ tests/sources/ tests/_fixture_builders/build_two_beacons_pcap.py tests/fixtures/pcaps/two_beacons.pcap
git commit -m "feat(sources): FrameSource Protocol + FilePcapSource"
```

---

## Task 8: `LivePcapSource` (Linux-only, smoke-tested)

**Files:**
- Create: `src/drone_detector/sources/live_pcap.py`
- Create: `tests/sources/test_live_pcap.py`

- [ ] **Step 1: Write a tiny smoke test marked live**

Create `tests/sources/test_live_pcap.py`:
```python
import pytest

from drone_detector.sources.live_pcap import LivePcapSource


def test_live_source_class_importable_on_all_platforms() -> None:
    # Construction must not require a live interface.
    src = LivePcapSource(iface="loobackiface_does_not_exist")
    src.close()


@pytest.mark.live
def test_live_source_can_start_and_stop_briefly() -> None:
    src = LivePcapSource(iface="wlan0mon", timeout_s=1)
    src.start()
    src.close()
```

- [ ] **Step 2: Run unmarked test to verify failure**

Run: `uv run pytest tests/sources/test_live_pcap.py -v -m "not live"`
Expected: FAIL — module not found.

- [ ] **Step 3: Implement LivePcapSource**

Create `src/drone_detector/sources/live_pcap.py`:
```python
"""Live monitor-mode sniffer using scapy's AsyncSniffer (Linux only)."""

from __future__ import annotations

import queue
from typing import Iterator

from scapy.sendrecv import AsyncSniffer


class LivePcapSource:
    def __init__(self, iface: str, *, timeout_s: float | None = None) -> None:
        self._iface = iface
        self._timeout_s = timeout_s
        self._sniffer: AsyncSniffer | None = None
        self._q: queue.Queue = queue.Queue()
        self._stopped = False

    def start(self) -> None:
        if self._sniffer is not None:
            return
        self._sniffer = AsyncSniffer(
            iface=self._iface,
            store=False,
            prn=self._q.put,
        )
        self._sniffer.start()

    def __iter__(self) -> Iterator:
        self.start()
        while not self._stopped:
            try:
                yield self._q.get(timeout=self._timeout_s or 1.0)
            except queue.Empty:
                if self._timeout_s is not None:
                    return

    def close(self) -> None:
        self._stopped = True
        if self._sniffer is not None:
            try:
                self._sniffer.stop()
            except Exception:
                pass
            self._sniffer = None
```

- [ ] **Step 4: Run unmarked tests to verify they pass**

Run: `uv run pytest tests/sources/test_live_pcap.py -v -m "not live"`
Expected: 1 passed, 1 deselected.

- [ ] **Step 5: Commit**

```bash
git add src/drone_detector/sources/live_pcap.py tests/sources/test_live_pcap.py
git commit -m "feat(sources): LivePcapSource using scapy AsyncSniffer (Linux only)"
```

---

## Task 9: `ReportSink` Protocol + `JsonlFileSink`

**Files:**
- Create: `src/drone_detector/sinks/__init__.py`
- Create: `src/drone_detector/sinks/base.py`
- Create: `src/drone_detector/sinks/jsonl_sink.py`
- Create: `tests/sinks/__init__.py`
- Create: `tests/sinks/test_jsonl_sink.py`

- [ ] **Step 1: Write failing test**

Create `tests/sinks/__init__.py` (empty).
Create `tests/sinks/test_jsonl_sink.py`:
```python
import json
from datetime import datetime, timezone

from drone_detector.models import DroneIDReport
from drone_detector.sinks.jsonl_sink import JsonlFileSink


def _make_report(serial: str = "X", when: datetime | None = None) -> DroneIDReport:
    return DroneIDReport(
        captured_at=when or datetime(2026, 5, 23, 10, 0, 0, tzinfo=timezone.utc),
        rssi=-70, drone_serial=serial,
        drone_lat=13.0, drone_lon=100.0,
        drone_altitude_m=10.0, drone_height_m=5.0,
        drone_speed_ns_mps=0.0, drone_speed_ew_mps=0.0, drone_speed_ud_mps=0.0,
        drone_yaw_deg=0.0,
        pilot_lat=None, pilot_lon=None, home_lat=None, home_lon=None,
        uuid_len=0, uuid="",
        raw_frame_hex="aa",
    )


def test_writes_one_json_object_per_line(tmp_path) -> None:
    path = tmp_path / "out.jsonl"
    sink = JsonlFileSink(path, dedup_window_s=0)
    sink.write(_make_report("A"))
    sink.write(_make_report("B"))
    sink.close()

    lines = path.read_text().splitlines()
    assert len(lines) == 2
    a = json.loads(lines[0])
    assert a["drone_serial"] == "A"
    assert a["captured_at"] == "2026-05-23T10:00:00+00:00"


def test_dedups_same_serial_within_window(tmp_path) -> None:
    path = tmp_path / "out.jsonl"
    sink = JsonlFileSink(path, dedup_window_s=5)
    base = datetime(2026, 5, 23, 10, 0, 0, tzinfo=timezone.utc)
    sink.write(_make_report("A", when=base))
    sink.write(_make_report("A", when=base.replace(second=3)))   # within 5s -> dropped
    sink.write(_make_report("A", when=base.replace(second=6)))   # next bucket -> emitted
    sink.close()
    lines = path.read_text().splitlines()
    assert len(lines) == 2
```

- [ ] **Step 2: Run test to verify failure**

Run: `uv run pytest tests/sinks/test_jsonl_sink.py -v`
Expected: FAIL — module not found.

- [ ] **Step 3: Implement Protocol and JsonlFileSink**

Create `src/drone_detector/sinks/__init__.py` (empty).
Create `src/drone_detector/sinks/base.py`:
```python
"""Sink Protocol for DroneIDReport instances."""

from typing import Protocol, runtime_checkable

from drone_detector.models import DroneIDReport


@runtime_checkable
class ReportSink(Protocol):
    def write(self, report: DroneIDReport) -> None: ...
    def close(self) -> None: ...
```

Create `src/drone_detector/sinks/jsonl_sink.py`:
```python
"""Append-only JSONL sink with per-(serial, time bucket) dedup."""

from __future__ import annotations

import dataclasses
import json
from pathlib import Path
from typing import IO

from drone_detector.models import DroneIDReport


def _bucket(report: DroneIDReport, window_s: int) -> int:
    if window_s <= 0:
        return -1  # disabled: every write is its own bucket via counter below
    return int(report.captured_at.timestamp()) // window_s


class JsonlFileSink:
    def __init__(self, path: Path, *, dedup_window_s: int = 5) -> None:
        self._path = Path(path)
        self._fh: IO[str] | None = None
        self._dedup_window_s = dedup_window_s
        self._seen: dict[tuple[str, int], None] = {}
        self._write_counter = 0

    def _open(self) -> IO[str]:
        if self._fh is None:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            self._fh = self._path.open("a", encoding="utf-8")
        return self._fh

    def write(self, report: DroneIDReport) -> None:
        if self._dedup_window_s > 0:
            key = (report.drone_serial, _bucket(report, self._dedup_window_s))
            if key in self._seen:
                return
            self._seen[key] = None
        else:
            self._write_counter += 1
        record = dataclasses.asdict(report)
        record["captured_at"] = report.captured_at.isoformat()
        line = json.dumps(record, ensure_ascii=False)
        fh = self._open()
        fh.write(line + "\n")
        fh.flush()

    def close(self) -> None:
        if self._fh is not None:
            self._fh.close()
            self._fh = None
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/sinks/test_jsonl_sink.py -v`
Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
git add src/drone_detector/sinks/ tests/sinks/
git commit -m "feat(sinks): ReportSink Protocol + JsonlFileSink with 5s dedup"
```

---

## Task 10: `StdoutSink`

**Files:**
- Create: `src/drone_detector/sinks/stdout_sink.py`
- Create: `tests/sinks/test_stdout_sink.py`

- [ ] **Step 1: Write failing test**

Create `tests/sinks/test_stdout_sink.py`:
```python
from datetime import datetime, timezone

from rich.console import Console

from drone_detector.models import DroneIDReport
from drone_detector.sinks.stdout_sink import StdoutSink


def _make_report(serial: str, when: datetime) -> DroneIDReport:
    return DroneIDReport(
        captured_at=when, rssi=-65, drone_serial=serial,
        drone_lat=13.7563, drone_lon=100.5018,
        drone_altitude_m=120.0, drone_height_m=45.5,
        drone_speed_ns_mps=1.2, drone_speed_ew_mps=-0.4, drone_speed_ud_mps=0.0,
        drone_yaw_deg=87.5,
        pilot_lat=13.7560, pilot_lon=100.5020,
        home_lat=None, home_lon=None,
        uuid_len=0, uuid="",
        raw_frame_hex="",
    )


def test_writes_one_line_with_serial_and_coords() -> None:
    import io
    buf = io.StringIO()
    console = Console(file=buf, force_terminal=False, color_system=None, width=200)
    sink = StdoutSink(console=console, dedup_window_s=0)
    sink.write(_make_report("ABC", datetime(2026, 5, 23, 10, 0, 0, tzinfo=timezone.utc)))
    out = buf.getvalue()
    assert "ABC" in out
    assert "13.7563" in out
    assert "100.5018" in out
    assert "-65" in out


def test_dedup_window_drops_within_bucket() -> None:
    import io
    buf = io.StringIO()
    console = Console(file=buf, force_terminal=False, color_system=None, width=200)
    sink = StdoutSink(console=console, dedup_window_s=5)
    base = datetime(2026, 5, 23, 10, 0, 0, tzinfo=timezone.utc)
    sink.write(_make_report("A", base))
    sink.write(_make_report("A", base.replace(second=3)))   # dropped
    sink.write(_make_report("A", base.replace(second=6)))   # emitted
    lines = [line for line in buf.getvalue().splitlines() if line.strip()]
    assert len(lines) == 2
```

- [ ] **Step 2: Run test to verify failure**

Run: `uv run pytest tests/sinks/test_stdout_sink.py -v`
Expected: FAIL — module not found.

- [ ] **Step 3: Implement StdoutSink**

Create `src/drone_detector/sinks/stdout_sink.py`:
```python
"""Pretty stdout sink (deduplicated by serial and 5-second bucket by default)."""

from __future__ import annotations

import sys
from typing import IO

from rich.console import Console

from drone_detector.models import DroneIDReport


def _bucket(report: DroneIDReport, window_s: int) -> int:
    return int(report.captured_at.timestamp()) // window_s


class StdoutSink:
    def __init__(
        self,
        *,
        console: Console | None = None,
        file: IO[str] | None = None,
        dedup_window_s: int = 5,
    ) -> None:
        self._console = console or Console(file=file or sys.stdout)
        self._dedup_window_s = dedup_window_s
        self._seen: dict[tuple[str, int], None] = {}

    def write(self, report: DroneIDReport) -> None:
        if self._dedup_window_s > 0:
            key = (report.drone_serial, _bucket(report, self._dedup_window_s))
            if key in self._seen:
                return
            self._seen[key] = None
        ts = report.captured_at.strftime("%H:%M:%S")
        pilot = (
            f"pilot=({report.pilot_lat:.5f},{report.pilot_lon:.5f})"
            if report.pilot_lat is not None and report.pilot_lon is not None
            else "pilot=unknown"
        )
        rssi = f"{report.rssi}dBm" if report.rssi is not None else "rssi=?"
        self._console.print(
            f"[cyan]{ts}[/cyan]  "
            f"[bold]{report.drone_serial}[/bold]  "
            f"drone=({report.drone_lat:.5f},{report.drone_lon:.5f}) "
            f"{pilot}  RSSI={rssi}"
        )

    def close(self) -> None:
        pass
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/sinks/test_stdout_sink.py -v`
Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
git add src/drone_detector/sinks/stdout_sink.py tests/sinks/test_stdout_sink.py
git commit -m "feat(sinks): StdoutSink with rich formatting and 5s dedup"
```

---

## Task 11: Pipeline (wire source → decoder → sinks)

**Files:**
- Create: `src/drone_detector/pipeline.py`
- Create: `tests/test_pipeline.py`

- [ ] **Step 1: Write failing test**

Create `tests/test_pipeline.py`:
```python
from datetime import datetime, timezone
from pathlib import Path

from drone_detector.models import DroneIDReport
from drone_detector.pipeline import run_pipeline
from drone_detector.sources.file_pcap import FilePcapSource


class RecordingSink:
    def __init__(self) -> None:
        self.reports: list[DroneIDReport] = []

    def write(self, report: DroneIDReport) -> None:
        self.reports.append(report)

    def close(self) -> None:
        pass


def test_pipeline_decodes_dji_beacon_and_skips_plain_beacon(fixtures_dir: Path) -> None:
    pcap = fixtures_dir / "pcaps" / "two_beacons.pcap"
    sink = RecordingSink()
    with FilePcapSource(pcap) as source:
        run_pipeline(
            source=source,
            sinks=[sink],
            clock=lambda: datetime(2026, 5, 23, 10, 0, 0, tzinfo=timezone.utc),
        )
    assert len(sink.reports) == 1
    assert sink.reports[0].drone_serial == "1581F5ABCDEF1234567890"
```

- [ ] **Step 2: Run test to verify failure**

Run: `uv run pytest tests/test_pipeline.py -v`
Expected: FAIL — module not found.

- [ ] **Step 3: Implement pipeline**

Create `src/drone_detector/pipeline.py`:
```python
"""Glue: pull packets from a FrameSource, decode DJI DroneID, push to each sink."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Callable, Iterable

from scapy.layers.dot11 import Dot11Beacon

from drone_detector.decoder.dji_droneid_v2 import (
    MalformedDroneIDError,
    parse_dji_droneid,
)
from drone_detector.decoder.ie_extract import extract_dji_ie
from drone_detector.decoder.radiotap import parse_radiotap
from drone_detector.sinks.base import ReportSink
from drone_detector.sources.base import FrameSource

log = logging.getLogger(__name__)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def run_pipeline(
    *,
    source: FrameSource,
    sinks: Iterable[ReportSink],
    clock: Callable[[], datetime] = _utcnow,
) -> None:
    sinks = list(sinks)
    for packet in source:
        try:
            if not packet.haslayer(Dot11Beacon):
                continue
            frame_body = bytes(packet[Dot11Beacon].payload)
            ie_payload = extract_dji_ie(frame_body)
            if ie_payload is None:
                continue
            meta = parse_radiotap(packet)
            report = parse_dji_droneid(
                ie_payload,
                captured_at=clock(),
                rssi=meta.rssi,
                raw_frame_hex=bytes(packet).hex(),
            )
        except MalformedDroneIDError as exc:
            log.debug("dropping malformed DroneID: %s", exc)
            continue
        except Exception:
            log.debug("skipping packet due to unexpected error", exc_info=True)
            continue

        for sink in sinks:
            try:
                sink.write(report)
            except Exception:
                log.exception("sink %r failed; continuing", sink)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_pipeline.py -v`
Expected: 1 passed.

- [ ] **Step 5: Commit**

```bash
git add src/drone_detector/pipeline.py tests/test_pipeline.py
git commit -m "feat(pipeline): wire source → decoder → sinks with error isolation"
```

---

## Task 12: CLI (`typer`)

**Files:**
- Create: `src/drone_detector/cli.py`
- Modify: `pyproject.toml` (add entrypoint)
- Create: `tests/test_cli.py`

- [ ] **Step 1: Add the CLI entrypoint to `pyproject.toml`**

Append to `pyproject.toml`:
```toml
[project.scripts]
drone-detector = "drone_detector.cli:app"
```

- [ ] **Step 2: Write failing test**

Create `tests/test_cli.py`:
```python
import json
from typer.testing import CliRunner

from drone_detector.cli import app


runner = CliRunner()


def test_version_prints_a_version_string() -> None:
    result = runner.invoke(app, ["version"])
    assert result.exit_code == 0
    assert "drone-detector" in result.stdout


def test_replay_decodes_pcap_and_writes_jsonl(tmp_path, fixtures_dir) -> None:
    pcap = fixtures_dir / "pcaps" / "two_beacons.pcap"
    out = tmp_path / "out.jsonl"
    result = runner.invoke(app, ["replay", str(pcap), "--out", str(out)])
    assert result.exit_code == 0, result.stdout
    lines = out.read_text().splitlines()
    assert len(lines) == 1
    record = json.loads(lines[0])
    assert record["drone_serial"] == "1581F5ABCDEF1234567890"
```

- [ ] **Step 3: Run test to verify failure**

Run: `uv run pytest tests/test_cli.py -v`
Expected: FAIL — module not found.

- [ ] **Step 4: Implement CLI**

Create `src/drone_detector/cli.py`:
```python
"""drone-detector command-line interface."""

from __future__ import annotations

import importlib.metadata
import subprocess
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console

from drone_detector.pipeline import run_pipeline
from drone_detector.sinks.jsonl_sink import JsonlFileSink
from drone_detector.sinks.stdout_sink import StdoutSink
from drone_detector.sources.file_pcap import FilePcapSource
from drone_detector.sources.live_pcap import LivePcapSource

app = typer.Typer(add_completion=False, help="DJI DroneID decoder for NBTC Thailand.")


def _build_sinks(out: Optional[Path]) -> list:
    sinks: list = [StdoutSink(console=Console())]
    if out is not None:
        sinks.append(JsonlFileSink(out))
    return sinks


@app.command()
def version() -> None:
    """Print the installed package version."""
    try:
        v = importlib.metadata.version("drone-detector")
    except importlib.metadata.PackageNotFoundError:
        v = "0.0.0+dev"
    typer.echo(f"drone-detector {v}")


@app.command()
def replay(
    pcap: Path = typer.Argument(..., exists=True, readable=True, dir_okay=False),
    out: Optional[Path] = typer.Option(None, "--out", help="JSONL output path"),
) -> None:
    """Decode a .pcap file and print/write detections."""
    sinks = _build_sinks(out)
    try:
        with FilePcapSource(pcap) as source:
            run_pipeline(source=source, sinks=sinks)
    finally:
        for s in sinks:
            s.close()


@app.command()
def listen(
    iface: str = typer.Option(..., "--iface", help="Monitor-mode WiFi interface (Linux)"),
    out: Optional[Path] = typer.Option(Path("detections.jsonl"), "--out"),
) -> None:
    """Live-capture DJI DroneID beacons from a monitor-mode interface."""
    sinks = _build_sinks(out)
    source = LivePcapSource(iface=iface)
    try:
        run_pipeline(source=source, sinks=sinks)
    finally:
        source.close()
        for s in sinks:
            s.close()


@app.command()
def hop(
    iface: str = typer.Option(..., "--iface"),
    channels: str = typer.Option("1,6,11,36,149", "--channels"),
    dwell_ms: int = typer.Option(500, "--dwell-ms"),
) -> None:
    """Rotate `iface` through `channels` every `dwell-ms` ms using `iw dev`."""
    import time
    ch_list = [c.strip() for c in channels.split(",") if c.strip()]
    typer.echo(f"hopping {iface} through {ch_list} every {dwell_ms}ms; Ctrl+C to stop")
    try:
        while True:
            for ch in ch_list:
                subprocess.run(["iw", "dev", iface, "set", "channel", ch], check=False)
                time.sleep(dwell_ms / 1000)
    except KeyboardInterrupt:
        typer.echo("stopped")
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest tests/test_cli.py -v`
Expected: 2 passed.

- [ ] **Step 6: Commit**

```bash
git add src/drone_detector/cli.py tests/test_cli.py pyproject.toml
git commit -m "feat(cli): typer CLI with version, replay, listen, hop"
```

---

## Task 13: Integration test — end-to-end replay → JSONL golden file

**Files:**
- Create: `tests/test_integration_replay.py`
- Create: `tests/fixtures/golden/two_beacons.expected.jsonl` (built in Step 1)

- [ ] **Step 1: Generate the golden file from the actual pipeline output**

Run a one-shot script to capture today's output as the golden record. Create `tests/_fixture_builders/build_golden_two_beacons.py`:
```python
"""Generate the golden JSONL from the current pipeline output. Run manually."""

import json
from datetime import datetime, timezone
from pathlib import Path

from drone_detector.pipeline import run_pipeline
from drone_detector.sinks.jsonl_sink import JsonlFileSink
from drone_detector.sources.file_pcap import FilePcapSource

ROOT = Path(__file__).resolve().parents[1]
PCAP = ROOT / "fixtures" / "pcaps" / "two_beacons.pcap"
OUT = ROOT / "fixtures" / "golden" / "two_beacons.expected.jsonl"

if __name__ == "__main__":
    OUT.parent.mkdir(parents=True, exist_ok=True)
    if OUT.exists():
        OUT.unlink()
    sink = JsonlFileSink(OUT, dedup_window_s=0)
    with FilePcapSource(PCAP) as source:
        run_pipeline(
            source=source,
            sinks=[sink],
            clock=lambda: datetime(2026, 5, 23, 10, 0, 0, tzinfo=timezone.utc),
        )
    sink.close()
    # Pretty-print so a human can diff it later
    lines = OUT.read_text().splitlines()
    print(f"wrote {len(lines)} line(s) to {OUT}")
    for line in lines:
        print(json.dumps(json.loads(line), indent=2, sort_keys=True))
```

Run it:
```bash
uv run python tests/_fixture_builders/build_golden_two_beacons.py
```
Expected: prints "wrote 1 line(s) to ..." and the golden file exists.

- [ ] **Step 2: Write the integration test**

Create `tests/test_integration_replay.py`:
```python
import json
from datetime import datetime, timezone

from drone_detector.pipeline import run_pipeline
from drone_detector.sinks.jsonl_sink import JsonlFileSink
from drone_detector.sources.file_pcap import FilePcapSource


def test_replay_matches_golden(tmp_path, fixtures_dir) -> None:
    pcap = fixtures_dir / "pcaps" / "two_beacons.pcap"
    out = tmp_path / "out.jsonl"

    sink = JsonlFileSink(out, dedup_window_s=0)
    with FilePcapSource(pcap) as source:
        run_pipeline(
            source=source,
            sinks=[sink],
            clock=lambda: datetime(2026, 5, 23, 10, 0, 0, tzinfo=timezone.utc),
        )
    sink.close()

    actual = [json.loads(line) for line in out.read_text().splitlines()]
    expected_path = fixtures_dir / "golden" / "two_beacons.expected.jsonl"
    expected = [json.loads(line) for line in expected_path.read_text().splitlines()]
    assert actual == expected
```

- [ ] **Step 3: Run integration test**

Run: `uv run pytest tests/test_integration_replay.py -v`
Expected: 1 passed.

- [ ] **Step 4: Commit**

```bash
git add tests/test_integration_replay.py tests/fixtures/golden/two_beacons.expected.jsonl tests/_fixture_builders/build_golden_two_beacons.py
git commit -m "test: end-to-end replay → JSONL golden file"
```

---

## Task 14: README and final quality gate

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Replace `README.md` with usage docs**

Overwrite `README.md`:
```markdown
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
```

- [ ] **Step 2: Run full quality gate**

Run each in order:
```bash
uv run ruff check .
uv run mypy src
uv run pytest --cov -m "not live" -v
```

Expected:
- ruff: All checks passed
- mypy: Success: no issues found
- pytest: all tests pass; coverage report shows ≥ 80% with decoder module near 100%

If coverage is below 80%, add tests for the uncovered branches before continuing.

- [ ] **Step 3: Commit**

```bash
git add README.md
git commit -m "docs: README with usage, hardware, and test instructions"
```

- [ ] **Step 4: Tag v0.1.0**

```bash
git tag v0.1.0
```

Do NOT push the tag — user policy.

---

## Done

At this point the detector:

- Decodes DJI DroneID v2 beacons from PCAPs on macOS or Linux.
- Has a CLI with `replay`, `listen`, `hop`, `version`.
- Writes detections to stdout and JSONL with 5-second per-serial dedup.
- Passes ruff, mypy, and a ≥ 80% covered pytest suite.

Next steps live in the spec's section 14 (Bluetooth RemoteID, ASTM F3411, web UI, DB sink, NFZ alerts).
