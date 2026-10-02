// Package gltftest builds small GLB files in memory for tests.
package gltftest

import (
	"bytes"
	"encoding/binary"
	"encoding/json"
	"image"
	"image/png"
	"math"

	"github.com/binaryc0de/escapebox/internal/gltf"
)

// M is a JSON object.
type M = map[string]any

// Builder accumulates glTF JSON objects and a single BIN buffer.
type Builder struct {
	bin         bytes.Buffer
	Nodes       []M
	Meshes      []M
	Accessors   []M
	BufferViews []M
	Materials   []M
	Images      []M
	Textures    []M
	Animations  []M
	// Roots are the scene's root nodes; nil means "every node without a parent".
	Roots []int
}

// View appends data to the BIN buffer (4-byte aligned) and returns the new
// bufferView index.
func (b *Builder) View(data []byte) int {
	for b.bin.Len()%4 != 0 {
		b.bin.WriteByte(0)
	}
	off := b.bin.Len()
	b.bin.Write(data)
	b.BufferViews = append(b.BufferViews, M{"buffer": 0, "byteOffset": off, "byteLength": len(data)})
	return len(b.BufferViews) - 1
}

// Accessor appends an accessor and returns its index.
func (b *Builder) Accessor(a M) int {
	b.Accessors = append(b.Accessors, a)
	return len(b.Accessors) - 1
}

func f32bytes(vals []float32) []byte {
	var buf bytes.Buffer
	_ = binary.Write(&buf, binary.LittleEndian, vals)
	return buf.Bytes()
}

// Positions adds a float VEC3 POSITION accessor with min/max and returns it.
func (b *Builder) Positions(pts [][3]float32) int {
	flat := make([]float32, 0, len(pts)*3)
	lo := []float64{math.Inf(1), math.Inf(1), math.Inf(1)}
	hi := []float64{math.Inf(-1), math.Inf(-1), math.Inf(-1)}
	for _, p := range pts {
		flat = append(flat, p[:]...)
		for k := 0; k < 3; k++ {
			lo[k] = math.Min(lo[k], float64(p[k]))
			hi[k] = math.Max(hi[k], float64(p[k]))
		}
	}
	v := b.View(f32bytes(flat))
	return b.Accessor(M{"bufferView": v, "componentType": 5126, "count": len(pts), "type": "VEC3", "min": lo, "max": hi})
}

// Indices adds a uint16 SCALAR index accessor.
func (b *Builder) Indices(idx []uint16) int {
	var buf bytes.Buffer
	_ = binary.Write(&buf, binary.LittleEndian, idx)
	v := b.View(buf.Bytes())
	return b.Accessor(M{"bufferView": v, "componentType": 5123, "count": len(idx), "type": "SCALAR"})
}

// Mesh appends a mesh with the given primitives and returns its index.
func (b *Builder) Mesh(name string, prims ...M) int {
	b.Meshes = append(b.Meshes, M{"name": name, "primitives": prims})
	return len(b.Meshes) - 1
}

// BoxMesh adds an indexed 12-triangle box spanning lo..hi.
func (b *Builder) BoxMesh(name string, lo, hi [3]float32) int {
	pts := make([][3]float32, 8)
	for c := 0; c < 8; c++ {
		p := lo
		if c&1 != 0 {
			p[0] = hi[0]
		}
		if c&2 != 0 {
			p[1] = hi[1]
		}
		if c&4 != 0 {
			p[2] = hi[2]
		}
		pts[c] = p
	}
	idx := []uint16{
		0, 2, 1, 1, 2, 3, // -z
		4, 5, 6, 5, 7, 6, // +z
		0, 1, 4, 1, 5, 4, // -y
		2, 6, 3, 3, 6, 7, // +y
		0, 4, 2, 2, 4, 6, // -x
		1, 3, 5, 3, 7, 5, // +x
	}
	pos := b.Positions(pts)
	ind := b.Indices(idx)
	return b.Mesh(name, M{"attributes": M{"POSITION": pos}, "indices": ind})
}

