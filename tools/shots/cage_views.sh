#!/usr/bin/env bash
# Renders the Night Shift server cage from fixed viewpoints with room_shots.tscn
# (the server cage and its puzzle props). Needs a GPU and a display.
#   tools/shots/cage_views.sh <out_dir> [project_dir=game]
set -euo pipefail
out="${1:?usage: $0 <out_dir> [project_dir]}"
mkdir -p "$out"; out="$(realpath "$out")"
proj="$(realpath "${2:-$(dirname "$0")/../../game}")"
cd "$proj"
exec godot --path . --resolution 1600x900 res://tests/scenes/room_shots.tscn -- \
  --room night_shift --out "$out" --views \
  cage_from_office:3.6,1.6,2.6:-90:-4 \
  cage_door:4.9,1.6,4.5:-80:-6 \
  rack_front:6.55,1.6,1.8:-90:-12 \
  patch_panel:6.95,1.4,1.8:-90:-14 \
  ups:6.95,1.35,1.0:-110:-22 \
  cage_inside:8.2,1.7,4.6:31:-10 \
  rack_stencil:6.95,1.75,1.8:-90:0
