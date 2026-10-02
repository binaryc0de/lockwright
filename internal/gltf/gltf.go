// Package gltf is a minimal, dependency-free reader for binary glTF 2.0 (GLB)
// files. It covers what tools/assetcheck needs: structural validation, node
// names and hierarchy with world transforms, triangle counts, world-space
// bounds, material and animation names, and image pixel sizes.
//
// It is not a full validator: it checks the GLB container, JSON parse, and
// that every index reference (accessor, bufferView, buffer, mesh, node,
// material, image, sampler) is in range and every accessor fits its
// bufferView.
package gltf

import (
	"encoding/base64"
	"encoding/binary"
	"encoding/json"
	"errors"
	"fmt"
	"math"
	"net/url"
	"os"
	"path/filepath"
	"strings"
)

// GLB container constants.
const (
	glbMagic      = 0x46546C67 // "glTF"
	chunkTypeJSON = 0x4E4F534A // "JSON"
	chunkTypeBIN  = 0x004E4942 // "BIN\0"
)

// Primitive modes.
const (
	ModePoints        = 0
	ModeLines         = 1
	ModeLineLoop      = 2
	ModeLineStrip     = 3
	ModeTriangles     = 4
	ModeTriangleStrip = 5
	ModeTriangleFan   = 6
)

// GLTF is the subset of the glTF 2.0 JSON schema this package reads.
type GLTF struct {
	Asset              Asset        `json:"asset"`
	Scene              *int         `json:"scene,omitempty"`
	Scenes             []Scene      `json:"scenes,omitempty"`
	Nodes              []Node       `json:"nodes,omitempty"`
	Meshes             []Mesh       `json:"meshes,omitempty"`
	Accessors          []Accessor   `json:"accessors,omitempty"`
	BufferViews        []BufferView `json:"bufferViews,omitempty"`
	Buffers            []Buffer     `json:"buffers,omitempty"`
	Materials          []Material   `json:"materials,omitempty"`
	Textures           []Texture    `json:"textures,omitempty"`
	Images             []Image      `json:"images,omitempty"`
	Animations         []Animation  `json:"animations,omitempty"`
	ExtensionsUsed     []string     `json:"extensionsUsed,omitempty"`
	ExtensionsRequired []string     `json:"extensionsRequired,omitempty"`
}

type Asset struct {
	Version   string `json:"version"`
	Generator string `json:"generator,omitempty"`
}

type Scene struct {
	Name  string `json:"name,omitempty"`
	Nodes []int  `json:"nodes,omitempty"`
}

type Node struct {
	Name        string    `json:"name,omitempty"`
	Mesh        *int      `json:"mesh,omitempty"`
	Children    []int     `json:"children,omitempty"`
	Matrix      []float64 `json:"matrix,omitempty"`
	Translation []float64 `json:"translation,omitempty"`
	Rotation    []float64 `json:"rotation,omitempty"`
	Scale       []float64 `json:"scale,omitempty"`
}

type Mesh struct {
	Name       string      `json:"name,omitempty"`
	Primitives []Primitive `json:"primitives"`
}

type Primitive struct {
	Attributes map[string]int `json:"attributes"`
	Indices    *int           `json:"indices,omitempty"`
	Mode       *int           `json:"mode,omitempty"`
	Material   *int           `json:"material,omitempty"`
}

type Accessor struct {
	BufferView    *int            `json:"bufferView,omitempty"`
	ByteOffset    int             `json:"byteOffset,omitempty"`
	ComponentType int             `json:"componentType"`
	Normalized    bool            `json:"normalized,omitempty"`
	Count         int             `json:"count"`
	Type          string          `json:"type"`
	Min           []float64       `json:"min,omitempty"`
	Max           []float64       `json:"max,omitempty"`
	Sparse        json.RawMessage `json:"sparse,omitempty"`
}

type BufferView struct {
	Buffer     int `json:"buffer"`
	ByteOffset int `json:"byteOffset,omitempty"`
	ByteLength int `json:"byteLength"`
	ByteStride int `json:"byteStride,omitempty"`
}

type Buffer struct {
	ByteLength int    `json:"byteLength"`
	URI        string `json:"uri,omitempty"`
}

type Material struct {
	Name string `json:"name,omitempty"`
}

