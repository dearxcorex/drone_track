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
