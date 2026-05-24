# Channel Hopping + ASTM F3411 Coverage — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add aggressive WiFi channel hopping inside `listen`, plus ASTM F3411 coverage via a ctypes wrapper around vendored `opendroneid-core-c`, so the detector catches DJI Air 3S (with motors armed) and non-DJI drones (Parrot, Autel, ESP32 modules).

**Architecture:** Single Python process. Three threads inside `listen`: hopper (calls `iw` every ~200ms), sniffer (scapy AsyncSniffer → queue), main (drain queue → decoder registry → sinks). IE extractor matches both DJI and ASTM OUIs. ASTM payloads decoded by ctypes wrapper around `libopendroneid.{so,dylib}` built from vendored C source. One unified `DroneReport` schema for both protocols.

**Tech Stack:** Python 3.11, scapy, typer, rich, ctypes, hatchling custom build hook, CMake (for libopendroneid), pytest, ruff, mypy. macOS dev → Raspberry Pi 5 deploy.

**Spec:** `docs/superpowers/specs/2026-05-24-channel-hop-and-astm-design.md`

---

## File Structure

### New files
| Path | Responsibility |
|---|---|
| `vendor/opendroneid-core-c/` (submodule) | Upstream C library, pinned to a tagged release |
| `build_libopendroneid.py` | Hatchling custom build hook: runs CMake, copies built library into `src/drone_detector/_lib/` |
| `src/drone_detector/_lib/__init__.py` | Empty package marker so the lib dir ships with the wheel |
| `src/drone_detector/decoder/astm_f3411.py` | ctypes wrapper + parser, exposes `parse_astm()`, raises `MalformedAstmError` |
| `src/drone_detector/decoder/registry.py` | `{tag → parser_fn}` dispatch table |
| `src/drone_detector/capture/__init__.py` | Empty package marker |
| `src/drone_detector/capture/hopper.py` | `ChannelHopper` daemon-thread class with mock-injectable `set_channel_fn` |
| `src/drone_detector/capture/iw_backend.py` | Linux-only `iw dev <iface> set channel <n>` subprocess wrapper |
| `tests/decoder/test_astm_f3411.py` | Unit tests for ASTM parser using byte fixtures |
| `tests/decoder/test_registry.py` | Registry dispatch tests |
| `tests/capture/__init__.py` | |
| `tests/capture/test_hopper.py` | Hopper tests with mock `set_channel_fn` |
| `tests/fixtures/beacons/sample_astm_basic_id.bin` | Hand-crafted ASTM Basic ID payload |
| `tests/fixtures/beacons/sample_astm_location.bin` | Hand-crafted ASTM Location payload |
| `tests/fixtures/beacons/sample_astm_pack.bin` | Message Pack container |
| `tests/fixtures/pcaps/mixed_protocols.pcap` | DJI + ASTM + plain beacon |
| `tests/fixtures/golden/mixed_protocols.expected.jsonl` | Expected JSONL output |
| `tests/_fixture_builders/build_sample_astm.py` | Generates the ASTM .bin fixtures |
| `tests/_fixture_builders/build_mixed_protocols_pcap.py` | Generates the mixed pcap |
| `scripts/pi_hop_smoke.sh` | Pi-only shell script: verify channel hopping actually changes the channel |

### Modified files
| Path | Change |
|---|---|
| `src/drone_detector/models.py` | Rename `DroneIDReport` → `DroneReport`, add `protocol`, `operator_id`, `astm_message_type`; loosen DJI-only fields to nullable |
| `src/drone_detector/decoder/ie_extract.py` | Walk IE list and match both OUIs; return `(tag, payload)` tuple |
| `src/drone_detector/decoder/dji_droneid_v2.py` | Return `DroneReport(protocol="dji_v2", ...)` |
| `src/drone_detector/pipeline.py` | Use registry to dispatch parser by tag |
| `src/drone_detector/sinks/base.py` | Update Protocol to take `DroneReport` |
| `src/drone_detector/sinks/jsonl_sink.py` | Same import rename |
| `src/drone_detector/sinks/stdout_sink.py` | Same import rename, handle new optional fields |
| `src/drone_detector/cli.py` | `listen` gains `--hop/--no-hop`, `--channels`, `--dwell-ms`, `--reset-on-stall` |
| `pyproject.toml` | Add hatchling custom build hook entry; bump version to `0.2.0` |
| `tests/decoder/test_ie_extract.py` | Adapt to new tuple return signature; add ASTM cases |
| `tests/decoder/test_dji_droneid_v2.py` | Replace `DroneIDReport` references |
| `tests/sinks/test_jsonl_sink.py` | Replace `DroneIDReport` references |
| `tests/sinks/test_stdout_sink.py` | Replace `DroneIDReport` references |
| `tests/test_pipeline.py` | Replace `DroneIDReport` references |
| `tests/test_integration_replay.py` | Add mixed-protocols replay assertion |
| `tests/test_models.py` | New field coverage |
| `README.md` | Document new `listen` flags, vendor build step, ASTM coverage |

---

## Task Ordering (Dependency-Driven)

1. **Vendor libopendroneid** → no other task depends on Python here
2. **Build hook** → produces the `.so/.dylib` that ASTM parser will load
3. **Schema migration** (`DroneReport`) → foundational rename, touches every layer
4. **IE extractor signature change** → introduces protocol tag
5. **Decoder registry** → dispatch table
6. **Pipeline integration** → wires registry in
7. **ASTM parser ctypes wrapper** → uses the built lib
8. **ASTM integration test** (mixed protocols pcap) → end-to-end ASTM path
9. **ChannelHopper class** → independent of decoder work
10. **iw backend** → adapter for hopper
11. **Listen subcommand integration** → wires hopper into CLI
12. **Listen CLI flags** → exposes config
13. **Reset-on-stall feature** → optional driver-wedge mitigation
14. **README + Pi smoke script** → docs and deploy aid

---

## Task 1: Add libopendroneid as a git submodule

**Files:**
- Create: `vendor/opendroneid-core-c/` (submodule)
- Modify: `.gitmodules` (created if absent)

- [ ] **Step 1: Pick a pinned tag**

Run: `git ls-remote --tags https://github.com/opendroneid/opendroneid-core-c | tail -20`
Pick the most recent release tag (e.g. `v2.0.0`). Record the chosen tag.

- [ ] **Step 2: Add the submodule pinned to that tag**

Run:
```bash
git submodule add https://github.com/opendroneid/opendroneid-core-c.git vendor/opendroneid-core-c
cd vendor/opendroneid-core-c && git checkout <TAG_FROM_STEP_1> && cd ../..
git add .gitmodules vendor/opendroneid-core-c
```

- [ ] **Step 3: Verify the vendored CMakeLists is there**

Run: `test -f vendor/opendroneid-core-c/libopendroneid/CMakeLists.txt && echo OK`
Expected: `OK`

- [ ] **Step 4: Commit**

```bash
git commit -m "vendor: pin opendroneid-core-c as submodule"
```

---

## Task 2: Build libopendroneid via Hatchling custom build hook

**Files:**
- Create: `build_libopendroneid.py`
- Create: `src/drone_detector/_lib/__init__.py`
- Modify: `pyproject.toml`

- [ ] **Step 1: Write the empty `_lib` package marker**

Create `src/drone_detector/_lib/__init__.py` with one line:
```python
"""Holds platform-specific compiled libraries (libopendroneid.so or .dylib)."""
```

- [ ] **Step 2: Write the custom hatchling build hook**