type Texture struct {
	Source *int `json:"source,omitempty"`
}

type Image struct {
	Name       string `json:"name,omitempty"`
	URI        string `json:"uri,omitempty"`
	MimeType   string `json:"mimeType,omitempty"`
	BufferView *int   `json:"bufferView,omitempty"`
}

type Animation struct {
	Name     string             `json:"name,omitempty"`
	Channels []AnimationChannel `json:"channels"`
	Samplers []AnimationSampler `json:"samplers"`
}

type AnimationChannel struct {
	Sampler int                    `json:"sampler"`
	Target  AnimationChannelTarget `json:"target"`
}

type AnimationChannelTarget struct {
	Node *int   `json:"node,omitempty"`
	Path string `json:"path"`
}

type AnimationSampler struct {
	Input         int    `json:"input"`
	Output        int    `json:"output"`
	Interpolation string `json:"interpolation,omitempty"`
}

// Document is a parsed GLB.
type Document struct {
	JSON GLTF
	// BIN is the GLB binary chunk (nil when absent).
	BIN []byte
	// BaseDir resolves external buffer and image URIs; empty disables them.
	BaseDir string
	// Warnings collects non-fatal issues found while parsing and inspecting.
	Warnings []string

	nodes     []NodeInfo
	sceneRoot []int
	buffers   [][]byte // resolved buffer data, nil if unavailable
}

// NodeInfo describes one node after hierarchy resolution.
type NodeInfo struct {
	Index    int
	Name     string
	Mesh     int // -1 when the node has no mesh
	MeshName string
	Parent   int // -1 for roots and nodes outside any hierarchy
	Children []int
	World    Mat4
	// InScene is true when the node is reachable from the active scene.
	InScene bool
}

// AABB is an axis-aligned bounding box.
type AABB struct {
	Min, Max [3]float64
}

// Center returns the box centre.
func (b AABB) Center() [3]float64 {
	return [3]float64{(b.Min[0] + b.Max[0]) / 2, (b.Min[1] + b.Max[1]) / 2, (b.Min[2] + b.Max[2]) / 2}
}

// Size returns the box extent along each axis.
func (b AABB) Size() [3]float64 {
	return [3]float64{b.Max[0] - b.Min[0], b.Max[1] - b.Min[1], b.Max[2] - b.Min[2]}
}

// AnimationInfo summarises one animation.
type AnimationInfo struct {
	Name     string
	Channels int
}

// ImageInfo describes one image and its decoded pixel size (0 when unknown).
type ImageInfo struct {
	Index    int
	Name     string
	MimeType string
	Format   string // "png", "jpeg", "ktx2" or "" when unknown
	Width    int
	Height   int
}

// ReadFile parses a GLB from disk; external URIs resolve next to the file.
func ReadFile(path string) (*Document, error) {
	data, err := os.ReadFile(path)
	if err != nil {
		return nil, err
	}
	return Parse(data, filepath.Dir(path))
}

// Parse parses and structurally validates a GLB. baseDir resolves external
// URIs and may be empty.
func Parse(data []byte, baseDir string) (*Document, error) {
	if len(data) < 12 {
		return nil, fmt.Errorf("glb: file too short (%d bytes)", len(data))
	}
	le := binary.LittleEndian
	if le.Uint32(data[0:4]) != glbMagic {
		return nil, errors.New("glb: bad magic (not a binary glTF file)")
	}
	if v := le.Uint32(data[4:8]); v != 2 {
		return nil, fmt.Errorf("glb: unsupported container version %d (want 2)", v)
	}
	total := int(le.Uint32(data[8:12]))
	if total != len(data) {
		return nil, fmt.Errorf("glb: header length %d does not match file size %d", total, len(data))
	}

	doc := &Document{BaseDir: baseDir}
	var jsonChunk []byte
	off := 12
	for i := 0; off < total; i++ {
		if off+8 > total {
			return nil, fmt.Errorf("glb: truncated chunk header at offset %d", off)
		}
		clen := int(le.Uint32(data[off : off+4]))
		ctype := le.Uint32(data[off+4 : off+8])
		start := off + 8
		if clen < 0 || start+clen > total {
			return nil, fmt.Errorf("glb: chunk %d length %d overruns file", i, clen)
		}
		if clen%4 != 0 {
			return nil, fmt.Errorf("glb: chunk %d length %d is not 4-byte aligned", i, clen)
		}
		chunk := data[start : start+clen]
		switch {
		case i == 0:
			if ctype != chunkTypeJSON {
				return nil, errors.New("glb: first chunk is not JSON")
			}
			jsonChunk = chunk
		case i == 1 && ctype == chunkTypeBIN:
			doc.BIN = chunk
		case ctype == chunkTypeJSON || ctype == chunkTypeBIN:
			return nil, fmt.Errorf("glb: unexpected extra %s chunk at index %d", chunkName(ctype), i)
		default:
			// Unknown chunk types must be ignored per the spec.
		}
		off = start + clen
	}
	if jsonChunk == nil {
		return nil, errors.New("glb: missing JSON chunk")
	}
	if err := json.Unmarshal(jsonChunk, &doc.JSON); err != nil {
		return nil, fmt.Errorf("glb: JSON chunk: %w", err)
	}
	if err := doc.validate(); err != nil {
		return nil, err
	}
	if err := doc.resolveHierarchy(); err != nil {
		return nil, err
	}
	return doc, nil
}

