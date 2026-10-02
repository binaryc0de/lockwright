#!/usr/bin/env bash
# Exported-build smoke test (M4, ADR-0021): the exported Linux dedicated
# server and the exported Linux client, with no --path and no --pack, find
# the room pack in packs/ next to their executables and play Night Shift to
# the win over ENet. Run tools/export.sh first.
#   tools/export_smoke.sh [room_id]
set -uo pipefail
cd "$(dirname "$0")/.."
ROOM="${1:-night_shift}"
SERVER=build/server-linux/escapebox-server.x86_64
CLIENT=build/client-linux/escapebox.x86_64
PORT=$((18000 + RANDOM % 900))
TOKEN="export-$RANDOM"
WORK="$(mktemp -d "${TMPDIR:-/tmp}/escapebox-export-XXXXXX")"
FAIL=0
PIDS=()
say() { printf '== %s\n' "$*"; }
bad() { printf 'FAIL: %s\n' "$*"; FAIL=1; }
cleanup() { for p in "${PIDS[@]}"; do kill "$p" 2>/dev/null; done; wait 2>/dev/null; }
trap cleanup EXIT

for f in "$SERVER" "$CLIENT"; do [ -x "$f" ] || { echo "missing $f; run tools/export.sh"; exit 2; }; done
ls build/server-linux/packs/"$ROOM"*.pck build/client-linux/packs/"$ROOM"*.pck >/dev/null 2>&1 || { echo "no $ROOM pack in packs/; run tools/export.sh"; exit 2; }

say "workdir $WORK, port $PORT"
"$SERVER" --headless -- --server --session export --room "$ROOM" --port "$PORT" --trust-positions \
	--token "$TOKEN" --snapshot "$WORK/session.json" > "$WORK/server.log" 2>&1 &
PIDS+=("$!")
for _ in $(seq 1 60); do grep -q "listening on" "$WORK/server.log" && break; sleep 0.25; done
grep -q "listening on" "$WORK/server.log" || { bad "exported server did not start (see $WORK/server.log)"; exit 1; }

say "exported client plays the room to the win"
timeout 300 "$CLIENT" --headless -- --connect "127.0.0.1:$PORT" --name Exported --token "$TOKEN" \
	--bot --bot-wait-win > "$WORK/client.log" 2>&1
rc=$?; [ $rc -eq 0 ] || bad "exported client exited $rc"
grep -q "session finished, won=true" "$WORK/client.log" || bad "exported client never saw the win"
grep -qiE "SCRIPT ERROR|Parse Error" "$WORK/server.log" "$WORK/client.log" && bad "script errors in the exported builds"

if [ $FAIL -eq 0 ]; then say "PASS (logs in $WORK)"; else say "FAILED (logs in $WORK)"; fi
exit $FAIL