Create `build_libopendroneid.py`:
```python
"""Hatchling custom build hook: build libopendroneid via CMake and copy into _lib/."""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

from hatchling.builders.hooks.plugin.interface import BuildHookInterface


class LibopendroneidBuildHook(BuildHookInterface):
    PLUGIN_NAME = "build_libopendroneid"

    def initialize(self, version: str, build_data: dict) -> None:
        root = Path(self.root)
        vendor = root / "vendor" / "opendroneid-core-c"
        if not vendor.exists():
            raise RuntimeError(
                "vendor/opendroneid-core-c not found; run "
                "`git submodule update --init --recursive`"
            )
        build_dir = vendor / "build"
        build_dir.mkdir(exist_ok=True)
        subprocess.run(
            ["cmake", "-S", str(vendor / "libopendroneid"), "-B", str(build_dir)],
            check=True,
        )
        subprocess.run(
            ["cmake", "--build", str(build_dir), "--config", "Release"],
            check=True,
        )
        dest = root / "src" / "drone_detector" / "_lib"
        dest.mkdir(parents=True, exist_ok=True)
        if sys.platform == "darwin":
            built = next(build_dir.glob("libopendroneid.dylib"))
        else:
            built = next(build_dir.glob("libopendroneid.so*"))
        shutil.copy2(built, dest / built.name)
        build_data["force_include"][str(dest / built.name)] = (
            f"drone_detector/_lib/{built.name}"
        )
```

- [ ] **Step 3: Wire the hook into `pyproject.toml`**

Add these blocks to `pyproject.toml`:
```toml
[tool.hatch.build.hooks.custom]
path = "build_libopendroneid.py"

[tool.hatch.build.targets.wheel]
packages = ["src/drone_detector"]
```
Also bump `version` from `0.1.0` to `0.2.0`.

- [ ] **Step 4: Initialize and build**

Run:
```bash
git submodule update --init --recursive
uv pip install -e .
```
Expected: build succeeds, `ls src/drone_detector/_lib/` shows `libopendroneid.{dylib,so}`.

- [ ] **Step 5: Smoke-test that ctypes can load it**

Run:
```bash
uv run python -c "import ctypes, pathlib, glob; p = sorted(glob.glob('src/drone_detector/_lib/libopendroneid.*'))[0]; print(ctypes.CDLL(p))"
```
Expected: prints `<CDLL '...libopendroneid.dylib', handle ...>` with no error.

- [ ] **Step 6: Commit**

```bash
git add build_libopendroneid.py src/drone_detector/_lib pyproject.toml
git commit -m "build: vendor + build libopendroneid via hatchling hook"
```

---

## Task 3: Migrate schema from DroneIDReport to DroneReport

**Files:**
- Modify: `src/drone_detector/models.py`
- Modify: `tests/test_models.py`

- [ ] **Step 1: Write the failing test for the new schema**

Replace the body of `tests/test_models.py` with:
```python
from datetime import UTC, datetime

import pytest

from drone_detector.models import DroneReport


def _base_kwargs() -> dict:
    return {
        "captured_at": datetime(2026, 5, 24, 12, 0, tzinfo=UTC),
        "rssi": -50,
        "protocol": "dji_v2",
        "raw_frame_hex": "deadbeef",
        "drone_serial": "1581F5ABCDEF",
        "operator_id": None,
        "drone_lat": 13.7,
        "drone_lon": 100.5,
        "drone_altitude_m": 12.3,
        "drone_height_m": 5.0,
        "drone_speed_ns_mps": 1.0,
        "drone_speed_ew_mps": 0.0,
        "drone_speed_ud_mps": 0.0,
        "drone_yaw_deg": 90.0,
        "pilot_lat": None,
        "pilot_lon": None,
        "home_lat": None,
        "home_lon": None,
        "astm_message_type": None,
        "uuid_len": 0,
        "uuid": "",
    }


def test_drone_report_is_frozen():
    r = DroneReport(**_base_kwargs())
    with pytest.raises(Exception):
        r.drone_serial = "changed"  # type: ignore[misc]


def test_drone_report_accepts_astm_protocol():
    kwargs = _base_kwargs() | {"protocol": "astm_f3411", "astm_message_type": 1}
    r = DroneReport(**kwargs)
    assert r.protocol == "astm_f3411"
    assert r.astm_message_type == 1


def test_drone_report_allows_nullable_telemetry():
    kwargs = _base_kwargs() | {
        "drone_lat": None,
        "drone_lon": None,
        "drone_altitude_m": None,
    }
    r = DroneReport(**kwargs)
    assert r.drone_lat is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_models.py -v`
Expected: ImportError or AttributeError — `DroneReport` does not exist yet.

- [ ] **Step 3: Rewrite `src/drone_detector/models.py`**

Replace entire file:
```python
from dataclasses import dataclass
from datetime import datetime
from typing import Literal


@dataclass(frozen=True)
class DroneReport:
    captured_at: datetime
    rssi: int | None
    protocol: Literal["dji_v2", "astm_f3411"]
    raw_frame_hex: str

    drone_serial: str
    operator_id: str | None

    drone_lat: float | None
    drone_lon: float | None
    drone_altitude_m: float | None
    drone_height_m: float | None
    drone_speed_ns_mps: float | None
    drone_speed_ew_mps: float | None
    drone_speed_ud_mps: float | None
    drone_yaw_deg: float | None

    pilot_lat: float | None
    pilot_lon: float | None
    home_lat: float | None
    home_lon: float | None

    astm_message_type: int | None
    uuid_len: int | None
    uuid: str | None
```

- [ ] **Step 4: Run model tests to verify they pass**

Run: `uv run pytest tests/test_models.py -v`
Expected: PASS for all three tests.

- [ ] **Step 5: Note the breakage — other modules still import `DroneIDReport`**

Run: `uv run pytest`
Expected: errors from `dji_droneid_v2.py`, sinks, and CLI all importing `DroneIDReport`. We fix these in the next steps **before** committing.

- [ ] **Step 6: Update `dji_droneid_v2.py` to return `DroneReport(protocol="dji_v2", ...)`**

In `src/drone_detector/decoder/dji_droneid_v2.py`:
- Change `from drone_detector.models import DroneIDReport` to `from drone_detector.models import DroneReport`
- Change return type from `DroneIDReport` to `DroneReport`
- In the returned constructor call, add `protocol="dji_v2", operator_id=None, astm_message_type=None,` and keep the rest of the fields unchanged.

- [ ] **Step 7: Update sinks**

In each of `src/drone_detector/sinks/base.py`, `jsonl_sink.py`, `stdout_sink.py`:
- Replace `DroneIDReport` with `DroneReport` in imports and type annotations.

In `stdout_sink.py`, also tolerate `None` for previously-required fields when rendering (e.g., format `drone_lat` as `"--"` if `None`).

- [ ] **Step 8: Update CLI and pipeline import-level references**

Grep for any remaining `DroneIDReport` references:
```bash
grep -rn DroneIDReport src tests
```
Replace each with `DroneReport`.

- [ ] **Step 9: Run full test suite**

Run: `uv run pytest`
Expected: All existing tests pass with the renamed model. New `test_drone_report_*` tests in `test_models.py` also pass.

- [ ] **Step 10: Commit**

```bash
git add src tests
git commit -m "refactor(models): rename DroneIDReport -> DroneReport with protocol discriminator"
```

---

## Task 4: Change IE extractor to return `(tag, payload)` tuple

**Files:**
- Modify: `src/drone_detector/decoder/ie_extract.py`
- Modify: `tests/decoder/test_ie_extract.py`

- [ ] **Step 1: Write failing tests for the new tuple signature**