func chunkName(t uint32) string {
	if t == chunkTypeJSON {
		return "JSON"
	}
	return "BIN"
}

// warnf records a warning once (repeated inspection calls do not duplicate it).
func (d *Document) warnf(format string, args ...any) {
	msg := fmt.Sprintf(format, args...)
	for _, w := range d.Warnings {
		if w == msg {
			return
		}
	}
	d.Warnings = append(d.Warnings, msg)
}

var componentSizes = map[int]int{5120: 1, 5121: 1, 5122: 2, 5123: 2, 5125: 4, 5126: 4}
var typeComponents = map[string]int{"SCALAR": 1, "VEC2": 2, "VEC3": 3, "VEC4": 4, "MAT2": 4, "MAT3": 9, "MAT4": 16}

func inRange(i, n int) bool { return i >= 0 && i < n }

// validate checks the asset version and every index reference.
func (d *Document) validate() error {
	g := &d.JSON
	if !strings.HasPrefix(g.Asset.Version, "2.") {
		return fmt.Errorf("gltf: asset.version %q is not 2.x", g.Asset.Version)
	}
	known := map[string]bool{"KHR_materials_emissive_strength": true, "KHR_texture_transform": true, "KHR_texture_basisu": true, "KHR_materials_ior": true, "KHR_materials_specular": true, "KHR_materials_transmission": true, "KHR_materials_volume": true, "KHR_materials_clearcoat": true, "KHR_materials_sheen": true, "KHR_materials_unlit": true, "KHR_mesh_quantization": true, "KHR_lights_punctual": true}
	for _, e := range g.ExtensionsRequired {
		if !known[e] {
			d.warnf("extension %s is required but not understood by assetcheck", e)
		}
	}

	// Buffers: resolve data so bufferView ranges can be checked.
	d.buffers = make([][]byte, len(g.Buffers))
	for i, b := range g.Buffers {
		if b.ByteLength < 1 {
			return fmt.Errorf("gltf: buffer %d has byteLength %d", i, b.ByteLength)
		}
		switch {
		case b.URI == "":
			if i != 0 {
				return fmt.Errorf("gltf: buffer %d has no uri (only buffer 0 may use the GLB BIN chunk)", i)
			}
			if d.BIN == nil {
				return errors.New("gltf: buffer 0 references the GLB BIN chunk but the file has none")
			}
			if b.ByteLength > len(d.BIN) || len(d.BIN)-b.ByteLength > 3 {
				return fmt.Errorf("gltf: buffer 0 byteLength %d does not match BIN chunk length %d", b.ByteLength, len(d.BIN))
			}
			d.buffers[i] = d.BIN[:b.ByteLength]
		default:
			data, err := d.loadURI(b.URI)
			if err != nil {
				d.warnf("buffer %d: %v", i, err)
				continue
			}
			if len(data) < b.ByteLength {
				return fmt.Errorf("gltf: buffer %d is %d bytes, byteLength says %d", i, len(data), b.ByteLength)
			}
			d.buffers[i] = data[:b.ByteLength]
		}
	}

	for i, bv := range g.BufferViews {
		if !inRange(bv.Buffer, len(g.Buffers)) {
			return fmt.Errorf("gltf: bufferView %d references missing buffer %d", i, bv.Buffer)
		}
		if bv.ByteOffset < 0 || bv.ByteLength < 1 || bv.ByteOffset+bv.ByteLength > g.Buffers[bv.Buffer].ByteLength {
			return fmt.Errorf("gltf: bufferView %d range [%d,+%d) exceeds buffer %d (%d bytes)", i, bv.ByteOffset, bv.ByteLength, bv.Buffer, g.Buffers[bv.Buffer].ByteLength)
		}
		if bv.ByteStride != 0 && (bv.ByteStride < 4 || bv.ByteStride > 252) {
			return fmt.Errorf("gltf: bufferView %d byteStride %d out of range", i, bv.ByteStride)
		}
	}

	for i, a := range g.Accessors {
		cs, ok := componentSizes[a.ComponentType]
		if !ok {
			return fmt.Errorf("gltf: accessor %d has invalid componentType %d", i, a.ComponentType)
		}
		nc, ok := typeComponents[a.Type]
		if !ok {
			return fmt.Errorf("gltf: accessor %d has invalid type %q", i, a.Type)
		}
		if a.Count < 1 {
			return fmt.Errorf("gltf: accessor %d has count %d", i, a.Count)
		}
		if a.BufferView == nil {
			continue
		}
		if !inRange(*a.BufferView, len(g.BufferViews)) {
			return fmt.Errorf("gltf: accessor %d references missing bufferView %d", i, *a.BufferView)
		}
		bv := g.BufferViews[*a.BufferView]
		elem := cs * nc
		stride := bv.ByteStride
		if stride == 0 {
			stride = elem
		}
		need := a.ByteOffset + stride*(a.Count-1) + elem
		if a.ByteOffset < 0 || need > bv.ByteLength {
			return fmt.Errorf("gltf: accessor %d needs %d bytes but bufferView %d has %d", i, need, *a.BufferView, bv.ByteLength)
		}
	}

	for i, m := range g.Meshes {
		if len(m.Primitives) == 0 {
			return fmt.Errorf("gltf: mesh %d (%q) has no primitives", i, m.Name)
		}
		for j, p := range m.Primitives {
			for attr, ai := range p.Attributes {
				if !inRange(ai, len(g.Accessors)) {
					return fmt.Errorf("gltf: mesh %d primitive %d attribute %s references missing accessor %d", i, j, attr, ai)
				}
			}
			if p.Indices != nil && !inRange(*p.Indices, len(g.Accessors)) {
				return fmt.Errorf("gltf: mesh %d primitive %d indices reference missing accessor %d", i, j, *p.Indices)
			}
			if p.Material != nil && !inRange(*p.Material, len(g.Materials)) {
				return fmt.Errorf("gltf: mesh %d primitive %d references missing material %d", i, j, *p.Material)
			}
			if p.Mode != nil && (*p.Mode < 0 || *p.Mode > 6) {
				return fmt.Errorf("gltf: mesh %d primitive %d has invalid mode %d", i, j, *p.Mode)
			}
		}
	}

	for i, n := range g.Nodes {
		if n.Mesh != nil && !inRange(*n.Mesh, len(g.Meshes)) {
			return fmt.Errorf("gltf: node %d (%q) references missing mesh %d", i, n.Name, *n.Mesh)
		}
		for _, c := range n.Children {
			if !inRange(c, len(g.Nodes)) {
				return fmt.Errorf("gltf: node %d (%q) references missing child %d", i, n.Name, c)
			}
		}
		if n.Matrix != nil && len(n.Matrix) != 16 {
			return fmt.Errorf("gltf: node %d (%q) matrix has %d elements", i, n.Name, len(n.Matrix))
		}
		if n.Translation != nil && len(n.Translation) != 3 {
			return fmt.Errorf("gltf: node %d (%q) translation has %d elements", i, n.Name, len(n.Translation))
		}
		if n.Rotation != nil && len(n.Rotation) != 4 {
			return fmt.Errorf("gltf: node %d (%q) rotation has %d elements", i, n.Name, len(n.Rotation))
		}
		if n.Scale != nil && len(n.Scale) != 3 {
			return fmt.Errorf("gltf: node %d (%q) scale has %d elements", i, n.Name, len(n.Scale))
		}
	}

	for i, s := range g.Scenes {
		for _, r := range s.Nodes {
			if !inRange(r, len(g.Nodes)) {
				return fmt.Errorf("gltf: scene %d references missing node %d", i, r)
			}
		}
	}
	if g.Scene != nil && !inRange(*g.Scene, len(g.Scenes)) {
		return fmt.Errorf("gltf: default scene %d does not exist", *g.Scene)
	}

	for i, t := range g.Textures {
		if t.Source != nil && !inRange(*t.Source, len(g.Images)) {
			return fmt.Errorf("gltf: texture %d references missing image %d", i, *t.Source)
		}
	}
	for i, im := range g.Images {
		if im.BufferView != nil && !inRange(*im.BufferView, len(g.BufferViews)) {
			return fmt.Errorf("gltf: image %d references missing bufferView %d", i, *im.BufferView)
		}
		if im.BufferView == nil && im.URI == "" {
			return fmt.Errorf("gltf: image %d has neither uri nor bufferView", i)
		}
	}

	for i, a := range g.Animations {
		for j, s := range a.Samplers {
			if !inRange(s.Input, len(g.Accessors)) || !inRange(s.Output, len(g.Accessors)) {
				return fmt.Errorf("gltf: animation %d (%q) sampler %d references a missing accessor", i, a.Name, j)
			}
		}
		for j, c := range a.Channels {
			if !inRange(c.Sampler, len(a.Samplers)) {
				return fmt.Errorf("gltf: animation %d (%q) channel %d references missing sampler %d", i, a.Name, j, c.Sampler)
			}
			if c.Target.Node != nil && !inRange(*c.Target.Node, len(g.Nodes)) {
				return fmt.Errorf("gltf: animation %d (%q) channel %d targets missing node %d", i, a.Name, j, *c.Target.Node)
			}
		}
	}
	return nil
}

