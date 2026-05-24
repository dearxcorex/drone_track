"""ctypes wrapper around libopendroneid for ASTM F3411 message decoding."""

from __future__ import annotations

import ctypes
from datetime import datetime
from pathlib import Path

from drone_detector.models import DroneReport


class MalformedAstmError(ValueError):
    """Raised when an ASTM F3411 payload is too short or otherwise malformed."""


def _resolve_lib_path() -> str:
    pkg_lib = Path(__file__).parent.parent / "_lib"
    for name in ("libopendroneid.dylib", "libopendroneid.so"):
        candidate = pkg_lib / name
        if candidate.exists():
            return str(candidate)
    raise RuntimeError(
        f"libopendroneid not found in {pkg_lib}. Run `uv pip install -e .`."
    )


_LIB = ctypes.CDLL(_resolve_lib_path())


# Mirror ODID_BasicID_data from opendroneid.h (field order verified against header).
# struct ODID_BasicID_data {
#     ODID_uatype_t UAType;   -- enum (underlying int)
#     ODID_idtype_t IDType;   -- enum (underlying int)
#     char UASID[ODID_ID_SIZE+1]; -- char[21]  (20 + 1 NUL)
# }
class _ODID_BasicID_data(ctypes.Structure):
    _fields_ = [
        ("UAType", ctypes.c_int),
        ("IDType", ctypes.c_int),
        ("UASID", ctypes.c_char * 21),  # ODID_ID_SIZE(20) + 1 NUL byte
    ]


# ODID_BasicID_encoded is __packed__ at 25 bytes.
# We pass the raw payload buffer directly — the C library reads it as-is.
_decodeBasicIDMessage = _LIB.decodeBasicIDMessage
_decodeBasicIDMessage.restype = ctypes.c_int
_decodeBasicIDMessage.argtypes = [
    ctypes.POINTER(_ODID_BasicID_data),
    ctypes.POINTER(ctypes.c_uint8 * 25),
]

ASTM_MIN_FRAME_BYTES = 25
ODID_SUCCESS = 0


def _message_type(payload: bytes) -> int:
    """Extract the 4-bit MessageType from the high nibble of byte 0.

    The ODID_BasicID_encoded header byte layout (LSb-first bit fields):
      bits[3:0] = ProtoVersion  (low nibble)
      bits[7:4] = MessageType   (high nibble)
    """
    return (payload[0] >> 4) & 0x0F


def parse_astm(
    payload: bytes,
    *,
    captured_at: datetime,
    rssi: int | None,
    raw_frame_hex: str,
) -> DroneReport:
    """Decode an ASTM F3411 wire frame and return a unified DroneReport.

    Currently handles MessageType 0 (Basic ID) only.
    Raises MalformedAstmError for short payloads, unknown message types, or
    non-zero return codes from the C decoder.
    """
    if len(payload) < ASTM_MIN_FRAME_BYTES:
        raise MalformedAstmError(
            f"payload {len(payload)}B < minimum {ASTM_MIN_FRAME_BYTES}B"
        )

    mtype = _message_type(payload)
    buf = (ctypes.c_uint8 * 25).from_buffer_copy(payload[:25])

    if mtype == 0:  # ODID_MESSAGETYPE_BASIC_ID
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
