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
	var b strings.Builder
	for _, k := range order {
		fmt.Fprintf(&b, "[preset.%s]\n", k)
		for _, l := range body[k] {
			b.WriteString(l + "\n")
		}
	}
	return strings.TrimRight(b.String(), "\n") + "\n", nil
}
