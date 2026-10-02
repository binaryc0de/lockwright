"""Read-only PNG delivery checks and repeat-build checksum comparison.

Run with Blender's bundled python3.13 (does not launch a Blender process).
--record saves an initial checksum manifest; --compare checks a fresh rebuild.
This independently decodes PNGs, including CRC, metadata and alpha checks.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path
import re
import struct
import zlib

import numpy as np

ROOT = Path(__file__).resolve().parents[2]


def read_png(path):
    data = path.read_bytes()
    assert data[:8] == b'\x89PNG\r\n\x1a\n', path
    cursor, chunks, compressed = 8, {}, b''
    while cursor < len(data):
        size = struct.unpack('>I', data[cursor:cursor+4])[0]
        kind, body = data[cursor+4:cursor+8], data[cursor+8:cursor+8+size]
        crc = struct.unpack('>I', data[cursor+8+size:cursor+12+size])[0]
        assert zlib.crc32(kind+body) & 0xffffffff == crc, f'{path}: CRC'
        chunks[kind] = body
        if kind == b'IDAT':
            compressed += body
        cursor += size + 12
    w, h, bits, color, compression, filtering, interlace = struct.unpack('>IIBBBBB', chunks[b'IHDR'])
    assert (bits, color, compression, filtering, interlace) == (8, 6, 0, 0, 0), path
    assert chunks[b'sRGB'] == b'\0' and b'gAMA' in chunks and b'IEND' in chunks, path
    raw = np.frombuffer(zlib.decompress(compressed), dtype=np.uint8).reshape(h, 1+4*w)
    assert np.all(raw[:, 0] == 0), path
    return raw[:, 1:].reshape(h, w, 4)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group()
    group.add_argument('--record', action='store_true')
    group.add_argument('--compare', action='store_true')
    parser.add_argument('documents', nargs='*', help='Optional request IDs; defaults to all metadata')
    args = parser.parse_args()
    hashes = {}
    count = 0
    metadata_dir = ROOT / 'assets/meta/printables'
    metas = sorted(metadata_dir.glob('*.json'))
    if args.documents:
        assert all(re.fullmatch(r'[a-z0-9_]+', name) for name in args.documents), 'Invalid document ID'
        metas = [metadata_dir / (name + '.json') for name in args.documents]
    for meta in metas:
        record = json.loads(meta.read_text())
        request = (ROOT / 'assets/requests/printables' / (record['asset_id'] + '.md')).read_text()
        expected = tuple(map(int, re.search(r'(\d+) x (\d+) px', request).groups()))
        hashes[str(meta.relative_to(ROOT))] = hashlib.sha256(meta.read_bytes()).hexdigest()
        for output in record['outputs']:
            path = ROOT / output['path']
            png = read_png(path)
            h, w = png.shape[:2]
            assert (w, h) == expected == tuple(output['size']), path
            if output['opaque']:
                assert np.all(png[:, :, 3] == 255), path
            else:
                if record['asset_id'] == 'rack_stencil':
                    assert (w, h) == (2048, 683)
                    assert output['text'][0]['text'] == 'RACK 062'
                    assert output['text'][0]['cap_height_px'] == 444
                    assert not np.any(png[:80, :, 3]) and not np.any(png[-60:, :, 3]), 'Paint clipped'
                    assert np.count_nonzero(png[:, :, 3] > 200) > 200000, 'Insufficient readable paint'
                    # Spatial checks independent of text metadata: no smudge
                    # between 0 and 6; six upper-right remains visibly open.
                    assert not np.any(png[119:564, 1419:1433, 3]), '0/6 gap contains paint'
                    assert not np.any(png[218:255, 1634:1645, 3]), '6 upper-right gap closed'
                    assert png[310, 1455, 3] > 200, '6 ascender missing'
                else:
                    assert output['path'].endswith('whiteboard_marker_layer.png'), path
                    x0, x1 = math.ceil(w*.58), math.floor(w*.88)
                    y0, y1 = math.ceil(h*.52), math.floor(h*.80)
                    assert not np.any(png[y0:y1+1, x0:x1+1]), 'Reserved UV interior must have zero RGBA'
                assert np.all(png[:, :, :3][png[:, :, 3] == 0] == 0), 'Transparent texels must have zero RGB'
            preview = ROOT / output['preview']
            small = read_png(preview)
            assert small.shape[:2] == (round(h/4), round(w/4)), preview
            for artifact, key in ((path, 'sha256'), (preview, 'preview_sha256')):
                digest = hashlib.sha256(artifact.read_bytes()).hexdigest()
                assert digest == output[key], artifact
                hashes[str(artifact.relative_to(ROOT))] = digest
            count += 1
            print(f'PASS PNG/CRC/sRGB/dimensions/alpha/preview: {path.name}')
    assert count > 0 and len(hashes) == count * 2 + len(metas), 'Missing or duplicate artifacts'
    baseline_name = '_'.join(args.documents) + '_first_build.sha256.json' if args.documents else 'first_build.sha256.json'
    baseline = ROOT / 'assets/cache/printables' / baseline_name
    if args.record:
        baseline.parent.mkdir(parents=True, exist_ok=True)
        baseline.write_text(json.dumps(hashes, sort_keys=True, indent=2) + '\n')
        print(f'Recorded first build: {len(hashes)} artifact hashes')
    if args.compare:
        previous = json.loads(baseline.read_text())
        assert hashes == previous, f'Rebuild differs: {[p for p in hashes if hashes[p] != previous.get(p)]}'
        print(f'PASS reproducibility: all {count} outputs, {count} previews and {len(metas)} metadata records byte-identical')


if __name__ == '__main__':
    main()
