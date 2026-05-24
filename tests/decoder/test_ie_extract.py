from drone_detector.decoder.ie_extract import extract_drone_ie


def _vendor_ie(oui: bytes, oui_type: int, payload: bytes) -> bytes:
    body = oui + bytes([oui_type]) + payload
    return bytes([0xDD, len(body)]) + body


def test_returns_dji_v2_tag_for_dji_oui():
    frame = _vendor_ie(b"\x60\x60\x1F", 0x09, b"\xaa\xbb")
    assert extract_drone_ie(frame) == ("dji_v2", b"\xaa\xbb")


def test_returns_astm_tag_for_astm_oui():
    frame = _vendor_ie(b"\xfa\x0b\xbc", 0x0D, b"\xcc\xdd")
    assert extract_drone_ie(frame) == ("astm_f3411", b"\xcc\xdd")


def test_returns_none_for_unknown_vendor():
    frame = _vendor_ie(b"\x11\x22\x33", 0x99, b"\xff")
    assert extract_drone_ie(frame) is None


def test_returns_none_when_truncated():
    # Element id + length declares 10 bytes, only 2 provided
    frame = bytes([0xDD, 10, 0x60, 0x60])
    assert extract_drone_ie(frame) is None


def test_handles_multiple_ies_finds_dji_after_others():
    other = bytes([0x00, 3, 0x41, 0x42, 0x43])  # SSID-shaped element
    dji = _vendor_ie(b"\x60\x60\x1F", 0x09, b"\x42")
    assert extract_drone_ie(other + dji) == ("dji_v2", b"\x42")
