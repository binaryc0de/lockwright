// Command assetcheck validates Codex-built assets against their requests in
// assets/requests/ (docs/ASSET_PIPELINE.md sections 4, 5, 6 and 8).
//
//	go run ./tools/assetcheck [-root dir] [-json] [asset_id ...]
//
// With no ids it checks every request (files starting with "_" are skipped)
// plus repo-wide checks. Exit status: 0 ok, 1 any FAIL, 2 usage/setup error.
package main

import (
	"encoding/json"
	"errors"
	"flag"
	"fmt"
	"io"
	"os"
	"path/filepath"
)

func main() {
	os.Exit(run(os.Args[1:], os.Stdout, os.Stderr))
}

func run(args []string, stdout, stderr io.Writer) int {
	fset := flag.NewFlagSet("assetcheck", flag.ContinueOnError)
	fset.SetOutput(stderr)
	root := fset.String("root", "", "repository root (default: nearest ancestor of the working directory containing go.mod)")
	asJSON := fset.Bool("json", false, "print a machine-readable JSON report")
	fset.Usage = func() {
		fmt.Fprintln(stderr, "usage: assetcheck [-root dir] [-json] [asset_id ...]")
		fset.PrintDefaults()
	}
	// Allow flags after positional ids (go's flag package stops at the first).
	var ids []string
	for {
		if err := fset.Parse(args); err != nil {
			return 2
		}
		args = fset.Args()
		if len(args) == 0 {
			break
		}
		ids = append(ids, args[0])
		args = args[1:]
	}

	if *root == "" {
		r, err := findRoot()
		if err != nil {
			fmt.Fprintln(stderr, "assetcheck:", err)
			return 2
		}
		*root = r
	}
	abs, err := filepath.Abs(*root)
	if err != nil {
		fmt.Fprintln(stderr, "assetcheck:", err)
		return 2
	}
	rep, err := Run(abs, ids)
	if err != nil {
		fmt.Fprintln(stderr, "assetcheck:", err)
		return 2
	}

	if *asJSON {
		enc := json.NewEncoder(stdout)
		enc.SetIndent("", "  ")
		if err := enc.Encode(rep); err != nil {
			fmt.Fprintln(stderr, "assetcheck:", err)
			return 2
		}
	} else {
		printText(stdout, rep)
	}
	if !rep.OK {
		return 1
	}
	return 0
}

func printText(w io.Writer, rep *Report) {
	var pass, fail, warn int
	for _, a := range append(append([]*AssetResult{}, rep.Assets...), rep.Global...) {
		for _, m := range a.Warnings {
			fmt.Fprintf(w, "WARN %s: %s\n", a.AssetID, m)
		}
		for _, m := range a.Failures {
			fmt.Fprintf(w, "FAIL %s: %s\n", a.AssetID, m)
		}
		warn += len(a.Warnings)
		switch a.Status {
		case "pass":
			pass++
			fmt.Fprintf(w, "PASS %s (%d tris, %d parts)\n", a.AssetID, a.Triangles, a.Parts)
		case "fail":
			fail++
		case "printable":
			fmt.Fprintf(w, "SKIP %s (printable faces only: checked by tools/printables)\n", a.AssetID)
		}
	}
	fmt.Fprintf(w, "assetcheck: %d asset(s) checked, %d passed, %d failed, %d warning(s)\n", len(rep.Assets), pass, fail, warn)
}

// findRoot walks up from the working directory to the directory with go.mod.
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
			return "", errors.New("no go.mod found above the working directory; pass -root")
		}
		dir = parent
	}
}
