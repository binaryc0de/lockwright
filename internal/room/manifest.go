// Package room loads and validates room manifests (room.yaml, spec_version 1).
// The normative format is docs/schema/room.schema.json; this package adds the
// checks a schema cannot express (graph shape, references, files on disk).
package room

import (
	"bytes"
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"

	"go.yaml.in/yaml/v3"
)

// Manifest is the typed view of room.yaml. Only fields that cross-checks need
// are typed; the schema validates the rest.
type Manifest struct {
	SpecVersion int                 `yaml:"spec_version"`
	ID          string              `yaml:"id"`
	Title       string              `yaml:"title"`
	Version     string              `yaml:"version"`
	Mode        Mode                `yaml:"mode"`
	EntryScene  string              `yaml:"entry_scene"`
	Briefing    map[string]string   `yaml:"briefing"`
	Variables   map[string]Variable `yaml:"variables"`
	Puzzles     []Puzzle            `yaml:"puzzles"`
	Exit        struct {
		Puzzle string `yaml:"puzzle"`
	} `yaml:"exit"`
	CTF struct {
		Challenges []Challenge `yaml:"challenges"`
	} `yaml:"ctf"`
	Solution []map[string]string `yaml:"solution"`
}

type Mode struct {
	DurationMinutes int `yaml:"duration_minutes"`
	Players         struct {
		Min int `yaml:"min"`
		Max int `yaml:"max"`
	} `yaml:"players"`
}

type Variable struct {
	Type    string   `yaml:"type"`
	Length  int      `yaml:"length"`
	Choices []string `yaml:"choices"`
}

type Puzzle struct {
	ID         string    `yaml:"id"`
	Title      string    `yaml:"title"`
	Requires   []string  `yaml:"requires"`
	SolvedWhen Condition `yaml:"solved_when"`
	Hints      []string  `yaml:"hints"`
}

// Condition mirrors the closed solved_when vocabulary (ADR-0005).
type Condition struct {
	ItemPickedUp string `yaml:"item_picked_up"`
	NodeState    *struct {
		Path  string `yaml:"path"`
		State string `yaml:"state"`
	} `yaml:"node_state"`
	FlagAccepted *struct {
		Challenge string `yaml:"challenge"`
	} `yaml:"flag_accepted"`
	AllOf []Condition `yaml:"all_of"`
	AnyOf []Condition `yaml:"any_of"`
}

type Challenge struct {
	ID    string `yaml:"id"`
	Kind  string `yaml:"kind"`
	Build string `yaml:"build"`
	Flag  struct {
		Type   string `yaml:"type"`
		Format string `yaml:"format"`
	} `yaml:"flag"`
	Healthcheck *struct {
		Path string `yaml:"path"`
	} `yaml:"healthcheck"`
}

// Loaded is a parsed manifest plus the untyped document used for schema
// validation and JSON emission.
type Loaded struct {
	Dir      string
	Manifest Manifest
	Doc      any
}

// Load reads <dir>/room.yaml.
func Load(dir string) (*Loaded, error) {
	raw, err := os.ReadFile(filepath.Join(dir, "room.yaml"))
	if err != nil {
		return nil, err
	}
	var doc any
	if err := yaml.Unmarshal(raw, &doc); err != nil {
		return nil, fmt.Errorf("parse room.yaml: %w", err)
	}
	var m Manifest
	if err := yaml.Unmarshal(raw, &m); err != nil {
		return nil, fmt.Errorf("parse room.yaml: %w", err)
	}
	return &Loaded{Dir: dir, Manifest: m, Doc: doc}, nil
}

// JSON returns the canonical room.json the Godot runtime reads (ADR-0006):
// the YAML document re-encoded with sorted keys and two-space indentation.
func (l *Loaded) JSON() ([]byte, error) {
	var buf bytes.Buffer
	enc := json.NewEncoder(&buf)
	enc.SetIndent("", "  ")
	enc.SetEscapeHTML(false)
	if err := enc.Encode(l.Doc); err != nil {
		return nil, err
	}
	return buf.Bytes(), nil
}
