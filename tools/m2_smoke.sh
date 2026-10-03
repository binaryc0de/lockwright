#!/usr/bin/env bash
# M2 multiplayer smoke test (ADR-0015), all headless on one machine:
#   1. a dedicated server starts with a snapshot file
#   2. Carol and Erin join and wait for the win without acting (3 clients at once
#      while Alice plays)
#   3. Alice plays solution steps 0-8 and leaves
#   4. the server is killed mid-session and restarted from its snapshot;
#      Carol reconnects on her own
#   5. Bob joins the restored session and finishes the room; Carol sees the win
#   6. a client with the wrong invite token is rejected
#   7. the same join + first steps over the WebSocket transport
# Exit 0 only if every step behaves. Usage: tools/m2_smoke.sh [room_id]
set -uo pipefail
cd "$(dirname "$0")/../game"
ROOM="${1:-night_shift}"
GODOT="${GODOT:-godot}"
PORT=$((17000 + RANDOM % 900))
WSPORT=$((PORT + 1000))
TOKEN="smoke-$RANDOM"
WORK="$(mktemp -d "${TMPDIR:-/tmp}/escapebox-m2-XXXXXX")"
SNAP="$WORK/session.json"
FAIL=0
PIDS=()

say() { printf '== %s\n' "$*"; }
bad() { printf 'FAIL: %s\n' "$*"; FAIL=1; }
cleanup() { for p in "${PIDS[@]}"; do kill "$p" 2>/dev/null; done; wait 2>/dev/null; }
trap cleanup EXIT

server() { # $1 log, $2 transport, $3 port
	"$GODOT" --headless --path . -- --server --session smoke --room "$ROOM" --port "$3" --trust-positions \
		--transport "$2" --token "$TOKEN" --snapshot "$SNAP" > "$WORK/$1" 2>&1 &
	SERVER_PID=$!
	PIDS+=("$SERVER_PID")
	for _ in $(seq 1 40); do
		grep -q "listening on" "$WORK/$1" 2>/dev/null && return 0
		sleep 0.25
	done
	bad "server did not start (see $WORK/$1)"; return 1
}

client() { # $1 log, $2 name, then extra args
	local log=$1 name=$2; shift 2
	"$GODOT" --headless --path . -- --connect "127.0.0.1:$PORT" --name "$name" --token "$TOKEN" --bot "$@" > "$WORK/$log" 2>&1
}

say "workdir $WORK, port $PORT"
server server1.log enet "$PORT" || exit 1

say "Carol and Erin join and wait for the win"
"$GODOT" --headless --path . -- --connect "127.0.0.1:$PORT" --name Carol --token "$TOKEN" \
	--bot --bot-steps 1-0 --bot-wait-win > "$WORK/carol.log" 2>&1 &
CAROL_PID=$!
PIDS+=("$CAROL_PID")
"$GODOT" --headless --path . -- --connect "127.0.0.1:$PORT" --name Erin --token "$TOKEN" \
	--bot --bot-steps 1-0 --bot-wait-win > "$WORK/erin.log" 2>&1 &
ERIN_PID=$!
PIDS+=("$ERIN_PID")
sleep 2

say "Alice plays steps 0-8"
client alice.log Alice --bot-steps 0-8
rc=$?; [ $rc -eq 0 ] || bad "Alice exited $rc"
grep -q '"picked_up":{"' "$SNAP" || bad "snapshot shows nothing picked up after Alice's steps"

say "kill the server mid-session, restart from the snapshot"
kill -9 "$SERVER_PID"; wait "$SERVER_PID" 2>/dev/null
server server2.log enet "$PORT" || exit 1
grep -q "restored snapshot" "$WORK/server2.log" || bad "server 2 did not restore the snapshot"
for _ in $(seq 1 80); do grep -q "player carol joined" "$WORK/server2.log" && break; sleep 0.25; done
grep -q "player carol joined" "$WORK/server2.log" || bad "Carol did not reconnect to the restarted server"

say "Bob finishes the room"
client bob.log Bob --bot-steps 9-end --bot-wait-win
rc=$?; [ $rc -eq 0 ] || bad "Bob exited $rc"
wait "$CAROL_PID"; rc=$?
[ $rc -eq 0 ] || bad "Carol exited $rc (she should have seen the win)"
grep -q "session finished, won=true" "$WORK/carol.log" || bad "Carol never saw the win"
wait "$ERIN_PID"; rc=$?
[ $rc -eq 0 ] || bad "Erin exited $rc (she should have seen the win)"
grep -q "player erin joined" "$WORK/server1.log" || bad "Erin never joined"
grep -q '"won":true' "$SNAP" || bad "final snapshot is not won"

say "wrong token is rejected"
"$GODOT" --headless --path . -- --connect "127.0.0.1:$PORT" --name Mallory --token nope --bot > "$WORK/mallory.log" 2>&1
rc=$?; [ $rc -eq 3 ] || bad "Mallory exited $rc, want 3 (rejected)"
kill "$SERVER_PID" 2>/dev/null; wait "$SERVER_PID" 2>/dev/null

say "WebSocket transport"
SNAP="$WORK/ws.json"
server server_ws.log ws "$WSPORT" || exit 1
"$GODOT" --headless --path . -- --connect "127.0.0.1:$WSPORT" --transport ws --name Dana --token "$TOKEN" \
	--bot --bot-steps 0-1 > "$WORK/dana.log" 2>&1
rc=$?; [ $rc -eq 0 ] || bad "Dana (ws) exited $rc"

if [ $FAIL -eq 0 ]; then say "PASS (logs in $WORK)"; else say "FAILED (logs in $WORK)"; fi
exit $FAIL
