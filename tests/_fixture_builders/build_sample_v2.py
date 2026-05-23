"""One-shot builder for tests/fixtures/beacons/sample_v2.bin. Run manually."""

import struct
from pathlib import Path


def build() -> bytes:
    serial = b"1581F5ABCDEF1234567890" + b"\x00" * (64 - 22)
    header = bytes([0x10, 0x00, 0x07, 0b101])  # frame type, version, seq, flags
    out = header
    out += bytes([0x40])  # serial length = 64
    out += serial
    # drone lon, lat (Bangkok-ish), scaled by 1e7
    out += struct.pack("<i", int(100.5018 * 1e7))   # lon
    out += struct.pack("<i", int(13.7563 * 1e7))    # lat
    # altitude 120.0 m -> 1200; height 45.5 m -> 455
    out += struct.pack("<h", 1200)
    out += struct.pack("<h", 455)
    # velocities m/s -> *100
    out += struct.pack("<h", 120)   # N/S +1.2
    out += struct.pack("<h", -40)   # E/W -0.4
    out += struct.pack("<h", 0)     # U/D
    out += struct.pack("<h", 8750)  # yaw 87.5
    out += struct.pack("<Q", 1716457800000)  # ts ms
    # pilot lat, lon
    out += struct.pack("<i", int(13.7560 * 1e7))
    out += struct.pack("<i", int(100.5020 * 1e7))
    # home lat, lon (unknown -> 0,0)
    out += struct.pack("<i", 0)
    out += struct.pack("<i", 0)
    # UUID
    uuid_bytes = bytes.fromhex("0102030405060708")
    out += bytes([len(uuid_bytes)]) + uuid_bytes
    return out


if __name__ == "__main__":
    p = Path(__file__).resolve().parents[1] / "fixtures" / "beacons" / "sample_v2.bin"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(build())
    print(f"wrote {p} ({p.stat().st_size} bytes)")
