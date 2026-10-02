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

if [[ "${1:-}" == "--no-godot" ]]; then exit 0; fi

step "godot import"
"$GODOT" --headless --path game --import 2>&1 | tail -n 3

step "gdUnit4"
GODOT_BIN="$(readlink -f "$(command -v "$GODOT")")" \
  bash game/addons/gdUnit4/runtest.sh --path game --headless --ignoreHeadlessMode -a res://tests -c
