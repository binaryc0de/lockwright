package gltf_test

import (
	"encoding/base64"
	"encoding/binary"
	"encoding/json"
	"math"
	"strings"
	"testing"

	"github.com/binaryc0de/lockwright/internal/gltf"
	"github.com/binaryc0de/lockwright/internal/gltf/gltftest"
)

func mustParse(t *testing.T, data []byte) *gltf.Document {
	t.Helper()
	doc, err := gltf.Parse(data, "")
	if err != nil {
		t.Fatalf("Parse: %v", err)
	}
	return doc
}

func near(a, b float64) bool { return math.Abs(a-b) < 1e-6 }

func TestEncodeParseRoundTrip(t *testing.T) {
	data := gltf.EncodeGLB([]byte(`{"asset":{"version":"2.0"},"nodes":[{"name":"a"}]}`), nil)
	if len(data)%4 != 0 {
		t.Fatalf("GLB length %d not 4-aligned", len(data))
	}
	doc := mustParse(t, data)
	if got := doc.NodeNames(); len(got) != 1 || got[0] != "a" {
		t.Fatalf("NodeNames = %v", got)
	}
}

func TestTriangleCounts(t *testing.T) {
	var b gltftest.Builder
	box := b.BoxMesh("box", [3]float32{0, 0, 0}, [3]float32{1, 1, 1}) // 12 tris, indexed
	// Non-indexed primitives sharing one 6-vertex POSITION accessor.
	pos := b.Positions([][3]float32{{0, 0, 0}, {1, 0, 0}, {0, 1, 0}, {1, 1, 0}, {0, 2, 0}, {1, 2, 0}})
	tri := b.Mesh("tri", gltftest.M{"attributes": gltftest.M{"POSITION": pos}})                // 6/3 = 2
	strip := b.Mesh("strip", gltftest.M{"attributes": gltftest.M{"POSITION": pos}, "mode": 5}) // 6-2 = 4
	fan := b.Mesh("fan", gltftest.M{"attributes": gltftest.M{"POSITION": pos}, "mode": 6})     // 4
	lines := b.Mesh("lines", gltftest.M{"attributes": gltftest.M{"POSITION": pos}, "mode": 1}) // 0
	b.Node("box_a", box)
	b.Node("box_b", box) // second instance of the same mesh
	b.Node("tri", tri)
	b.Node("strip", strip)
	b.Node("fan", fan)
	b.Node("lines", lines)
	orphan := b.Node("not_in_scene", box)
	b.Roots = []int{0, 1, 2, 3, 4, 5}
	_ = orphan

	doc := mustParse(t, b.GLB())
	cases := map[int]int{box: 12, tri: 2, strip: 4, fan: 4, lines: 0}
	for mesh, want := range cases {
		if got := doc.MeshTriangles(mesh); got != want {
			t.Errorf("MeshTriangles(%d) = %d, want %d", mesh, got, want)
		}
	}
	// 12 + 12 + 2 + 4 + 4 + 0; the orphan node is outside the scene.
	if got := doc.TotalTriangles(); got != 34 {
		t.Errorf("TotalTriangles = %d, want 34", got)
	}
	for _, n := range doc.NodeNames() {
		if n == "not_in_scene" {
			t.Errorf("NodeNames includes a node outside the scene")
		}
	}
}

func TestHierarchyTransformBounds(t *testing.T) {
	var b gltftest.Builder
	unit := b.BoxMesh("unit", [3]float32{-0.5, -0.5, -0.5}, [3]float32{0.5, 0.5, 0.5})
	parent := b.Node("parent", -1)
	child := b.Node("child", unit)
	b.Child(parent, child)
	// parent: translate (10,0,0), rotate 90 deg about Y, scale 2.
	s := math.Sqrt2 / 2
	b.Nodes[parent]["translation"] = []float64{10, 0, 0}
	b.Nodes[parent]["rotation"] = []float64{0, s, 0, s}
	b.Nodes[parent]["scale"] = []float64{2, 2, 2}
	// child: offset +1 on local X (becomes -Z after the 90 deg Y rotation, x2 scale).
	b.Nodes[child]["translation"] = []float64{1, 0, 0}
	// A second root using an explicit matrix: scale y by 3, translate y by 5.
	m := b.Node("matrixed", unit)
	b.Nodes[m]["matrix"] = []float64{1, 0, 0, 0, 0, 3, 0, 0, 0, 0, 1, 0, 0, 5, 0, 1}

	doc := mustParse(t, b.GLB())
	nodes := doc.Nodes()
	if nodes[child].Parent != parent || nodes[child].MeshName != "unit" {
		t.Fatalf("child info = %+v", nodes[child])
	}
	c := nodes[child].World.TransformPoint([3]float64{0, 0, 0})
	if !near(c[0], 10) || !near(c[1], 0) || !near(c[2], -2) {
		t.Fatalf("child origin in world = %v, want (10,0,-2)", c)
	}
	box, ok := doc.Bounds()
	if !ok {
		t.Fatal("Bounds not ok")
	}
	// child box: centre (10,0,-2), half extent 1 -> [9,11] x [-1,1] x [-3,-1]
	// matrixed box: x [-0.5,0.5], y [3.5,6.5], z [-0.5,0.5]
	want := gltf.AABB{Min: [3]float64{-0.5, -1, -3}, Max: [3]float64{11, 6.5, 0.5}}
	for k := 0; k < 3; k++ {
		if !near(box.Min[k], want.Min[k]) || !near(box.Max[k], want.Max[k]) {
			t.Fatalf("Bounds = %+v, want %+v", box, want)
		}
	}
}

