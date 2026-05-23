"""Extract metadata (RSSI today; channel/MCS later) from scapy's RadioTap layer."""

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class RadioTapMeta:
    rssi: int | None


def parse_radiotap(packet: Any) -> RadioTapMeta:
    rssi = getattr(packet, "dBm_AntSignal", None)
    return RadioTapMeta(rssi=int(rssi) if rssi is not None else None)
