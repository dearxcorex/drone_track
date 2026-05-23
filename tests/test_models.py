import dataclasses
from datetime import UTC, datetime

from drone_detector.models import DroneIDReport


def test_drone_id_report_is_frozen_and_holds_all_fields() -> None:
    report = DroneIDReport(
        captured_at=datetime(2026, 5, 23, 10, 0, 0, tzinfo=UTC),
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
    assert dataclasses.is_dataclass(report)
    try:
        report.drone_serial = "x"  # type: ignore[misc]
    except dataclasses.FrozenInstanceError:
        pass
    else:
        raise AssertionError("DroneIDReport must be frozen")


def test_pilot_and_home_default_to_none() -> None:
    report = DroneIDReport(
        captured_at=datetime(2026, 5, 23, 10, 0, 0, tzinfo=UTC),
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
    assert report.pilot_lon is None
    assert report.home_lat is None
    assert report.home_lon is None
