package main

import (
	"os"
	"path/filepath"
	"reflect"
	"strings"
	"testing"
)

const presetsCfg = `[preset.3]

name="room-pack-a"
exclude_filter="res://core/*,res://rooms/b/*"

[preset.3.options]

[preset.4]

name="room-pack-b"
exclude_filter="res://core/*"
`

func TestPresetsMustExcludeOtherRooms(t *testing.T) {
	if m := missingExcludes(presetsCfg, "room-pack-a", []string{"b"}); len(m) != 0 {
		t.Fatalf("a excludes b already: %v", m)
	}
	if m := missingExcludes(presetsCfg, "room-pack-b", []string{"a", "c"}); !reflect.DeepEqual(m, []string{"res://rooms/a/*", "res://rooms/c/*"}) {
		t.Fatalf("b missing: %v", m)
	}
}

func TestForeignRoomPathsInAPackAreFound(t *testing.T) {
	pack := []byte("GDPC....res://rooms/a/room.json....rooms/b/README.md")
	if got := foreignRooms(pack, []string{"b", "c"}); !reflect.DeepEqual(got, []string{"b"}) {
		t.Fatalf("found %v", got)
	}
}

func TestOtherRoomsListsEveryRoomDirectory(t *testing.T) {
	dir := t.TempDir()
	for _, d := range []string{"a", "b", "draft"} {
		os.MkdirAll(filepath.Join(dir, "rooms", d), 0o755)
	}
	os.WriteFile(filepath.Join(dir, "rooms", "notes.txt"), nil, 0o644)
	got, err := otherRooms(dir, "a")
	if err != nil || strings.Join(got, ",") != "b,draft" {
		t.Fatalf("%v %v", got, err)
	}
}

// The real presets: every room's pack excludes every other room.
func TestRealPresetsAreScoped(t *testing.T) {
	game := filepath.Join("..", "..", "game")
	b, err := os.ReadFile(filepath.Join(game, "export_presets.cfg"))
	if err != nil {
		t.Fatal(err)
	}
	rooms, _ := os.ReadDir(filepath.Join(game, "rooms"))
	for _, r := range rooms {
		if _, err := os.Stat(filepath.Join(game, "rooms", r.Name(), "room.yaml")); err != nil {
			continue // not a packable room yet
		}
		others, _ := otherRooms(game, r.Name())
		if m := missingExcludes(string(b), "room-pack-"+r.Name(), others); len(m) != 0 {
			t.Errorf("room-pack-%s must exclude %v", r.Name(), m)
		}
	}
}
