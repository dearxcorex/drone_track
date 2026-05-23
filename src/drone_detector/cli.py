"""drone-detector command-line interface."""

from __future__ import annotations

import importlib.metadata
import subprocess
import time
from pathlib import Path

import typer
from rich.console import Console

from drone_detector.pipeline import run_pipeline
from drone_detector.sinks.base import ReportSink
from drone_detector.sinks.jsonl_sink import JsonlFileSink
from drone_detector.sinks.stdout_sink import StdoutSink
from drone_detector.sources.file_pcap import FilePcapSource
from drone_detector.sources.live_pcap import LivePcapSource

app = typer.Typer(add_completion=False, help="DJI DroneID decoder for NBTC Thailand.")


def _build_sinks(out: Path | None) -> list[ReportSink]:
    sinks: list[ReportSink] = [StdoutSink(console=Console())]
    if out is not None:
        sinks.append(JsonlFileSink(out))
    return sinks


@app.command()
def version() -> None:
    """Print the installed package version."""
    try:
        v = importlib.metadata.version("drone-detector")
    except importlib.metadata.PackageNotFoundError:
        v = "0.0.0+dev"
    typer.echo(f"drone-detector {v}")


@app.command()
def replay(
    pcap: Path = typer.Argument(..., exists=True, readable=True, dir_okay=False),  # noqa: B008
    out: Path | None = typer.Option(None, "--out", help="JSONL output path"),  # noqa: B008
) -> None:
    """Decode a .pcap file and print/write detections."""
    sinks = _build_sinks(out)
    try:
        with FilePcapSource(pcap) as source:
            run_pipeline(source=source, sinks=sinks)
    finally:
        for s in sinks:
            s.close()


@app.command()
def listen(
    iface: str = typer.Option(..., "--iface", help="Monitor-mode WiFi interface (Linux)"),  # noqa: B008
    out: Path | None = typer.Option(Path("detections.jsonl"), "--out"),  # noqa: B008
) -> None:
    """Live-capture DJI DroneID beacons from a monitor-mode interface."""
    sinks = _build_sinks(out)
    source = LivePcapSource(iface=iface)
    try:
        run_pipeline(source=source, sinks=sinks)
    finally:
        source.close()
        for s in sinks:
            s.close()


@app.command()
def hop(
    iface: str = typer.Option(..., "--iface"),  # noqa: B008
    channels: str = typer.Option("1,6,11,36,149", "--channels"),  # noqa: B008
    dwell_ms: int = typer.Option(500, "--dwell-ms"),  # noqa: B008
) -> None:
    """Rotate `iface` through `channels` every `dwell-ms` ms using `iw dev`."""
    ch_list = [c.strip() for c in channels.split(",") if c.strip()]
    typer.echo(f"hopping {iface} through {ch_list} every {dwell_ms}ms; Ctrl+C to stop")
    try:
        while True:
            for ch in ch_list:
                subprocess.run(["iw", "dev", iface, "set", "channel", ch], check=False)
                time.sleep(dwell_ms / 1000)
    except KeyboardInterrupt:
        typer.echo("stopped")
