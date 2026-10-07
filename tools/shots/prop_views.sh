#!/usr/bin/env bash
# Renders each part of a prop GLB as Godot imports it, with the web build's
# Compatibility renderer, plus a contact sheet. Use it to accept an asset:
# Blender previews cannot show import problems (UV sets, alpha, normal maps).
#   tools/shots/prop_views.sh <glb under game/, e.g. rooms/quiet_sun/assets/props/qs_ruin_kit.glb> <out_dir> [part]
set -euo pipefail
glb="${1:?usage: $0 <glb> <out_dir> [part]}"; out="${2:?usage: $0 <glb> <out_dir> [part]}"
mkdir -p "$out"; out="$(realpath "$out")"
cd "$(dirname "$0")/../../game"
godot --headless --path . --import >/dev/null 2>&1 || true
extra=(); [[ -n "${3:-}" ]] && extra=(--part "$3")
godot --path . --resolution 960x720 --rendering-driver opengl3 --rendering-method gl_compatibility \
  res://tests/scenes/prop_shots.tscn -- --glb "res://${glb#game/}" --out "$out" "${extra[@]}"
python3 - "$out" <<'PY'
import glob, sys
from PIL import Image
d = sys.argv[1]
fs = sorted(f for f in glob.glob(d + "/*__*.png"))
if fs:
    w, h = 480, 360; cols = 4
    sheet = Image.new("RGB", (w * cols, h * ((len(fs) + cols - 1) // cols)), (30, 30, 30))
    for i, f in enumerate(fs):
        sheet.paste(Image.open(f).convert("RGB").resize((w, h)), ((i % cols) * w, (i // cols) * h))
    sheet.save(d + "/sheet.png")
    print("sheet:", d + "/sheet.png")
PY
