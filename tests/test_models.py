import dataclasses
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
    with pytest.raises(dataclasses.FrozenInstanceError):
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
