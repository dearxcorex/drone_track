"""Sink Protocol for DroneReport instances."""

from typing import Protocol, runtime_checkable

from drone_detector.models import DroneReport


@runtime_checkable
class ReportSink(Protocol):
    def write(self, report: DroneReport) -> None: ...
    def close(self) -> None: ...
