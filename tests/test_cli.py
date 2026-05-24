import json
from unittest.mock import patch

from typer.testing import CliRunner

from drone_detector.cli import app

runner = CliRunner()


def test_version_prints_a_version_string() -> None:
    result = runner.invoke(app, ["version"])
    assert result.exit_code == 0
    assert "drone-detector" in result.stdout


def test_replay_decodes_pcap_and_writes_jsonl(tmp_path, fixtures_dir) -> None:
    pcap = fixtures_dir / "pcaps" / "two_beacons.pcap"
    out = tmp_path / "out.jsonl"
    result = runner.invoke(app, ["replay", str(pcap), "--out", str(out)])
    assert result.exit_code == 0, result.stdout
    lines = out.read_text().splitlines()
    assert len(lines) == 1
    record = json.loads(lines[0])
    assert record["drone_serial"] == "1581F5ABCDEF1234567890"


def test_listen_no_hop_does_not_start_hopper():
    runner = CliRunner()
    with patch("drone_detector.cli.ChannelHopper") as mock_hop, \
         patch("drone_detector.cli.LivePcapSource") as mock_src, \
         patch("drone_detector.cli.run_pipeline") as mock_run:
        mock_run.return_value = None
        mock_src.return_value.close.return_value = None
        result = runner.invoke(app, ["listen", "--iface", "wlan1", "--no-hop"])
        assert result.exit_code == 0
        mock_hop.assert_not_called()


def test_listen_hop_starts_hopper_and_stops_it():
    runner = CliRunner()
    started = {"value": False}
    stopped = {"value": False}

    class FakeHopper:
        def __init__(self, **kwargs):
            pass

        def start(self):
            started["value"] = True

        def stop(self):
            stopped["value"] = True

        def join(self, timeout=None):
            pass

    with patch("drone_detector.cli.ChannelHopper", FakeHopper), \
         patch("drone_detector.cli.LivePcapSource") as mock_src, \
         patch("drone_detector.cli.run_pipeline") as mock_run:
        mock_run.return_value = None
        mock_src.return_value.close.return_value = None
        result = runner.invoke(
            app,
            ["listen", "--iface", "wlan1", "--hop", "--channels", "1,6", "--dwell-ms", "100"],
        )
        assert result.exit_code == 0
        assert started["value"]
        assert stopped["value"]
