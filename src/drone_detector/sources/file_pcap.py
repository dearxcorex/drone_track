"""Stream 802.11 frames from a .pcap file. Cross-platform; primary macOS dev mode."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from typing import Any

from scapy.utils import PcapReader


class FilePcapSource:
    def __init__(self, path: Path) -> None:
        self._path = Path(path)
        self._reader: PcapReader | None = None

    def __enter__(self) -> FilePcapSource:
        self._reader = PcapReader(str(self._path))
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    def __iter__(self) -> Iterator[Any]:
        if self._reader is None:
            self._reader = PcapReader(str(self._path))
        yield from self._reader

    def close(self) -> None:
        if self._reader is not None:
            self._reader.close()
            self._reader = None
