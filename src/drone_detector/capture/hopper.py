"""Daemon-thread channel hopper. Calls a user-provided set_channel_fn on a fixed cadence."""

from __future__ import annotations

import logging
import threading
import time
from collections.abc import Callable

log = logging.getLogger(__name__)

SetChannelFn = Callable[[str, int], None]


class ChannelHopper(threading.Thread):
    def __init__(
        self,
        *,
        iface: str,
        channels: list[int],
        dwell_ms: int,
        set_channel_fn: SetChannelFn,
        reset_on_stall: int = 0,
        reset_fn: Callable[[str], None] | None = None,
    ) -> None:
        super().__init__(name=f"hopper-{iface}", daemon=True)
        if not channels:
            raise ValueError("channels must be non-empty")
        if dwell_ms <= 0:
            raise ValueError("dwell_ms must be positive")
        self._iface = iface
        self._channels = list(channels)
        self._dwell_s = dwell_ms / 1000.0
        self._set_channel = set_channel_fn
        self._stop_event = threading.Event()
        self._reset_on_stall = reset_on_stall
        self._reset_fn = reset_fn
        self._empty_hops = 0
        # Set when a packet is seen; cleared each hop so consecutive-empty counting is accurate.
        self._packet_seen = threading.Event()

    def stop(self) -> None:
        self._stop_event.set()

    def notify_packet_seen(self) -> None:
        """Called by external consumers when a frame decodes; resets the stall counter."""
        self._packet_seen.set()

    def run(self) -> None:
        i = 0
        while not self._stop_event.is_set():
            ch = self._channels[i % len(self._channels)]
            try:
                self._set_channel(self._iface, ch)
                if self._packet_seen.is_set():
                    self._empty_hops = 0
                    self._packet_seen.clear()
                else:
                    self._empty_hops += 1
                if (
                    self._reset_on_stall
                    and self._empty_hops >= self._reset_on_stall
                    and self._reset_fn
                ):
                    try:
                        self._reset_fn(self._iface)
                    except Exception:
                        log.warning("reset_fn failed for %s", self._iface, exc_info=True)
                    self._empty_hops = 0
            except Exception:
                log.warning("set_channel %s -> %d failed", self._iface, ch, exc_info=True)
            i += 1
            # Sleep in small slices so stop() is responsive
            slept = 0.0
            while slept < self._dwell_s and not self._stop_event.is_set():
                tick = min(0.05, self._dwell_s - slept)
                time.sleep(tick)
                slept += tick
