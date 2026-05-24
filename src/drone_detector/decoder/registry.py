"""Dispatch table mapping a protocol tag to its parser function."""

from __future__ import annotations

from datetime import datetime
from typing import Protocol

from drone_detector.decoder.astm_f3411 import parse_astm
from drone_detector.decoder.dji_droneid_v2 import parse_dji_droneid
from drone_detector.models import DroneReport


class ParserFn(Protocol):
    def __call__(
        self,
        payload: bytes,
        *,
        captured_at: datetime,
        rssi: int | None,
        raw_frame_hex: str,
    ) -> DroneReport: ...


_PARSERS: dict[str, ParserFn] = {
    "dji_v2": parse_dji_droneid,
    "astm_f3411": parse_astm,
}


def dispatch(tag: str) -> ParserFn:
    return _PARSERS[tag]


def parse(
    tag: str,
    payload: bytes,
    *,
    captured_at: datetime,
    rssi: int | None,
    raw_frame_hex: str,
) -> DroneReport:
    return dispatch(tag)(
        payload, captured_at=captured_at, rssi=rssi, raw_frame_hex=raw_frame_hex
    )
