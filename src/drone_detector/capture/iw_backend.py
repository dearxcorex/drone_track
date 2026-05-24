"""Linux-only backend that wraps `iw dev <iface> set channel <n>` via subprocess.

Not unit-tested on macOS — exercised by Pi smoke script and live `listen` runs.
"""

from __future__ import annotations

import subprocess


class IwError(RuntimeError):
    pass


def set_channel(iface: str, channel: int) -> None:
    proc = subprocess.run(
        ["iw", "dev", iface, "set", "channel", str(channel)],
        check=False,
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        raise IwError(
            f"iw set channel failed for {iface}/{channel}: "
            f"rc={proc.returncode} stderr={proc.stderr.strip()}"
        )


def link_down_up(iface: str) -> None:
    """Reset the interface — used by the reset-on-stall flow."""
    for action in ("down", "up"):
        proc = subprocess.run(
            ["ip", "link", "set", iface, action],
            check=False,
            capture_output=True,
            text=True,
        )
        if proc.returncode != 0:
            raise IwError(
                f"ip link set {iface} {action} failed: "
                f"rc={proc.returncode} stderr={proc.stderr.strip()}"
            )
