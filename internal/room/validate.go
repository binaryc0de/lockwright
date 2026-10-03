package room

import (
	"bytes"
	"errors"
	"fmt"
	"io/fs"
	"os"
	"path/filepath"
	"regexp"
	"slices"
	"strings"

	"github.com/santhosh-tekuri/jsonschema/v6"
)

type Level string

const (
	Error   Level = "error"
	Warning Level = "warning"
)

type Issue struct {
	Level Level  `json:"level"`
	Code  string `json:"code"`
	Msg   string `json:"message"`
}

func (i Issue) String() string { return fmt.Sprintf("%s [%s] %s", i.Level, i.Code, i.Msg) }

// Report collects issues for one room.
type Report struct {
	Room   string  `json:"room"`
	Issues []Issue `json:"issues"`
}

func (r *Report) add(l Level, code, format string, args ...any) {
	r.Issues = append(r.Issues, Issue{Level: l, Code: code, Msg: fmt.Sprintf(format, args...)})
}

// Failed reports whether any issue is an error.
func (r *Report) Failed() bool {
	return slices.ContainsFunc(r.Issues, func(i Issue) bool { return i.Level == Error })
}

// CompileSchema loads docs/schema/room.schema.json.
func CompileSchema(path string) (*jsonschema.Schema, error) {
	c := jsonschema.NewCompiler()
	return c.Compile(path)
}

var (
	templateRe  = regexp.MustCompile(`\{\{\s*([a-zA-Z0-9_.]+)\s*\}\}`)
	literalFlag = regexp.MustCompile(`(?i)\bflag\{[^{}\s]+\}`)
	classNameRe = regexp.MustCompile(`(?m)^\s*class_name\s`)
	// Room scripts may only use the SDK API (PLAN.md 8.2). Warnings in the prototype.
	forbiddenAPIs = []string{"rpc(", "rpc_id(", "multiplayer.", "HTTPRequest", "HTTPClient", "OS.execute", "OS.create_process", "OS.shell_open", "StreamPeerTCP", "PacketPeerUDP", "load_resource_pack"}
)

// Validate runs every prototype check on a room directory. resRoot is the
// Godot project root (the directory res:// maps to).
func Validate(dir, resRoot string, schema *jsonschema.Schema) *Report {
	rep := &Report{Room: filepath.Base(dir)}
	l, err := Load(dir)
	if err != nil {
		rep.add(Error, "load", "%v", err)
		return rep
	}
	if schema != nil {
		// Round-trip through JSON so the validator sees exactly the value
		// types encoding/json produces (and room.json will contain).
		js, err := l.JSON()
		if err != nil {
			rep.add(Error, "load", "room.yaml is not representable as JSON: %v", err)
			return rep
		}
		inst, err := jsonschema.UnmarshalJSON(bytes.NewReader(js))
		if err != nil {
			rep.add(Error, "load", "%v", err)
			return rep
		}
		if err := schema.Validate(inst); err != nil {
			var ve *jsonschema.ValidationError
			if errors.As(err, &ve) {
				for _, leaf := range leaves(ve) {
					rep.add(Error, "schema", "%s", leaf)
				}
			} else {
				rep.add(Error, "schema", "%v", err)
			}
			// Typed checks below assume a schema-shaped document; stop here.
			return rep
		}
	}
	m := l.Manifest

	if m.ID != filepath.Base(dir) {
		rep.add(Error, "id", "id %q does not match directory name %q", m.ID, filepath.Base(dir))
	}
	if m.Mode.Players.Min > m.Mode.Players.Max {
		rep.add(Error, "players", "mode.players.min (%d) > max (%d)", m.Mode.Players.Min, m.Mode.Players.Max)
	}

	checkFiles(rep, l, resRoot)
	puzzles := checkGraph(rep, m)
	checkConditions(rep, m, resRoot, puzzles)
	checkChallenges(rep, l)
	checkTemplates(rep, m)
	checkDifficulties(rep, m, resRoot)
	checkSources(rep, dir)
	checkJSON(rep, l)
	return rep
}

