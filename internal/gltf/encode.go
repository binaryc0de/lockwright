package gltf

import (
	"bytes"
	"encoding/binary"
)

// EncodeGLB assembles a GLB container from a JSON chunk and an optional BIN
// chunk (nil omits it). Both chunks are padded to 4 bytes as the spec
// requires (JSON with spaces, BIN with zeros). It does not validate content;
// tests use it to build fixtures, including deliberately broken ones.
func EncodeGLB(jsonChunk, bin []byte) []byte {
	pad := func(b []byte, fill byte) []byte {
		out := append([]byte(nil), b...)
		for len(out)%4 != 0 {
			out = append(out, fill)
		}
		return out
	}
	j := pad(jsonChunk, ' ')
	total := 12 + 8 + len(j)
	var b []byte
	if bin != nil {
		b = pad(bin, 0)
		total += 8 + len(b)
	}
	var buf bytes.Buffer
	le := binary.LittleEndian
	w := func(v uint32) { _ = binary.Write(&buf, le, v) }
	w(glbMagic)
	w(2)
	w(uint32(total))
	w(uint32(len(j)))
	w(chunkTypeJSON)
	buf.Write(j)
	if bin != nil {
		w(uint32(len(b)))
		w(chunkTypeBIN)
		buf.Write(b)
	}
	return buf.Bytes()
}
