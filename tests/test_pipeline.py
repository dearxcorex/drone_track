from datetime import UTC, datetime
from pathlib import Path

from drone_detector.models import DroneReport
from drone_detector.pipeline import run_pipeline
from drone_detector.sources.file_pcap import FilePcapSource


class RecordingSink:
    def __init__(self) -> None:
        self.reports: list[DroneReport] = []

    def write(self, report: DroneReport) -> None:
        self.reports.append(report)

    def close(self) -> None:
        pass


def test_pipeline_decodes_dji_beacon_and_skips_plain_beacon(fixtures_dir: Path) -> None:
    pcap = fixtures_dir / "pcaps" / "two_beacons.pcap"
    sink = RecordingSink()
    with FilePcapSource(pcap) as source:
        run_pipeline(
            source=source,
            sinks=[sink],
            clock=lambda: datetime(2026, 5, 23, 10, 0, 0, tzinfo=UTC),
        )
    assert len(sink.reports) == 1
    assert sink.reports[0].drone_serial == "1581F5ABCDEF1234567890"
