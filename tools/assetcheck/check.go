package main

import (
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"errors"
	"fmt"
	"io/fs"
	"math"
	"os"
	"path/filepath"
	"sort"
	"strings"

	"github.com/binaryc0de/escapebox/internal/gltf"
)

// Tolerances in metres (docs/ASSET_PIPELINE.md section 8).
const (
	tolPlane  = 0.001 // floor / mount plane
	tolCentre = 0.005 // horizontal centring
)

// AssetResult is the outcome for one asset id.
type AssetResult struct {
	AssetID   string   `json:"asset_id"`
	Status    string   `json:"result"` // pass | fail | not_built | printable
	Request   string   `json:"request_status,omitempty"`
	GLB       string   `json:"glb,omitempty"`
	Triangles int      `json:"triangles"`
	Parts     int      `json:"parts"`
	Failures  []string `json:"failures"`
	Warnings  []string `json:"warnings"`
}

func (a *AssetResult) fail(format string, args ...any) {
	a.Failures = append(a.Failures, fmt.Sprintf(format, args...))
}

func (a *AssetResult) warn(format string, args ...any) {
	a.Warnings = append(a.Warnings, fmt.Sprintf(format, args...))
}

// Report is the whole run.
type Report struct {
	Root   string         `json:"root"`
	OK     bool           `json:"ok"`
	Assets []*AssetResult `json:"assets"`
	// Global holds repo-wide findings, keyed by the asset id they concern.
	Global []*AssetResult `json:"global"`
}

// Run checks the given asset ids, or every request plus the global checks
// when ids is empty.
func Run(root string, ids []string) (*Report, error) {
	rep := &Report{Root: root, Assets: []*AssetResult{}, Global: []*AssetResult{}}
	reqDir := filepath.Join(root, "assets", "requests")
	all := len(ids) == 0
	if all {
		var err error
		ids, err = listRequestIDs(reqDir)
		if err != nil {
			return nil, err
		}
	}
	for _, id := range ids {
		rep.Assets = append(rep.Assets, checkAsset(root, id))
	}
	if all {
		rep.Global = globalChecks(root)
	}
	rep.OK = true
	for _, a := range append(append([]*AssetResult{}, rep.Assets...), rep.Global...) {
		if len(a.Failures) > 0 {
			rep.OK = false
		}
	}
	return rep, nil
}

func listRequestIDs(dir string) ([]string, error) {
	entries, err := os.ReadDir(dir)
	if err != nil {
		return nil, fmt.Errorf("reading %s: %w", dir, err)
	}
	var ids []string
	for _, e := range entries {
		n := e.Name()
		if e.IsDir() || !strings.HasSuffix(n, ".md") || strings.HasPrefix(n, "_") {
			continue
		}
		ids = append(ids, strings.TrimSuffix(n, ".md"))
	}
	sort.Strings(ids)
	return ids, nil
}

// findGLBs returns every candidate GLB path for id, core library first.
func findGLBs(root, id string) []string {
	var out []string
	core := filepath.Join(root, "game", "assets", "core", "props", id+".glb")
	if fileExists(core) {
		out = append(out, core)
	}
	rooms, _ := filepath.Glob(filepath.Join(root, "game", "rooms", "*", "assets"))
	sort.Strings(rooms)
	for _, dir := range rooms {
		_ = filepath.WalkDir(dir, func(p string, d fs.DirEntry, err error) error {
			if err == nil && !d.IsDir() && d.Name() == id+".glb" {
				out = append(out, p)
			}
			return nil
		})
	}
	return out
}

func fileExists(p string) bool {
	st, err := os.Stat(p)
	return err == nil && !st.IsDir()
}

func rel(root, p string) string {
	if r, err := filepath.Rel(root, p); err == nil {
		return filepath.ToSlash(r)
	}
	return p
}

