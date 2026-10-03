#!/usr/bin/env bash
# Exports the Linux and Windows clients, the Linux dedicated server and every
# room pack into build/, and puts the packs in packs/ next to each binary
# (RoomLoader.find_local_pack, ADR-0021). Needs the Godot export templates.
#   tools/export.sh
set -euo pipefail
cd "$(dirname "$0")/.."
GODOT="${GODOT:-godot}"
for p in client-linux client-win server-linux client-web; do
	dir="build/$p"
	rm -rf "$dir"; mkdir -p "$dir/packs"
	echo "== export $p"
	"$GODOT" --headless --path game --export-release "$p" > "build/export-$p.log" 2>&1 \
		|| { tail -20 "build/export-$p.log"; exit 1; }
done
for room in game/rooms/*/; do
	id="$(basename "$room")"
	[ -f "$room/room.json" ] || continue
	echo "== pack $id"
	go run ./tools/packroom "$id"
done
for p in client-linux client-win server-linux; do
	cp build/packs/*.pck "build/$p/packs/"
done
ls -la build/client-linux build/client-win build/server-linux build/*/packs
