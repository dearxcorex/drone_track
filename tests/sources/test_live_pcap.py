import pytest

from drone_detector.sources.live_pcap import LivePcapSource


def test_live_source_class_importable_on_all_platforms() -> None:
    # Construction must not require a live interface.
    src = LivePcapSource(iface="loobackiface_does_not_exist")
    src.close()


@pytest.mark.live
def test_live_source_can_start_and_stop_briefly() -> None:
    src = LivePcapSource(iface="wlan0mon", timeout_s=1)
    src.start()
    src.close()
