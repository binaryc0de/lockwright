#!/usr/bin/env bash
# Runs every check CI runs. Usage: tools/test.sh [--no-godot]
set -euo pipefail
cd "$(dirname "$0")/.."

GODOT="${GODOT:-godot}"
step() { printf '\n== %s\n' "$*"; }

step "gofmt"
unformatted=$(gofmt -l internal platform tools)
if [[ -n "$unformatted" ]]; then echo "needs gofmt:"; echo "$unformatted"; exit 1; fi

step "go vet + go test"
go vet ./...
go test ./...

step "roomcheck"
go run ./tools/roomcheck

step "assetcheck"
go run ./tools/assetcheck

step "texture budget (browser build, ADR-0024)"
python3 tools/texture_budget.py --check

step "room CTF challenges (go test in each challenge module)"
for mod in game/rooms/*/ctf/*/go.mod; do
  [[ -f "$mod" ]] || continue
  (cd "$(dirname "$mod")" && gofmt -l . | (! grep .) && go vet ./... && go test ./...)
done

if [[ "${1:-}" == "--no-godot" ]]; then exit 0; fi

step "godot import"
"$GODOT" --headless --path game --import 2>&1 | tail -n 3

step "gdUnit4"
GODOT_BIN="$(readlink -f "$(command -v "$GODOT")")" \
  bash game/addons/gdUnit4/runtest.sh --path game --headless --ignoreHeadlessMode -a res://tests -c

step "room packs (export + replay from the pack alone)"
for room_yaml in game/rooms/*/room.yaml; do
  id="$(basename "$(dirname "$room_yaml")")"
  if [[ -f "game/tests/rooms/test_${id}.gd" ]]; then
    go run ./tools/packroom -verify "$id"
  fi
done

step "multiplayer smoke (server + bots + crash/restore + ws, ADR-0015)"
GODOT="$GODOT" tools/m2_smoke.sh

step "platform smoke (platform + game servers + bots + flag + crash restart, ADR-0018)"
GODOT="$GODOT" tools/m3_smoke.sh

step "browser smoke (web export + headless Chrome plays to the win, ADR-0023/0025)"
if command -v google-chrome >/dev/null; then
  mkdir -p build/client-web
  "$GODOT" --headless --path game --export-release client-web > build/export-client-web.log 2>&1
  for f in build/client-web/*.pck build/client-web/*.wasm build/client-web/*.js; do gzip -9 -k -f "$f"; done
  tools/web_smoke.sh standard
else
  echo "skipped: google-chrome not installed"
fi
