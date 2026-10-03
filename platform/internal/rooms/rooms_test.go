package rooms

import (
	"os"
	"path/filepath"
	"strings"
	"testing"
)

func TestLoadsTheRealNightShift(t *testing.T) {
	c, err := Load(filepath.Join("..", "..", "..", "game", "rooms"))
	if err != nil {
		t.Fatal(err)
	}
	r, ok := c.Room("night_shift")
	if !ok || r.Title == "" || r.Mode.DurationMinutes != 60 {
		t.Fatalf("night_shift: %+v %v", r, ok)
	}
	ch, ok := r.Challenge("intranet")
	if !ok || ch.Build != "ctf/intranet" || ch.Flag.Type != "per_instance" || ch.Flag.InjectEnv != "FLAG" ||
		len(ch.Ports) != 1 || ch.Ports[0].Container != 8080 || ch.Healthcheck.Path != "/healthz" {
		t.Fatalf("intranet challenge %+v", ch)
	}
	if _, err := os.Stat(filepath.Join(r.Dir, ch.Build, "Dockerfile")); err != nil {
		t.Fatal(err)
	}
}

func TestRejectsMismatchedID(t *testing.T) {
	dir := t.TempDir()
	os.MkdirAll(filepath.Join(dir, "a"), 0o755)
	os.WriteFile(filepath.Join(dir, "a", "room.json"), []byte(`{"id":"b"}`), 0o644)
	if _, err := Load(dir); err == nil {
		t.Fatal("mismatched id accepted")
	}
}

func TestSummaryComesFromTheIntroBriefing(t *testing.T) {
	c, err := Load("../../../game/rooms")
	if err != nil {
		t.Fatal(err)
	}
	r, _ := c.Room("night_shift")
	if !strings.HasPrefix(r.Summary, "23:10, Kestrel Logistics regional office.") || strings.Contains(r.Summary, "**") || len(r.Summary) > 330 {
		t.Fatalf("summary %q", r.Summary)
	}
}

func TestDraftRoomsAreHiddenUnlessAsked(t *testing.T) {
	dir := t.TempDir()
	for id, body := range map[string]string{
		"ready": `{"id":"ready","title":"Ready","version":"1.0.0"}`,
		"wip":   `{"id":"wip","title":"WIP","version":"0.1.0","draft":true}`,
	} {
		os.MkdirAll(filepath.Join(dir, id), 0o755)
		os.WriteFile(filepath.Join(dir, id, "room.json"), []byte(body), 0o644)
	}
	c, err := Load(dir)
	if err != nil {
		t.Fatal(err)
	}
	if _, ok := c.Room("wip"); ok || len(c.All()) != 1 || strings.Join(c.Hidden(), ",") != "wip" {
		t.Fatalf("public catalog: %+v hidden %v", c.All(), c.Hidden())
	}
	c, err = LoadWithDrafts(dir)
	if err != nil {
		t.Fatal(err)
	}
	if r, ok := c.Room("wip"); !ok || !r.Draft || len(c.All()) != 2 || len(c.Hidden()) != 0 {
		t.Fatalf("development catalog: %+v hidden %v", c.All(), c.Hidden())
	}
}