// loadURI returns the bytes of a data: URI or an external file next to the GLB.
func (d *Document) loadURI(uri string) ([]byte, error) {
	if strings.HasPrefix(uri, "data:") {
		comma := strings.IndexByte(uri, ',')
		if comma < 0 {
			return nil, errors.New("malformed data URI")
		}
		if !strings.HasSuffix(uri[:comma], ";base64") {
			return nil, errors.New("data URI is not base64-encoded")
		}
		return base64.StdEncoding.DecodeString(uri[comma+1:])
	}
	if d.BaseDir == "" {
		return nil, fmt.Errorf("external uri %q not resolvable (no base directory)", uri)
	}
	p, err := url.PathUnescape(uri)
	if err != nil {
		p = uri
	}
	if filepath.IsAbs(p) || strings.Contains(p, "://") {
		return nil, fmt.Errorf("uri %q is not a relative path", uri)
	}
	return os.ReadFile(filepath.Join(d.BaseDir, filepath.FromSlash(p)))
}

// resolveHierarchy computes parents, scene membership and world matrices.
func (d *Document) resolveHierarchy() error {
	g := &d.JSON
	d.nodes = make([]NodeInfo, len(g.Nodes))
	for i, n := range g.Nodes {
		info := NodeInfo{Index: i, Name: n.Name, Mesh: -1, Parent: -1, Children: n.Children}
		if n.Mesh != nil {
			info.Mesh = *n.Mesh
			info.MeshName = g.Meshes[*n.Mesh].Name
		}
		d.nodes[i] = info
	}
	for i, n := range g.Nodes {
		for _, c := range n.Children {
			if c == i {
				return fmt.Errorf("gltf: node %d (%q) is its own child", i, n.Name)
			}
			if d.nodes[c].Parent != -1 {
				return fmt.Errorf("gltf: node %d (%q) has more than one parent", c, g.Nodes[c].Name)
			}
			d.nodes[c].Parent = i
		}
	}

	switch {
	case g.Scene != nil:
		d.sceneRoot = g.Scenes[*g.Scene].Nodes
	case len(g.Scenes) > 0:
		d.sceneRoot = g.Scenes[0].Nodes
	default:
		for i := range d.nodes {
			if d.nodes[i].Parent == -1 {
				d.sceneRoot = append(d.sceneRoot, i)
			}
		}
	}

	visited := make([]bool, len(g.Nodes))
	var walk func(i int, parent Mat4) error
	walk = func(i int, parent Mat4) error {
		if visited[i] {
			return fmt.Errorf("gltf: node %d (%q) reached twice (cycle or shared subtree)", i, g.Nodes[i].Name)
		}
		visited[i] = true
		world := parent.Mul(LocalMatrix(g.Nodes[i]))
		d.nodes[i].World = world
		d.nodes[i].InScene = true
		for _, c := range g.Nodes[i].Children {
			if err := walk(c, world); err != nil {
				return err
			}
		}
		return nil
	}
	for _, r := range d.sceneRoot {
		if d.nodes[r].Parent != -1 {
			return fmt.Errorf("gltf: scene root node %d (%q) has a parent", r, g.Nodes[r].Name)
		}
		if err := walk(r, Identity()); err != nil {
			return err
		}
	}
	// Nodes outside the scene still get a world matrix for inspection.
	for i := range d.nodes {
		if !visited[i] && d.nodes[i].Parent == -1 {
			var walkOut func(i int, parent Mat4)
			walkOut = func(i int, parent Mat4) {
				if visited[i] {
					return
				}
				visited[i] = true
				d.nodes[i].World = parent.Mul(LocalMatrix(g.Nodes[i]))
				for _, c := range g.Nodes[i].Children {
					walkOut(c, d.nodes[i].World)
				}
			}
			walkOut(i, Identity())
		}
	}
	for i := range d.nodes {
		if !visited[i] {
			return fmt.Errorf("gltf: node %d (%q) is part of a parent cycle", i, g.Nodes[i].Name)
		}
	}
	return nil
}