Replace `tests/decoder/test_ie_extract.py` with:
```python
from drone_detector.decoder.ie_extract import extract_drone_ie


def _vendor_ie(oui: bytes, oui_type: int, payload: bytes) -> bytes:
    body = oui + bytes([oui_type]) + payload
    return bytes([0xDD, len(body)]) + body


def test_returns_dji_v2_tag_for_dji_oui():
    frame = _vendor_ie(b"\x60\x60\x1F", 0x09, b"\xaa\xbb")
    assert extract_drone_ie(frame) == ("dji_v2", b"\xaa\xbb")


def test_returns_astm_tag_for_astm_oui():
    frame = _vendor_ie(b"\xfa\x0b\xbc", 0x0D, b"\xcc\xdd")
    assert extract_drone_ie(frame) == ("astm_f3411", b"\xcc\xdd")


def test_returns_none_for_unknown_vendor():
    frame = _vendor_ie(b"\x11\x22\x33", 0x99, b"\xff")
    assert extract_drone_ie(frame) is None


def test_returns_none_when_truncated():
    # Element id + length declares 10 bytes, only 2 provided
    frame = bytes([0xDD, 10, 0x60, 0x60])
    assert extract_drone_ie(frame) is None


def test_handles_multiple_ies_finds_dji_after_others():
    other = bytes([0x00, 3, 0x41, 0x42, 0x43])  # SSID-shaped element
    dji = _vendor_ie(b"\x60\x60\x1F", 0x09, b"\x42")
    assert extract_drone_ie(other + dji) == ("dji_v2", b"\x42")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/decoder/test_ie_extract.py -v`
Expected: ImportError on `extract_drone_ie`.

- [ ] **Step 3: Rewrite `src/drone_detector/decoder/ie_extract.py`**

```python
"""Walk the IE list of an 802.11 frame body, return (protocol_tag, payload) or None."""

DJI_OUI = b"\x60\x60\x1F"
DJI_DRONEID_V2_OUI_TYPE = 0x09
ASTM_OUI = b"\xfa\x0b\xbc"
ASTM_F3411_OUI_TYPE = 0x0D
VENDOR_SPECIFIC_ELEMENT_ID = 0xDD


def extract_drone_ie(frame_body: bytes) -> tuple[str, bytes] | None:
    """Walk the IE list; return (tag, payload) for the first recognized vendor IE."""
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
            inner = bytes(frame_body[start + 4 : end])
            if oui == DJI_OUI and oui_type == DJI_DRONEID_V2_OUI_TYPE:
                return ("dji_v2", inner)
            if oui == ASTM_OUI and oui_type == ASTM_F3411_OUI_TYPE:
                return ("astm_f3411", inner)
        i = end
    return None
```

- [ ] **Step 4: Run tests**

Run: `uv run pytest tests/decoder/test_ie_extract.py -v`
Expected: All five tests PASS.

- [ ] **Step 5: Update pipeline to use the new signature (compile only, registry comes next)**

In `src/drone_detector/pipeline.py`, change:
```python
from drone_detector.decoder.ie_extract import extract_dji_ie
# ...
ie_payload = extract_dji_ie(frame_body)
if ie_payload is None:
    continue
```
to:
```python
from drone_detector.decoder.ie_extract import extract_drone_ie
# ...
match = extract_drone_ie(frame_body)
if match is None:
    continue
tag, ie_payload = match
if tag != "dji_v2":
    continue   # ASTM dispatch added by registry task
```

- [ ] **Step 6: Run full suite**

Run: `uv run pytest`
Expected: all green.

- [ ] **Step 7: Commit**

```bash
git add src tests
git commit -m "refactor(ie_extract): return (tag, payload) with DJI + ASTM support"
```

---

## Task 5: Decoder registry

**Files:**
- Create: `src/drone_detector/decoder/registry.py`
- Create: `tests/decoder/test_registry.py`

- [ ] **Step 1: Write failing registry tests**

Create `tests/decoder/test_registry.py`:
```python
import pytest

from drone_detector.decoder import registry


def test_dispatch_unknown_tag_raises():
    with pytest.raises(KeyError):
        registry.dispatch("not_a_protocol")


def test_dji_v2_registered():
    parser = registry.dispatch("dji_v2")
    assert callable(parser)


def test_astm_f3411_registered():
    parser = registry.dispatch("astm_f3411")
    assert callable(parser)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/decoder/test_registry.py -v`
Expected: ImportError on `registry`.

- [ ] **Step 3: Create the registry module**

`src/drone_detector/decoder/registry.py`:
```python
"""Dispatch table mapping a protocol tag to its parser function."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime

from drone_detector.decoder.astm_f3411 import parse_astm
from drone_detector.decoder.dji_droneid_v2 import parse_dji_droneid
from drone_detector.models import DroneReport

ParserFn = Callable[..., DroneReport]


_PARSERS: dict[str, ParserFn] = {
    "dji_v2": parse_dji_droneid,
    "astm_f3411": parse_astm,
}


def dispatch(tag: str) -> ParserFn:
    return _PARSERS[tag]


def parse(
    tag: str,
    payload: bytes,
    *,
    captured_at: datetime,
    rssi: int | None,
    raw_frame_hex: str,
) -> DroneReport:
    return dispatch(tag)(
        payload, captured_at=captured_at, rssi=rssi, raw_frame_hex=raw_frame_hex
    )
```

- [ ] **Step 4: Run tests — they will fail because `parse_astm` does not yet exist**

Run: `uv run pytest tests/decoder/test_registry.py -v`
Expected: ImportError. **We need a stub `parse_astm` so the import resolves.**

- [ ] **Step 5: Create stub ASTM parser to unblock the import**

Create `src/drone_detector/decoder/astm_f3411.py`:
```python
"""Stub. Real ctypes wrapper added in Task 7."""

from datetime import datetime

from drone_detector.models import DroneReport


class MalformedAstmError(ValueError):
    """Raised when an ASTM F3411 payload is too short or otherwise malformed."""


def parse_astm(
    payload: bytes,
    *,
    captured_at: datetime,
    rssi: int | None,
    raw_frame_hex: str,
) -> DroneReport:
    raise NotImplementedError("parse_astm is implemented in Task 7")
```

- [ ] **Step 6: Run registry tests**

Run: `uv run pytest tests/decoder/test_registry.py -v`
Expected: All three PASS.

- [ ] **Step 7: Commit**

```bash
git add src/drone_detector/decoder/registry.py \
        src/drone_detector/decoder/astm_f3411.py \
        tests/decoder/test_registry.py
git commit -m "feat(decoder): registry dispatch + ASTM stub"
```

---

## Task 6: Wire registry into pipeline

**Files:**
- Modify: `src/drone_detector/pipeline.py`
- Modify: `tests/test_pipeline.py`

- [ ] **Step 1: Add a failing pipeline test that exercises an ASTM IE**

Append to `tests/test_pipeline.py`:
```python
from scapy.layers.dot11 import Dot11, Dot11Beacon


class _FakeSource:
    """Iterable that yields a single hand-built scapy packet."""

    def __init__(self, pkt) -> None:
        self._pkt = pkt

    def __iter__(self):
        yield self._pkt


def _build_beacon_with_vendor_ie(oui: bytes, oui_type: int, payload: bytes):
    body = oui + bytes([oui_type]) + payload
    ie = bytes([0xDD, len(body)]) + body
    return Dot11(addr1="ff:ff:ff:ff:ff:ff") / Dot11Beacon() / ie


def test_pipeline_drops_astm_when_parser_unimplemented():
    """ASTM frames go to parse_astm; today it raises NotImplementedError.
    Pipeline must log and continue, not crash. Replaced by Task 7 real decode."""
    pkt = _build_beacon_with_vendor_ie(b"\xfa\x0b\xbc", 0x0D, b"\xaa\xbb\xcc")
    sink = RecordingSink()
    run_pipeline(
        source=_FakeSource(pkt),
        sinks=[sink],
        clock=lambda: datetime(2026, 5, 24, 12, 0, tzinfo=UTC),
    )
    assert sink.reports == []   # parser raised, no report emitted, loop survived
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_pipeline.py -v -k astm`
Expected: test fails — pipeline either errors or matches DJI only.

- [ ] **Step 3: Rewrite pipeline body to use the registry**

