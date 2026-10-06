#!/usr/bin/env bash
# Every room played to the win in a real browser by the play bot, with
# keyboard and mouse (number keys, then drag and drop) and on a phone
# (ADR-0038 addendum). Serves build/client-web and build/packs from a private
# platform on its own port (drafts included: it is private). About 20 minutes. Needs google-chrome and python
# playwright; run tools/export.sh first.
#   tools/browser_bots.sh [room_id ...]
set -uo pipefail
cd "$(dirname "$0")/.."
command -v google-chrome >/dev/null || { echo "SKIP: google-chrome not installed"; exit 0; }
python3 -c "import playwright" 2>/dev/null || { echo "SKIP: python playwright not installed"; exit 0; }
[ -f build/client-web/index.html ] || { echo "run tools/export.sh first"; exit 2; }
PORT=$((8600 + RANDOM % 300))
# Own game and challenge port ranges, away from an always-on platform's.
GP=$((24000 + RANDOM % 400 * 10))
CP=$((30000 + RANDOM % 400 * 25))
WORK="$(mktemp -d "${TMPDIR:-/tmp}/escapebox-bots-XXXXXX")"
go build -o "$WORK/platform" ./platform/cmd/platform || exit 1
"$WORK/platform" -addr "127.0.0.1:$PORT" -data "$WORK/data" -rooms game/rooms -game game \
	-game-ports "$GP-$((GP + 9))" -challenge-ports "$CP-$((CP + 20))" \
	-web build/client-web -packs build/packs -drafts > "$WORK/platform.log" 2>&1 &
PP=$!
trap 'kill $PP 2>/dev/null; wait $PP 2>/dev/null' EXIT
for _ in $(seq 1 40); do curl -sf "http://127.0.0.1:$PORT/healthz" >/dev/null && break; sleep 0.25; done
ROOMS=("$@")
[ ${#ROOMS[@]} -gt 0 ] || ROOMS=($(for r in game/rooms/*/room.yaml; do basename "$(dirname "$r")"; done))
FAIL=0
for id in "${ROOMS[@]}"; do
	for mode in "deskbot=1" "deskbot=1&deskdrag=1" "touchbot=1 --phone"; do
		q="${mode%% *}"; extra=""; [[ "$mode" == *"--phone"* ]] && extra="--phone --limit 5400"  # phone emulation renders slowly
		echo "== $id: $q $extra"
		python3 tools/browserbot.py "http://127.0.0.1:$PORT/play/?room=$id&$q" $extra --out "$WORK/$id-${q//[&=]/_}" || FAIL=1
	done
done
[ $FAIL -eq 0 ] && echo "== PASS (logs in $WORK)" || echo "== FAILED (logs in $WORK)"
exit $FAIL
