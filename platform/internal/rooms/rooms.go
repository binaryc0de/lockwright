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
	"strings"

	"github.com/binaryc0de/escapebox/platform/internal/orchestrator"
)

// Room is one installed room.
type Room struct {
	ID      string `json:"id"`
	Title   string `json:"title"`
	Version string `json:"version"`
	// Draft rooms are work in progress (room.yaml `draft: true`, ADR-0030):
	// the catalog leaves them out unless it was loaded with drafts.
	Draft bool `json:"draft"`
	Mode  struct {
		DurationMinutes int `json:"duration_minutes"`
		Players         struct {
			Min int `json:"min"`
			Max int `json:"max"`
		} `json:"players"`
	} `json:"mode"`
	CTF struct {
		Challenges []orchestrator.Challenge `json:"challenges"`
	} `json:"ctf"`
	// Difficulties the room offers (room.yaml `difficulties`); the first is
	// the default. Empty for rooms with a single level.
	Difficulties []Difficulty `json:"difficulties"`
	Briefing     struct {
		IntroMD string `json:"intro_md"`
	} `json:"briefing"`
	// Summary is the opening of the intro briefing, plain text, for the lobby.
	Summary string `json:"-"`
	// Dir is the room's directory (challenge build contexts live under it).
	Dir string `json:"-"`
}

// Challenge returns a challenge by id.
// Difficulty is one level of a room, as listed in the catalog.
type Difficulty struct {
	ID          string `json:"id"`
	Title       string `json:"title"`
	Description string `json:"description"`
}

// HasDifficulty reports whether id is one of the room's levels; "" always is
// (the default).
func (r Room) HasDifficulty(id string) bool {
	if id == "" {
		return true
	}
	for _, d := range r.Difficulties {
		if d.ID == id {
			return true
		}
	}
	return false
}

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
	rooms  map[string]Room
	hidden []string
}

// Load reads every <dir>/*/room.json, leaving out draft rooms.
func Load(dir string) (*Catalog, error) {
	return load(dir, false)
}

// LoadWithDrafts reads every <dir>/*/room.json, draft rooms included (for a
// private development platform).
func LoadWithDrafts(dir string) (*Catalog, error) {
	return load(dir, true)
}

func load(dir string, drafts bool) (*Catalog, error) {
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
		if r.Draft && !drafts {
			c.hidden = append(c.hidden, r.ID)
			continue
		}
		r.Dir = filepath.Dir(m)
		if r.Briefing.IntroMD != "" && !strings.Contains(r.Briefing.IntroMD, "..") {
			if b, err := os.ReadFile(filepath.Join(r.Dir, r.Briefing.IntroMD)); err == nil {
				r.Summary = summarize(string(b), 320)
			}
		}
		c.rooms[r.ID] = r
	}
	return c, nil
}

// Room returns an installed room.
func (c *Catalog) Room(id string) (Room, bool) {
	r, ok := c.rooms[id]
	return r, ok
}

// Hidden returns the ids of draft rooms that were left out, sorted.
func (c *Catalog) Hidden() []string {
	out := append([]string(nil), c.hidden...)
	sort.Strings(out)
	return out
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

// summarize turns the start of a markdown briefing into plain text: headings
// dropped, emphasis markers removed, paragraphs joined, cut at a word.
func summarize(md string, max int) string {
	var parts []string
	for _, para := range strings.Split(strings.ReplaceAll(md, "\r\n", "\n"), "\n\n") {
		p := strings.TrimSpace(para)
		if p == "" || strings.HasPrefix(p, "#") {
			continue
		}
		p = strings.NewReplacer("**", "", "__", "", "*", "", "_", "", "\n", " ").Replace(p)
		parts = append(parts, p)
		if len(strings.Join(parts, " ")) >= max {
			break
		}
	}
	s := strings.Join(parts, " ")
	if len(s) > max {
		cut := strings.LastIndex(s[:max], " ")
		if cut < max/2 {
			cut = max
		}
		s = strings.TrimRight(s[:cut], ",.;:") + " ..."
	}
	return s
}
