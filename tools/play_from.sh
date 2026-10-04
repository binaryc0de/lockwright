#!/usr/bin/env bash
# Dev play from part-way through a room: a local headless server, a bot that
# replays room.yaml's solution up to and including the step that solves
# PUZZLE, then a windowed client for you. No platform, nothing published.
#   tools/play_from.sh clockmaker strike_true      # start at the hidden stair
#   NAME=Jason tools/play_from.sh clockmaker open_gate
set -euo pipefail
cd "$(dirname "$0")/.."

ROOM="${1:?usage: tools/play_from.sh ROOM PUZZLE}"
PUZZLE="${2:?usage: tools/play_from.sh ROOM PUZZLE}"
GODOT="${GODOT:-godot}"
NAME="${NAME:-Player}"
PORT=$((18000 + RANDOM % 900))
TOKEN="dev-$RANDOM"
WORK="$(mktemp -d "${TMPDIR:-/tmp}/escapebox-play-XXXXXX")"

# The last solution step of the puzzle: the step after which it is solved,
# found by replaying the solution in the room test helper.
LAST=$("$GODOT" --headless --path game res://tests/scenes/solution_step.tscn -- --room "$ROOM" --puzzle "$PUZZLE" 2>/dev/null \
	| sed -n 's/^solved_at_step //p')
if [[ -z "$LAST" ]]; then
	echo "could not find the step that solves $PUZZLE in $ROOM" >&2
	exit 1
fi

cleanup() { kill "${SERVER_PID:-}" 2>/dev/null || true; wait 2>/dev/null || true; }
trap cleanup EXIT

cd game
"$GODOT" --headless --path . -- --server --session dev --room "$ROOM" --port "$PORT" --trust-positions \
	--token "$TOKEN" --snapshot "$WORK/session.json" > "$WORK/server.log" 2>&1 &
SERVER_PID=$!
for _ in $(seq 1 40); do
	grep -q "listening on" "$WORK/server.log" 2>/dev/null && break
	sleep 0.25
done
echo "== bot replays steps 0-$LAST (up to $PUZZLE)"
"$GODOT" --headless --path . -- --connect "127.0.0.1:$PORT" --name Replay --token "$TOKEN" \
	--bot --bot-steps "0-$LAST" > "$WORK/bot.log" 2>&1
echo "== your turn (server log: $WORK/server.log)"
"$GODOT" --path . -- --connect "127.0.0.1:$PORT" --name "$NAME" --token "$TOKEN"
