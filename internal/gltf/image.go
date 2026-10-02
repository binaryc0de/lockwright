package gltf

import (
	"bytes"
	"encoding/binary"
	"errors"
)

var (
	pngSignature  = []byte{0x89, 'P', 'N', 'G', '\r', '\n', 0x1A, '\n'}
	ktx2Signature = []byte{0xAB, 'K', 'T', 'X', ' ', '2', '0', 0xBB, '\r', '\n', 0x1A, '\n'}
)

// ImageSize sniffs PNG, JPEG or KTX2 data and returns its format and pixel
// size without decoding pixels.
func ImageSize(data []byte) (format string, width, height int, err error) {
	switch {
	case bytes.HasPrefix(data, pngSignature):
		w, h, err := pngSize(data)
		return "png", w, h, err
	case len(data) >= 3 && data[0] == 0xFF && data[1] == 0xD8 && data[2] == 0xFF:
		w, h, err := jpegSize(data)
		return "jpeg", w, h, err
	case bytes.HasPrefix(data, ktx2Signature):
		if len(data) < 28 {
			return "ktx2", 0, 0, errors.New("truncated KTX2 header")
		}
		le := binary.LittleEndian
		return "ktx2", int(le.Uint32(data[20:24])), int(le.Uint32(data[24:28])), nil
	default:
		return "", 0, 0, errors.New("unrecognised image format (not PNG, JPEG or KTX2)")
	}
}

func pngSize(data []byte) (int, int, error) {
	// signature(8) + length(4) + "IHDR"(4) + width(4) + height(4)
	if len(data) < 24 || string(data[12:16]) != "IHDR" {
		return 0, 0, errors.New("PNG without a leading IHDR chunk")
	}
	be := binary.BigEndian
	return int(be.Uint32(data[16:20])), int(be.Uint32(data[20:24])), nil
}

func jpegSize(data []byte) (int, int, error) {
	i := 2
	for i < len(data) {
		if data[i] != 0xFF {
			return 0, 0, errors.New("JPEG marker expected")
		}
		for i < len(data) && data[i] == 0xFF {
			i++ // fill bytes
		}
		if i >= len(data) {
			break
		}
		marker := data[i]
		i++
		switch {
		case marker == 0xD8 || marker == 0x01 || (marker >= 0xD0 && marker <= 0xD7):
			continue // standalone markers
		case marker == 0xD9 || marker == 0xDA:
			return 0, 0, errors.New("JPEG has no SOF before scan data")
		}
		if i+2 > len(data) {
			break
		}
		segLen := int(binary.BigEndian.Uint16(data[i : i+2]))
		if segLen < 2 || i+segLen > len(data) {
			return 0, 0, errors.New("truncated JPEG segment")
		}
		if marker >= 0xC0 && marker <= 0xCF && marker != 0xC4 && marker != 0xC8 && marker != 0xCC {
			if segLen < 7 {
				return 0, 0, errors.New("truncated JPEG SOF segment")
			}
			h := int(binary.BigEndian.Uint16(data[i+3 : i+5]))
			w := int(binary.BigEndian.Uint16(data[i+5 : i+7]))
			return w, h, nil
		}
		i += segLen
	}
	return 0, 0, errors.New("JPEG SOF marker not found")
}
