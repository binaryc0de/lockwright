// Command packroom exports a room pack (PLAN.md 8.4):
//
//	go run ./tools/packroom [-verify] <room_id>
//
// It runs roomcheck, exports game/rooms/<room_id> with the room-pack-<room_id>
// preset into build/packs/<room_id>-<version>.pck, and writes the sha256 and
// a catalog entry next to it. With -verify it then proves the pack is
// self-contained: it copies the game project without rooms/, mounts the pack
// there, and runs the room's gdUnit4 tests (tests/rooms/test_<room_id>.gd)
// with EB_TEST_PACK pointing at the pack.
package main

import (
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"errors"
	"flag"
	"fmt"
	"io"
	"io/fs"
	"os"
	"os/exec"
	"path/filepath"
	"strings"

	"github.com/binaryc0de/escapebox/internal/room"
)

// CatalogEntry is what the platform catalog lists for a pack (docs/API.md).
type CatalogEntry struct {
	RoomID          string `json:"room_id"`
	Title           string `json:"title"`
	Version         string `json:"version"`
	DurationMinutes int    `json:"duration_minutes"`
	PlayersMin      int    `json:"players_min"`
	PlayersMax      int    `json:"players_max"`
	PackFile        string `json:"pack_file"`
	SHA256          string `json:"sha256"`
	Size            int64  `json:"size"`
}

func main() {
	if err := run(os.Args[1:]); err != nil {
		fmt.Fprintln(os.Stderr, "packroom:", err)
		os.Exit(1)
	}
}

func run(args []string) error {
	fset := flag.NewFlagSet("packroom", flag.ContinueOnError)
	root := fset.String("root", "", "repository root (default: nearest parent with go.mod)")
	godot := fset.String("godot", envOr("GODOT", "godot"), "Godot 4.7 binary")
	out := fset.String("out", "", "output directory (default <root>/build/packs)")
	verify := fset.Bool("verify", false, "after export, run the room's tests against the pack in a copy of the project without rooms/")
	if err := fset.Parse(args); err != nil {
		return err
	}
	if fset.NArg() != 1 {
		return errors.New("usage: packroom [-verify] <room_id>")
	}
	id := fset.Arg(0)
	if *root == "" {
		r, err := findRoot()
		if err != nil {
			return err
		}
		*root = r
	}
	if *out == "" {
		*out = filepath.Join(*root, "build", "packs")
	}
	gameDir := filepath.Join(*root, "game")
	roomDir := filepath.Join(gameDir, "rooms", id)

	schema, err := room.CompileSchema(filepath.Join(*root, "docs", "schema", "room.schema.json"))
	if err != nil {
		return err
	}
	rep := room.Validate(roomDir, gameDir, schema)
	for _, i := range rep.Issues {
		fmt.Println("  " + i.String())
	}
	if rep.Failed() {
		return fmt.Errorf("roomcheck failed for %s", id)
	}
	l, err := room.Load(roomDir)
	if err != nil {
		return err
	}
	m := l.Manifest

	preset := "room-pack-" + id
	presets, err := os.ReadFile(filepath.Join(gameDir, "export_presets.cfg"))
	if err != nil {
		return err
	}
	if !strings.Contains(string(presets), fmt.Sprintf("name=%q", preset)) {
		return fmt.Errorf("export preset %q missing from game/export_presets.cfg; copy room-pack-night_shift and change the room path", preset)
	}
	if err := os.MkdirAll(*out, 0o755); err != nil {
		return err
	}
	packName := fmt.Sprintf("%s-%s.pck", id, m.Version)
	packPath, err := filepath.Abs(filepath.Join(*out, packName))
	if err != nil {
		return err
	}
	_ = os.Remove(packPath)
	cmd := exec.Command(*godot, "--headless", "--path", gameDir, "--export-pack", preset, packPath)
	cmd.Stdout, cmd.Stderr = os.Stdout, os.Stderr
	if err := cmd.Run(); err != nil {
		return fmt.Errorf("godot export: %w", err)
	}
	if _, err := os.Stat(packPath); err != nil {
		return fmt.Errorf("godot reported success but %s is missing", packPath)
	}

	sum, size, err := hashFile(packPath)
	if err != nil {
		return err
	}
	entry := CatalogEntry{
		RoomID: id, Title: m.Title, Version: m.Version,
		DurationMinutes: m.Mode.DurationMinutes, PlayersMin: m.Mode.Players.Min, PlayersMax: m.Mode.Players.Max,
		PackFile: packName, SHA256: sum, Size: size,
	}
	js, _ := json.MarshalIndent(entry, "", "  ")
	if err := os.WriteFile(strings.TrimSuffix(packPath, ".pck")+".json", append(js, '\n'), 0o644); err != nil {
		return err
	}
	if err := os.WriteFile(packPath+".sha256", []byte(sum+"  "+packName+"\n"), 0o644); err != nil {
		return err
	}
	fmt.Printf("packed %s (%d bytes, sha256 %s)\n", packPath, size, sum)

	if *verify {
		return verifyPack(*godot, gameDir, id, packPath)
	}
	return nil
}

