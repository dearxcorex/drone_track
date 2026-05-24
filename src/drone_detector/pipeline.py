"""Glue: pull packets from a FrameSource, decode DJI DroneID, push to each sink."""

from __future__ import annotations

import logging
from collections.abc import Callable, Iterable
from datetime import UTC, datetime

from scapy.layers.dot11 import Dot11Beacon

from drone_detector.decoder import registry
from drone_detector.decoder.astm_f3411 import MalformedAstmError
from drone_detector.decoder.dji_droneid_v2 import MalformedDroneIDError
from drone_detector.decoder.ie_extract import extract_drone_ie
from drone_detector.decoder.radiotap import parse_radiotap
from drone_detector.sinks.base import ReportSink
from drone_detector.sources.base import FrameSource

log = logging.getLogger(__name__)


def _utcnow() -> datetime:
    return datetime.now(UTC)


def run_pipeline(
    *,
    source: FrameSource,
    sinks: Iterable[ReportSink],
    clock: Callable[[], datetime] = _utcnow,
) -> None:
    sink_list = list(sinks)
    for packet in source:
        try:
            if not packet.haslayer(Dot11Beacon):
                continue
            frame_body = bytes(packet[Dot11Beacon].payload)
            match = extract_drone_ie(frame_body)
            if match is None:
                continue
            tag, ie_payload = match
            meta = parse_radiotap(packet)
            try:
                report = registry.parse(
                    tag,
                    ie_payload,
                    captured_at=clock(),
                    rssi=meta.rssi,
                    raw_frame_hex=bytes(packet).hex(),
                )
            except (MalformedDroneIDError, MalformedAstmError) as exc:
                log.debug("dropping malformed/unsupported %s frame: %s", tag, exc)
                continue
        except Exception:
            log.debug("skipping packet due to unexpected error", exc_info=True)
            continue

        for sink in sink_list:
            try:
                sink.write(report)
            except Exception:
                log.exception("sink %r failed; continuing", sink)
