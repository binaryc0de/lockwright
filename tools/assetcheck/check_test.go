package main

import (
	"bytes"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"os"
	"path/filepath"
	"strings"
	"testing"

	"github.com/binaryc0de/escapebox/internal/gltf/gltftest"
)

// fixture describes one asset in a temporary repo tree. Zero value fields
// mean "build it correctly"; tests break one thing at a time.
type fixture struct {
	id      string
	request string // request markdown

	noGLB      bool
	glbInRoom  bool // put the GLB under game/rooms/test_room/assets/props/
	corruptGLB bool
	dropPart   string
	dropAnim   string
	emptyAnim  string
	offset     [3]float64
	texPx      int // 0 = no texture

	metaPartsAsObjects bool
	metaDropPart       string
	metaTriangles      int // 0 = correct count
	noMeta             bool
	staleHash          bool
	noPreviews         bool
}

func writeFile(t *testing.T, path string, data []byte) {
	t.Helper()
	if err := os.MkdirAll(filepath.Dir(path), 0o755); err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(path, data, 0o644); err != nil {
		t.Fatal(err)
	}
}

// buildRepo writes the fixture into a fresh temp root and returns it.
func buildRepo(t *testing.T, fs ...fixture) string {
	t.Helper()
	root := t.TempDir()
	for _, f := range fs {
		buildAsset(t, root, f)
	}
	return root
}

func buildAsset(t *testing.T, root string, f fixture) {
	t.Helper()
	writeFile(t, filepath.Join(root, "assets", "requests", f.id+".md"), []byte(f.request))
	req, err := ParseRequest(f.id, f.request)
	if err != nil {
		t.Fatal(err)
	}

	// Geometry that satisfies the request's origin rule.
	var b gltftest.Builder
	lo, hi := [3]float32{-0.2, 0, -0.2}, [3]float32{0.2, 0.8, 0.2} // floor prop
	if req.Origin == OriginMountBack {
		lo, hi = [3]float32{-0.0375, -0.0575, -0.022}, [3]float32{0.0375, 0.0575, 0}
	}
	box := b.BoxMesh("box", lo, hi)
	var parts []string
	nodes := map[string]int{}
	for _, p := range req.Parts {
		if p == f.dropPart {
			continue
		}
		parts = append(parts, p)
		n := b.Node(p, box)
		b.Nodes[n]["translation"] = f.offset[:]
		nodes[p] = n
	}
	for _, a := range req.Animations {
		if a != f.dropAnim {
			b.Animation(a, nodes[req.Parts[0]], a != f.emptyAnim)
		}
	}
	if f.texPx > 0 {
		b.PNGImage("T_"+f.id+"_base", f.texPx, f.texPx)
	}
	b.Material("M_" + f.id + "_body")
	glb := b.GLB()
	tris := 12 * len(parts)
	if f.corruptGLB {
		glb = glb[:len(glb)-8]
	}
	if !f.noGLB {
		dir := filepath.Join(root, "game", "assets", "core", "props")
		if f.glbInRoom {
			dir = filepath.Join(root, "game", "rooms", "test_room", "assets", "props")
		}
		writeFile(t, filepath.Join(dir, f.id+".glb"), glb)
	}

	script := []byte("# build script for " + f.id + "\ndef build(out_dir):\n    pass\n")
	scriptPath := filepath.Join(root, "tools", "blender", "props", f.id+".py")
	writeFile(t, scriptPath, script)
	sum := sha256.Sum256(script)

	if !f.noMeta {
		var metaParts []any
		for _, p := range req.Parts {
			if p == f.metaDropPart {
				continue
			}
			if f.metaPartsAsObjects {
				metaParts = append(metaParts, map[string]any{"name": p, "separate_transform": true})
			} else {
				metaParts = append(metaParts, p)
			}
		}
		metaTris := tris
		if f.metaTriangles != 0 {
			metaTris = f.metaTriangles
		}
		meta, _ := json.MarshalIndent(map[string]any{
			"asset_id":        f.id,
			"triangles":       metaTris,
			"parts":           metaParts,
			"animations":      req.Animations,
			"origin":          req.Origin,
			"script_sha256":   hex.EncodeToString(sum[:]),
			"blender_version": "5.2.2",
		}, "", "  ")
		writeFile(t, filepath.Join(root, "assets", "meta", f.id+".json"), meta)
	}
	if f.staleHash {
		writeFile(t, scriptPath, append(script, []byte("# edited after build\n")...))
	}
	if !f.noPreviews {
		for _, v := range []string{"front", "iso", "detail"} {
			writeFile(t, filepath.Join(root, "assets", "previews", f.id+"_"+v+".png"), gltftest.PNG(4, 4))
		}
	}
}