func leaves(ve *jsonschema.ValidationError) []string {
	if len(ve.Causes) == 0 {
		loc := "/" + strings.Join(ve.InstanceLocation, "/")
		return []string{fmt.Sprintf("%s: %v", loc, ve.ErrorKind)}
	}
	var out []string
	for _, c := range ve.Causes {
		out = append(out, leaves(c)...)
	}
	return out
}

func checkFiles(rep *Report, l *Loaded, resRoot string) {
	m := l.Manifest
	wantPrefix := "res://rooms/" + m.ID + "/"
	if !strings.HasPrefix(m.EntryScene, wantPrefix) {
		rep.add(Error, "entry_scene", "entry_scene %q must live under %s", m.EntryScene, wantPrefix)
	} else if _, err := os.Stat(ResToFS(m.EntryScene, resRoot)); err != nil {
		rep.add(Error, "entry_scene", "entry_scene %q not found", m.EntryScene)
	}
	for key, rel := range m.Briefing {
		if !safeRel(rel) {
			rep.add(Error, "path", "briefing.%s %q must be a relative path inside the room", key, rel)
			continue
		}
		if _, err := os.Stat(filepath.Join(l.Dir, rel)); err != nil {
			rep.add(Error, "briefing", "briefing.%s file %q not found", key, rel)
		}
	}
}

func safeRel(p string) bool {
	if filepath.IsAbs(p) {
		return false
	}
	return !slices.Contains(strings.Split(filepath.ToSlash(p), "/"), "..")
}

// checkGraph verifies the puzzle dependency chart: unique ids, resolvable
// prerequisites, no cycles, an exit puzzle that exists, and no orphans.
func checkGraph(rep *Report, m Manifest) map[string]Puzzle {
	byID := map[string]Puzzle{}
	for _, p := range m.Puzzles {
		if _, dup := byID[p.ID]; dup {
			rep.add(Error, "graph", "duplicate puzzle id %q", p.ID)
		}
		byID[p.ID] = p
	}
	for _, p := range m.Puzzles {
		for _, r := range p.Requires {
			if _, ok := byID[r]; !ok {
				rep.add(Error, "graph", "puzzle %q requires unknown puzzle %q", p.ID, r)
			}
			if r == p.ID {
				rep.add(Error, "graph", "puzzle %q requires itself", p.ID)
			}
		}
	}
	if cycle := findCycle(m.Puzzles, byID); cycle != nil {
		rep.add(Error, "graph", "puzzle graph has a cycle: %s", strings.Join(cycle, " -> "))
	}
	exit, ok := byID[m.Exit.Puzzle]
	if !ok {
		rep.add(Error, "graph", "exit.puzzle %q is not a declared puzzle", m.Exit.Puzzle)
		return byID
	}
	// Every puzzle should contribute to the exit; anything else is a dead end.
	needed := map[string]bool{}
	var walk func(id string)
	walk = func(id string) {
		if needed[id] {
			return
		}
		needed[id] = true
		for _, r := range byID[id].Requires {
			walk(r)
		}
	}
	walk(exit.ID)
	for _, p := range m.Puzzles {
		if !needed[p.ID] {
			rep.add(Warning, "graph", "puzzle %q does not lead to the exit puzzle %q", p.ID, exit.ID)
		}
	}
	return byID
}

// findCycle returns one cycle as a list of ids (first id repeated at the end), or nil.
func findCycle(puzzles []Puzzle, byID map[string]Puzzle) []string {
	const (
		white = iota
		grey
		black
	)
	color := map[string]int{}
	var stack []string
	var visit func(id string) []string
	visit = func(id string) []string {
		color[id] = grey
		stack = append(stack, id)
		for _, r := range byID[id].Requires {
			if _, ok := byID[r]; !ok {
				continue
			}
			switch color[r] {
			case grey:
				i := slices.Index(stack, r)
				return append(slices.Clone(stack[i:]), r)
			case white:
				if c := visit(r); c != nil {
					return c
				}
			}
		}
		stack = stack[:len(stack)-1]
		color[id] = black
		return nil
	}
	for _, p := range puzzles {
		if color[p.ID] == white {
			if c := visit(p.ID); c != nil {
				return c
			}
		}
	}
	return nil
}

