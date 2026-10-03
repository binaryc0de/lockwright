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
	Solution     []map[string]string `yaml:"solution"`
	Difficulties []Difficulty        `yaml:"difficulties"`
}

// Difficulty is one level of a room (ADR-0022). The first listed is the
// default. A level replaces fields of puzzles and challenges with the same id,
// and may replace the whole solution.
type Difficulty struct {
	ID          string                       `yaml:"id"`
	Title       string                       `yaml:"title"`
	Description string                       `yaml:"description"`
	Puzzles     map[string]PuzzleOverride    `yaml:"puzzles"`
	Challenges  map[string]ChallengeOverride `yaml:"challenges"`
	Solution    []map[string]string          `yaml:"solution"`
}

// PuzzleOverride holds the puzzle fields a difficulty may replace; nil means
// "keep the base value".
type PuzzleOverride struct {
	Title    *string   `yaml:"title"`
	Requires *[]string `yaml:"requires"`
	Hints    []string  `yaml:"hints"`
	GMNotes  *string   `yaml:"gm_notes"`
}

// ChallengeOverride holds the challenge fields a difficulty may replace.
type ChallengeOverride struct {
	Hints []string `yaml:"hints"`
}

// Variant returns the manifest as played at difficulty id (the base for an
// id the room does not declare). Mirrors RoomManifest.for_difficulty.
func (m Manifest) Variant(id string) Manifest {
	v := m
	v.Puzzles = append([]Puzzle(nil), m.Puzzles...)
	for _, d := range m.Difficulties {
		if d.ID != id {
			continue
		}
		for i, p := range v.Puzzles {
			o, ok := d.Puzzles[p.ID]
			if !ok {
				continue
			}
			if o.Title != nil {
				p.Title = *o.Title
			}
			if o.Requires != nil {
				p.Requires = append([]string(nil), (*o.Requires)...)
			}
			if o.Hints != nil {
				p.Hints = o.Hints
			}
			v.Puzzles[i] = p
		}
		if d.Solution != nil {
			v.Solution = d.Solution
		}
	}
	return v
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
