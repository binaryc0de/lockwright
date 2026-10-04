#!/usr/bin/env bash
# Deterministic, offline documents; shares the prop builder's process lock.
set -euo pipefail
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd)"
BLENDER_BIN="${BLENDER:-blender}"
command -v "$BLENDER_BIN" >/dev/null
command -v flock >/dev/null
mkdir -p "$ROOT/assets/cache"
exec 9>"$ROOT/assets/cache/.blender-build.lock"
flock 9
VERSION_OUTPUT="$(PULSE_SERVER=unix:/nonexistent-blender-asset-audio "$BLENDER_BIN" -b --factory-startup --threads 4 -noaudio --version)"
VERSION="$(sed -nE 's/^Blender ([0-9]+\.[0-9]+\.[0-9]+).*$/\1/p' <<< "$VERSION_OUTPUT" | head -n1)"
[[ "$VERSION" =~ ^5\.2\.[0-9]+$ ]] || { echo "Requires Blender 5.2.x; found $VERSION" >&2; exit 1; }
cd "$ROOT"
PULSE_SERVER=unix:/nonexistent-blender-asset-audio "$BLENDER_BIN" -b --factory-startup --threads 4 -noaudio --python-exit-code 1 --python "$ROOT/tools/printables/clockmaker.py" -- "$@"