// checkDifficulties validates every difficulty as its own room: ids unique,
// overrides name real puzzles and challenges, and the varied graph, solution
// and templates pass the same checks as the base.
func checkDifficulties(rep *Report, m Manifest, resRoot string) {
	seen := map[string]bool{}
	puzzles := map[string]bool{}
	for _, p := range m.Puzzles {
		puzzles[p.ID] = true
	}
	challenges := map[string]bool{}
	for _, c := range m.CTF.Challenges {
		challenges[c.ID] = true
	}
	for _, d := range m.Difficulties {
		if seen[d.ID] {
			rep.add(Error, "difficulty", "duplicate difficulty id %q", d.ID)
			continue
		}
		seen[d.ID] = true
		for id := range d.Puzzles {
			if !puzzles[id] {
				rep.add(Error, "difficulty", "difficulty %q overrides unknown puzzle %q", d.ID, id)
			}
		}
		for id := range d.Challenges {
			if !challenges[id] {
				rep.add(Error, "difficulty", "difficulty %q overrides unknown challenge %q", d.ID, id)
			}
		}
		if d.Puzzles == nil && d.Challenges == nil && d.Solution == nil {
			continue // same as the base, already checked
		}
		sub := &Report{}
		v := m.Variant(d.ID)
		byID := checkGraph(sub, v)
		checkConditions(sub, v, resRoot, byID)
		checkTemplates(sub, v)
		for _, is := range sub.Issues {
			rep.add(is.Level, is.Code, "difficulty %s: %s", d.ID, is.Msg)
		}
	}
}

func checkConditions(rep *Report, m Manifest, resRoot string, puzzles map[string]Puzzle) {
	challenges := map[string]bool{}
	for _, c := range m.CTF.Challenges {
		challenges[c.ID] = true
	}
	var paths map[string]bool
	if strings.HasPrefix(m.EntryScene, "res://") {
		if p, err := ScenePaths(ResToFS(m.EntryScene, resRoot), resRoot); err == nil {
			paths = p
		}
	}
	var check func(pid string, c Condition)
	check = func(pid string, c Condition) {
		if c.NodeState != nil && paths != nil && !paths[c.NodeState.Path] {
			rep.add(Error, "node_path", "puzzle %q: node_state path %q not found in %s", pid, c.NodeState.Path, m.EntryScene)
		}
		if c.FlagAccepted != nil && !challenges[c.FlagAccepted.Challenge] {
			rep.add(Error, "ctf", "puzzle %q: flag_accepted references unknown challenge %q", pid, c.FlagAccepted.Challenge)
		}
		for _, sub := range c.AllOf {
			check(pid, sub)
		}
		for _, sub := range c.AnyOf {
			check(pid, sub)
		}
	}
	for _, p := range m.Puzzles {
		check(p.ID, p.SolvedWhen)
	}
	for i, step := range m.Solution {
		for _, key := range []string{"target", "lock", "node"} {
			if v, ok := step[key]; ok && paths != nil && !paths[v] {
				rep.add(Error, "node_path", "solution[%d].%s %q not found in %s", i, key, v, m.EntryScene)
			}
		}
		if ch, ok := step["challenge"]; ok && !challenges[ch] {
			rep.add(Error, "ctf", "solution[%d] references unknown challenge %q", i, ch)
		}
	}
}