In `src/drone_detector/pipeline.py`, replace the parse block:
```python
from drone_detector.decoder import registry
from drone_detector.decoder.astm_f3411 import MalformedAstmError
from drone_detector.decoder.dji_droneid_v2 import MalformedDroneIDError
from drone_detector.decoder.ie_extract import extract_drone_ie
from drone_detector.decoder.radiotap import parse_radiotap
# ...
match = extract_drone_ie(frame_body)
if match is None:
    continue
tag, ie_payload = match
meta = parse_radiotap(packet)
try:
    report = registry.parse(
        tag,
        ie_payload,
        captured_at=clock(),
        rssi=meta.rssi,
        raw_frame_hex=bytes(packet).hex(),
    )
except (MalformedDroneIDError, MalformedAstmError, NotImplementedError) as exc:
    log.debug("dropping malformed/unsupported %s frame: %s", tag, exc)
    continue
```

- [ ] **Step 4: Run full suite**

Run: `uv run pytest`
Expected: all tests pass — DJI flow unchanged, ASTM frames are dropped without crashing.

- [ ] **Step 5: Commit**

```bash
git add src/drone_detector/pipeline.py tests/test_pipeline.py
git commit -m "feat(pipeline): dispatch via decoder registry"
```

---

## Task 7: ASTM ctypes wrapper — minimum decode of a Basic ID message

**Files:**
- Create: `tests/_fixture_builders/build_sample_astm.py`
- Create: `tests/fixtures/beacons/sample_astm_basic_id.bin`
- Modify: `src/drone_detector/decoder/astm_f3411.py`
- Create: `tests/decoder/test_astm_f3411.py`

- [ ] **Step 1: Build the Basic ID fixture**

Create `tests/_fixture_builders/build_sample_astm.py`:
```python
"""Hand-crafts ASTM F3411 message fixtures.

Reference: docs/astm_f3411_message_layouts.md (write a brief one if absent;
the libopendroneid headers in vendor/opendroneid-core-c/libopendroneid/opendroneid.h
are the source of truth)."""

from __future__ import annotations

from pathlib import Path

# ASTM F3411 message header: ProtocolVersion (high nibble) | MessageType (low nibble)
# Basic ID: MessageType=0, ProtocolVersion=2 => 0x02
# Body: IDType (1 byte) | UAType (1 byte) | UASID (20 bytes) | reserved (3 bytes)
# Total message = 25 bytes.

def build_basic_id() -> bytes:
    header = bytes([0x02])
    id_type = 1   # Serial Number
    ua_type = 1   # Aeroplane / fixed wing — pick any valid value
    uas_id = b"1581F5ABCDEF1234567" + b"\x00"  # 20 bytes total
    reserved = b"\x00" * 3
    return header + bytes([id_type, ua_type]) + uas_id + reserved


def main() -> None:
    out = Path("tests/fixtures/beacons/sample_astm_basic_id.bin")
    out.write_bytes(build_basic_id())
    print(f"wrote {out} ({out.stat().st_size}B)")


if __name__ == "__main__":
    main()
```

Run: `uv run python tests/_fixture_builders/build_sample_astm.py`
Expected: `wrote tests/fixtures/beacons/sample_astm_basic_id.bin (25B)`

- [ ] **Step 2: Write the failing ASTM parser test**

Create `tests/decoder/test_astm_f3411.py`:
```python
from datetime import UTC, datetime
from pathlib import Path

import pytest

from drone_detector.decoder.astm_f3411 import MalformedAstmError, parse_astm

FIXTURES = Path(__file__).parent.parent / "fixtures" / "beacons"


def test_parse_basic_id_returns_drone_report():
    payload = (FIXTURES / "sample_astm_basic_id.bin").read_bytes()
    r = parse_astm(
        payload,
        captured_at=datetime(2026, 5, 24, 12, 0, tzinfo=UTC),
        rssi=-50,
        raw_frame_hex="deadbeef",
    )
    assert r.protocol == "astm_f3411"
    assert r.astm_message_type == 0
    assert r.drone_serial.startswith("1581F5ABCDEF")


def test_parse_rejects_short_payload():
    with pytest.raises(MalformedAstmError):
        parse_astm(
            b"\x02\x01",
            captured_at=datetime(2026, 5, 24, 12, 0, tzinfo=UTC),
            rssi=None,
            raw_frame_hex="",
        )
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `uv run pytest tests/decoder/test_astm_f3411.py -v`
Expected: tests fail with `NotImplementedError` (stub) or import error.

- [ ] **Step 4: Inspect the libopendroneid header to get struct + function names**

Run: `head -200 vendor/opendroneid-core-c/libopendroneid/opendroneid.h`
Note the names of: `ODID_BasicID_data`, `ODID_BasicID_encoded`, `decodeBasicIDMessage`, `ODID_messagetype_t` enum values. Use the EXACT names you find in your wrapper.

- [ ] **Step 5: Implement the ctypes wrapper**

Replace `src/drone_detector/decoder/astm_f3411.py` with the full implementation. The wrapper:
1. Loads the library via `_resolve_lib_path()`
2. Declares `ODID_BasicID_data` and `ODID_Location_data` ctypes Structures matching the C structs (UAType, IDType, UASID buffer)
3. Reads the first byte to determine message type (high nibble = version, low nibble = type)
4. Calls the appropriate `decodeXxxMessage(&decoded, &encoded)` function
5. Returns a `DroneReport` with `protocol="astm_f3411"`, `astm_message_type=<type>`, fields projected from the decoded struct

```python
"""ctypes wrapper around libopendroneid for ASTM F3411 message decoding."""

from __future__ import annotations

import ctypes
from datetime import datetime
from pathlib import Path

from drone_detector.models import DroneReport


class MalformedAstmError(ValueError):
    pass


def _resolve_lib_path() -> str:
    pkg_lib = Path(__file__).parent.parent / "_lib"
    for name in ("libopendroneid.so", "libopendroneid.dylib"):
        candidate = pkg_lib / name
        if candidate.exists():
            return str(candidate)
    raise RuntimeError(
        f"libopendroneid not found in {pkg_lib}. Run `uv pip install -e .`."
    )


_LIB = ctypes.CDLL(_resolve_lib_path())


# Mirror ODID_BasicID_data from opendroneid.h. Cross-check field order!
class _ODID_BasicID_data(ctypes.Structure):
    _fields_ = [
        ("UAType", ctypes.c_int),
        ("IDType", ctypes.c_int),
        ("UASID", ctypes.c_char * 21),   # ODID_ID_SIZE + 1 NUL
    ]


_decodeBasicIDMessage = _LIB.decodeBasicIDMessage
_decodeBasicIDMessage.restype = ctypes.c_int
_decodeBasicIDMessage.argtypes = [
    ctypes.POINTER(_ODID_BasicID_data),
    ctypes.POINTER(ctypes.c_uint8 * 25),
]

ASTM_MIN_FRAME_BYTES = 25
ODID_SUCCESS = 0


def _message_type(payload: bytes) -> int:
    return payload[0] & 0x0F


