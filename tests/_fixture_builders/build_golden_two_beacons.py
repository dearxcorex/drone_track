"""Generate the golden JSONL from the current pipeline output. Run manually."""

import json
from datetime import UTC, datetime
from pathlib import Path

from drone_detector.pipeline import run_pipeline
from drone_detector.sinks.jsonl_sink import JsonlFileSink
from drone_detector.sources.file_pcap import FilePcapSource

ROOT = Path(__file__).resolve().parents[1]
PCAP = ROOT / "fixtures" / "pcaps" / "two_beacons.pcap"
OUT = ROOT / "fixtures" / "golden" / "two_beacons.expected.jsonl"

if __name__ == "__main__":
    OUT.parent.mkdir(parents=True, exist_ok=True)
    if OUT.exists():
        OUT.unlink()
    sink = JsonlFileSink(OUT, dedup_window_s=0)
    with FilePcapSource(PCAP) as source:
        run_pipeline(
            source=source,
            sinks=[sink],
            clock=lambda: datetime(2026, 5, 23, 10, 0, 0, tzinfo=UTC),
        )
    sink.close()
    lines = OUT.read_text().splitlines()
    print(f"wrote {len(lines)} line(s) to {OUT}")
    for line in lines:
        print(json.dumps(json.loads(line), indent=2, sort_keys=True))
