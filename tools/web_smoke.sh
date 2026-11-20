#!/usr/bin/env bash
# Browser smoke test (M5, ADR-0023/0025): the exported web client, served by the
# platform, plays Night Shift to the win in headless Chrome on the integrated
# GPU. It downloads and verifies the room pack, joins over WebSocket, and the
# bot submits the session's real flag (computed from the platform secret, as
# m3_smoke does without Docker). Needs google-chrome and tools/export.sh output.
#   tools/web_smoke.sh [standard|hard]
set -uo pipefail
cd "$(dirname "$0")/.."
DIFF="${1:-standard}"
command -v google-chrome >/dev/null || { echo "SKIP: google-chrome not installed"; exit 0; }
[ -f build/client-web/index.html ] || { echo "run tools/export.sh first"; exit 2; }
PORT=$((8600 + RANDOM % 300))
# Own game and challenge port ranges, away from an always-on platform's
# defaults (7777-7799, 20000-20999), so a test never races a live game.
GP=$((24000 + RANDOM % 400 * 10))
CP=$((30000 + RANDOM % 400 * 25))
WORK="$(mktemp -d "${TMPDIR:-/tmp}/escapebox-web-XXXXXX")"
FAIL=0
bad() { printf 'FAIL: %s\n' "$*"; FAIL=1; }
go build -o "$WORK/platform" ./platform/cmd/platform || exit 1
"$WORK/platform" -addr ":$PORT" -data "$WORK/data" -rooms game/rooms -game game -godot godot -transport ws \
	-game-ports "$GP-$((GP + 9))" -challenge-ports "$CP-$((CP + 20))" \
	-web build/client-web -packs build/packs -test-trust-positions > "$WORK/platform.log" 2>&1 &
PP=$!
trap 'kill $PP 2>/dev/null; wait $PP 2>/dev/null' EXIT
for _ in $(seq 1 40); do curl -sf "http://127.0.0.1:$PORT/healthz" >/dev/null && break; sleep 0.25; done
S=$(curl -sf -X POST -H 'Content-Type: application/json' "http://127.0.0.1:$PORT/api/sessions" -d "{\"room_id\":\"night_shift\",\"difficulty\":\"$DIFF\"}") || { bad "create session"; exit 1; }
SID=$(jq -r .session_id <<<"$S"); CODE=$(jq -r .invite_code <<<"$S")
FLAG=$(go run ./platform/cmd/flagcalc -secret "$WORK/data/secret.key" -session "$SID" -challenge intranet)
echo "== $DIFF session $SID: headless Chrome plays from http://127.0.0.1:$PORT/play/?code=$CODE"
python3 tools/webshot.py "http://127.0.0.1:$PORT/play/?code=$CODE&name=Browser&bot=1&flag=$FLAG" "$WORK" --at 150 > "$WORK/webshot.out" 2>&1
grep -h "webgl:" "$WORK/webshot.out"
grep -q "room pack: user://packs/" "$WORK/console.log" || bad "the browser did not download the room pack"
grep -q "session finished, won=true" "$WORK/console.log" || bad "the browser never saw the win (see $WORK/console.log)"
curl -fs "http://127.0.0.1:$PORT/api/sessions/$SID" | jq -e '.won == true' >/dev/null || bad "platform did not record the win"
if [ $FAIL -eq 0 ]; then echo "== PASS (logs in $WORK)"; else echo "== FAILED (logs in $WORK)"; fi
exit $FAIL
