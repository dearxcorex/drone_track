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


from scapy.layers.dot11 import Dot11, Dot11Beacon  # noqa: E402


class _FakeSource:
    """Iterable that yields a single hand-built scapy packet."""

    def __init__(self, pkt) -> None:
        self._pkt = pkt

    def __iter__(self):
        yield self._pkt


def _build_beacon_with_vendor_ie(oui: bytes, oui_type: int, payload: bytes):
    body = oui + bytes([oui_type]) + payload
    ie = bytes([0xDD, len(body)]) + body
    return Dot11(addr1="ff:ff:ff:ff:ff:ff") / Dot11Beacon() / ie


def test_pipeline_drops_astm_when_parser_unimplemented():
    """ASTM frames go to parse_astm; today it raises NotImplementedError.
    Pipeline must log and continue, not crash. Replaced by Task 7 real decode."""
    pkt = _build_beacon_with_vendor_ie(b"\xfa\x0b\xbc", 0x0D, b"\xaa\xbb\xcc")
    sink = RecordingSink()
    run_pipeline(
        source=_FakeSource(pkt),
        sinks=[sink],
        clock=lambda: datetime(2026, 5, 24, 12, 0, tzinfo=UTC),
    )
    assert sink.reports == []   # parser raised, no report emitted, loop survived
