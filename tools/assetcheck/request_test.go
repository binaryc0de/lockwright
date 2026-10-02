package main

import (
	"os"
	"reflect"
	"strings"
	"testing"
)

func readFixture(t *testing.T, name string) string {
	t.Helper()
	b, err := os.ReadFile("testdata/" + name)
	if err != nil {
		t.Fatal(err)
	}
	return string(b)
}

func TestParseRequestKeypad4(t *testing.T) {
	r, err := ParseRequest("keypad_4", readFixture(t, "keypad_4.md"))
	if err != nil {
		t.Fatal(err)
	}
	if r.Title != "keypad_4" || r.Status != "open" || r.Class != "prop" {
		t.Errorf("title/status/class = %q %q %q", r.Title, r.Status, r.Class)
	}
	if r.TriangleBudget != 20000 {
		t.Errorf("TriangleBudget = %d, want 20000", r.TriangleBudget)
	}
	if r.TextureMaxPx != 1024 {
		t.Errorf("TextureMaxPx = %d, want 1024", r.TextureMaxPx)
	}
	wantParts := []string{"body", "btn_0", "btn_1", "btn_2", "btn_3", "btn_4", "btn_5", "btn_6", "btn_7", "btn_8", "btn_9",
		"btn_clear", "btn_enter", "screen", "led_status", "body-col"}
	if !reflect.DeepEqual(r.Parts, wantParts) {
		t.Errorf("Parts = %v\nwant    %v", r.Parts, wantParts)
	}
	if len(r.Animations) != 0 {
		t.Errorf("Animations = %v, want none", r.Animations)
	}
	if r.Origin != OriginMountBack {
		t.Errorf("Origin = %q, want %q", r.Origin, OriginMountBack)
	}
	if len(r.Notes) != 0 {
		t.Errorf("Notes = %v", r.Notes)
	}
}

func TestParseRequestHeroTemplate(t *testing.T) {
	r, err := ParseRequest("drawer_cabinet", readFixture(t, "hero_template.md"))
	if err != nil {
		t.Fatal(err)
	}
	if r.Status != "in_review" || r.Class != "hero" {
		t.Errorf("status/class = %q %q", r.Status, r.Class)
	}
	if r.TriangleBudget != 60000 {
		t.Errorf("TriangleBudget = %d, want the hero number 60000", r.TriangleBudget)
	}
	if r.TextureMaxPx != 2048 {
		t.Errorf("TextureMaxPx = %d, want first occurrence 2048", r.TextureMaxPx)
	}
	wantParts := []string{"body", "btn_0", "btn_1", "btn_2", "btn_3", "btn_4", "btn_5", "btn_6", "btn_7", "btn_8", "btn_9",
		"btn_enter", "btn_clear", "drawer_01", "drawer_02", "drawer_03", "screen"}
	if !reflect.DeepEqual(r.Parts, wantParts) {
		t.Errorf("Parts = %v\nwant    %v", r.Parts, wantParts)
	}
	if !reflect.DeepEqual(r.Animations, []string{"open", "close"}) {
		t.Errorf("Animations = %v", r.Animations)
	}
	// The template's "(or wall-mount plane for wall props)" aside must not
	// make every floor prop a wall prop.
	if r.Origin != OriginBaseCenter {
		t.Errorf("Origin = %q, want %q", r.Origin, OriginBaseCenter)
	}
}

func TestParseRequestVariants(t *testing.T) {
	base := readFixture(t, "hero_template.md")
	prop := strings.Replace(base, "**Class:** hero", "**Class:** prop", 1)
	r, err := ParseRequest("x", prop)
	if err != nil {
		t.Fatal(err)
	}
	if r.TriangleBudget != 20000 {
		t.Errorf("prop class TriangleBudget = %d, want first number 20000", r.TriangleBudget)
	}

	hinge := strings.Replace(base, "- Origin: base centre on the floor plane (or wall-mount plane for wall props)", "- Origin: on the hinge axis of the lid", 1)
	if r, _ := ParseRequest("x", hinge); r.Origin != OriginHinge {
		t.Errorf("hinge Origin = %q", r.Origin)
	}
	source := strings.Replace(base, "- Origin: base centre on the floor plane (or wall-mount plane for wall props)", "- Origin: as the source (CC0 drop-in; the clamp mount stays where it was)", 1)
	if r, _ := ParseRequest("x", source); r.Origin != OriginSource {
		t.Errorf("source Origin = %q", r.Origin)
	}
	surface := strings.Replace(base, "- Origin: base centre on the floor plane (or wall-mount plane for wall props)", "- Origin: back face of this surface-mount box", 1)
	if r, _ := ParseRequest("x", surface); r.Origin != OriginMountBack {
		t.Errorf("surface-mount Origin = %q", r.Origin)
	}

	noBudget := strings.Replace(base, "- Triangles: <= 20,000 (prop) | <= 60000 (hero)\n", "", 1)
	noBudget = strings.Replace(noBudget, "at <= 2048 px; emissive at <= 512 px", "at full size", 1)
	r, err = ParseRequest("x", noBudget)
	if err != nil {
		t.Fatal(err)
	}
	if r.TriangleBudget != 60000 || r.TextureMaxPx != 2048 || len(r.Notes) != 1 {
		t.Errorf("defaults: tris %d tex %d notes %v", r.TriangleBudget, r.TextureMaxPx, r.Notes)
	}

	if _, err := ParseRequest("x", strings.Replace(base, "**Status:**", "Stat:", 1)); err == nil {
		t.Error("missing Status line should be an error")
	}
}

func TestExpandRange(t *testing.T) {
	cases := []struct {
		a, b string
		want []string
		ok   bool
	}{
		{"btn_0", "btn_3", []string{"btn_0", "btn_1", "btn_2", "btn_3"}, true},
		{"led_08", "led_10", []string{"led_08", "led_09", "led_10"}, true},
		{"a_1", "b_2", []string{"a_1", "b_2"}, false},
		{"x_5", "x_1", []string{"x_5", "x_1"}, false},
	}
	for _, c := range cases {
		got, ok := expandRange(c.a, c.b)
		if ok != c.ok || !reflect.DeepEqual(got, c.want) {
			t.Errorf("expandRange(%s, %s) = %v %v", c.a, c.b, got, ok)
		}
	}
}
