#!/usr/bin/env bash
# Builds a room's intro trailer (docs/research/06-intro-videos.md):
#   tools/trailer/build.sh <room_id>
# 1. records media/rooms/<id>/trailer.json in the real room with Godot's
#    Movie Maker (native 1080p; the window must not be resized, or Movie Maker
#    upscales a crop), 2. assembles it with optional story clips
#    (media/rooms/<id>/clips/*.mp4, in name order) and narration
#    (narration.wav, from `go run ./tools/narrate media/rooms/<id>`) into
#    intro.mp4 and poster.jpg with Blender.
set -euo pipefail
cd "$(dirname "$0")/../.."
ROOM="${1:?usage: tools/trailer/build.sh <room_id>}"
MEDIA="media/rooms/$ROOM"
[[ -f "$MEDIA/trailer.json" ]] || { echo "no $MEDIA/trailer.json"; exit 1; }
WORK="build/trailer/$ROOM"
mkdir -p "$WORK"
GODOT="${GODOT:-godot}"
echo "== recording $ROOM (Movie Maker, 30 fps)"
"$GODOT" --path game --write-movie "$PWD/$WORK/rec.avi" --fixed-fps 30 \
	res://tests/scenes/room_trailer.tscn -- --room "$ROOM" --shots "$PWD/$MEDIA/trailer.json" > "$WORK/godot.log" 2>&1
grep -E "frames at" "$WORK/godot.log"
ARGS=(--record "$PWD/$WORK/rec.avi" --out-dir "$PWD/$MEDIA")
if [[ -f "$MEDIA/narration.wav" ]]; then
	START="$(python3 -c "import json,sys; print(json.load(open(sys.argv[1])).get('start_s', 1.0))" "$MEDIA/narration.json" 2>/dev/null || echo 1.0)"
	ARGS+=(--narration "$PWD/$MEDIA/narration.wav" --narration-start "$START")
fi
shopt -s nullglob
CLIPS=()
SRC=("$MEDIA"/clips/*.mp4)
if (( ${#SRC[@]} )); then
	# Story clips (Flow/Veo) come at 24 fps with loud, unlevelled sound; the
	# sequencer does not retime, so convert them to the trailer's 30 fps and
	# level their sound below the narration.
	command -v "${FFMPEG:-ffmpeg}" > /dev/null || { echo "story clips need ffmpeg"; exit 1; }
	mkdir -p "$WORK/clips"
	for c in "${SRC[@]}"; do
		out="$PWD/$WORK/clips/$(basename "$c")"
		"${FFMPEG:-ffmpeg}" -hide_banner -v error -y -i "$c" -vf "fps=30,scale=1280:720" \
			-af "loudnorm=I=-30:TP=-6:LRA=11,aresample=48000" -c:v libx264 -crf 16 -preset medium \
			-c:a aac -b:a 192k -ac 2 "$out"
		CLIPS+=("$out")
	done
	ARGS+=(--pre "$(IFS=,; echo "${CLIPS[*]}")")
fi
echo "== assembling (Blender FFmpeg)"
"${BLENDER:-blender}" -b --factory-startup --python tools/trailer/assemble.py -- "${ARGS[@]}" > "$WORK/blender.log" 2>&1 \
	|| { tail -20 "$WORK/blender.log"; exit 1; }
grep "TRAILER wrote" "$WORK/blender.log"
# Index first, so browsers start playing before the whole file has arrived.
if command -v "${FFMPEG:-ffmpeg}" > /dev/null; then
	"${FFMPEG:-ffmpeg}" -hide_banner -v error -y -i "$MEDIA/intro.mp4" -c copy -movflags +faststart "$WORK/faststart.mp4"
	mv "$WORK/faststart.mp4" "$MEDIA/intro.mp4"
else
	echo "warning: no ffmpeg, intro.mp4 keeps its index at the end (slower start in browsers)"
fi
ls -la "$MEDIA"/intro.mp4 "$MEDIA"/poster.jpg