def parse_astm(
    payload: bytes,
    *,
    captured_at: datetime,
    rssi: int | None,
    raw_frame_hex: str,
) -> DroneReport:
    if len(payload) < ASTM_MIN_FRAME_BYTES:
        raise MalformedAstmError(f"payload {len(payload)}B < minimum {ASTM_MIN_FRAME_BYTES}B")
    mtype = _message_type(payload)
    buf = (ctypes.c_uint8 * 25).from_buffer_copy(payload[:25])
    if mtype == 0:  # Basic ID
        decoded = _ODID_BasicID_data()
        rc = _decodeBasicIDMessage(ctypes.byref(decoded), ctypes.byref(buf))
        if rc != ODID_SUCCESS:
            raise MalformedAstmError(f"decodeBasicIDMessage rc={rc}")
        serial = decoded.UASID.decode("ascii", errors="replace").rstrip("\x00")
        return DroneReport(
            captured_at=captured_at,
            rssi=rssi,
            protocol="astm_f3411",
            raw_frame_hex=raw_frame_hex,
            drone_serial=serial,
            operator_id=None,
            drone_lat=None,
            drone_lon=None,
            drone_altitude_m=None,
            drone_height_m=None,
            drone_speed_ns_mps=None,
            drone_speed_ew_mps=None,
            drone_speed_ud_mps=None,
            drone_yaw_deg=None,
            pilot_lat=None,
            pilot_lon=None,
            home_lat=None,
            home_lon=None,
            astm_message_type=mtype,
            uuid_len=None,
            uuid=None,
        )
    raise MalformedAstmError(f"message type {mtype} not yet supported")
```

- [ ] **Step 6: Run ASTM parser tests**

Run: `uv run pytest tests/decoder/test_astm_f3411.py -v`
Expected: both tests PASS.

- [ ] **Step 7: Run full suite**

Run: `uv run pytest`
Expected: all green.

- [ ] **Step 8: Commit**

```bash
git add src/drone_detector/decoder/astm_f3411.py \
        tests/_fixture_builders/build_sample_astm.py \
        tests/fixtures/beacons/sample_astm_basic_id.bin \
        tests/decoder/test_astm_f3411.py
git commit -m "feat(decoder): ASTM F3411 Basic ID parser via libopendroneid ctypes"
```

---

## Task 8: Add Location message support to ASTM parser

**Files:**
- Modify: `tests/_fixture_builders/build_sample_astm.py`
- Create: `tests/fixtures/beacons/sample_astm_location.bin`
- Modify: `src/drone_detector/decoder/astm_f3411.py`
- Modify: `tests/decoder/test_astm_f3411.py`

- [ ] **Step 1: Extend the fixture builder**

Add to `tests/_fixture_builders/build_sample_astm.py`:
```python
import struct


def build_location() -> bytes:
    # MessageType=1, ProtocolVersion=2 => header byte 0x12
    header = bytes([0x12])
    status = 0x10        # operational
    track_dir = 90       # degrees
    speed = 50           # 0.25 m/s units => 12.5 m/s
    vert_speed = 0
    # lat/lon scaled by 1e7
    lat = int(13.7 * 1e7).to_bytes(4, "little", signed=True)
    lon = int(100.5 * 1e7).to_bytes(4, "little", signed=True)
    pressure_alt = struct.pack("<H", 0)
    geodetic_alt = struct.pack("<H", 0)
    height = struct.pack("<H", 100)  # 10.0 m at 0.5m units (spec dependent — confirm in header)
    horiz_acc = 0
    vert_acc = 0
    baro_acc = 0
    speed_acc = 0
    timestamp = struct.pack("<H", 0)
    ts_acc = 0
    reserved = 0
    body = (
        bytes([status, track_dir])
        + struct.pack("<bb", speed, vert_speed)
        + lat + lon
        + pressure_alt + geodetic_alt + height
        + bytes([(horiz_acc << 4) | vert_acc, (baro_acc << 4) | speed_acc])
        + timestamp + bytes([(ts_acc << 4) | reserved])
    )
    return (header + body).ljust(25, b"\x00")[:25]
```
Then extend `main()`:
```python
def main() -> None:
    out_dir = Path("tests/fixtures/beacons")
    (out_dir / "sample_astm_basic_id.bin").write_bytes(build_basic_id())
    (out_dir / "sample_astm_location.bin").write_bytes(build_location())
    print("wrote basic_id + location fixtures")
```
Run: `uv run python tests/_fixture_builders/build_sample_astm.py`

> **Implementer note:** The exact byte layout of `ODID_Location_encoded` is in `opendroneid.h`. Cross-check field widths if any test fails on decode rc — the spec packs several values into half-bytes. The fixture above is illustrative; adjust to match the header.

- [ ] **Step 2: Add a failing test for Location decode**

Append to `tests/decoder/test_astm_f3411.py`:
```python
def test_parse_location_returns_lat_lon():
    payload = (FIXTURES / "sample_astm_location.bin").read_bytes()
    r = parse_astm(
        payload,
        captured_at=datetime(2026, 5, 24, 12, 0, tzinfo=UTC),
        rssi=-60,
        raw_frame_hex="",
    )
    assert r.astm_message_type == 1
    assert r.drone_lat == pytest.approx(13.7, rel=1e-5)
    assert r.drone_lon == pytest.approx(100.5, rel=1e-5)
```

- [ ] **Step 3: Run test to verify it fails**

Run: `uv run pytest tests/decoder/test_astm_f3411.py::test_parse_location_returns_lat_lon -v`
Expected: `MalformedAstmError("message type 1 not yet supported")`.

- [ ] **Step 4: Extend the parser with Location handling**

In `src/drone_detector/decoder/astm_f3411.py`, add after the BasicID block:
```python
class _ODID_Location_data(ctypes.Structure):
    _fields_ = [
        ("Status", ctypes.c_int),
        ("Direction", ctypes.c_float),
        ("SpeedHorizontal", ctypes.c_float),
        ("SpeedVertical", ctypes.c_float),
        ("Latitude", ctypes.c_double),
        ("Longitude", ctypes.c_double),
        ("AltitudeBaro", ctypes.c_float),
        ("AltitudeGeo", ctypes.c_float),
        ("HeightType", ctypes.c_int),
        ("Height", ctypes.c_float),
        ("HorizAccuracy", ctypes.c_int),
        ("VertAccuracy", ctypes.c_int),
        ("BaroAccuracy", ctypes.c_int),
        ("SpeedAccuracy", ctypes.c_int),
        ("TSAccuracy", ctypes.c_int),
        ("TimeStamp", ctypes.c_float),
    ]


_decodeLocationMessage = _LIB.decodeLocationMessage
_decodeLocationMessage.restype = ctypes.c_int
_decodeLocationMessage.argtypes = [
    ctypes.POINTER(_ODID_Location_data),
    ctypes.POINTER(ctypes.c_uint8 * 25),
]
```
Then in `parse_astm`, add a branch:
```python
if mtype == 1:
    decoded = _ODID_Location_data()
    rc = _decodeLocationMessage(ctypes.byref(decoded), ctypes.byref(buf))
    if rc != ODID_SUCCESS:
        raise MalformedAstmError(f"decodeLocationMessage rc={rc}")
    return DroneReport(
        captured_at=captured_at,
        rssi=rssi,
        protocol="astm_f3411",
        raw_frame_hex=raw_frame_hex,
        drone_serial="",
        operator_id=None,
        drone_lat=decoded.Latitude or None,
        drone_lon=decoded.Longitude or None,
        drone_altitude_m=decoded.AltitudeGeo or None,
        drone_height_m=decoded.Height or None,
        drone_speed_ns_mps=None,
        drone_speed_ew_mps=None,
        drone_speed_ud_mps=decoded.SpeedVertical or None,
        drone_yaw_deg=decoded.Direction or None,
        pilot_lat=None,
        pilot_lon=None,
        home_lat=None,
        home_lon=None,
        astm_message_type=mtype,
        uuid_len=None,
        uuid=None,
    )
```

> **Implementer note:** field names in the actual `ODID_Location_data` struct (verify in `opendroneid.h`) may differ — copy them exactly. The lat/lon conversion is done by libopendroneid; just project the decoded doubles. Use `or None` instead of explicit zero-check since the C library already returns NaN/zero for unset values; treat `0.0` as `None` matching the existing DJI convention.

- [ ] **Step 5: Run Location test**

Run: `uv run pytest tests/decoder/test_astm_f3411.py -v`
Expected: all PASS.

- [ ] **Step 6: Run full suite**

Run: `uv run pytest`
Expected: all green.

- [ ] **Step 7: Commit**

```bash
git add src/drone_detector/decoder/astm_f3411.py \
        tests/_fixture_builders/build_sample_astm.py \
        tests/fixtures/beacons/sample_astm_location.bin \
        tests/decoder/test_astm_f3411.py
