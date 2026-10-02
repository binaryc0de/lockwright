#!/usr/bin/env bash
# Renders the Night Shift office from fixed viewpoints with room_shots.tscn
# (the six look-test views plus the exit wall and south wall). Needs a GPU and a display.
#   tools/shots/office_views.sh <out_dir> [project_dir=game]
set -euo pipefail
out="${1:?usage: $0 <out_dir> [project_dir]}"
mkdir -p "$out"; out="$(realpath "$out")"
proj="$(realpath "${2:-$(dirname "$0")/../../game}")"
cd "$proj"
exec godot --path . --resolution 1600x900 res://tests/scenes/room_shots.tscn -- \
  --room night_shift --out "$out" --views \
  wide_north:3.0,1.6,4.4:0:-8 \
  corner:4.6,1.65,3.7:40:-14 \
  desk:1.85,1.5,1.75:0:-30 \
  whiteboard:4.1,1.6,2.0:0:-4 \
  cabinet:1.45,1.55,3.2:180:-22 \
  cabinet_wide:4.2,1.6,1.9:135:-12 \
  exit_wall:3.4,1.65,2.5:90:-2 \
  exit_keypad:0.75,1.5,3.25:90:-8 \
  intercom_clock:1.3,1.75,1.7:65:8 \
  south_wall:3.9,1.6,2.4:180:-6
