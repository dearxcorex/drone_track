from drone_detector.sources.file_pcap import FilePcapSource


def test_file_pcap_source_yields_all_packets(fixtures_dir) -> None:
    pcap = fixtures_dir / "pcaps" / "two_beacons.pcap"
    with FilePcapSource(pcap) as source:
        packets = list(source)
    assert len(packets) == 2


def test_file_pcap_source_is_idempotent_on_close(fixtures_dir) -> None:
    pcap = fixtures_dir / "pcaps" / "two_beacons.pcap"
    source = FilePcapSource(pcap)
    list(source)
    source.close()
    source.close()  # second call must not raise
