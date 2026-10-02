package room

import (
	"bufio"
	"fmt"
	"os"
	"path/filepath"
	"regexp"
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
			// Scene root: its children are addressed without a prefix.
			if inst := instRe.FindStringSubmatch(attrs["instance"]); inst != nil && prefix == "" {
				if err := descend(ext[inst[1]], resRoot, "", out, depth); err != nil {
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
