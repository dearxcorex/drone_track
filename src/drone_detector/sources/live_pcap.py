"""Live monitor-mode sniffer using scapy's AsyncSniffer (Linux only).

Uses libpcap (PACKET_MMAP) instead of the default AF_PACKET socket so the
sniffer survives transient ENETDOWN events that the kernel raises during
`iw set channel` calls. Without this, channel hopping kills scapy's
receive thread after the first hop.
"""

from __future__ import annotations

import queue
from collections.abc import Iterator

from scapy.config import conf
from scapy.sendrecv import AsyncSniffer


class LivePcapSource:
    def __init__(self, iface: str, *, timeout_s: float | None = None) -> None:
        self._iface = iface
        self._timeout_s = timeout_s
        self._sniffer: AsyncSniffer | None = None
        self._q: queue.Queue[object] = queue.Queue()
        self._stopped = False

    def start(self) -> None:
        if self._sniffer is not None:
            return
        conf.use_pcap = True
        self._sniffer = AsyncSniffer(
            iface=self._iface,
            store=False,
            prn=self._q.put,
        )
        self._sniffer.start()

    def __iter__(self) -> Iterator[object]:
        self.start()
        while not self._stopped:
            try:
                yield self._q.get(timeout=self._timeout_s or 1.0)
            except queue.Empty:
                if self._timeout_s is not None:
                    return

    def close(self) -> None:
        self._stopped = True
        if self._sniffer is not None:
            try:
                self._sniffer.stop()
            except Exception:
                pass
            self._sniffer = None
