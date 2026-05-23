import io
from datetime import UTC, datetime

from rich.console import Console

from drone_detector.models import DroneIDReport
from drone_detector.sinks.stdout_sink import StdoutSink


def _make_report(serial: str, when: datetime) -> DroneIDReport:
    return DroneIDReport(
        captured_at=when, rssi=-65, drone_serial=serial,
        drone_lat=13.7563, drone_lon=100.5018,
        drone_altitude_m=120.0, drone_height_m=45.5,
        drone_speed_ns_mps=1.2, drone_speed_ew_mps=-0.4, drone_speed_ud_mps=0.0,
        drone_yaw_deg=87.5,
        pilot_lat=13.7560, pilot_lon=100.5020,
        home_lat=None, home_lon=None,
        uuid_len=0, uuid="",
        raw_frame_hex="",
    )


def test_writes_one_line_with_serial_and_coords() -> None:
    buf = io.StringIO()
    console = Console(file=buf, force_terminal=False, color_system=None, width=200)
    sink = StdoutSink(console=console, dedup_window_s=0)
    sink.write(_make_report("ABC", datetime(2026, 5, 23, 10, 0, 0, tzinfo=UTC)))
    out = buf.getvalue()
    assert "ABC" in out
    assert "13.7563" in out
    assert "100.5018" in out
    assert "-65" in out


def test_dedup_window_drops_within_bucket() -> None:
    buf = io.StringIO()
    console = Console(file=buf, force_terminal=False, color_system=None, width=200)
    sink = StdoutSink(console=console, dedup_window_s=5)
    base = datetime(2026, 5, 23, 10, 0, 0, tzinfo=UTC)
    sink.write(_make_report("A", base))
    sink.write(_make_report("A", base.replace(second=3)))   # dropped
    sink.write(_make_report("A", base.replace(second=6)))   # emitted
    lines = [line for line in buf.getvalue().splitlines() if line.strip()]
    assert len(lines) == 2
