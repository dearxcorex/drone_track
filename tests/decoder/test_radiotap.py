from scapy.layers.dot11 import RadioTap

from drone_detector.decoder.radiotap import RadioTapMeta, parse_radiotap


def test_parses_rssi_when_present() -> None:
    rt = RadioTap(present="dBm_AntSignal", dBm_AntSignal=-67)
    meta = parse_radiotap(rt)
    assert meta == RadioTapMeta(rssi=-67)


def test_returns_none_rssi_when_absent() -> None:
    rt = RadioTap()  # no signal field
    meta = parse_radiotap(rt)
    assert meta.rssi is None
