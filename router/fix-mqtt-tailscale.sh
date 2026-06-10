#!/bin/sh
# fix-mqtt-tailscale.sh — run ON the GL-AXT1800 router (root@172.16.8.1), not the Mac.
#
# PROBLEM
#   The MQTT broker hive.manion.org is a public A-record pointing at a Tailscale-only
#   IP (100.77.186.118, tailnet node "machone"). The Revel ESP32 (revel-monitor) cannot
#   run Tailscale, so it relies on this router to bridge LAN -> tailnet.
#
#   GL.iNet's "Allow Remote Access LAN" toggle creates the lan->tailscale0 *forwarding*,
#   but NOT masquerade. Without masquerade, LAN clients reach hive sourced as 172.16.8.x,
#   hive has no route back to the van LAN, and every reply is dropped -> Home Assistant
#   shows "Revel Monitor: unavailable".
#
# FIX
#   Add masquerade to the tailscale0 firewall zone (persistent in /etc/config/firewall,
#   loaded by fw4 on every boot). Confirmed to survive reboots 2026-06-09.
#
#   The ONLY thing that wipes it is changing the GL.iNet Tailscale *web-UI toggles*
#   (that regenerates the zone). If you ever flip those, re-run:  ./fix-mqtt-tailscale.sh
#
# PREREQUISITE (set once via the GL.iNet web UI, persists):
#   Tailscale -> "Allow Remote Access LAN" = ON  (provides the lan->tailscale0 forwarding)
#
# USAGE
#   ./fix-mqtt-tailscale.sh            # apply the fix (idempotent) then verify
#   ./fix-mqtt-tailscale.sh diagnose   # read-only health check, changes nothing
#   ./fix-mqtt-tailscale.sh verify     # just re-run the LAN-sourced reachability test

set -eu

BROKER_IP="100.77.186.118"     # hive.manion.org / tailnet node "machone"
LAN_IP="172.16.8.1"            # router LAN interface — proxy source for an ESP32 packet
ZONE="firewall.tailscale0"     # GL.iNet-created firewall zone for the tailscale0 device

diagnose() {
    echo "=== tailscale session (is hive online & reachable from the router?) ==="
    tailscale status 2>&1 | grep -E "$BROKER_IP|^#" || tailscale status 2>&1 | head -8
    echo "--- router -> hive ---"
    ping -c2 -W2 "$BROKER_IP" 2>&1 | tail -2
    echo
    echo "=== firewall: forwarding present? masq present? ==="
    uci show firewall | grep -i tailscale || echo "(no tailscale firewall config — is 'Allow Remote Access LAN' ON?)"
    echo
    echo "=== the decisive test: LAN-SOURCED reachability (what a LAN client/ESP32 sees) ==="
    echo "    100% loss => masquerade missing (run: $0 apply)"
    echo "      0% loss => path is healthy"
    ping -I "$LAN_IP" -c2 -W2 "$BROKER_IP" 2>&1 | tail -3
}

apply() {
    cur="$(uci -q get "${ZONE}.masq" || echo "")"
    if [ "$cur" = "1" ]; then
        echo "masq already set on tailscale0 zone — nothing to change."
    else
        echo "setting masquerade on the tailscale0 zone..."
        uci set "${ZONE}.masq=1"
        uci commit firewall
        /etc/init.d/firewall reload 2>/dev/null
        echo "applied + committed (persists across reboots)."
    fi
    sleep 2
    verify
}

verify() {
    echo "=== verify: LAN-sourced ping to hive (want 0% loss) ==="
    if ping -I "$LAN_IP" -c2 -W2 "$BROKER_IP" 2>&1 | tee /dev/stderr | grep -q " 0% packet loss"; then
        echo "PASS — LAN clients (incl. the ESP32) can reach the broker."
        echo "      Full MQTT/1883 check is best run from a LAN host:"
        echo "        nc -z hive.manion.org 1883"
        echo "        mosquitto_sub -h hive.manion.org -u canaduino -t 'revel/#' -v"
    else
        echo "FAIL — return path still broken. Check 'Allow Remote Access LAN' is ON,"
        echo "       that the router itself reaches hive ($0 diagnose), and re-run '$0 apply'."
        return 1
    fi
}

case "${1:-apply}" in
    diagnose) diagnose ;;
    apply)    apply ;;
    verify)   verify ;;
    *) echo "usage: $0 [diagnose|apply|verify]" >&2; exit 2 ;;
esac