func keypadRequest(t *testing.T, status string) string {
	return strings.Replace(readFixture(t, "keypad_4.md"), "**Status:** open", "**Status:** "+status, 1)
}

func heroRequest(t *testing.T, status string) string {
	return strings.Replace(readFixture(t, "hero_template.md"), "**Status:** in_review | accepted | rejected", "**Status:** "+status, 1)
}

func keypad(t *testing.T) fixture {
	return fixture{id: "keypad_4", request: keypadRequest(t, "in_review"), texPx: 1024}
}

func hero(t *testing.T) fixture {
	return fixture{id: "drawer_cabinet", request: heroRequest(t, "in_review"), texPx: 2048, metaPartsAsObjects: true}
}

func runIDs(t *testing.T, root string, ids ...string) *Report {
	t.Helper()
	rep, err := Run(root, ids)
	if err != nil {
		t.Fatal(err)
	}
	return rep
}

func assetResult(t *testing.T, rep *Report, id string) *AssetResult {
	t.Helper()
	for _, a := range rep.Assets {
		if a.AssetID == id {
			return a
		}
	}
	t.Fatalf("no result for %s", id)
	return nil
}

func contains(list []string, sub string) bool {
	for _, s := range list {
		if strings.Contains(s, sub) {
			return true
		}
	}
	return false
}

// hasLine reports whether some output line starts with prefix and contains sub.
func hasLine(out, prefix, sub string) bool {
	for _, ln := range strings.Split(out, "\n") {
		if strings.HasPrefix(ln, prefix) && strings.Contains(ln, sub) {
			return true
		}
	}
	return false
}

func TestEndToEndPass(t *testing.T) {
	root := buildRepo(t, keypad(t), hero(t))
	rep := runIDs(t, root)
	if !rep.OK {
		t.Fatalf("report not OK: %+v %+v", rep.Assets[0], rep.Assets[1])
	}
	k := assetResult(t, rep, "keypad_4")
	if k.Status != "pass" || k.Triangles != 16*12 || k.Parts != 16 || len(k.Warnings) != 0 {
		t.Errorf("keypad_4 = %+v", k)
	}
	h := assetResult(t, rep, "drawer_cabinet")
	if h.Status != "pass" || h.Triangles != 17*12 || len(h.Warnings) != 0 {
		t.Errorf("drawer_cabinet = %+v", h)
	}

	// CLI text output and exit code.
	var out, errOut bytes.Buffer
	code := run([]string{"-root", root, "keypad_4"}, &out, &errOut)
	if code != 0 || !strings.Contains(out.String(), "PASS keypad_4 (192 tris, 16 parts)\n") {
		t.Errorf("exit %d, stdout:\n%s\nstderr:\n%s", code, out.String(), errOut.String())
	}
	// Flags after ids, JSON output.
	out.Reset()
	code = run([]string{"keypad_4", "-root", root, "-json"}, &out, &errOut)
	var decoded Report
	if code != 0 || json.Unmarshal(out.Bytes(), &decoded) != nil || !decoded.OK || len(decoded.Assets) != 1 {
		t.Errorf("json run: exit %d, out %s", code, out.String())
	}
}

func TestEndToEndRoomAssetLocation(t *testing.T) {
	f := keypad(t)
	f.glbInRoom = true
	rep := runIDs(t, buildRepo(t, f), "keypad_4")
	if a := rep.Assets[0]; a.Status != "pass" || a.GLB != "game/rooms/test_room/assets/props/keypad_4.glb" {
		t.Errorf("room asset = %+v", a)
	}
}