// Nodes returns every node with its resolved hierarchy information.
func (d *Document) Nodes() []NodeInfo { return d.nodes }

// SceneRoots returns the root node indices of the active scene.
func (d *Document) SceneRoots() []int { return d.sceneRoot }

// NodeNames returns the names of all nodes reachable from the active scene.
func (d *Document) NodeNames() []string {
	var out []string
	for _, n := range d.nodes {
		if n.InScene {
			out = append(out, n.Name)
		}
	}
	return out
}

// MaterialNames returns material names in index order.
func (d *Document) MaterialNames() []string {
	out := make([]string, len(d.JSON.Materials))
	for i, m := range d.JSON.Materials {
		out[i] = m.Name
	}
	return out
}

// Animations returns each animation's name and channel count.
func (d *Document) Animations() []AnimationInfo {
	out := make([]AnimationInfo, len(d.JSON.Animations))
	for i, a := range d.JSON.Animations {
		out[i] = AnimationInfo{Name: a.Name, Channels: len(a.Channels)}
	}
	return out
}

// PrimitiveTriangles returns the triangle count of one primitive.
func (d *Document) PrimitiveTriangles(p Primitive) int {
	mode := ModeTriangles
	if p.Mode != nil {
		mode = *p.Mode
	}
	n := 0
	if p.Indices != nil {
		n = d.JSON.Accessors[*p.Indices].Count
	} else if pos, ok := p.Attributes["POSITION"]; ok {
		n = d.JSON.Accessors[pos].Count
	}
	switch mode {
	case ModeTriangles:
		return n / 3
	case ModeTriangleStrip, ModeTriangleFan:
		if n < 3 {
			return 0
		}
		return n - 2
	default:
		return 0
	}
}

