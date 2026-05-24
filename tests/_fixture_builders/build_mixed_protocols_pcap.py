"""Builds tests/fixtures/pcaps/mixed_protocols.pcap with three beacons:
- one plain beacon (no vendor IE) — should be ignored by pipeline
- one with a DJI DroneID v2 IE (payload from sample_v2.bin)
- one with an ASTM F3411 Basic ID IE (payload from sample_astm_basic_id.bin)
"""

from pathlib import Path

from scapy.all import wrpcap
from scapy.layers.dot11 import Dot11, Dot11Beacon, Dot11Elt, RadioTap

ROOT = Path(__file__).resolve().parents[1]
BEACONS_DIR = ROOT / "fixtures" / "beacons"
PCAP_PATH = ROOT / "fixtures" / "pcaps" / "mixed_protocols.pcap"

DJI_OUI_AND_TYPE = b"\x60\x60\x1F\x09"
ASTM_OUI_AND_TYPE = b"\xfa\x0b\xbc\x0d"


def build() -> None:
    plain_beacon = (
        RadioTap()
        / Dot11(type=0, subtype=8, addr1="ff:ff:ff:ff:ff:ff",
                addr2="11:22:33:44:55:66", addr3="11:22:33:44:55:66")
        / Dot11Beacon(cap=0x0411)
        / Dot11Elt(ID=0, info=b"OtherAP")
    )

    dji_payload = (BEACONS_DIR / "sample_v2.bin").read_bytes()
    dji_ie = Dot11Elt(ID=221, info=DJI_OUI_AND_TYPE + dji_payload)
    dji_beacon = (
        RadioTap(present="dBm_AntSignal", dBm_AntSignal=-60)
        / Dot11(type=0, subtype=8, addr1="ff:ff:ff:ff:ff:ff",
                addr2="aa:bb:cc:dd:ee:ff", addr3="aa:bb:cc:dd:ee:ff")
        / Dot11Beacon(cap=0x0411)
        / Dot11Elt(ID=0, info=b"NBTC-TEST")
        / dji_ie
    )

    astm_payload = (BEACONS_DIR / "sample_astm_basic_id.bin").read_bytes()
    astm_ie = Dot11Elt(ID=221, info=ASTM_OUI_AND_TYPE + astm_payload)
    astm_beacon = (
        RadioTap(present="dBm_AntSignal", dBm_AntSignal=-70)
        / Dot11(type=0, subtype=8, addr1="ff:ff:ff:ff:ff:ff",
                addr2="cc:dd:ee:ff:00:11", addr3="cc:dd:ee:ff:00:11")
        / Dot11Beacon(cap=0x0411)
        / Dot11Elt(ID=0, info=b"ASTM-TEST")
        / astm_ie
    )

    PCAP_PATH.parent.mkdir(parents=True, exist_ok=True)
    wrpcap(str(PCAP_PATH), [plain_beacon, dji_beacon, astm_beacon])
    print(f"wrote {PCAP_PATH}")


if __name__ == "__main__":
    build()
