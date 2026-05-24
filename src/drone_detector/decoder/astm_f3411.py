"""Stub. Real ctypes wrapper added in Task 7."""

from datetime import datetime

from drone_detector.models import DroneReport


class MalformedAstmError(ValueError):
    """Raised when an ASTM F3411 payload is too short or otherwise malformed."""


def parse_astm(
    payload: bytes,
    *,
    captured_at: datetime,
    rssi: int | None,
    raw_frame_hex: str,
) -> DroneReport:
    raise NotImplementedError("parse_astm is implemented in Task 7")
