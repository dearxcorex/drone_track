import time

from drone_detector.capture.hopper import ChannelHopper


def test_hopper_cycles_through_channels():
    calls: list[tuple[str, int]] = []
    h = ChannelHopper(
        iface="wlan1",
        channels=[1, 6, 11],
        dwell_ms=10,
        set_channel_fn=lambda iface, ch: calls.append((iface, ch)),
    )
    h.start()
    time.sleep(0.08)   # ~8 ticks
    h.stop()
    h.join(timeout=1.0)
    # First three calls should be channels 1,6,11 in order
    seen_channels = [ch for _, ch in calls[:3]]
    assert seen_channels == [1, 6, 11]
    # Should have wrapped around at least once
    assert len(calls) >= 4
    assert all(iface == "wlan1" for iface, _ in calls)


def test_hopper_stop_is_idempotent():
    h = ChannelHopper(
        iface="wlan1",
        channels=[1],
        dwell_ms=10,
        set_channel_fn=lambda i, c: None,
    )
    h.start()
    h.stop()
    h.stop()  # second call must not raise
    h.join(timeout=1.0)


def test_hopper_swallows_set_channel_errors():
    def failing(_iface: str, _ch: int) -> None:
        raise RuntimeError("driver wedged")

    h = ChannelHopper(
        iface="wlan1",
        channels=[1, 6],
        dwell_ms=10,
        set_channel_fn=failing,
    )
    h.start()
    time.sleep(0.05)
    assert h.is_alive()   # did not crash on the exception
    h.stop()
    h.join(timeout=1.0)
