"""Builds tests/fixtures/pcaps/two_beacons.pcap with two beacons:
- one with a DJI DroneID IE (payload from sample_v2.bin)
- one without
"""

from pathlib import Path

from scapy.all import wrpcap
from scapy.layers.dot11 import Dot11, Dot11Beacon, Dot11Elt, RadioTap

ROOT = Path(__file__).resolve().parents[1]
BEACONS_DIR = ROOT / "fixtures" / "beacons"
PCAP_PATH = ROOT / "fixtures" / "pcaps" / "two_beacons.pcap"

DJI_OUI_AND_TYPE = b"\x60\x60\x1F\x09"


def build() -> None:
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
    plain_beacon = (
        RadioTap()
        / Dot11(type=0, subtype=8, addr1="ff:ff:ff:ff:ff:ff",
                addr2="11:22:33:44:55:66", addr3="11:22:33:44:55:66")
        / Dot11Beacon(cap=0x0411)
        / Dot11Elt(ID=0, info=b"OtherAP")
    )
    PCAP_PATH.parent.mkdir(parents=True, exist_ok=True)
    wrpcap(str(PCAP_PATH), [dji_beacon, plain_beacon])
    print(f"wrote {PCAP_PATH}")


if __name__ == "__main__":
    build()
