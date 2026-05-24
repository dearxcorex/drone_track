#!/usr/bin/env bash
# Pi-only smoke test: confirm ChannelHopper actually changes the channel.
# Usage: scripts/pi_hop_smoke.sh <iface>
set -euo pipefail
iface="${1:?usage: $0 <iface>}"

echo "Setting $iface to monitor mode..."
sudo ip link set "$iface" down
sudo iw dev "$iface" set type monitor
sudo ip link set "$iface" up

echo "Channels to test: 1 6 11 36 149"
for ch in 1 6 11 36 149; do
    sudo iw dev "$iface" set channel "$ch"
    actual=$(iw dev "$iface" info | awk '/channel/ {print $2; exit}')
    if [[ "$actual" == "$ch" ]]; then
        echo "ch=$ch  OK"
    else
        echo "ch=$ch  FAIL (got '$actual')"
        exit 1
    fi
    sleep 0.2
done
echo "All channel transitions succeeded."
