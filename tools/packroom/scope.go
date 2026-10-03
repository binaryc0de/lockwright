package main

import (
	"bytes"
	"fmt"
	"os"
	"path/filepath"
	"sort"
	"strings"
)

// A room pack must hold only its own room. Godot's room-pack presets export
// every resource that no filter excludes, so each preset has to exclude every
// other room's directory; otherwise one room's pack carries another's files
// (a draft room's design and scene inside a public pack, ADR-0030).

// otherRooms lists the directories under <gameDir>/rooms except id's.
func otherRooms(gameDir, id string) ([]string, error) {
	entries, err := os.ReadDir(filepath.Join(gameDir, "rooms"))
	if err != nil {
		return nil, err
	}
	var out []string
	for _, e := range entries {
		if e.IsDir() && e.Name() != id {
			out = append(out, e.Name())
		}
	}
	sort.Strings(out)
	return out, nil
}

// presetValue returns key's value in the [preset.N] section named name.
func presetValue(presets, name, key string) (string, bool) {
	inSection := false
	for _, line := range strings.Split(presets, "\n") {
		line = strings.TrimSpace(line)
		if strings.HasPrefix(line, "[") {
			inSection = false
			continue
		}
		if line == fmt.Sprintf("name=%q", name) {
			inSection = true
			continue
		}
		if inSection && strings.HasPrefix(line, key+"=") {
			v := strings.TrimPrefix(line, key+"=")
			return strings.Trim(v, `"`), true
		}
	}
	return "", false
}

// missingExcludes returns the exclude patterns the preset lacks, one
// "res://rooms/<other>/*" per other room.
func missingExcludes(presets, preset string, others []string) []string {
	have := map[string]bool{}
	if v, ok := presetValue(presets, preset, "exclude_filter"); ok {
		for _, p := range strings.Split(v, ",") {
			have[strings.TrimSpace(p)] = true
		}
	}
	var missing []string
	for _, o := range others {
		if want := "res://rooms/" + o + "/*"; !have[want] {
			missing = append(missing, want)
		}
	}
	return missing
}

// foreignRooms returns the other rooms whose paths appear in a built pack.
func foreignRooms(pack []byte, others []string) []string {
	var found []string
	for _, o := range others {
		if bytes.Contains(pack, []byte("rooms/"+o+"/")) {
			found = append(found, o)
		}
	}
	return found
}
