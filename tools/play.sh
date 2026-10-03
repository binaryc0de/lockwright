#!/usr/bin/env bash
# One command to play a room with everything real (platform, game server,
# Docker CTF challenge): starts the platform, creates a session, opens the
# game joined to it, and shuts it all down when you quit the game.
#   tools/play.sh [--hard | --difficulty <id>] [--tailscale] [--serve] [room_id] [your name]
# --serve hosts the game for others without opening it yourself: it prints the
# link and join code and runs until Ctrl+C.
# --tailscale advertises this machine's Tailscale address, so friends you have
# shared the machine with can open the printed link (needs `tailscale up`).
# Friends on the LAN join from their main menu with this PC's address
# (printed below, e.g. 192.168.1.20:8090) and the join code.
# Env: PLATFORM_PORT (default 8090), GODOT (default godot).
set -euo pipefail
cd "$(dirname "$0")/.."
DIFFICULTY=""
ADVERTISE=""
SERVE=0
POS=()
while [ $# -gt 0 ]; do
	case "$1" in
		--hard) DIFFICULTY=hard ;;
		--serve) SERVE=1 ;;
		--tailscale) ADVERTISE="$(tailscale ip -4 2>/dev/null | head -1)"
			[ -n "$ADVERTISE" ] || { echo "Tailscale is not up: run 'sudo tailscale up' first"; exit 1; } ;;
		--difficulty) DIFFICULTY="${2:?--difficulty needs an id}"; shift ;;
		*) POS+=("$1") ;;
	esac
	shift
done
ROOM="${POS[0]:-night_shift}"
NAME="${POS[1]:-${USER:-Player}}"
PORT="${PLATFORM_PORT:-8090}"
GODOT="${GODOT:-godot}"
LOG="$(mktemp -d "${TMPDIR:-/tmp}/escapebox-play-XXXXXX")"

if ss -ltn 2>/dev/null | grep -q ":$PORT "; then
	if systemctl --user is-active --quiet escapebox-platform.service 2>/dev/null; then
		echo "The always-on escapebox service already runs on port $PORT: open its lobby and press Start a game"
		echo "(tools/install-service.sh --status shows the address). Or use another port: PLATFORM_PORT=8091 $0"
	else
		echo "Port $PORT is in use (something else is listening). Try: PLATFORM_PORT=8091 $0"
	fi
	exit 1
fi
docker info >/dev/null 2>&1 || echo "WARNING: Docker is not reachable; the CTF challenge will not start (the laptop will say so)."

echo "== building the platform"
go build -o "$LOG/platform" ./platform/cmd/platform
# WebSocket game servers: browsers cannot use ENet, and desktop clients speak
# WebSocket too. The browser client is served at /play/ when it was exported
# (tools/export.sh).
WEB=()
[ -f build/client-web/index.html ] && WEB=(-web build/client-web)
[ -d build/packs ] && WEB+=(-packs build/packs)
ADV=()
[ -n "$ADVERTISE" ] && ADV=(-advertise "$ADVERTISE")
"$LOG/platform" -addr ":$PORT" -data data -rooms game/rooms -game game -godot "$GODOT" -transport ws "${WEB[@]}" "${ADV[@]}" > "$LOG/platform.log" 2>&1 &
PLATFORM_PID=$!
cleanup() { kill "$PLATFORM_PID" 2>/dev/null; wait "$PLATFORM_PID" 2>/dev/null; echo "== platform stopped (logs in $LOG)"; }
trap cleanup EXIT
for _ in $(seq 1 40); do curl -sf "http://127.0.0.1:$PORT/healthz" >/dev/null && break; sleep 0.25; done
curl -sf "http://127.0.0.1:$PORT/healthz" >/dev/null || { echo "platform did not start:"; tail -5 "$LOG/platform.log"; exit 1; }

CODE="$(curl -sf -X POST "http://127.0.0.1:$PORT/api/sessions" -d "{\"room_id\":\"$ROOM\",\"difficulty\":\"$DIFFICULTY\"}" | sed -n 's/.*"invite_code":"\([^"]*\)".*/\1/p')"
[ -n "$CODE" ] || { echo "could not create a session for $ROOM"; tail -5 "$LOG/platform.log"; exit 1; }
IP="$(grep -o 'advertise=[0-9.]*' "$LOG/platform.log" | head -1 | cut -d= -f2)"
echo "== $ROOM (${DIFFICULTY:-default difficulty}) is ready. Join code: $CODE   (friends: ${IP:-this-pc}:$PORT + code $CODE)"
if [ ${#WEB[@]} -gt 0 ]; then
	if [ -n "$ADVERTISE" ]; then
		TSNAME="$(tailscale status --json 2>/dev/null | jq -r '.Self.DNSName' | sed 's/\.$//')"
		if tailscale serve status 2>/dev/null | grep -q "127.0.0.1:$PORT"; then
			echo "== friends open: https://$TSNAME/play/?code=$CODE"
		else
			echo "== browsers need HTTPS: run 'tailscale serve --bg --https=443 http://127.0.0.1:$PORT' once, then share https://$TSNAME/play/?code=$CODE"
		fi
	else
		echo "== in a browser on this PC: http://127.0.0.1:$PORT/play/?code=$CODE"
	fi
fi
if [ "$SERVE" = 1 ]; then
	echo "== hosting only; players join with the link or code above. Press Ctrl+C to stop."
	echo "   (another game: curl -X POST http://127.0.0.1:$PORT/api/sessions -d '{\"room_id\":\"$ROOM\"}')"
	wait "$PLATFORM_PID" || true
else
	"$GODOT" --path game -- --join "127.0.0.1:$PORT" --code "$CODE" --name "$NAME" > "$LOG/game.log" 2>&1 || true
fi