// MeshTriangles returns the triangle count of one mesh (all primitives).
func (d *Document) MeshTriangles(mesh int) int {
	total := 0
	for _, p := range d.JSON.Meshes[mesh].Primitives {
		total += d.PrimitiveTriangles(p)
	}
	return total
}

// TotalTriangles counts triangles over every mesh instance in the scene.
func (d *Document) TotalTriangles() int {
	cache := map[int]int{}
	total := 0
	for _, n := range d.nodes {
		if !n.InScene || n.Mesh < 0 {
			continue
		}
		t, ok := cache[n.Mesh]
		if !ok {
			t = d.MeshTriangles(n.Mesh)
			cache[n.Mesh] = t
		}
		total += t
	}
	return total
}

// Bounds returns the world-space AABB of every mesh instance in the scene.
// ok is false when there is no geometry with known bounds.
func (d *Document) Bounds() (box AABB, ok bool) {
	box = AABB{
		Min: [3]float64{math.Inf(1), math.Inf(1), math.Inf(1)},
		Max: [3]float64{math.Inf(-1), math.Inf(-1), math.Inf(-1)},
	}
	for _, n := range d.nodes {
		if !n.InScene || n.Mesh < 0 {
			continue
		}
		for pi, p := range d.JSON.Meshes[n.Mesh].Primitives {
			pos, has := p.Attributes["POSITION"]
			if !has {
				continue
			}
			lmin, lmax, found := d.accessorMinMax3(pos)
			if !found {
				d.warnf("mesh %q primitive %d: POSITION accessor %d has no usable min/max; skipped in bounds", n.MeshName, pi, pos)
				continue
			}
			for c := 0; c < 8; c++ {
				corner := [3]float64{lmin[0], lmin[1], lmin[2]}
				if c&1 != 0 {
					corner[0] = lmax[0]
				}
				if c&2 != 0 {
					corner[1] = lmax[1]
				}
				if c&4 != 0 {
					corner[2] = lmax[2]
				}
				w := n.World.TransformPoint(corner)
				for k := 0; k < 3; k++ {
					box.Min[k] = math.Min(box.Min[k], w[k])
					box.Max[k] = math.Max(box.Max[k], w[k])
				}
				ok = true
			}
		}
	}
	return box, ok
}