// verifyPack runs tests/rooms/test_<id>.gd in a copy of the game project that
// has no rooms/ directory, so the room can only come from the pack.
func verifyPack(godot, gameDir, id, packPath string) error {
	test := filepath.Join(gameDir, "tests", "rooms", "test_"+id+".gd")
	if _, err := os.Stat(test); err != nil {
		return fmt.Errorf("-verify needs %s", test)
	}
	tmp, err := os.MkdirTemp("", "packroom-verify-")
	if err != nil {
		return err
	}
	defer os.RemoveAll(tmp)
	if err := copyTree(gameDir, tmp, func(rel string) bool {
		top := strings.Split(filepath.ToSlash(rel), "/")[0]
		return top == "rooms" || top == ".godot" || top == "reports"
	}); err != nil {
		return err
	}
	if err := os.MkdirAll(filepath.Join(tmp, "rooms"), 0o755); err != nil {
		return err
	}
	fmt.Println("verify: importing a copy of the project without rooms/ ...")
	// Godot's headless importer occasionally dies part-way through a fresh
	// full import (no crash message; seen once in tools/test.sh after VRAM
	// compression came in). Importing is idempotent, so retry once.
	var outb []byte
	for attempt := 1; attempt <= 2; attempt++ {
		imp := exec.Command(godot, "--headless", "--path", tmp, "--import")
		var err error
		if outb, err = imp.CombinedOutput(); err == nil {
			break
		} else if attempt == 2 {
			return fmt.Errorf("import copy (twice): %w\n%s", err, outb)
		}
		fmt.Println("verify: import of the copy failed; retrying once")
	}
	bin, err := exec.LookPath(godot)
	if err != nil {
		return err
	}
	if resolved, err := filepath.EvalSymlinks(bin); err == nil {
		bin = resolved
	}
	runner := exec.Command("bash", filepath.Join(tmp, "addons", "gdUnit4", "runtest.sh"),
		"--path", tmp, "--headless", "--ignoreHeadlessMode", "-a", "res://tests/rooms/test_"+id+".gd")
	runner.Env = append(os.Environ(), "GODOT_BIN="+bin, "EB_TEST_PACK="+packPath)
	runner.Stdout, runner.Stderr = os.Stdout, os.Stderr
	if err := runner.Run(); err != nil {
		return fmt.Errorf("pack verification tests failed: %w", err)
	}
	fmt.Println("verify: room tests pass when loaded from the pack only")
	return nil
}

func copyTree(src, dst string, skip func(rel string) bool) error {
	return filepath.WalkDir(src, func(path string, d fs.DirEntry, err error) error {
		if err != nil {
			return err
		}
		rel, _ := filepath.Rel(src, path)
		if rel == "." {
			return nil
		}
		if skip(rel) {
			if d.IsDir() {
				return filepath.SkipDir
			}
			return nil
		}
		target := filepath.Join(dst, rel)
		if d.IsDir() {
			return os.MkdirAll(target, 0o755)
		}
		in, err := os.Open(path)
		if err != nil {
			return err
		}
		defer in.Close()
		outf, err := os.Create(target)
		if err != nil {
			return err
		}
		if _, err := io.Copy(outf, in); err != nil {
			outf.Close()
			return err
		}
		return outf.Close()
	})
}

func hashFile(path string) (string, int64, error) {
	f, err := os.Open(path)
	if err != nil {
		return "", 0, err
	}
	defer f.Close()
	h := sha256.New()
	n, err := io.Copy(h, f)
	if err != nil {
		return "", 0, err
	}
	return hex.EncodeToString(h.Sum(nil)), n, nil
}

func envOr(k, def string) string {
	if v := os.Getenv(k); v != "" {
		return v
	}
	return def
}

func findRoot() (string, error) {
	dir, err := os.Getwd()
	if err != nil {
		return "", err
	}
	for {
		if _, err := os.Stat(filepath.Join(dir, "go.mod")); err == nil {
			return dir, nil
		}
		parent := filepath.Dir(dir)
		if parent == dir {
			return "", errors.New("no go.mod found above the current directory; pass -root")
		}
		dir = parent
	}
}