func TestBoundsWithoutMinMaxReadsData(t *testing.T) {
	var b gltftest.Builder
	mesh := b.BoxMesh("box", [3]float32{1, 2, 3}, [3]float32{4, 5, 6})
	pos := b.Meshes[mesh]["primitives"].([]gltftest.M)[0]["attributes"].(gltftest.M)["POSITION"].(int)
	delete(b.Accessors[pos], "min")
	delete(b.Accessors[pos], "max")
	b.Node("box", mesh)
	box, ok := mustParse(t, b.GLB()).Bounds()
	if !ok || !near(box.Min[0], 1) || !near(box.Max[2], 6) {
		t.Fatalf("Bounds = %+v ok=%v", box, ok)
	}
}

func TestPNGSizeFromBufferViewAndDataURI(t *testing.T) {
	var b gltftest.Builder
	b.PNGImage("T_test_base", 37, 19)
	b.Images = append(b.Images, gltftest.M{"name": "T_test_uri", "uri": "data:image/png;base64," + base64.StdEncoding.EncodeToString(gltftest.PNG(5, 7))})
	b.Images = append(b.Images, gltftest.M{"name": "T_test_junk", "uri": "data:application/octet-stream;base64," + base64.StdEncoding.EncodeToString([]byte("not an image"))})
	b.Material("M_test_body")
	doc := mustParse(t, b.GLB())
	imgs := doc.Images()
	if len(imgs) != 3 {
		t.Fatalf("got %d images", len(imgs))
	}
	if imgs[0].Format != "png" || imgs[0].Width != 37 || imgs[0].Height != 19 {
		t.Errorf("bufferView image = %+v", imgs[0])
	}
	if imgs[1].Width != 5 || imgs[1].Height != 7 {
		t.Errorf("data URI image = %+v", imgs[1])
	}
	if imgs[2].Width != 0 || len(doc.Warnings) != 1 || !strings.Contains(doc.Warnings[0], "T_test_junk") {
		t.Errorf("junk image = %+v, warnings = %v", imgs[2], doc.Warnings)
	}
	if names := doc.MaterialNames(); len(names) != 1 || names[0] != "M_test_body" {
		t.Errorf("MaterialNames = %v", names)
	}
}

func TestJPEGAndKTX2Size(t *testing.T) {
	// Minimal JPEG: SOI, APP0 stub, SOF0 with height 300 width 400.
	jpeg := []byte{0xFF, 0xD8, 0xFF, 0xE0, 0x00, 0x04, 0x00, 0x00,
		0xFF, 0xC0, 0x00, 0x0B, 0x08, 0x01, 0x2C, 0x01, 0x90, 0x01, 0x01, 0x11, 0x00}
	f, w, h, err := gltf.ImageSize(jpeg)
	if err != nil || f != "jpeg" || w != 400 || h != 300 {
		t.Errorf("jpeg = %s %dx%d %v", f, w, h, err)
	}
	ktx := make([]byte, 80)
	copy(ktx, []byte{0xAB, 'K', 'T', 'X', ' ', '2', '0', 0xBB, '\r', '\n', 0x1A, '\n'})
	binary.LittleEndian.PutUint32(ktx[20:], 1024)
	binary.LittleEndian.PutUint32(ktx[24:], 512)
	f, w, h, err = gltf.ImageSize(ktx)
	if err != nil || f != "ktx2" || w != 1024 || h != 512 {
		t.Errorf("ktx2 = %s %dx%d %v", f, w, h, err)
	}
}

func TestAnimations(t *testing.T) {
	var b gltftest.Builder
	n := b.Node("door", -1)
	b.Animation("open", n, true)
	b.Animation("empty", n, false)
	anims := mustParse(t, b.GLB()).Animations()
	if len(anims) != 2 || anims[0].Name != "open" || anims[0].Channels != 1 || anims[1].Channels != 0 {
		t.Fatalf("Animations = %+v", anims)
	}
}

func TestStructuralErrors(t *testing.T) {
	good := func() *gltftest.Builder {
		var b gltftest.Builder
		b.Node("body", b.BoxMesh("body", [3]float32{}, [3]float32{1, 1, 1}))
		return &b
	}
	encode := func(doc gltftest.M, bin []byte) []byte {
		j, _ := json.Marshal(doc)
		return gltf.EncodeGLB(j, bin)
	}
	glb := good().GLB()
	cases := map[string]struct {
		data []byte
		want string
	}{
		"bad magic":    {append([]byte("glTX"), glb[4:]...), "magic"},
		"version 1":    {func() []byte { d := append([]byte(nil), glb...); d[4] = 1; return d }(), "version"},
		"length":       {glb[:len(glb)-4], "length"},
		"bad json":     {gltf.EncodeGLB([]byte(`{"asset":`), nil), "JSON"},
		"asset 1.0":    {gltf.EncodeGLB([]byte(`{"asset":{"version":"1.0"}}`), nil), "asset.version"},
		"node mesh":    {gltf.EncodeGLB([]byte(`{"asset":{"version":"2.0"},"nodes":[{"mesh":3}]}`), nil), "missing mesh"},
		"accessor bv":  {func() []byte { b := good(); b.Accessors[0]["bufferView"] = 99; return b.GLB() }(), "missing bufferView"},
		"accessor len": {func() []byte { b := good(); b.Accessors[0]["count"] = 1000; return b.GLB() }(), "needs"},
		"no bin":       {func() []byte { b := good(); return encode(b.JSON(), nil) }(), "BIN"},
		"cycle":        {gltf.EncodeGLB([]byte(`{"asset":{"version":"2.0"},"nodes":[{"children":[1]},{"children":[0]}]}`), nil), "cycle"},
	}
	for name, c := range cases {
		_, err := gltf.Parse(c.data, "")
		if err == nil || !strings.Contains(err.Error(), c.want) {
			t.Errorf("%s: err = %v, want containing %q", name, err, c.want)
		}
	}
}
