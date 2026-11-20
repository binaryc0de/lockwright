// Command roomcheck validates room packs in source form (PLAN.md Section 8.4).
//
//	go run ./tools/roomcheck                       # every game/rooms/*/ with a room.yaml
//	go run ./tools/roomcheck game/rooms/night_shift
//	go run ./tools/roomcheck -write-json game/rooms/night_shift
//
// Exit status 1 if any room has an error.
package main

import (
	"encoding/json"
	"errors"
	"flag"
	"fmt"
	"os"
	"path/filepath"

	"github.com/binaryc0de/lockwright/internal/room"
)

func main() {
	os.Exit(run(os.Args[1:]))
}

func run(args []string) int {
	fs := flag.NewFlagSet("roomcheck", flag.ContinueOnError)
	root := fs.String("root", "", "repository root (default: nearest parent with go.mod)")
	asJSON := fs.Bool("json", false, "print reports as JSON")
	writeJSON := fs.Bool("write-json", false, "regenerate room.json from room.yaml before checking")
	if err := fs.Parse(args); err != nil {
		return 2
	}
	if *root == "" {
		r, err := findRoot()
		if err != nil {
			fmt.Fprintln(os.Stderr, "roomcheck:", err)
			return 2
		}
		*root = r
	}
	schema, err := room.CompileSchema(filepath.Join(*root, "docs", "schema", "room.schema.json"))
	if err != nil {
		fmt.Fprintln(os.Stderr, "roomcheck: schema:", err)
		return 2
	}
	resRoot := filepath.Join(*root, "game")

	dirs := fs.Args()
	if len(dirs) == 0 {
		matches, _ := filepath.Glob(filepath.Join(resRoot, "rooms", "*", "room.yaml"))
		for _, m := range matches {
			dirs = append(dirs, filepath.Dir(m))
		}
		if len(dirs) == 0 {
			fmt.Println("roomcheck: no rooms found under game/rooms/")
			return 0
		}
	}

	var reports []*room.Report
	failed := false
	for _, d := range dirs {
		if *writeJSON {
			if err := room.WriteJSON(d); err != nil {
				fmt.Fprintf(os.Stderr, "roomcheck: %s: %v\n", d, err)
				return 2
			}
		}
		rep := room.Validate(d, resRoot, schema)
		reports = append(reports, rep)
		failed = failed || rep.Failed()
	}

	if *asJSON {
		enc := json.NewEncoder(os.Stdout)
		enc.SetIndent("", "  ")
		_ = enc.Encode(reports)
	} else {
		for _, rep := range reports {
			status := "PASS"
			if rep.Failed() {
				status = "FAIL"
			}
			fmt.Printf("%s %s\n", status, rep.Room)
			for _, i := range rep.Issues {
				fmt.Printf("  %s\n", i)
			}
		}
	}
	if failed {
		return 1
	}
	return 0
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
