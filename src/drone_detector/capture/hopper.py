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

    def stop(self) -> None:
        self._stop_event.set()

    def run(self) -> None:
        i = 0
        while not self._stop_event.is_set():
            ch = self._channels[i % len(self._channels)]
            try:
                self._set_channel(self._iface, ch)
            except Exception:
                log.warning("set_channel %s -> %d failed", self._iface, ch, exc_info=True)
            i += 1
            # Sleep in small slices so stop() is responsive
            slept = 0.0
            while slept < self._dwell_s and not self._stop_event.is_set():
                tick = min(0.05, self._dwell_s - slept)
                time.sleep(tick)
                slept += tick
