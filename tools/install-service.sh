#!/usr/bin/env bash
# Runs the escapebox platform as an always-on systemd user service (M5,
# ADR-0028): the lobby site, browser client, room packs and on-demand game
# servers on port 8090, reachable over Tailscale HTTPS. Re-run after pulling
# changes (it rebuilds and restarts).
#   tools/install-service.sh            install or update, then start
#   tools/install-service.sh --status   show the service and its address
#   tools/install-service.sh --uninstall
# Options via env: PLATFORM_PORT (8090), MAX_GAMES (4), GODOT (godot).
set -euo pipefail
cd "$(dirname "$0")/.."
REPO="$(pwd)"
UNIT=escapebox-platform.service
UNIT_FILE="$HOME/.config/systemd/user/$UNIT"
PORT="${PLATFORM_PORT:-8090}"

case "${1:-}" in
--uninstall)
	systemctl --user disable --now "$UNIT" 2>/dev/null || true
	rm -f "$UNIT_FILE"
	systemctl --user daemon-reload
	echo "removed $UNIT (tailscale serve is unchanged; 'tailscale serve --https=443 off' stops it)"
	exit 0 ;;
--status)
	systemctl --user --no-pager status "$UNIT" | head -12 || true
	tailscale serve status 2>/dev/null || true
	exit 0 ;;
esac

[ -f build/client-web/index.html ] && ls build/packs/*.pck >/dev/null 2>&1 || {
	echo "== building the clients and room packs first (tools/export.sh)"; tools/export.sh > build/export.log 2>&1 || { tail -20 build/export.log; exit 1; }
}
echo "== building the platform"
go build -o build/platform ./platform/cmd/platform

GODOT_BIN="$(command -v "${GODOT:-godot}")" || { echo "godot not found"; exit 1; }
TS_IP="$(tailscale ip -4 2>/dev/null | head -1 || true)"
ADV=()
[ -n "$TS_IP" ] && ADV=(-advertise "$TS_IP")
mkdir -p "$(dirname "$UNIT_FILE")"
cat > "$UNIT_FILE" <<UNITEOF
[Unit]
Description=escapebox platform (lobby, browser client, game servers)
After=network-online.target docker.service

[Service]
WorkingDirectory=$REPO
Environment=PATH=$(dirname "$GODOT_BIN"):/usr/local/bin:/usr/bin:/bin
ExecStart=$REPO/build/platform -addr :$PORT -data $REPO/data -rooms game/rooms -game game -godot $GODOT_BIN -transport ws -web build/client-web -packs build/packs -max-games ${MAX_GAMES:-4} ${ADV[*]}
Restart=on-failure
RestartSec=3

[Install]
WantedBy=default.target
UNITEOF
systemctl --user daemon-reload
systemctl --user enable "$UNIT" >/dev/null 2>&1
systemctl --user restart "$UNIT"
for _ in $(seq 1 40); do curl -sf "http://127.0.0.1:$PORT/healthz" >/dev/null && break; sleep 0.25; done
curl -sf "http://127.0.0.1:$PORT/healthz" >/dev/null || { echo "the platform did not come up:"; journalctl --user -u "$UNIT" -n 20 --no-pager; exit 1; }

if [ -n "$TS_IP" ]; then
	tailscale serve status 2>/dev/null | grep -q "127.0.0.1:$PORT" || tailscale serve --bg --https=443 "http://127.0.0.1:$PORT" >/dev/null
	NAME="$(tailscale status --json | jq -r '.Self.DNSName' | sed 's/\.$//')"
	echo "== running: https://$NAME/  (lobby; friends you share this machine with can start and join games)"
else
	echo "== running on http://127.0.0.1:$PORT/ (Tailscale is not up: only this PC can use it)"
fi
loginctl show-user "$USER" -p Linger 2>/dev/null | grep -q "Linger=yes" || \
	echo "   note: it stops when you log out; to keep it running at boot without logging in: sudo loginctl enable-linger $USER"
