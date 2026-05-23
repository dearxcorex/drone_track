import json
from datetime import UTC, datetime

from drone_detector.models import DroneIDReport
from drone_detector.sinks.jsonl_sink import JsonlFileSink


def _make_report(serial: str = "X", when: datetime | None = None) -> DroneIDReport:
    return DroneIDReport(
        captured_at=when or datetime(2026, 5, 23, 10, 0, 0, tzinfo=UTC),
        rssi=-70, drone_serial=serial,
        drone_lat=13.0, drone_lon=100.0,
        drone_altitude_m=10.0, drone_height_m=5.0,
        drone_speed_ns_mps=0.0, drone_speed_ew_mps=0.0, drone_speed_ud_mps=0.0,
        drone_yaw_deg=0.0,
        pilot_lat=None, pilot_lon=None, home_lat=None, home_lon=None,
        uuid_len=0, uuid="",
        raw_frame_hex="aa",
    )


def test_writes_one_json_object_per_line(tmp_path) -> None:
    path = tmp_path / "out.jsonl"
    sink = JsonlFileSink(path, dedup_window_s=0)
    sink.write(_make_report("A"))
    sink.write(_make_report("B"))
    sink.close()

    lines = path.read_text().splitlines()
    assert len(lines) == 2
    a = json.loads(lines[0])
    assert a["drone_serial"] == "A"
    assert a["captured_at"] == "2026-05-23T10:00:00+00:00"


def test_dedups_same_serial_within_window(tmp_path) -> None:
    path = tmp_path / "out.jsonl"
    sink = JsonlFileSink(path, dedup_window_s=5)
    base = datetime(2026, 5, 23, 10, 0, 0, tzinfo=UTC)
    sink.write(_make_report("A", when=base))
    sink.write(_make_report("A", when=base.replace(second=3)))   # within 5s -> dropped
    sink.write(_make_report("A", when=base.replace(second=6)))   # next bucket -> emitted
    sink.close()
    lines = path.read_text().splitlines()
    assert len(lines) == 2
