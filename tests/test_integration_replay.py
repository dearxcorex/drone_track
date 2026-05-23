import json
from datetime import UTC, datetime
from pathlib import Path

from drone_detector.pipeline import run_pipeline
from drone_detector.sinks.jsonl_sink import JsonlFileSink
from drone_detector.sources.file_pcap import FilePcapSource


def test_replay_matches_golden(tmp_path: Path, fixtures_dir: Path) -> None:
    pcap = fixtures_dir / "pcaps" / "two_beacons.pcap"
    out = tmp_path / "out.jsonl"

    sink = JsonlFileSink(out, dedup_window_s=0)
    with FilePcapSource(pcap) as source:
        run_pipeline(
            source=source,
            sinks=[sink],
            clock=lambda: datetime(2026, 5, 23, 10, 0, 0, tzinfo=UTC),
        )
    sink.close()

    actual = [json.loads(line) for line in out.read_text().splitlines()]
    expected_path = fixtures_dir / "golden" / "two_beacons.expected.jsonl"
    expected = [json.loads(line) for line in expected_path.read_text().splitlines()]
    assert actual == expected
