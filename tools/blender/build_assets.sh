#!/usr/bin/env bash
# Rebuild all requested props, or a subset: build_assets.sh keypad_4
set -euo pipefail
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd)"
BLENDER_BIN="${BLENDER:-blender}"
command -v "$BLENDER_BIN" >/dev/null || { echo "ERROR: Blender not found: $BLENDER_BIN" >&2; exit 1; }
command -v flock >/dev/null || { echo 'ERROR: flock is required to serialize Blender builds' >&2; exit 1; }
mkdir -p "$ROOT/assets/cache"
# Hold across the version check AND every build; concurrent callers wait here.
exec 9>"$ROOT/assets/cache/.blender-build.lock"
flock 9
VERSION_OUTPUT="$(PULSE_SERVER=unix:/nonexistent-blender-asset-audio "$BLENDER_BIN" -b --factory-startup --threads 4 -noaudio --version)"
VERSION="$(sed -nE 's/^Blender ([0-9]+\.[0-9]+\.[0-9]+).*$/\1/p' <<< "$VERSION_OUTPUT" | head -n1)"
if [[ ! "$VERSION" =~ ^5\.2\.[0-9]+$ ]]; then
    echo "ERROR: asset pipeline requires Blender 5.2.x; found '${VERSION:-unknown}' at $BLENDER_BIN" >&2
    exit 1
fi
if (( $# == 0 )); then
    shopt -s nullglob
    SCRIPTS=("$ROOT"/tools/blender/props/*.py)
    (( ${#SCRIPTS[@]} )) || { echo 'ERROR: no prop scripts found' >&2; exit 1; }
else
    SCRIPTS=()
    for ASSET_ID in "$@"; do
        [[ "$ASSET_ID" =~ ^[a-z][a-z0-9_]*$ ]] || { echo "ERROR: invalid asset id: $ASSET_ID" >&2; exit 1; }
        SCRIPTS+=("$ROOT/tools/blender/props/$ASSET_ID.py")
    done
fi
# Validate the entire selection before starting expensive work.
for SCRIPT in "${SCRIPTS[@]}"; do
    [[ -f "$SCRIPT" ]] || { echo "ERROR: missing asset script: $SCRIPT" >&2; exit 1; }
    ASSET_ID="$(basename "$SCRIPT" .py)"
    [[ -f "$ROOT/assets/requests/$ASSET_ID.md" ]] || { echo "ERROR: missing request for $ASSET_ID" >&2; exit 1; }
done
cd "$ROOT"
for SCRIPT in "${SCRIPTS[@]}"; do
    ASSET_ID="$(basename "$SCRIPT" .py)"
    # A request may name a room-specific output (**Output:** `game/rooms/<room>/assets/props/<id>.glb`,
    # ADR-0030); everything else goes to the core library.
    OUT_DIR="$ROOT/game/assets/core/props"
    OUTPUT="$(sed -nE 's/^\*\*Output:\*\* `([^`]+\.glb)`.*/\1/p' "$ROOT/assets/requests/$ASSET_ID.md" | head -n1)"
    if [[ -n "$OUTPUT" ]]; then
        [[ "$OUTPUT" =~ ^game/rooms/[a-z0-9_]+/assets/props/$ASSET_ID\.glb$ ]] || { echo "ERROR: $ASSET_ID: unexpected Output path $OUTPUT" >&2; exit 1; }
        OUT_DIR="$ROOT/$(dirname "$OUTPUT")"
        mkdir -p "$OUT_DIR"
    fi
    echo "Building $ASSET_ID with Blender $VERSION (CPU only, 4 threads) -> ${OUT_DIR#$ROOT/}"
    PULSE_SERVER=unix:/nonexistent-blender-asset-audio "$BLENDER_BIN" -b --factory-startup --threads 4 -noaudio --python-exit-code 1 --python "$SCRIPT" -- --out "$OUT_DIR"
done
