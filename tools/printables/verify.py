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


def verify_briefing(record, request, png, small):
    """Extra request and pixel checks for the two briefing documents."""
    doc_id = record['asset_id']
    if doc_id not in ('network_diagram_laminated', 'work_order'):
        return
    assert record['request_sha256'] == hashlib.sha256(request.encode()).hexdigest(), 'Stale request metadata'
    text = record['outputs'][0]['text']
    section = 'A laminated A4 network diagram' if doc_id == 'network_diagram_laminated' else 'Exact text'
    required = re.findall(r'`([^`]+)`', request.split(section, 1)[1])
    assert set(required).issubset(t['text'] for t in text), 'Missing exact request text'
    for item in text:
        if 'lines' in item:
            assert re.sub(r'\s+', ' ', ' '.join(item['lines'])) == re.sub(r'\s+', ' ', item['text']), 'Wrapped text lost words'
        assert item['cap_height_25_px'] >= 7, 'Undersized text'
    if doc_id == 'network_diagram_laminated':
        by_id = {t['id']: t['text'] for t in text}
        for letter, port in zip('ABCD', ('3', '7', '1', '5')):
            assert by_id['cable_' + letter] == letter and by_id['port_' + letter] == port, 'Incorrect cable mapping'
        # Count actual white runs on each cable, independently of metadata.
        # Test both delivered pixels and the final quarter-size preview.
        for pixels, divisor in ((png, 1), (small, 4)):
            for row, expected in enumerate((1, 2, 3, 0)):
                y = (782 + row * 121) // divisor
                scan = pixels[y, 382//divisor:900//divisor, :3]
                white = np.all(scan > 235, axis=1)
                changes = np.diff(np.pad(white.astype(np.int8), (1, 1)))
                starts, ends = np.flatnonzero(changes == 1), np.flatnonzero(changes == -1)
                assert len(starts) == expected, f'Cable {"ABCD"[row]} stripe count at 1/{divisor}'
                assert np.all(ends-starts >= 24//divisor), 'Stripe too narrow to count'
                assert np.all(starts[1:]-ends[:-1] >= 28//divisor), 'Stripes merged'
        print('PASS exact text/mappings/pixel stripe counts: A=1, B=2, C=3, D=0 at full and 25% size')
    else:
        assert len(text) == len(required) == 10, 'Work order must contain all ten exact strings'
        print('PASS exact text/word wrapping/cap sizes: all ten work-order strings')


def verify_password_clues(record, request):
    """Checks confined to the two password-clue printable requests."""
    doc_id = record['asset_id']
    if doc_id not in ('it_password_policy', 'anniversary_card'):
        return
    assert record['request_sha256'] == hashlib.sha256(request.encode()).hexdigest(), 'Stale request metadata'
    required = []
    for line in request.split('## Acceptance', 1)[0].splitlines():
        if line.startswith('- ') and '`' in line:
            required.extend(line.split('`')[1::2])
    text = record['outputs'][0]['text']
    assert [item['text'] for item in text] == required, 'Display text differs from request order/wording'
    assert len(text) == (9 if doc_id == 'it_password_policy' else 6), 'Missing text fields'
    for item in text:
        assert item['cap_height_25_px'] >= 7.5, 'Undersized quarter-size text'
        if 'lines' in item:
            assert re.sub(r'\s+', ' ', ' '.join(item['lines'])) == re.sub(r'\s+', ' ', item['text']), 'Wrapped text lost words'
    by_id = {item['id']: item for item in text}
    if doc_id == 'it_password_policy':
        symbols = by_id['symbol_rule']
        assert symbols['text'] == '2. One symbol:   !   #   $   %   &   *', 'Symbol order/spacing'
        assert symbols['cap_height_25_px'] >= 11, 'Small symbols'
        assert 'lines' not in symbols, 'Symbol row must remain on one line'
        assert by_id['example']['text'] == 'Example:  Falcon!2016', 'Example punctuation/case/spacing'
    else:
        assert by_id['joined_year']['text'] == 'Mark Reyes - IT - with us since 2019', 'Wrong join year'
        assert by_id['joined_year']['cap_height_25_px'] >= 9.5, 'Small join year'
    print(f'PASS exact text/wrapped words/clue sizes: {doc_id}')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group()
    group.add_argument('--record', action='store_true')
    group.add_argument('--compare', action='store_true')
    parser.add_argument('documents', nargs='*', help='Optional request IDs; defaults to all metadata')
    args = parser.parse_args()
    # Clockmaker metadata is confined to the request's allowed reports lane.
    from verify_clockmaker import IDS, verify as verify_clockmaker
    selected_clockmaker = [doc for doc in args.documents if doc in IDS]
    if not args.documents:
        selected_clockmaker = [doc for doc in IDS if (ROOT / 'assets/reports/printables' / (doc+'.json')).exists()]
    if selected_clockmaker:
        verify_clockmaker(selected_clockmaker, args.record, args.compare)
        if args.documents and len(selected_clockmaker) == len(args.documents):
            return
        args.documents = [doc for doc in args.documents if doc not in IDS]
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
            verify_briefing(record, request, png, small)
            verify_password_clues(record, request)
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
