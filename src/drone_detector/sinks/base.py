"""Sink Protocol for DroneIDReport instances."""

from typing import Protocol, runtime_checkable

from drone_detector.models import DroneIDReport


@runtime_checkable
class ReportSink(Protocol):
    def write(self, report: DroneIDReport) -> None: ...
    def close(self) -> None: ...