func TestEndToEndFailures(t *testing.T) {
	cases := []struct {
		name   string
		mutate func(f *fixture)
		hero   bool
		want   string
	}{
		{"missing part", func(f *fixture) { f.dropPart = "btn_7" }, false, "missing named parts (glTF node names): btn_7"},
		{"missing collision helper", func(f *fixture) { f.dropPart = "body-col" }, false, "missing named parts (glTF node names): body-col"},
		{"stale hash", func(f *fixture) { f.staleHash = true }, false, "meta is stale"},
		{"over triangle budget", func(f *fixture) {
			f.request = strings.Replace(f.request, "Triangles: <= 20000", "Triangles: <= 100", 1)
		}, false, "192 triangles exceeds budget 100"},
		{"texture over budget", func(f *fixture) { f.texPx = 2048 }, false, "is 2048x2048 px, budget 1024 px"},
		{"bad mount origin", func(f *fixture) { f.offset = [3]float64{0, 0, 0.011} }, false, "origin not on mount plane"},
		{"mount off centre", func(f *fixture) { f.offset = [3]float64{0.01, 0, 0} }, false, "origin not centred on mount plane"},
		{"bad floor origin", func(f *fixture) { f.offset = [3]float64{0, 0.05, 0} }, true, "origin not on floor plane"},
		{"floor off centre", func(f *fixture) { f.offset = [3]float64{0, 0, 0.02} }, true, "origin not at base centre"},
		{"missing animation", func(f *fixture) { f.dropAnim = "close" }, true, `missing animation "close"`},
		{"empty animation", func(f *fixture) { f.emptyAnim = "open" }, true, `animation "open" has no channels`},
		{"meta missing", func(f *fixture) { f.noMeta = true }, false, "meta assets/meta/keypad_4.json missing"},
		{"meta part missing", func(f *fixture) { f.metaDropPart = "led_status" }, false, "meta parts missing: led_status"},
		{"glb missing in review", func(f *fixture) { f.noGLB = true }, false, "GLB missing (request status in_review)"},
		{"glb missing accepted", func(f *fixture) {
			f.noGLB = true
			f.request = keypadRequest(t, "accepted")
		}, false, "GLB missing (request status accepted)"},
		{"glb corrupt", func(f *fixture) { f.corruptGLB = true }, false, "does not load"},
		{"previews missing accepted", func(f *fixture) {
			f.noPreviews = true
			f.request = keypadRequest(t, "accepted")
		}, false, "preview assets/previews/keypad_4_front.png missing"},
	}
	for _, c := range cases {
		t.Run(c.name, func(t *testing.T) {
			f := keypad(t)
			if c.hero {
				f = hero(t)
			}
			c.mutate(&f)
			rep := runIDs(t, buildRepo(t, f), f.id)
			a := rep.Assets[0]
			if rep.OK || a.Status != "fail" || !contains(a.Failures, c.want) {
				t.Fatalf("want FAIL containing %q, got %s failures=%q warnings=%q", c.want, a.Status, a.Failures, a.Warnings)
			}
			if len(a.Failures) != 1 && !strings.HasPrefix(c.want, "preview") {
				t.Errorf("expected exactly one failure, got %q", a.Failures)
			}
			var out bytes.Buffer
			if code := run([]string{"-root", rep.Root, f.id}, &out, &out); code != 1 || !hasLine(out.String(), "FAIL "+f.id+": ", c.want) {
				t.Errorf("CLI exit %d output:\n%s", code, out.String())
			}
		})
	}
}

func TestEndToEndWarnings(t *testing.T) {
	cases := []struct {
		name   string
		mutate func(f *fixture)
		want   string
	}{
		{"not built yet", func(f *fixture) { f.noGLB = true; f.request = keypadRequest(t, "open") }, "not built yet (request status open)"},
		{"meta triangle mismatch", func(f *fixture) { f.metaTriangles = 999 }, "meta triangles 999 != GLB triangles 192"},
		{"previews missing in review", func(f *fixture) { f.noPreviews = true }, "preview assets/previews/keypad_4_iso.png missing"},
	}
	for _, c := range cases {
		t.Run(c.name, func(t *testing.T) {
			f := keypad(t)
			c.mutate(&f)
			rep := runIDs(t, buildRepo(t, f), f.id)
			a := rep.Assets[0]
			if !rep.OK || len(a.Failures) != 0 || !contains(a.Warnings, c.want) {
				t.Fatalf("want only WARN containing %q, got failures=%q warnings=%q", c.want, a.Failures, a.Warnings)
			}
		})
	}
}

func TestGlobalChecks(t *testing.T) {
	root := buildRepo(t, keypad(t))
	writeFile(t, filepath.Join(root, "tools", "blender", "props", "orphan_prop.py"), []byte("def build(out_dir): pass\n"))
	writeFile(t, filepath.Join(root, "tools", "blender", "props", "__init__.py"), nil)
	writeFile(t, filepath.Join(root, "assets", "requests", "_template.md"), []byte("not a request"))

	rep := runIDs(t, root)
	if rep.OK || len(rep.Assets) != 1 || len(rep.Global) != 1 {
		t.Fatalf("report = assets %d global %d ok %v", len(rep.Assets), len(rep.Global), rep.OK)
	}
	g := rep.Global[0]
	if g.AssetID != "orphan_prop" || !contains(g.Failures, "has no request assets/requests/orphan_prop.md") {
		t.Errorf("global = %+v", g)
	}
	// Named ids skip the global checks.
	if rep := runIDs(t, root, "keypad_4"); !rep.OK {
		t.Errorf("named run should ignore global checks: %+v", rep.Global)
	}
	// Unknown id fails.
	if rep := runIDs(t, root, "nope"); rep.OK || !contains(rep.Assets[0].Failures, "no request file") {
		t.Errorf("unknown id = %+v", rep.Assets[0])
	}
}
