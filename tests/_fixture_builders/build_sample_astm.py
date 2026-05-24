"""Builds ASTM F3411 Basic ID and Location fixtures using libopendroneid's own encoder.

Using encode*Message guarantees the fixture bytes exactly match what
decode*Message expects — no manual byte-layout guessing required.
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


# ODID_Location_data field order verified against opendroneid.h lines 295-312.
# All enum fields use c_int (C enums are int-sized).
class _ODID_Location_data(ctypes.Structure):
    _fields_ = [
        ("Status", ctypes.c_int),           # ODID_status_t (enum -> int)
        ("Direction", ctypes.c_float),
        ("SpeedHorizontal", ctypes.c_float),
        ("SpeedVertical", ctypes.c_float),
        ("Latitude", ctypes.c_double),
        ("Longitude", ctypes.c_double),
        ("AltitudeBaro", ctypes.c_float),
        ("AltitudeGeo", ctypes.c_float),
        ("HeightType", ctypes.c_int),       # ODID_Height_reference_t (enum -> int)
        ("Height", ctypes.c_float),
        ("HorizAccuracy", ctypes.c_int),    # ODID_Horizontal_accuracy_t (enum -> int)
        ("VertAccuracy", ctypes.c_int),     # ODID_Vertical_accuracy_t (enum -> int)
        ("BaroAccuracy", ctypes.c_int),     # ODID_Vertical_accuracy_t (enum -> int)
        ("SpeedAccuracy", ctypes.c_int),    # ODID_Speed_accuracy_t (enum -> int)
        ("TSAccuracy", ctypes.c_int),       # ODID_Timestamp_accuracy_t (enum -> int)
        ("TimeStamp", ctypes.c_float),
    ]


# ODID_Location_encoded (packed): 25 bytes total
class _ODID_Location_encoded(ctypes.Structure):
    _pack_ = 1
    _fields_ = [
        ("raw", ctypes.c_uint8 * 25),
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


def build_location() -> bytes:
    lib = _resolve_lib()

    encode_fn = lib.encodeLocationMessage
    encode_fn.restype = ctypes.c_int
    encode_fn.argtypes = [
        ctypes.POINTER(_ODID_Location_encoded),
        ctypes.POINTER(_ODID_Location_data),
    ]

    in_data = _ODID_Location_data()
    in_data.Status = 2              # ODID_STATUS_AIRBORNE
    in_data.Direction = 90.0        # degrees (East)
    in_data.SpeedHorizontal = 5.0   # m/s
    in_data.SpeedVertical = 0.5     # m/s
    in_data.Latitude = 13.7
    in_data.Longitude = 100.5
    in_data.AltitudeBaro = 50.0     # metres
    in_data.AltitudeGeo = 55.0      # metres
    in_data.HeightType = 0          # ODID_HEIGHT_REF_OVER_TAKEOFF
    in_data.Height = 30.0           # metres
    in_data.HorizAccuracy = 5       # some enum value
    in_data.VertAccuracy = 3
    in_data.BaroAccuracy = 3
    in_data.SpeedAccuracy = 2
    in_data.TSAccuracy = 1
    in_data.TimeStamp = 120.5       # seconds after full hour

    encoded = _ODID_Location_encoded()
    rc = encode_fn(ctypes.byref(encoded), ctypes.byref(in_data))
    if rc != 0:
        raise RuntimeError(f"encodeLocationMessage returned {rc}")

    raw = bytes(encoded)
    assert len(raw) == 25, f"Expected 25 bytes, got {len(raw)}"
    return raw


def main() -> None:
    out_dir = Path("tests/fixtures/beacons")
    basic_id_data = build_basic_id()
    (out_dir / "sample_astm_basic_id.bin").write_bytes(basic_id_data)
    print(f"wrote sample_astm_basic_id.bin ({len(basic_id_data)}B): {basic_id_data.hex()}")

    location_data = build_location()
    (out_dir / "sample_astm_location.bin").write_bytes(location_data)
    print(f"wrote sample_astm_location.bin ({len(location_data)}B): {location_data.hex()}")


if __name__ == "__main__":
    main()
