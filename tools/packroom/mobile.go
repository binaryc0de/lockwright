package main

import (
	"fmt"
	"regexp"
	"strings"
)

// Phones and tablets cannot use the desktop texture formats (S3TC/BPTC);
// Godot would unpack every texture to raw RGBA there, several times the
// memory (ADR-0038). So every room also gets a "-mobile" pack exported with
// ETC2/ASTC textures. Its preset is derived from the room's desktop preset
// and rewritten on every run, so the two never drift: edit the desktop one.

var sectionRe = regexp.MustCompile(`^\[preset\.(\d+)(\.options)?\]$`)

// presetSections splits export_presets.cfg into its [preset.N] and
// [preset.N.options] sections, keyed by "N" and "N.options", in file order.
func presetSections(presets string) (order []string, body map[string][]string) {
	body = map[string][]string{}
	cur := ""
	for _, line := range strings.Split(strings.TrimRight(presets, "\n"), "\n") {
		if m := sectionRe.FindStringSubmatch(strings.TrimSpace(line)); m != nil {
			cur = m[1] + m[2]
			order = append(order, cur)
			continue
		}
		if cur != "" {
			body[cur] = append(body[cur], line)
		}
	}
	return order, body
}

func sectionNamed(body map[string][]string, order []string, name string) string {
	for _, k := range order {
		if strings.HasSuffix(k, ".options") {
			continue
		}
		for _, l := range body[k] {
			if strings.TrimSpace(l) == fmt.Sprintf("name=%q", name) {
				return k
			}
		}
	}
	return ""
}

// withMobilePreset returns presets with "<preset>-mobile" (re)written from
// "<preset>": same filters, ETC2/ASTC textures instead of S3TC/BPTC. Godot
// numbers presets 0..n-1 without gaps, so an existing mobile preset keeps its
// number and a new one is appended.
func withMobilePreset(presets, preset string) (string, error) {
	order, body := presetSections(presets)
	src := sectionNamed(body, order, preset)
	if src == "" {
		return "", fmt.Errorf("export preset %q missing", preset)
	}
	mobile := preset + "-mobile"
	dst := sectionNamed(body, order, mobile)
	if dst == "" {
		n := 0
		for _, k := range order {
			if !strings.HasSuffix(k, ".options") {
				n++
			}
		}
		dst = fmt.Sprint(n)
		order = append(order, dst, dst+".options")
	}
	var main []string
	for _, l := range body[src] {
		switch {
		case strings.HasPrefix(l, "name="):
			l = fmt.Sprintf("name=%q", mobile)
		case strings.HasPrefix(l, "export_path="):
			l = strings.Replace(l, ".pck\"", "-mobile.pck\"", 1)
		}
		main = append(main, l)
	}
	var opts []string
	for _, l := range body[src+".options"] {
		switch {
		case strings.HasPrefix(l, "texture_format/s3tc_bptc="):
			l = "texture_format/s3tc_bptc=false"
		case strings.HasPrefix(l, "texture_format/etc2_astc="):
			l = "texture_format/etc2_astc=true"
		}
		opts = append(opts, l)
	}
	body[dst] = main
	body[dst+".options"] = opts
	return joinSections(order, body), nil
}

func joinSections(order []string, body map[string][]string) string {
	var b strings.Builder
	for _, k := range order {
		fmt.Fprintf(&b, "[preset.%s]\n", k)
		for _, l := range body[k] {
			b.WriteString(l + "\n")
		}
	}
	return strings.TrimRight(b.String(), "\n") + "\n"
}

// Room art in assets/core (props, materials, CC0 textures) is not in the
// browser client's own pack: a browser holds that pack in memory, and most of
// it belonged to one room (ADR-0038). Each room pack therefore carries the
// shared assets it uses. The room's preset exports the room's own resources
// plus their dependencies; packroom writes that list on every run.

// sharedArt lists the assets/core folders that travel with the room packs
// that use them. assets/core/third_party/kenney stays in the client (SDK
// sounds).
var sharedArt = []string{
	"res://assets/core/props/*", "res://assets/core/materials/*",
	"res://assets/core/third_party/ambientcg/*", "res://assets/core/third_party/polyhaven/*",
}

// resourceExts are the files under a room that are Godot resources; data
// files (yaml, json, md) come in through the preset's include_filter.
var resourceExts = map[string]bool{
	".tscn": true, ".scn": true, ".tres": true, ".res": true, ".gd": true, ".gdshader": true,
	".glb": true, ".gltf": true, ".obj": true, ".png": true, ".jpg": true, ".jpeg": true,
	".webp": true, ".svg": true, ".exr": true, ".hdr": true, ".ogg": true, ".wav": true,
	".mp3": true, ".ttf": true, ".otf": true, ".woff": true, ".woff2": true,
}

// withRoomResources sets the preset to export `files` and their dependencies
// (Godot's "resources" filter), and keeps assets/core out of its excludes so
// those dependencies are packed.
func withRoomResources(presets, preset string, files []string) (string, error) {
	order, body := presetSections(presets)
	k := sectionNamed(body, order, preset)
	if k == "" {
		return "", fmt.Errorf("export preset %q missing", preset)
	}
	quoted := make([]string, len(files))
	for i, f := range files {
		quoted[i] = fmt.Sprintf("%q", f)
	}
	lines := body[k]
	hasFiles := false
	for i, l := range lines {
		switch {
		case strings.HasPrefix(l, "export_filter="):
			lines[i] = `export_filter="resources"`
		case strings.HasPrefix(l, "export_files="):
			lines[i] = "export_files=PackedStringArray(" + strings.Join(quoted, ", ") + ")"
			hasFiles = true
		case strings.HasPrefix(l, "exclude_filter="):
			var keep []string
			for _, p := range strings.Split(strings.Trim(strings.TrimPrefix(l, "exclude_filter="), `"`), ",") {
				if p != "" && p != "res://assets/*" {
					keep = append(keep, p)
				}
			}
			lines[i] = fmt.Sprintf("exclude_filter=%q", strings.Join(keep, ","))
		}
	}
	if !hasFiles {
		for i, l := range lines {
			if strings.HasPrefix(l, "export_filter=") {
				lines = append(lines[:i+1], append([]string{"export_files=PackedStringArray(" + strings.Join(quoted, ", ") + ")"}, lines[i+1:]...)...)
				break
			}
		}
	}
	body[k] = lines
	return joinSections(order, body), nil
}