func checkAsset(root, id string) *AssetResult {
	res := &AssetResult{AssetID: id, Failures: []string{}, Warnings: []string{}}
	defer func() {
		switch {
		case len(res.Failures) > 0:
			res.Status = "fail"
		case res.Status == "":
			res.Status = "pass"
		}
	}()

	reqPath := filepath.Join(root, "assets", "requests", id+".md")
	text, err := os.ReadFile(reqPath)
	if err != nil {
		res.fail("no request file %s", rel(root, reqPath))
		return res
	}
	req, err := ParseRequest(id, string(text))
	if err != nil {
		res.fail("cannot parse request: %v", err)
		return res
	}
	res.Request = req.Status
	res.Parts = len(req.Parts)
	if req.Title != "" && req.Title != id {
		res.warn("request heading %q does not match file name %s.md", req.Title, id)
	}
	for _, n := range req.Notes {
		res.warn("request: %s", n)
	}
	reviewed := req.Status == "in_review" || req.Status == "accepted"
	accepted := req.Status == "accepted"
	if req.Class == "printable" {
		// Printed or carved faces only: no GLB; their generator has its own
		// checks (tools/printables/verify.py).
		res.Status = "printable"
		return res
	}

	// 1. Locate the GLB.
	glbs := findGLBs(root, id)
	if len(glbs) == 0 {
		if reviewed {
			res.fail("GLB missing (request status %s); expected game/assets/core/props/%s.glb or game/rooms/*/assets/**/%s.glb", req.Status, id, id)
		} else {
			res.warn("not built yet (request status %s)", req.Status)
			res.Status = "not_built"
		}
		return res
	}
	if len(glbs) > 1 {
		var rs []string
		for _, g := range glbs {
			rs = append(rs, rel(root, g))
		}
		res.warn("multiple GLBs found (%s); checking %s", strings.Join(rs, ", "), rs[0])
	}
	glbPath := glbs[0]
	res.GLB = rel(root, glbPath)

	// 2. Parse and structurally validate.
	doc, err := gltf.ReadFile(glbPath)
	if err != nil {
		res.fail("%s does not load: %v", res.GLB, err)
		return res
	}

	// 3. Budgets.
	res.Triangles = doc.TotalTriangles()
	if res.Triangles > req.TriangleBudget {
		res.fail("%d triangles exceeds budget %d", res.Triangles, req.TriangleBudget)
	}
	for _, im := range doc.Images() {
		name := im.Name
		if name == "" {
			name = fmt.Sprintf("image #%d", im.Index)
		}
		if im.Width > req.TextureMaxPx || im.Height > req.TextureMaxPx {
			res.fail("texture %s is %dx%d px, budget %d px", name, im.Width, im.Height, req.TextureMaxPx)
		}
	}

	// 4. Named parts.
	nodeNames := map[string]bool{}
	for _, n := range doc.NodeNames() {
		nodeNames[n] = true
	}
	var missing []string
	for _, p := range req.Parts {
		if !nodeNames[p] {
			missing = append(missing, p)
		}
	}
	if len(missing) > 0 {
		res.fail("missing named parts (glTF node names): %s", strings.Join(missing, ", "))
	}

	// 5. Animations.
	anims := map[string]int{}
	for _, a := range doc.Animations() {
		anims[a.Name] = a.Channels
	}
	for _, want := range req.Animations {
		ch, ok := anims[want]
		switch {
		case !ok:
			res.fail("missing animation %q", want)
		case ch == 0:
			res.fail("animation %q has no channels", want)
		}
	}

	// 6. Origin.
	checkOrigin(res, doc, req.Origin)

	for _, w := range doc.Warnings {
		res.warn("glb: %s", w)
	}

	// 7. Meta.
	checkMeta(res, root, id, req)

	// 8. Previews.
	for _, view := range []string{"front", "iso", "detail"} {
		p := filepath.Join(root, "assets", "previews", fmt.Sprintf("%s_%s.png", id, view))
		if fileExists(p) {
			continue
		}
		if accepted {
			res.fail("preview %s missing", rel(root, p))
		} else {
			res.warn("preview %s missing", rel(root, p))
		}
	}
	return res
}

func fmtVec(v [3]float64) string {
	return fmt.Sprintf("(%.4f, %.4f, %.4f)", v[0], v[1], v[2])
}

func checkOrigin(res *AssetResult, doc *gltf.Document, kind string) {
	box, ok := doc.Bounds()
	if !ok {
		res.fail("no mesh geometry with POSITION bounds; cannot check origin")
		return
	}
	c := box.Center()
	where := fmt.Sprintf("bounds min %s max %s", fmtVec(box.Min), fmtVec(box.Max))
	switch kind {
	case OriginBaseCenter:
		if math.Abs(box.Min[1]) > tolPlane {
			res.fail("origin not on floor plane: bounds min y = %.4f m (want 0 +/- 1 mm); %s", box.Min[1], where)
		}
		if math.Abs(c[0]) > tolCentre || math.Abs(c[2]) > tolCentre {
			res.fail("origin not at base centre: bounds centre x = %.4f, z = %.4f m (want 0 +/- 5 mm); %s", c[0], c[2], where)
		}
	case OriginMountBack:
		if math.Abs(box.Max[2]) > tolPlane {
			res.fail("origin not on mount plane: bounds max z = %.4f m (want 0 +/- 1 mm, prop faces -Z); %s", box.Max[2], where)
		}
		if math.Abs(c[0]) > tolCentre {
			res.fail("origin not centred on mount plane: bounds centre x = %.4f m (want 0 +/- 5 mm); %s", c[0], where)
		}
		if math.Abs(c[1]) > tolCentre {
			res.warn("bounds centre y = %.4f m; a mount-plane-centre origin would put it near 0", c[1])
		}
	case OriginHinge:
		res.warn("hinge origin not checked automatically; verify in-engine (%s)", where)
	case OriginSource:
		res.warn("source origin kept for a drop-in replacement; verify in-engine (%s)", where)
	}
}

