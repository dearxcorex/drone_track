from datetime import UTC, datetime

import pytest

from drone_detector.decoder.dji_droneid_v2 import (
    MalformedDroneIDError,
    parse_dji_droneid,
)

CAPTURED = datetime(2026, 5, 23, 10, 0, 0, tzinfo=UTC)


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
        parse_dji_droneid(
            b"\x10\x00\x07\x05\x40" + b"\x00" * 10,
            captured_at=CAPTURED,
            rssi=None,
            raw_frame_hex="",
        )
