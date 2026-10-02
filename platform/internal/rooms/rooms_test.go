package rooms

import (
	"os"
	"path/filepath"
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
