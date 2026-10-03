#!/usr/bin/env bash
# One command to play a room with everything real (platform, game server,
# Docker CTF challenge): starts the platform, creates a session, opens the
# game joined to it, and shuts it all down when you quit the game.
#   tools/play.sh [--hard | --difficulty <id>] [room_id] [your name]
# Friends on the LAN join from their main menu with this PC's address
# (printed below, e.g. 192.168.1.20:8090) and the join code.
# Env: PLATFORM_PORT (default 8090), GODOT (default godot).
set -euo pipefail
cd "$(dirname "$0")/.."
DIFFICULTY=""
POS=()
while [ $# -gt 0 ]; do
	case "$1" in
		--hard) DIFFICULTY=hard ;;
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
	echo "Port $PORT is in use (something else is listening). Try: PLATFORM_PORT=8091 $0"; exit 1
fi
docker info >/dev/null 2>&1 || echo "WARNING: Docker is not reachable; the CTF challenge will not start (the laptop will say so)."

echo "== building the platform"
go build -o "$LOG/platform" ./platform/cmd/platform
"$LOG/platform" -addr ":$PORT" -data data -rooms game/rooms -game game -godot "$GODOT" > "$LOG/platform.log" 2>&1 &
PLATFORM_PID=$!
cleanup() { kill "$PLATFORM_PID" 2>/dev/null; wait "$PLATFORM_PID" 2>/dev/null; echo "== platform stopped (logs in $LOG)"; }
trap cleanup EXIT
for _ in $(seq 1 40); do curl -sf "http://127.0.0.1:$PORT/healthz" >/dev/null && break; sleep 0.25; done
curl -sf "http://127.0.0.1:$PORT/healthz" >/dev/null || { echo "platform did not start:"; tail -5 "$LOG/platform.log"; exit 1; }

CODE="$(curl -sf -X POST "http://127.0.0.1:$PORT/api/sessions" -d "{\"room_id\":\"$ROOM\",\"difficulty\":\"$DIFFICULTY\"}" | sed -n 's/.*"invite_code":"\([^"]*\)".*/\1/p')"
[ -n "$CODE" ] || { echo "could not create a session for $ROOM"; tail -5 "$LOG/platform.log"; exit 1; }
IP="$(grep -o 'advertise=[0-9.]*' "$LOG/platform.log" | head -1 | cut -d= -f2)"
echo "== $ROOM (${DIFFICULTY:-default difficulty}) is ready. Join code: $CODE   (friends: ${IP:-this-pc}:$PORT + code $CODE)"
"$GODOT" --path game -- --join "127.0.0.1:$PORT" --code "$CODE" --name "$NAME" > "$LOG/game.log" 2>&1 || true