func checkChallenges(rep *Report, l *Loaded) {
	seen := map[string]bool{}
	for _, c := range l.Manifest.CTF.Challenges {
		if seen[c.ID] {
			rep.add(Error, "ctf", "duplicate challenge id %q", c.ID)
		}
		seen[c.ID] = true
		if c.Build == "" {
			continue
		}
		if !safeRel(c.Build) {
			rep.add(Error, "path", "challenge %q build %q must be a relative path inside the room", c.ID, c.Build)
			continue
		}
		if _, err := os.Stat(filepath.Join(l.Dir, c.Build, "Dockerfile")); err != nil {
			rep.add(Error, "ctf", "challenge %q: no Dockerfile in %s", c.ID, c.Build)
		}
	}
}

// checkTemplates makes sure every {{name}} in lock codes and solution values
// refers to a declared variable or to flags.<challenge>.
func checkTemplates(rep *Report, m Manifest) {
	challenges := map[string]bool{}
	for _, c := range m.CTF.Challenges {
		challenges[c.ID] = true
	}
	for i, step := range m.Solution {
		for _, match := range templateRe.FindAllStringSubmatch(step["value"], -1) {
			name := match[1]
			if ch, ok := strings.CutPrefix(name, "flags."); ok {
				if !challenges[ch] {
					rep.add(Error, "template", "solution[%d]: {{%s}} names an unknown challenge", i, name)
				}
				continue
			}
			if _, ok := m.Variables[name]; !ok {
				rep.add(Error, "template", "solution[%d]: {{%s}} is not a declared variable", i, name)
			}
		}
	}
}

// checkSources scans room text files for literal flags and room scripts for
// APIs the SDK rules forbid.
func checkSources(rep *Report, dir string) {
	_ = filepath.WalkDir(dir, func(path string, d fs.DirEntry, err error) error {
		if err != nil || d.IsDir() {
			return nil
		}
		ext := strings.ToLower(filepath.Ext(path))
		if !slices.Contains([]string{".gd", ".tscn", ".tres", ".yaml", ".yml", ".json", ".md", ".txt", ".go", ".py", ".js", ".html", ".sql", ".env"}, ext) &&
			filepath.Base(path) != "Dockerfile" {
			return nil
		}
		data, err := os.ReadFile(path)
		if err != nil {
			return nil
		}
		rel, _ := filepath.Rel(dir, path)
		if loc := literalFlag.FindIndex(data); loc != nil {
			line := bytes.Count(data[:loc[0]], []byte("\n")) + 1
			// Never echo the value itself: it may be a real flag.
			rep.add(Error, "flag_literal", "%s:%d contains what looks like a literal flag; flags must be templates", rel, line)
		}
		if ext == ".gd" {
			if classNameRe.Match(data) {
				rep.add(Warning, "class_name", "%s declares class_name; pack class caches are ignored (ADR-0007), use preload()", rel)
			}
			for _, api := range forbiddenAPIs {
				if bytes.Contains(data, []byte(api)) {
					rep.add(Warning, "forbidden_api", "%s uses %q; room scripts should only use the SDK API", rel, api)
				}
			}
		}
		return nil
	})
}

// checkJSON verifies the generated room.json matches room.yaml (ADR-0006).
func checkJSON(rep *Report, l *Loaded) {
	want, err := l.JSON()
	if err != nil {
		rep.add(Error, "room_json", "cannot encode room.json: %v", err)
		return
	}
	got, err := os.ReadFile(filepath.Join(l.Dir, "room.json"))
	if err != nil {
		rep.add(Error, "room_json", "room.json missing; run: go run ./tools/roomcheck -write-json %s", l.Dir)
		return
	}
	if !bytes.Equal(got, want) {
		rep.add(Error, "room_json", "room.json is stale; run: go run ./tools/roomcheck -write-json %s", l.Dir)
	}
}

// WriteJSON regenerates <dir>/room.json from room.yaml.
func WriteJSON(dir string) error {
	l, err := Load(dir)
	if err != nil {
		return err
	}
	b, err := l.JSON()
	if err != nil {
		return err
	}
	return os.WriteFile(filepath.Join(dir, "room.json"), b, 0o644)
}
