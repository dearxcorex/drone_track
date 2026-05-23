import json

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
