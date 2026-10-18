#!/usr/bin/env bash
# Records a captioned play-through video of a room: the play bot at a watching
# pace (?deskbot=1&tour=1) in headless Chrome against a private platform, as a
# player on a computer would play it (W A S D, mouse look, E, number keys).
# Captions come from media/rooms/<id>/playthrough_captions.yaml if present.
# A step longer than CUT_AFTER seconds (default 25) has its middle cut out.
# LIMIT (seconds, default 5400) stops the recording early: a quick check.
# Needs google-chrome, python playwright, ffmpeg with libass; run
# tools/export.sh first. The video carries the solution: it is for checking
# the design against the build, not for players.
#   tools/playthrough.sh <room_id> [out.mp4]
set -euo pipefail
cd "$(dirname "$0")/.."
ROOM="${1:?usage: tools/playthrough.sh <room_id> [out.mp4]}"
[ -f build/client-web/index.html ] || { echo "run tools/export.sh first"; exit 2; }
# A short temp path: Chrome's socket path must stay short.
WORK="$(mktemp -d /tmp/escapebox-playthrough-XXXXXX)"
OUT="${2:-$WORK/$ROOM-playthrough.mp4}"
PORT=$((8600 + RANDOM % 300))
GP=$((24000 + RANDOM % 400 * 10))
CP=$((30000 + RANDOM % 400 * 25))
go build -o "$WORK/platform" ./platform/cmd/platform
"$WORK/platform" -addr "127.0.0.1:$PORT" -data "$WORK/data" -rooms game/rooms -game game \
	-game-ports "$GP-$((GP + 9))" -challenge-ports "$CP-$((CP + 20))" \
	-web build/client-web -packs build/packs -drafts > "$WORK/platform.log" 2>&1 &
PP=$!
trap 'kill $PP 2>/dev/null; wait $PP 2>/dev/null' EXIT
for _ in $(seq 1 40); do curl -sf "http://127.0.0.1:$PORT/healthz" >/dev/null && break; sleep 0.25; done
echo "== recording $ROOM (frames in $WORK/rec)"
python3 tools/playthrough.py record "http://127.0.0.1:$PORT/play/?room=$ROOM&deskbot=1&tour=1" --out "$WORK/rec" --limit "${LIMIT:-5400}" \
	|| echo "warning: the bot reported problems (see $WORK/rec/timeline.jsonl); cutting anyway"
[ -s "$WORK/rec/frames.jsonl" ] || { echo "no frames recorded"; exit 1; }
CAP="media/rooms/$ROOM/playthrough_captions.yaml"
[ -f "$CAP" ] || CAP=""
python3 tools/playthrough.py cut "$ROOM" "$WORK/rec" ${CAP:+--captions "$CAP"} --video "$OUT" --cut-after "${CUT_AFTER:-25}"
