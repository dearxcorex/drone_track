"""Pretty stdout sink (deduplicated by serial and 5-second bucket by default)."""

from __future__ import annotations

import sys
from typing import IO

from rich.console import Console

from drone_detector.models import DroneIDReport


def _bucket(report: DroneIDReport, window_s: int) -> int:
    return int(report.captured_at.timestamp()) // window_s


class StdoutSink:
    def __init__(
        self,
        *,
        console: Console | None = None,
        file: IO[str] | None = None,
        dedup_window_s: int = 5,
    ) -> None:
        self._console = console or Console(file=file or sys.stdout)
        self._dedup_window_s = dedup_window_s
        self._seen: dict[tuple[str, int], None] = {}

    def write(self, report: DroneIDReport) -> None:
        if self._dedup_window_s > 0:
            key = (report.drone_serial, _bucket(report, self._dedup_window_s))
            if key in self._seen:
                return
            self._seen[key] = None
        ts = report.captured_at.strftime("%H:%M:%S")
        pilot = (
            f"pilot=({report.pilot_lat:.5f},{report.pilot_lon:.5f})"
            if report.pilot_lat is not None and report.pilot_lon is not None
            else "pilot=unknown"
        )
        rssi = f"{report.rssi}dBm" if report.rssi is not None else "rssi=?"
        self._console.print(
            f"[cyan]{ts}[/cyan]  "
            f"[bold]{report.drone_serial}[/bold]  "
            f"drone=({report.drone_lat:.5f},{report.drone_lon:.5f}) "
            f"{pilot}  RSSI={rssi}"
        )

    def close(self) -> None:
        pass
