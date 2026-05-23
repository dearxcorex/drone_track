from drone_detector.decoder.ie_extract import extract_dji_ie


def _build_ie(oui: bytes, oui_type: int, payload: bytes) -> bytes:
    body = oui + bytes([oui_type]) + payload
    return bytes([0xDD, len(body)]) + body


def test_extracts_payload_from_dji_droneid_ie() -> None:
    payload = bytes(range(20))
    frame = b"\x00\x01\x02" + _build_ie(b"\x60\x60\x1F", 0x09, payload) + b"\xFF\xFF"
    assert extract_dji_ie(frame) == payload


def test_returns_none_when_no_dji_ie_present() -> None:
    frame = _build_ie(b"\x00\x50\xF2", 0x04, b"\x01\x02")  # Microsoft WPS, not DJI
    assert extract_dji_ie(frame) is None


def test_skips_non_vendor_ies_and_finds_dji() -> None:
    ssid_ie = bytes([0x00, 4]) + b"test"
    rates_ie = bytes([0x01, 2]) + b"\x82\x84"
    dji = _build_ie(b"\x60\x60\x1F", 0x09, b"\xAA\xBB")
    frame = ssid_ie + rates_ie + dji
    assert extract_dji_ie(frame) == b"\xAA\xBB"


def test_returns_none_on_truncated_ie() -> None:
    # Length byte says 10 but only 2 bytes follow
    frame = bytes([0xDD, 10, 0x60, 0x60])
    assert extract_dji_ie(frame) is None
