"""Parse the payload of a DJI DroneID v2 vendor IE into a DroneReport.

Byte layout is documented in docs/dji_droneid_v2_format.md (the single source of truth).
All multi-byte fields are little-endian.
"""

import struct
from datetime import datetime

from drone_detector.models import DroneReport

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
) -> DroneReport:
    """Decode a DJI DroneID v2 IE payload (without OUI/OUI-type) into a DroneReport."""
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
    (_ts_ms,) = struct.unpack_from("<Q", payload, cursor)
    cursor += 8
    pilot_lat_i, pilot_lon_i, home_lat_i, home_lon_i = struct.unpack_from("<iiii", payload, cursor)
    cursor += 16

    uuid_len = payload[cursor]
    cursor += 1
    if cursor + uuid_len > len(payload):
        raise MalformedDroneIDError("uuid extends past payload")
    uuid_hex = payload[cursor : cursor + uuid_len].hex()

    pilot_lat, pilot_lon = _none_if_zero_pair(
        pilot_lat_i / LAT_LON_SCALE, pilot_lon_i / LAT_LON_SCALE
    )
    home_lat, home_lon = _none_if_zero_pair(
        home_lat_i / LAT_LON_SCALE, home_lon_i / LAT_LON_SCALE
    )

    return DroneReport(
        captured_at=captured_at,
        rssi=rssi,
        protocol="dji_v2",
        operator_id=None,
        astm_message_type=None,
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