// metaFile is the subset of assets/meta/<id>.json that assetcheck reads.
type metaFile struct {
	AssetID      string            `json:"asset_id"`
	Triangles    *int              `json:"triangles"`
	Parts        []json.RawMessage `json:"parts"`
	ScriptSHA256 string            `json:"script_sha256"`
}

func metaPartNames(raw []json.RawMessage) ([]string, error) {
	var out []string
	for _, r := range raw {
		var s string
		if err := json.Unmarshal(r, &s); err == nil {
			out = append(out, s)
			continue
		}
		var o struct {
			Name string `json:"name"`
		}
		if err := json.Unmarshal(r, &o); err != nil || o.Name == "" {
			return nil, fmt.Errorf("parts entry %s is neither a string nor an object with \"name\"", string(r))
		}
		out = append(out, o.Name)
	}
	return out, nil
}

func checkMeta(res *AssetResult, root, id string, req *Request) {
	metaPath := filepath.Join(root, "assets", "meta", id+".json")
	data, err := os.ReadFile(metaPath)
	if err != nil {
		res.fail("meta %s missing", rel(root, metaPath))
		return
	}
	var m metaFile
	if err := json.Unmarshal(data, &m); err != nil {
		res.fail("meta %s does not parse: %v", rel(root, metaPath), err)
		return
	}
	if m.AssetID != id {
		res.fail("meta asset_id %q does not match %q", m.AssetID, id)
	}

	scriptPath := filepath.Join(root, "tools", "blender", "props", id+".py")
	script, err := os.ReadFile(scriptPath)
	switch {
	case errors.Is(err, fs.ErrNotExist):
		res.fail("build script %s missing", rel(root, scriptPath))
	case err != nil:
		res.fail("reading build script: %v", err)
	default:
		sum := sha256.Sum256(script)
		want := hex.EncodeToString(sum[:])
		got := strings.ToLower(strings.TrimPrefix(strings.TrimSpace(m.ScriptSHA256), "sha256:"))
		if got == "" {
			res.fail("meta script_sha256 missing")
		} else if got != want {
			res.fail("meta is stale: script_sha256 %s != sha256(%s) %s; rebuild", shortHash(got), rel(root, scriptPath), shortHash(want))
		}
	}

	if m.Triangles == nil {
		res.warn("meta has no triangles field")
	} else if *m.Triangles != res.Triangles {
		res.warn("meta triangles %d != GLB triangles %d", *m.Triangles, res.Triangles)
	}

	names, err := metaPartNames(m.Parts)
	if err != nil {
		res.fail("meta parts: %v", err)
		return
	}
	have := map[string]bool{}
	for _, n := range names {
		have[n] = true
	}
	var missing []string
	for _, p := range req.Parts {
		if !have[p] {
			missing = append(missing, p)
		}
	}
	if len(missing) > 0 {
		res.fail("meta parts missing: %s", strings.Join(missing, ", "))
	}
}

func shortHash(h string) string {
	if len(h) > 12 {
		return h[:12]
	}
	return h
}

// globalChecks: every build script has a request. (An accepted request
// without a GLB is reported by the per-asset check, which runs for every
// request in all-assets mode.)
func globalChecks(root string) []*AssetResult {
	out := []*AssetResult{}
	scripts, _ := filepath.Glob(filepath.Join(root, "tools", "blender", "props", "*.py"))
	sort.Strings(scripts)
	for _, s := range scripts {
		base := filepath.Base(s)
		if strings.HasPrefix(base, "_") {
			continue // __init__.py and private helpers
		}
		id := strings.TrimSuffix(base, ".py")
		req := filepath.Join(root, "assets", "requests", id+".md")
		if !fileExists(req) {
			out = append(out, &AssetResult{
				AssetID:  id,
				Status:   "fail",
				Failures: []string{fmt.Sprintf("build script %s has no request %s", rel(root, s), rel(root, req))},
				Warnings: []string{},
			})
		}
	}
	return out
}
