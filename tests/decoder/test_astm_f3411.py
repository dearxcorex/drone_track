from datetime import UTC, datetime
from pathlib import Path

import pytest

from drone_detector.decoder.astm_f3411 import MalformedAstmError, parse_astm

FIXTURES = Path(__file__).parent.parent / "fixtures" / "beacons"


def test_parse_basic_id_returns_drone_report():
    payload = (FIXTURES / "sample_astm_basic_id.bin").read_bytes()
    r = parse_astm(
        payload,
        captured_at=datetime(2026, 5, 24, 12, 0, tzinfo=UTC),
        rssi=-50,
        raw_frame_hex="deadbeef",
    )
    assert r.protocol == "astm_f3411"
    assert r.astm_message_type == 0
    assert r.drone_serial.startswith("1581F5ABCDEF")


def test_parse_rejects_short_payload():
    with pytest.raises(MalformedAstmError):
        parse_astm(
            b"\x02\x01",
            captured_at=datetime(2026, 5, 24, 12, 0, tzinfo=UTC),
            rssi=None,
            raw_frame_hex="",
        )
