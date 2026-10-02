// Package rooms is the platform's view of installed rooms: each
// <rooms_dir>/<id>/room.json (the generated manifest, ADR-0006). The
// platform trusts its own copy of a room for challenge definitions and
// flags, never what a game server sends.
package rooms

import (
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"sort"

	"github.com/binaryc0de/escapebox/platform/internal/orchestrator"
)

// Room is one installed room.
type Room struct {
	ID      string `json:"id"`
	Title   string `json:"title"`
	Version string `json:"version"`
	Mode    struct {
		DurationMinutes int `json:"duration_minutes"`
		Players         struct {
			Min int `json:"min"`
			Max int `json:"max"`
		} `json:"players"`
	} `json:"mode"`
	CTF struct {
		Challenges []orchestrator.Challenge `json:"challenges"`
	} `json:"ctf"`
	// Dir is the room's directory (challenge build contexts live under it).
	Dir string `json:"-"`
}

// Challenge returns a challenge by id.
func (r Room) Challenge(id string) (orchestrator.Challenge, bool) {
	for _, c := range r.CTF.Challenges {
		if c.ID == id {
			return c, true
		}
	}
	return orchestrator.Challenge{}, false
}

// Catalog holds the installed rooms.
type Catalog struct {
	rooms map[string]Room
}

// Load reads every <dir>/*/room.json.
func Load(dir string) (*Catalog, error) {
	matches, err := filepath.Glob(filepath.Join(dir, "*", "room.json"))
	if err != nil {
		return nil, err
	}
	c := &Catalog{rooms: map[string]Room{}}
	for _, m := range matches {
		b, err := os.ReadFile(m)
		if err != nil {
			return nil, err
		}
		var r Room
		if err := json.Unmarshal(b, &r); err != nil {
			return nil, fmt.Errorf("%s: %w", m, err)
		}
		if r.ID == "" || r.ID != filepath.Base(filepath.Dir(m)) {
			return nil, fmt.Errorf("%s: id %q does not match its directory", m, r.ID)
		}
		r.Dir = filepath.Dir(m)
		c.rooms[r.ID] = r
	}
	return c, nil
}

// Room returns an installed room.
func (c *Catalog) Room(id string) (Room, bool) {
	r, ok := c.rooms[id]
	return r, ok
}

// All returns every room, sorted by id.
func (c *Catalog) All() []Room {
	out := make([]Room, 0, len(c.rooms))
	for _, r := range c.rooms {
		out = append(out, r)
	}
	sort.Slice(out, func(i, j int) bool { return out[i].ID < out[j].ID })
	return out
}
