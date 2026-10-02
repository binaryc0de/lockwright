#!/usr/bin/env bash
# Renders the M1 look-test viewpoints of Night Shift's office corner
# (desk, whiteboard, filing cabinet) with room_shots.tscn. Needs a GPU and a display.
#   tools/shots/looktest_views.sh <out_dir> [extra godot args]
set -euo pipefail
out="${1:?usage: $0 <out_dir>}"; shift || true
mkdir -p "$out"; out="$(realpath "$out")"
cd "$(dirname "$0")/../../game"
exec godot --path . --resolution 1600x900 "$@" res://tests/scenes/room_shots.tscn -- \
  --room night_shift --out "$out" --views \
  wide_north:3.0,1.6,4.4:0:-8 \
  corner:4.6,1.65,3.7:40:-14 \
  desk:1.85,1.5,1.75:0:-30 \
  whiteboard:4.1,1.6,2.0:0:-4 \
  cabinet:1.45,1.55,3.2:180:-22 \
  cabinet_wide:4.2,1.6,1.9:135:-12