git commit -m "feat(decoder): ASTM Location message decode"
```

---

## Task 9: Mixed-protocol PCAP integration test

**Files:**
- Create: `tests/_fixture_builders/build_mixed_protocols_pcap.py`
- Create: `tests/fixtures/pcaps/mixed_protocols.pcap`
- Create: `tests/fixtures/golden/mixed_protocols.expected.jsonl`
- Modify: `tests/test_integration_replay.py`

- [ ] **Step 1: Write the pcap builder**

Create `tests/_fixture_builders/build_mixed_protocols_pcap.py`. Use the existing `tests/_fixture_builders/build_two_beacons_pcap.py` as the template — same scapy `wrpcap` approach. The new builder produces 3 beacons in order:
1. Plain beacon (no vendor IE) — should be ignored
2. DJI DroneID v2 beacon (load payload from `tests/fixtures/beacons/sample_v2.bin`)
3. ASTM F3411 Basic ID beacon (load payload from `tests/fixtures/beacons/sample_astm_basic_id.bin`)

Wrap each ASTM payload in the IE envelope: `\xdd\x{len}\xfa\x0b\xbc\x0d<payload>`.

Run: `uv run python tests/_fixture_builders/build_mixed_protocols_pcap.py`
Expected: `tests/fixtures/pcaps/mixed_protocols.pcap` exists.

- [ ] **Step 2: Add the integration test (golden file generated on first run)**

Append to `tests/test_integration_replay.py`:
```python
def test_replay_mixed_protocols_matches_golden(tmp_path: Path, fixtures_dir: Path) -> None:
    pcap = fixtures_dir / "pcaps" / "mixed_protocols.pcap"
    out = tmp_path / "out.jsonl"

    sink = JsonlFileSink(out, dedup_window_s=0)
    with FilePcapSource(pcap) as source:
        run_pipeline(
            source=source,
            sinks=[sink],
            clock=lambda: datetime(2026, 5, 24, 10, 0, 0, tzinfo=UTC),
        )
    sink.close()

    actual = [json.loads(line) for line in out.read_text().splitlines()]
    expected_path = fixtures_dir / "golden" / "mixed_protocols.expected.jsonl"
    expected = [json.loads(line) for line in expected_path.read_text().splitlines()]
    assert actual == expected
```
This mirrors the existing `test_replay_matches_golden` pattern — same `FilePcapSource` + `JsonlFileSink(dedup_window_s=0)` + fixed `clock` for deterministic timestamps.

- [ ] **Step 3: Generate the golden file**

The test will fail the first time because the golden file does not exist yet. Run the test once to produce a real `out.jsonl` from the pipeline, then copy that into place:
```bash
uv run pytest tests/test_integration_replay.py::test_replay_mixed_protocols_matches_golden -v
# the test fails on assert; find the tmp_path it used in the test output
# Easier: run the pipeline manually with a fixed clock:
uv run python -c "
from datetime import UTC, datetime
from pathlib import Path
from drone_detector.pipeline import run_pipeline
from drone_detector.sinks.jsonl_sink import JsonlFileSink
from drone_detector.sources.file_pcap import FilePcapSource

out = Path('tests/fixtures/golden/mixed_protocols.expected.jsonl')
sink = JsonlFileSink(out, dedup_window_s=0)
with FilePcapSource(Path('tests/fixtures/pcaps/mixed_protocols.pcap')) as src:
    run_pipeline(source=src, sinks=[sink],
                 clock=lambda: datetime(2026, 5, 24, 10, 0, 0, tzinfo=UTC))
sink.close()
print(out.read_text())
"
```
Inspect the printed JSONL: must be exactly 2 lines (DJI + ASTM, in pcap order). If counts differ, fix the pcap builder before continuing.

- [ ] **Step 4: Run integration test**

Run: `uv run pytest tests/test_integration_replay.py -v`
Expected: both `test_two_beacons` and `test_replay_mixed_protocols_matches_golden` PASS.

- [ ] **Step 5: Run full suite + coverage gate**

Run: `uv run pytest --cov=drone_detector --cov-fail-under=80`
Expected: all green, coverage ≥ 80%.

- [ ] **Step 6: Commit**

```bash
git add tests/_fixture_builders/build_mixed_protocols_pcap.py \
        tests/fixtures/pcaps/mixed_protocols.pcap \
        tests/fixtures/golden/mixed_protocols.expected.jsonl \
        tests/test_integration_replay.py
git commit -m "test: integration replay of mixed DJI+ASTM pcap"
```

---

## Task 10: ChannelHopper daemon-thread class

**Files:**
- Create: `src/drone_detector/capture/__init__.py`
- Create: `src/drone_detector/capture/hopper.py`
- Create: `tests/capture/__init__.py`
- Create: `tests/capture/test_hopper.py`

- [ ] **Step 1: Write failing hopper tests**

Create `tests/capture/__init__.py` (empty file).

Create `tests/capture/test_hopper.py`:
```python
import threading
import time

from drone_detector.capture.hopper import ChannelHopper


def test_hopper_cycles_through_channels():
    calls: list[tuple[str, int]] = []
    h = ChannelHopper(
        iface="wlan1",
        channels=[1, 6, 11],
        dwell_ms=10,
        set_channel_fn=lambda iface, ch: calls.append((iface, ch)),
    )
    h.start()
    time.sleep(0.08)   # ~8 ticks
    h.stop()
    h.join(timeout=1.0)
    # First three calls should be channels 1,6,11 in order
    seen_channels = [ch for _, ch in calls[:3]]
    assert seen_channels == [1, 6, 11]
    # Should have wrapped around at least once
    assert len(calls) >= 4
    assert all(iface == "wlan1" for iface, _ in calls)


def test_hopper_stop_is_idempotent():
    h = ChannelHopper(
        iface="wlan1",
        channels=[1],
        dwell_ms=10,
        set_channel_fn=lambda i, c: None,
    )
    h.start()
    h.stop()
    h.stop()  # second call must not raise
    h.join(timeout=1.0)


def test_hopper_swallows_set_channel_errors():
    def failing(_iface: str, _ch: int) -> None:
        raise RuntimeError("driver wedged")

    h = ChannelHopper(
        iface="wlan1",
        channels=[1, 6],
        dwell_ms=10,
        set_channel_fn=failing,
    )
    h.start()
    time.sleep(0.05)
    assert h.is_alive()   # did not crash on the exception
    h.stop()
    h.join(timeout=1.0)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/capture/test_hopper.py -v`
Expected: ImportError on `drone_detector.capture.hopper`.

- [ ] **Step 3: Implement the hopper**

Create `src/drone_detector/capture/__init__.py` (empty).

Create `src/drone_detector/capture/hopper.py`:
```python
"""Daemon-thread channel hopper. Calls a user-provided set_channel_fn on a fixed cadence."""

from __future__ import annotations

import logging
import threading
import time
from collections.abc import Callable

log = logging.getLogger(__name__)

SetChannelFn = Callable[[str, int], None]


