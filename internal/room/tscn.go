package room

import (
	"bufio"
	"fmt"
	"os"
	"path/filepath"
	"regexp"
	"sort"
	"strings"
)

var (
	extResRe = regexp.MustCompile(`^\[ext_resource\b.*?\bpath="([^"]+)".*?\bid="([^"]+)"`)
	nodeRe   = regexp.MustCompile(`^\[node\b(.*)\]$`)
	attrRe   = regexp.MustCompile(`(\w+)=("[^"]*"|ExtResource\(\s*"[^"]*"\s*\))`)
	instRe   = regexp.MustCompile(`ExtResource\(\s*"([^"]*)"\s*\)`)
)

const maxSceneDepth = 8

// ScenePaths returns every node path (relative to the scene root, e.g.
// "Cabinet/Keypad") in a text scene, descending into instanced sub-scenes so
// paths inside prefabs resolve too. resRoot is the directory res:// maps to.
func ScenePaths(scenePath, resRoot string) (map[string]bool, error) {
	out := map[string]bool{}
	if err := collectPaths(scenePath, resRoot, "", out, 0); err != nil {
		return nil, err
	}
	return out, nil
}

func collectPaths(scenePath, resRoot, prefix string, out map[string]bool, depth int) error {
	if depth > maxSceneDepth {
		return fmt.Errorf("%s: scene instancing deeper than %d levels", scenePath, maxSceneDepth)
	}
	f, err := os.Open(scenePath)
	if err != nil {
		return err
	}
	defer f.Close()

	ext := map[string]string{}
	sc := bufio.NewScanner(f)
	sc.Buffer(make([]byte, 1024*1024), 16*1024*1024)
	for sc.Scan() {
		line := strings.TrimSpace(sc.Text())
		if m := extResRe.FindStringSubmatch(line); m != nil {
			ext[m[2]] = m[1]
			continue
		}
		m := nodeRe.FindStringSubmatch(line)
		if m == nil {
			continue
		}
		attrs := map[string]string{}
		for _, a := range attrRe.FindAllStringSubmatch(m[1], -1) {
			attrs[a[1]] = strings.Trim(a[2], `"`)
		}
		parent, hasParent := attrs["parent"]
		if !hasParent {
			// Scene root. An inherited scene's root instances its base scene;
			// the base's children sit at the same level as this scene's own
			// children, so they keep the current prefix.
			if inst := instRe.FindStringSubmatch(attrs["instance"]); inst != nil {
				if err := descend(ext[inst[1]], resRoot, prefix, out, depth); err != nil {
					return err
				}
			}
			continue
		}
		var rel string
		switch parent {
		case ".":
			rel = attrs["name"]
		default:
			rel = parent + "/" + attrs["name"]
		}
		full := join(prefix, rel)
		out[full] = true
		if inst := instRe.FindStringSubmatch(attrs["instance"]); inst != nil {
			if err := descend(ext[inst[1]], resRoot, full, out, depth); err != nil {
				return err
			}
		}
	}
	return sc.Err()
}

func descend(resPath, resRoot, prefix string, out map[string]bool, depth int) error {
	if !strings.HasPrefix(resPath, "res://") || !strings.HasSuffix(resPath, ".tscn") {
		return nil // .glb/.scn instances: their internals are not addressable by path here
	}
	return collectPaths(ResToFS(resPath, resRoot), resRoot, prefix, out, depth+1)
}

// ResToFS maps a res:// path to the filesystem under resRoot.
func ResToFS(resPath, resRoot string) string {
	return filepath.Join(resRoot, filepath.FromSlash(strings.TrimPrefix(resPath, "res://")))
}

func join(prefix, rel string) string {
	if prefix == "" {
		return rel
	}
	return prefix + "/" + rel
}

var editableRe = regexp.MustCompile(`^\[editable path="([^"]*)"\]`)

// UneditableOverrides lists instanced nodes in a text scene whose children are
// overridden (`[node name=.. parent="Inst/.."]` with no type or instance)
// without an `[editable path="Inst"]` line. Godot applies such overrides when
// it loads the text scene, but its export repacks scenes and drops them, so a
// room pack silently loses them (hidden variants reappear; ADR-0024 notes).
func UneditableOverrides(scenePath string) ([]string, error) {
	f, err := os.Open(scenePath)
	if err != nil {
		return nil, err
	}
	defer f.Close()
	instances := map[string]bool{}
	editable := map[string]bool{}
	var overrideParents []string
	sc := bufio.NewScanner(f)
	sc.Buffer(make([]byte, 1<<20), 1<<24)
	for sc.Scan() {
		line := sc.Text()
		if m := editableRe.FindStringSubmatch(line); m != nil {
			editable[m[1]] = true
			continue
		}
		m := nodeRe.FindStringSubmatch(line)
		if m == nil {
			continue
		}
		attrs := map[string]string{}
		for _, a := range attrRe.FindAllStringSubmatch(m[1], -1) {
			attrs[a[1]] = strings.Trim(a[2], `"`)
		}
		parent, hasParent := attrs["parent"]
		if !hasParent {
			continue
		}
		path := join(strings.TrimPrefix(strings.TrimPrefix(parent, "."), "/"), attrs["name"])
		switch {
		case attrs["instance"] != "":
			instances[path] = true
		case attrs["type"] == "":
			overrideParents = append(overrideParents, strings.TrimPrefix(strings.TrimPrefix(parent, "."), "/"))
		}
	}
	missing := map[string]bool{}
	for _, p := range overrideParents {
		parts := strings.Split(p, "/")
		for i := len(parts); i > 0; i-- {
			cand := strings.Join(parts[:i], "/")
			if instances[cand] {
				if !editable[cand] {
					missing[cand] = true
				}
				break
			}
		}
	}
	out := make([]string, 0, len(missing))
	for k := range missing {
		out = append(out, k)
	}
	sort.Strings(out)
	return out, sc.Err()
}