// Node appends a node (mesh < 0 means no mesh) and returns its index. Set
// transforms with b.Nodes[i]["translation"] etc.
func (b *Builder) Node(name string, mesh int) int {
	n := M{"name": name}
	if mesh >= 0 {
		n["mesh"] = mesh
	}
	b.Nodes = append(b.Nodes, n)
	return len(b.Nodes) - 1
}

// Child makes child a child of parent.
func (b *Builder) Child(parent, child int) {
	kids, _ := b.Nodes[parent]["children"].([]int)
	b.Nodes[parent]["children"] = append(kids, child)
}

// Material appends a named material.
func (b *Builder) Material(name string) int {
	b.Materials = append(b.Materials, M{"name": name})
	return len(b.Materials) - 1
}

// PNG returns an encoded w x h PNG.
func PNG(w, h int) []byte {
	var buf bytes.Buffer
	if err := png.Encode(&buf, image.NewGray(image.Rect(0, 0, w, h))); err != nil {
		panic(err)
	}
	return buf.Bytes()
}

// PNGImage embeds a w x h PNG through a bufferView and adds a texture for it.
func (b *Builder) PNGImage(name string, w, h int) int {
	v := b.View(PNG(w, h))
	b.Images = append(b.Images, M{"name": name, "mimeType": "image/png", "bufferView": v})
	idx := len(b.Images) - 1
	b.Textures = append(b.Textures, M{"source": idx})
	return idx
}

// Animation adds an animation; with a channel it translates node over 1 s.
func (b *Builder) Animation(name string, node int, withChannel bool) int {
	anim := M{"name": name, "channels": []M{}, "samplers": []M{}}
	if withChannel {
		in := b.Accessor(M{"bufferView": b.View(f32bytes([]float32{0, 1})), "componentType": 5126, "count": 2, "type": "SCALAR", "min": []float64{0}, "max": []float64{1}})
		out := b.Accessor(M{"bufferView": b.View(f32bytes([]float32{0, 0, 0, 0, 0, 0.1})), "componentType": 5126, "count": 2, "type": "VEC3"})
		anim["samplers"] = []M{{"input": in, "output": out}}
		anim["channels"] = []M{{"sampler": 0, "target": M{"node": node, "path": "translation"}}}
	}
	b.Animations = append(b.Animations, anim)
	return len(b.Animations) - 1
}

// JSON returns the glTF JSON document.
func (b *Builder) JSON() M {
	roots := b.Roots
	if roots == nil {
		hasParent := map[int]bool{}
		for _, n := range b.Nodes {
			kids, _ := n["children"].([]int)
			for _, k := range kids {
				hasParent[k] = true
			}
		}
		roots = []int{}
		for i := range b.Nodes {
			if !hasParent[i] {
				roots = append(roots, i)
			}
		}
	}
	doc := M{
		"asset":  M{"version": "2.0", "generator": "gltftest"},
		"scene":  0,
		"scenes": []M{{"nodes": roots}},
	}
	set := func(k string, v []M) {
		if len(v) > 0 {
			doc[k] = v
		}
	}
	set("nodes", b.Nodes)
	set("meshes", b.Meshes)
	set("accessors", b.Accessors)
	set("bufferViews", b.BufferViews)
	set("materials", b.Materials)
	set("images", b.Images)
	set("textures", b.Textures)
	set("animations", b.Animations)
	if b.bin.Len() > 0 {
		doc["buffers"] = []M{{"byteLength": b.bin.Len()}}
	}
	return doc
}

// GLB encodes the builder's content as a GLB file.
func (b *Builder) GLB() []byte {
	j, err := json.Marshal(b.JSON())
	if err != nil {
		panic(err)
	}
	var bin []byte
	if b.bin.Len() > 0 {
		bin = b.bin.Bytes()
	}
	return gltf.EncodeGLB(j, bin)
}
