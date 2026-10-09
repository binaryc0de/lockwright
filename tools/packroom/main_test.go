package main

import (
	"os"
	"path/filepath"
	"strings"
	"testing"
)

func TestUnreferencedModelsAreLeftOut(t *testing.T) {
	dir := t.TempDir()
	room := filepath.Join(dir, "rooms", "r")
	if err := os.MkdirAll(room, 0o755); err != nil {
		t.Fatal(err)
	}
	write := func(name, body string) {
		if err := os.WriteFile(filepath.Join(room, name), []byte(body), 0o644); err != nil {
			t.Fatal(err)
		}
	}
	write("room.tscn", `[ext_resource path="res://rooms/r/used.glb"]`)
	write("used.glb", "x")
	write("source.glb", "x")
	write("kit.res", "x")
	got, err := roomResources(dir, "r")
	if err != nil {
		t.Fatal(err)
	}
	want := []string{"res://rooms/r/kit.res", "res://rooms/r/room.tscn", "res://rooms/r/used.glb"}
	if strings.Join(got, ",") != strings.Join(want, ",") {
		t.Fatalf("got %v, want %v", got, want)
	}
}
