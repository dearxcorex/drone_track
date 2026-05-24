"""Append-only JSONL sink with per-(serial, time bucket) dedup."""

from __future__ import annotations

import dataclasses
import json
from pathlib import Path
from typing import IO

from drone_detector.models import DroneReport


def _bucket(report: DroneReport, window_s: int) -> int:
    if window_s <= 0:
        return -1
    return int(report.captured_at.timestamp()) // window_s


class JsonlFileSink:
    def __init__(self, path: Path, *, dedup_window_s: int = 5) -> None:
        self._path = Path(path)
        self._fh: IO[str] | None = None
        self._dedup_window_s = dedup_window_s
        self._seen: dict[tuple[str, int], None] = {}

    def _open(self) -> IO[str]:
        if self._fh is None:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            self._fh = self._path.open("a", encoding="utf-8")
        return self._fh

    def write(self, report: DroneReport) -> None:
        if self._dedup_window_s > 0:
            key = (report.drone_serial, _bucket(report, self._dedup_window_s))
            if key in self._seen:
                return
            self._seen[key] = None
        record = dataclasses.asdict(report)
        record["captured_at"] = report.captured_at.isoformat()
        line = json.dumps(record, ensure_ascii=False)
        fh = self._open()
        fh.write(line + "\n")
        fh.flush()

    def close(self) -> None:
        if self._fh is not None:
            self._fh.close()
            self._fh = None
