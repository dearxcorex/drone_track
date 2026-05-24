"""Builds ASTM F3411 Basic ID fixture using libopendroneid's own encoder.

Using encodeBasicIDMessage guarantees the fixture bytes exactly match what
decodeBasicIDMessage expects — no manual byte-layout guessing required.
"""

from __future__ import annotations

import ctypes
from pathlib import Path


def _resolve_lib() -> ctypes.CDLL:
    pkg_lib = Path(__file__).parent.parent.parent / "src" / "drone_detector" / "_lib"
    for name in ("libopendroneid.dylib", "libopendroneid.so"):
        candidate = pkg_lib / name
        if candidate.exists():
            return ctypes.CDLL(str(candidate))
    raise RuntimeError(f"libopendroneid not found in {pkg_lib}")


# ODID_BasicID_data: UAType (int), IDType (int), UASID (char[21])
class _ODID_BasicID_data(ctypes.Structure):
    _fields_ = [
        ("UAType", ctypes.c_int),
        ("IDType", ctypes.c_int),
        ("UASID", ctypes.c_char * 21),
    ]


# ODID_BasicID_encoded (packed): 25 bytes total
class _ODID_BasicID_encoded(ctypes.Structure):
    _pack_ = 1
    _fields_ = [
        ("header", ctypes.c_uint8),   # ProtoVersion(4)|MessageType(4)
        ("type_fields", ctypes.c_uint8),  # UAType(4)|IDType(4)
        ("UASID", ctypes.c_char * 20),
        ("Reserved", ctypes.c_char * 3),
    ]


def build_basic_id() -> bytes:
    lib = _resolve_lib()

    encode_fn = lib.encodeBasicIDMessage
    encode_fn.restype = ctypes.c_int
    encode_fn.argtypes = [
        ctypes.POINTER(_ODID_BasicID_encoded),
        ctypes.POINTER(_ODID_BasicID_data),
    ]

    in_data = _ODID_BasicID_data()
    in_data.UAType = 1   # ODID_UATYPE_AEROPLANE
    in_data.IDType = 1   # ODID_IDTYPE_SERIAL_NUMBER
    in_data.UASID = b"1581F5ABCDEF1234567"  # 19 chars + implicit NUL = 20 bytes

    encoded = _ODID_BasicID_encoded()
    rc = encode_fn(ctypes.byref(encoded), ctypes.byref(in_data))
    if rc != 0:
        raise RuntimeError(f"encodeBasicIDMessage returned {rc}")

    raw = bytes(encoded)
    assert len(raw) == 25, f"Expected 25 bytes, got {len(raw)}"
    return raw


def main() -> None:
    out = Path("tests/fixtures/beacons/sample_astm_basic_id.bin")
    data = build_basic_id()
    out.write_bytes(data)
    print(f"wrote {out} ({out.stat().st_size}B)")
    # Show hex for debugging
    print(f"hex: {data.hex()}")


if __name__ == "__main__":
    main()
