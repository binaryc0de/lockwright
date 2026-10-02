package gltf

// Mat4 is a 4x4 column-major matrix, matching glTF's node.matrix layout:
// element (row r, column c) is m[c*4+r].
type Mat4 [16]float64

// Identity returns the identity matrix.
func Identity() Mat4 {
	return Mat4{1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1}
}

// Mul returns m * o.
func (m Mat4) Mul(o Mat4) Mat4 {
	var r Mat4
	for c := 0; c < 4; c++ {
		for row := 0; row < 4; row++ {
			var s float64
			for k := 0; k < 4; k++ {
				s += m[k*4+row] * o[c*4+k]
			}
			r[c*4+row] = s
		}
	}
	return r
}

// TransformPoint applies m to the point p (w = 1).
func (m Mat4) TransformPoint(p [3]float64) [3]float64 {
	return [3]float64{
		m[0]*p[0] + m[4]*p[1] + m[8]*p[2] + m[12],
		m[1]*p[0] + m[5]*p[1] + m[9]*p[2] + m[13],
		m[2]*p[0] + m[6]*p[1] + m[10]*p[2] + m[14],
	}
}

// TRS builds T * R * S from a translation, unit quaternion (x, y, z, w) and
// scale.
func TRS(t [3]float64, q [4]float64, s [3]float64) Mat4 {
	x, y, z, w := q[0], q[1], q[2], q[3]
	r00 := 1 - 2*(y*y+z*z)
	r01 := 2 * (x*y - z*w)
	r02 := 2 * (x*z + y*w)
	r10 := 2 * (x*y + z*w)
	r11 := 1 - 2*(x*x+z*z)
	r12 := 2 * (y*z - x*w)
	r20 := 2 * (x*z - y*w)
	r21 := 2 * (y*z + x*w)
	r22 := 1 - 2*(x*x+y*y)
	return Mat4{
		r00 * s[0], r10 * s[0], r20 * s[0], 0,
		r01 * s[1], r11 * s[1], r21 * s[1], 0,
		r02 * s[2], r12 * s[2], r22 * s[2], 0,
		t[0], t[1], t[2], 1,
	}
}

// LocalMatrix returns a node's local transform from matrix or TRS.
func LocalMatrix(n Node) Mat4 {
	if len(n.Matrix) == 16 {
		var m Mat4
		copy(m[:], n.Matrix)
		return m
	}
	t := [3]float64{}
	q := [4]float64{0, 0, 0, 1}
	s := [3]float64{1, 1, 1}
	if len(n.Translation) == 3 {
		copy(t[:], n.Translation)
	}
	if len(n.Rotation) == 4 {
		copy(q[:], n.Rotation)
	}
	if len(n.Scale) == 3 {
		copy(s[:], n.Scale)
	}
	return TRS(t, q, s)
}