class ChannelHopper(threading.Thread):
    def __init__(
        self,
        *,
        iface: str,
        channels: list[int],
        dwell_ms: int,
        set_channel_fn: SetChannelFn,
    ) -> None:
        super().__init__(name=f"hopper-{iface}", daemon=True)
        if not channels:
            raise ValueError("channels must be non-empty")
        if dwell_ms <= 0:
            raise ValueError("dwell_ms must be positive")
        self._iface = iface
        self._channels = list(channels)
        self._dwell_s = dwell_ms / 1000.0
        self._set_channel = set_channel_fn
        self._stop_event = threading.Event()

    def stop(self) -> None:
        self._stop_event.set()

    def run(self) -> None:
        i = 0
        while not self._stop_event.is_set():
            ch = self._channels[i % len(self._channels)]
            try:
                self._set_channel(self._iface, ch)
            except Exception:
                log.warning("set_channel %s -> %d failed", self._iface, ch, exc_info=True)
            i += 1
            # Sleep in small slices so stop() is responsive
            slept = 0.0
            while slept < self._dwell_s and not self._stop_event.is_set():
                tick = min(0.05, self._dwell_s - slept)
                time.sleep(tick)
                slept += tick
```

- [ ] **Step 4: Run hopper tests**

Run: `uv run pytest tests/capture/test_hopper.py -v`
Expected: all three PASS.

- [ ] **Step 5: Run full suite**

Run: `uv run pytest`
Expected: all green.

- [ ] **Step 6: Commit**

```bash
git add src/drone_detector/capture tests/capture
git commit -m "feat(capture): ChannelHopper daemon thread"
```

---

## Task 11: iw subprocess backend

**Files:**
- Create: `src/drone_detector/capture/iw_backend.py`
- Modify: `pyproject.toml` (mark `iw_backend` excluded from macOS coverage)

- [ ] **Step 1: Write the iw_backend module**

Create `src/drone_detector/capture/iw_backend.py`:
```python
"""Linux-only backend that wraps `iw dev <iface> set channel <n>` via subprocess.

Not unit-tested on macOS — exercised by Pi smoke script and live `listen` runs.
"""

from __future__ import annotations

import subprocess


class IwError(RuntimeError):
    pass


