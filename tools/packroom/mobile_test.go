package main

import (
	"os"
	"strconv"
	"strings"
	"testing"
)

func TestMobilePresetIsDerivedAndStable(t *testing.T) {
	b, err := os.ReadFile("../../game/export_presets.cfg")
	if err != nil {
		t.Fatal(err)
	}
	orig := string(b)
	once, err := withMobilePreset(orig, "room-pack-night_shift")
	if err != nil {
		t.Fatal(err)
	}
	twice, err := withMobilePreset(once, "room-pack-night_shift")
	if err != nil {
		t.Fatal(err)
	}
	if once != twice {
		t.Fatal("rewriting an existing mobile preset changed the file")
	}
	if had := strings.Contains(orig, `name="room-pack-night_shift-mobile"`); !had &&
		!strings.HasPrefix(once, strings.TrimRight(orig, "\n")) {
		t.Error("adding the mobile preset changed the existing presets")
	}
	if v, _ := presetValue(once, "room-pack-night_shift-mobile", "export_path"); !strings.HasSuffix(v, "-mobile.pck") {
		t.Errorf("export_path %q", v)
	}
	desk, _ := presetValue(once, "room-pack-night_shift", "exclude_filter")
	mob, _ := presetValue(once, "room-pack-night_shift-mobile", "exclude_filter")
	if desk == "" || desk != mob {
		t.Errorf("filters differ: %q vs %q", desk, mob)
	}
	order, body := presetSections(once)
	n := 0
	for _, k := range order {
		if !strings.HasSuffix(k, ".options") {
			if k != strconv.Itoa(n) {
				t.Fatalf("preset sections not numbered 0..n-1: %v", order)
			}
			n++
		}
	}
	opts := strings.Join(body[sectionNamed(body, order, "room-pack-night_shift-mobile")+".options"], "\n")
	if !strings.Contains(opts, "texture_format/s3tc_bptc=false") || !strings.Contains(opts, "texture_format/etc2_astc=true") {
		t.Errorf("mobile options: %s", opts)
	}
}
