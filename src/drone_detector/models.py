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