def set_channel(iface: str, channel: int) -> None:
    proc = subprocess.run(
        ["iw", "dev", iface, "set", "channel", str(channel)],
        check=False,
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        raise IwError(
            f"iw set channel failed for {iface}/{channel}: "
            f"rc={proc.returncode} stderr={proc.stderr.strip()}"
        )


def link_down_up(iface: str) -> None:
    """Reset the interface — used by the reset-on-stall flow."""
    for action in ("down", "up"):
        proc = subprocess.run(
            ["ip", "link", "set", iface, action],
            check=False,
            capture_output=True,
            text=True,
        )
        if proc.returncode != 0:
            raise IwError(
                f"ip link set {iface} {action} failed: "
                f"rc={proc.returncode} stderr={proc.stderr.strip()}"
            )
```

- [ ] **Step 2: Add a coverage-omit rule (macOS skips Linux-only modules)**

In `pyproject.toml`, under `[tool.coverage.run]` add:
```toml
omit = ["src/drone_detector/capture/iw_backend.py"]
```

- [ ] **Step 3: Run full suite to confirm coverage still passes**

Run: `uv run pytest --cov=drone_detector --cov-fail-under=80`
Expected: all green.

- [ ] **Step 4: Commit**

```bash
git add src/drone_detector/capture/iw_backend.py pyproject.toml
git commit -m "feat(capture): iw subprocess backend for channel + link reset"
```

---

## Task 12: Wire ChannelHopper into the `listen` subcommand

**Files:**
- Modify: `src/drone_detector/cli.py`
- Modify: `tests/test_cli.py` (add a unit test that confirms `listen --no-hop` doesn't start a hopper)

- [ ] **Step 1: Write the failing CLI test**

Append to `tests/test_cli.py`:
```python
from unittest.mock import patch

from typer.testing import CliRunner

from drone_detector.cli import app


def test_listen_no_hop_does_not_start_hopper():
    runner = CliRunner()
    with patch("drone_detector.cli.ChannelHopper") as mock_hop, \
         patch("drone_detector.cli.LivePcapSource") as mock_src, \
         patch("drone_detector.cli.run_pipeline") as mock_run:
        mock_run.return_value = None
        mock_src.return_value.close.return_value = None
        result = runner.invoke(app, ["listen", "--iface", "wlan1", "--no-hop"])
        assert result.exit_code == 0
        mock_hop.assert_not_called()


def test_listen_hop_starts_hopper_and_stops_it():
    runner = CliRunner()
    started = {"value": False}
    stopped = {"value": False}

    class FakeHopper:
        def __init__(self, **kwargs):
            pass

        def start(self):
            started["value"] = True

        def stop(self):
            stopped["value"] = True

        def join(self, timeout=None):
            pass

    with patch("drone_detector.cli.ChannelHopper", FakeHopper), \
         patch("drone_detector.cli.LivePcapSource") as mock_src, \
         patch("drone_detector.cli.run_pipeline") as mock_run:
        mock_run.return_value = None
        mock_src.return_value.close.return_value = None
        result = runner.invoke(
            app,
            ["listen", "--iface", "wlan1", "--hop", "--channels", "1,6", "--dwell-ms", "100"],
        )
        assert result.exit_code == 0
        assert started["value"]
        assert stopped["value"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_cli.py -v -k listen`
Expected: ImportError on `ChannelHopper` from cli.

- [ ] **Step 3: Update the `listen` command**

In `src/drone_detector/cli.py`:
- Add imports at the top:
  ```python
  from drone_detector.capture.hopper import ChannelHopper
  from drone_detector.capture.iw_backend import set_channel
  ```
- Replace the `listen` function:
  ```python
  @app.command()
  def listen(
      iface: str = typer.Option(..., "--iface", help="Monitor-mode WiFi interface (Linux)"),  # noqa: B008
      out: Path | None = typer.Option(Path("detections.jsonl"), "--out"),  # noqa: B008
      hop: bool = typer.Option(True, "--hop/--no-hop", help="Cycle channels while listening"),  # noqa: B008
      channels: str = typer.Option(
          "1,6,11,36,40,44,149,153,157,161",
          "--channels",
          help="Comma-separated channel list",
      ),  # noqa: B008
      dwell_ms: int = typer.Option(200, "--dwell-ms"),  # noqa: B008
      reset_on_stall: int = typer.Option(  # noqa: B008
          20,
          "--reset-on-stall",
          help="ip link down/up after N consecutive empty hops; 0 to disable",
      ),
  ) -> None:
      """Live-capture WiFi RemoteID beacons from a monitor-mode interface."""
      sinks = _build_sinks(out)
      source = LivePcapSource(iface=iface)
      hopper: ChannelHopper | None = None
      if hop:
          ch_list = [int(c.strip()) for c in channels.split(",") if c.strip()]
          hopper = ChannelHopper(
              iface=iface,
              channels=ch_list,
              dwell_ms=dwell_ms,
              set_channel_fn=set_channel,
          )
          hopper.start()
      try:
          run_pipeline(source=source, sinks=sinks)
      finally:
          if hopper is not None:
              hopper.stop()
              hopper.join(timeout=1.0)
          source.close()
          for s in sinks:
              s.close()
  ```
- Also remove the now-unused `subprocess`/`time` imports if the `hop` subcommand is the only remaining user; keep them if `hop` still uses them.

- [ ] **Step 4: Run CLI tests**

Run: `uv run pytest tests/test_cli.py -v`
Expected: all PASS.

- [ ] **Step 5: Run full suite**

Run: `uv run pytest`
Expected: all green.

- [ ] **Step 6: Commit**

```bash
git add src/drone_detector/cli.py tests/test_cli.py
git commit -m "feat(cli): listen owns ChannelHopper with --hop/--no-hop/--channels/--dwell-ms"
```

---

## Task 13: Reset-on-stall driver-wedge mitigation

**Files:**
- Modify: `src/drone_detector/capture/hopper.py`
- Modify: `tests/capture/test_hopper.py`
- Modify: `src/drone_detector/cli.py` (already wired in Task 12; just pass the callback)

- [ ] **Step 1: Write a failing test for reset-on-stall**

Append to `tests/capture/test_hopper.py`:
```python
def test_hopper_reset_after_n_consecutive_empty_hops():
    resets: list[str] = []
    h = ChannelHopper(
        iface="wlan1",
        channels=[1, 6],
        dwell_ms=10,
        set_channel_fn=lambda i, c: None,
        reset_on_stall=2,
        reset_fn=lambda iface: resets.append(iface),
    )
    h.start()
    time.sleep(0.06)   # ~6 hops, no notifications => should trigger ~3 resets
    h.stop()
    h.join(timeout=1.0)
    assert len(resets) >= 1
    assert resets[0] == "wlan1"


def test_hopper_reset_not_triggered_when_notified():
    resets: list[str] = []
    h = ChannelHopper(
        iface="wlan1",
        channels=[1, 6],
        dwell_ms=10,
        set_channel_fn=lambda i, c: None,
        reset_on_stall=2,
        reset_fn=lambda iface: resets.append(iface),
    )
    h.start()
    for _ in range(6):
        h.notify_packet_seen()   # external signal that frames are arriving
        time.sleep(0.01)
    h.stop()
    h.join(timeout=1.0)
    assert resets == []
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/capture/test_hopper.py -v -k reset`
Expected: TypeError on unknown kwargs `reset_on_stall` / `reset_fn`.

- [ ] **Step 3: Extend the hopper**

In `src/drone_detector/capture/hopper.py`:
- Add params `reset_on_stall: int = 0` and `reset_fn: Callable[[str], None] | None = None` to `__init__`
- Add `self._empty_hops = 0` and `self._reset_on_stall = reset_on_stall` + `self._reset_fn = reset_fn`
- Add method `notify_packet_seen(self)` that resets `self._empty_hops = 0`
- In `run()`, after each successful `set_channel`:
  ```python
  self._empty_hops += 1
  if self._reset_on_stall and self._empty_hops >= self._reset_on_stall and self._reset_fn:
      try:
          self._reset_fn(self._iface)
      except Exception:
          log.warning("reset_fn failed for %s", self._iface, exc_info=True)
      self._empty_hops = 0
  ```

- [ ] **Step 4: Run hopper tests**

Run: `uv run pytest tests/capture/test_hopper.py -v`
Expected: all PASS.

- [ ] **Step 5: Wire the reset path in CLI**

In `src/drone_detector/cli.py`, where `ChannelHopper` is constructed:
```python
from drone_detector.capture.iw_backend import link_down_up, set_channel
# ...
hopper = ChannelHopper(
    iface=iface,
    channels=ch_list,
    dwell_ms=dwell_ms,
    set_channel_fn=set_channel,
    reset_on_stall=reset_on_stall,
    reset_fn=link_down_up if reset_on_stall > 0 else None,
)
```

Also wire `notify_packet_seen` via a tiny sink wrapper. In `src/drone_detector/cli.py`, define just above the `listen` function:
```python
class _HopperNotifySink:
    """Sink wrapper: forwards report to inner sinks AND tells the hopper a frame arrived."""

    def __init__(self, inner: list[ReportSink], hopper: ChannelHopper) -> None:
        self._inner = inner
        self._hopper = hopper

    def write(self, report) -> None:
        self._hopper.notify_packet_seen()
        for s in self._inner:
            try:
                s.write(report)
            except Exception:
                pass  # pipeline already isolates sink errors; mirror that here

    def close(self) -> None:
        for s in self._inner:
            s.close()
```
Then in the `listen` body, when `hopper is not None` after start:
```python
sinks = [_HopperNotifySink(sinks, hopper)]   # replace the list with the wrapper
```
The wrapper presents the same `ReportSink` shape to `run_pipeline`, and notifies the hopper exactly once per decoded report.

- [ ] **Step 6: Run full suite**

Run: `uv run pytest`
Expected: all green.

- [ ] **Step 7: Commit**

```bash
git add src/drone_detector/capture/hopper.py \
        src/drone_detector/cli.py \
        tests/capture/test_hopper.py
git commit -m "feat(capture): reset-on-stall driver-wedge mitigation"
```

---

## Task 14: Pi smoke script + README update

**Files:**
- Create: `scripts/pi_hop_smoke.sh`
- Modify: `README.md`

- [ ] **Step 1: Write the Pi smoke script**

Create `scripts/pi_hop_smoke.sh`:
```bash
#!/usr/bin/env bash
# Pi-only smoke test: confirm ChannelHopper actually changes the channel.
# Usage: scripts/pi_hop_smoke.sh <iface>
set -euo pipefail
iface="${1:?usage: $0 <iface>}"

echo "Setting $iface to monitor mode..."
sudo ip link set "$iface" down
sudo iw dev "$iface" set type monitor
sudo ip link set "$iface" up

echo "Channels to test: 1 6 11 36 149"
for ch in 1 6 11 36 149; do
    sudo iw dev "$iface" set channel "$ch"
    actual=$(iw dev "$iface" info | awk '/channel/ {print $2; exit}')
    if [[ "$actual" == "$ch" ]]; then
        echo "ch=$ch  OK"
    else
        echo "ch=$ch  FAIL (got '$actual')"
        exit 1
    fi
    sleep 0.2
done
echo "All channel transitions succeeded."
```
Run: `chmod +x scripts/pi_hop_smoke.sh`

- [ ] **Step 2: Update the README**

In `README.md`, add or update:
- Under **Usage**, document the new `listen` flags:
  ```
  drone-detector listen --iface wlan1 \
      --hop --channels 1,6,11,36,40,44,149,153,157,161 \
      --dwell-ms 200 \
      --reset-on-stall 20
  ```
- Under **Hardware**, note the Pi 5 + Tenda U10 combination
- Under **Build**, mention the submodule and uv install steps:
  ```bash
  git clone --recurse-submodules <repo>
  uv pip install -e .
  ```
- Under **Test**, add the Pi smoke script invocation
- Under **Field test**, document the **drone must be armed** requirement

- [ ] **Step 3: Run the suite one more time**

Run: `uv run pytest --cov=drone_detector --cov-fail-under=80`
Expected: all green, ≥ 80% coverage.

- [ ] **Step 4: Commit**

```bash
git add scripts/pi_hop_smoke.sh README.md
git commit -m "docs+scripts: Pi hop smoke script + README updates for hop/ASTM"
```

---

## Task 15: Field validation on the Pi (manual)

**Not a code task — a deploy + run script.**

- [ ] **Step 1: Push to a feature branch (only when user explicitly OKs)**

Wait for explicit user approval before any `git push`. The user's memory is clear: local commits OK, push always needs permission.

- [ ] **Step 2: On the Pi, pull and rebuild**

```bash
ssh deardevx@192.168.0.128 \
  'cd ~/drone_detector && git pull && git submodule update --init --recursive && uv pip install -e .'
```

- [ ] **Step 3: Run the smoke script**

```bash
ssh deardevx@192.168.0.128 'cd ~/drone_detector && scripts/pi_hop_smoke.sh wlan1'
```
Expected: every channel transition reports `OK`.

- [ ] **Step 4: Live capture with Air 3S armed**

```bash
ssh deardevx@192.168.0.128 \
  'cd ~/drone_detector && sudo uv run drone-detector listen --iface wlan1 \
      --out detections.jsonl'
```
Power on the Air 3S + RC, **arm the drone (spin motors)** outdoors. Watch stdout for a `DroneReport(protocol="dji_v2", drone_serial="...")` within ~3 seconds. Stop with Ctrl+C.

- [ ] **Step 5: Tag the release**

```bash
git tag v0.2.0 && git log -1
```
(Push the tag only on explicit user approval.)

---

## Coverage & quality gates (after each task)

- `uv run pytest --cov=drone_detector --cov-fail-under=80`
- `uv run ruff check src tests`
- `uv run mypy src`

If any gate fails, fix before committing.