// accessorMinMax3 returns a VEC3 accessor's min/max, falling back to reading
// float data when min/max are absent.
func (d *Document) accessorMinMax3(i int) (lo, hi [3]float64, ok bool) {
	a := d.JSON.Accessors[i]
	if a.Type != "VEC3" {
		return lo, hi, false
	}
	if len(a.Min) == 3 && len(a.Max) == 3 {
		copy(lo[:], a.Min)
		copy(hi[:], a.Max)
		return lo, hi, true
	}
	if a.ComponentType != 5126 || a.BufferView == nil || len(a.Sparse) > 0 {
		return lo, hi, false
	}
	bv := d.JSON.BufferViews[*a.BufferView]
	buf := d.buffers[bv.Buffer]
	if buf == nil {
		return lo, hi, false
	}
	stride := bv.ByteStride
	if stride == 0 {
		stride = 12
	}
	lo = [3]float64{math.Inf(1), math.Inf(1), math.Inf(1)}
	hi = [3]float64{math.Inf(-1), math.Inf(-1), math.Inf(-1)}
	base := bv.ByteOffset + a.ByteOffset
	for e := 0; e < a.Count; e++ {
		o := base + e*stride
		for k := 0; k < 3; k++ {
			v := float64(math.Float32frombits(binary.LittleEndian.Uint32(buf[o+4*k:])))
			lo[k] = math.Min(lo[k], v)
			hi[k] = math.Max(hi[k], v)
		}
	}
	return lo, hi, true
}

// bufferViewBytes returns the bytes of a bufferView, or nil if unavailable.
func (d *Document) bufferViewBytes(i int) []byte {
	bv := d.JSON.BufferViews[i]
	buf := d.buffers[bv.Buffer]
	if buf == nil {
		return nil
	}
	return buf[bv.ByteOffset : bv.ByteOffset+bv.ByteLength]
}

// Images returns every image with its pixel size. Images whose size cannot be
// determined get Width/Height 0 and add a warning to d.Warnings.
func (d *Document) Images() []ImageInfo {
	out := make([]ImageInfo, len(d.JSON.Images))
	for i, im := range d.JSON.Images {
		info := ImageInfo{Index: i, Name: im.Name, MimeType: im.MimeType}
		label := im.Name
		if label == "" {
			label = fmt.Sprintf("#%d", i)
		}
		var data []byte
		if im.BufferView != nil {
			data = d.bufferViewBytes(*im.BufferView)
			if data == nil {
				d.warnf("image %s: bufferView data unavailable", label)
			}
		} else {
			var err error
			data, err = d.loadURI(im.URI)
			if err != nil {
				d.warnf("image %s: %v", label, err)
				data = nil
			}
		}
		if data != nil {
			format, w, h, err := ImageSize(data)
			if err != nil {
				d.warnf("image %s: %v; size unknown", label, err)
			} else {
				info.Format, info.Width, info.Height = format, w, h
			}
		}
		out[i] = info
	}
	return out
}
