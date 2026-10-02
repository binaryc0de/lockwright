"""Offline SVG subset rasterizer, run only through Blender's bundled Python.

SVG text comes from request backtick strings; printed glyph outlines come from
Blender's bundled Inter, triangulated then rasterized on CPU. Handwriting is
original stroke geometry. NumPy is bundled with Blender; no pip/system fonts,
render engine, graphics context, network, or external executables are needed.
Supported SVG: rect, ellipse/circle, polygon/polyline, line, text/tspan, groups.
All raster work uses 2x antialiasing. PNGs have deterministic sRGB metadata.
"""
import argparse
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import re
import struct
import sys
import traceback
import xml.etree.ElementTree as ET
import zlib

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
sys.dont_write_bytecode = True
sys.path.insert(0, str(HERE))
from lettering import strokes

spec = importlib.util.spec_from_file_location('printable_surface', HERE / 'overlays/surface.py')
surface = importlib.util.module_from_spec(spec)
spec.loader.exec_module(surface)

DOCUMENTS = {
    'fire_inspection_certificate': [('fire_inspection_certificate', 1536, 2048, 'paper')],
    'wifi_card_front_back': [('wifi_card_front', 1536, 1024, 'laminate'),
                             ('wifi_card_back', 1536, 1024, 'laminate')],
    'sticky_note_username': [('sticky_note_username', 1024, 1024, 'note')],
    'whiteboard_marker_layer': [('whiteboard_marker_layer', 2048, 1262, 'marker')],
    'laptop_screen_login': [('laptop_screen_login', 2048, 1283, 'screen')],
    'rack_stencil': [('rack_stencil', 2048, 683, 'stencil')],
    'network_diagram_laminated': [('network_diagram_laminated', 2048, 1448, 'laminate')],
    'work_order': [('work_order', 1448, 2048, 'paper')],
}
CRITICAL = {
    'fire_inspection_certificate': ['FIRE SAFETY INSPECTION CERTIFICATE', 'SITE 417'],
    'wifi_card_front_back': ['GUEST WiFi', 'Password: Kestrel#2019'],
    'sticky_note_username': ['user: mreyes'],
    'whiteboard_marker_layer': ['Filing cabinet code:', 'UV pen (audit rule!)  -->'],
    'laptop_screen_login': ['Kestrel Intranet', 'Your session has expired. Please sign in again.',
                            'Username', 'Password', 'Sign in', '23:12'],
    'rack_stencil': ['RACK 062'],
    'network_diagram_laminated': ['Kestrel Logistics - site network (rev 7)',
                                 'Cage rack: patch panel P1 -> UPS bypass relay',
                                 'A', '3', 'B', '7', 'C', '1', 'D', '5'],
    'work_order': ['KESTREL LOGISTICS', 'CONTRACTOR WORK ORDER  KL-WO-2026-0417',
                   "Laptop + creds on Mark's desk - good luck! - J."],
}


def rgba(value, opacity=1):
    if value == 'none':
        return np.array([0, 0, 0, 0], dtype=np.float32)
    value = value.lstrip('#')
    return np.array([int(value[i:i+2], 16) / 255 for i in (0, 2, 4)] + [opacity], dtype=np.float32)


def chunk(kind, data):
    return struct.pack('>I', len(data)) + kind + data + struct.pack('>I', zlib.crc32(kind + data) & 0xffffffff)


def write_png(path, pixels):
    h, w, _ = pixels.shape
    raw = b''.join(b'\0' + row.tobytes() for row in pixels)
    payload = (b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', w, h, 8, 6, 0, 0, 0))
               + chunk(b'sRGB', b'\0') + chunk(b'gAMA', struct.pack('>I', 45455))
               + chunk(b'IDAT', zlib.compress(raw, 9)) + chunk(b'IEND', b''))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload)


class Canvas:
    def __init__(self, w, h, transparent=False):
        self.w, self.h, self.scale = w, h, 2
        self.data = np.zeros((h * 2, w * 2, 4), dtype=np.float32)
        self.text = []
        self.transparent = transparent

    def region(self, bounds):
        x0, y0, x1, y1 = bounds
        x0, y0 = max(0, int(math.floor(x0 * 2))), max(0, int(math.floor(y0 * 2)))
        x1, y1 = min(self.w * 2, int(math.ceil(x1 * 2)) + 1), min(self.h * 2, int(math.ceil(y1 * 2)) + 1)
        if x1 <= x0 or y1 <= y0:
            return None
        yy, xx = np.mgrid[y0:y1, x0:x1].astype(np.float32)
        return self.data[y0:y1, x0:x1], (xx + .5) / 2, (yy + .5) / 2

    @staticmethod
    def blend(view, mask, color):
        alpha = mask.astype(np.float32) * color[3]
        a = alpha[:, :, None]
        # Premultiplied-alpha framebuffer: correct antialiasing on transparent ink.
        view[:, :, :3] = color[:3] * a + view[:, :, :3] * (1 - a)
        view[:, :, 3] = alpha + view[:, :, 3] * (1 - alpha)

    def polygon(self, points, color):
        if color[3] == 0:
            return
        points = np.asarray(points)
        region = self.region((*points.min(axis=0), *points.max(axis=0)))
        if region is None:
            return
        view, xx, yy = region
        mask = np.zeros(xx.shape, dtype=bool)
        for i, (x1, y1) in enumerate(points):
            x2, y2 = points[i-1]
            if y1 != y2:
                mask ^= ((y1 > yy) != (y2 > yy)) & (xx < (x2-x1) * (yy-y1) / (y2-y1) + x1)
        self.blend(view, mask, color)

    def line(self, a, b, width, color):
        ax, ay = a
        bx, by = b
        r = width / 2
        region = self.region((min(ax, bx)-r, min(ay, by)-r, max(ax, bx)+r, max(ay, by)+r))
        if region is None:
            return
        view, xx, yy = region
        denom = (bx-ax)**2 + (by-ay)**2
        t = np.clip(((xx-ax)*(bx-ax) + (yy-ay)*(by-ay)) / max(denom, 1e-9), 0, 1)
        self.blend(view, (xx-ax-t*(bx-ax))**2 + (yy-ay-t*(by-ay))**2 <= r*r, color)

    def polyline(self, points, width, color, seed=0):
        for i in range(len(points)-1):
            self.line(points[i], points[i+1], width * (1 + .055 * math.sin(i * .73 + seed)), color)

    def rect(self, x, y, w, h, radius, fill, stroke, sw):
        r = min(radius, w / 2, h / 2)
        points = []
        for cx, cy, start in ((x+w-r, y+r, -math.pi/2), (x+w-r, y+h-r, 0),
                              (x+r, y+h-r, math.pi/2), (x+r, y+r, math.pi)):
            for i in range(13):
                angle = start + i * math.pi / 24
                points.append((cx+r*math.cos(angle), cy+r*math.sin(angle)))
        self.polygon(points, fill)
        if stroke[3]:
            self.polyline(points + [points[0]], sw, stroke)

    def ellipse(self, cx, cy, rx, ry, fill, stroke, sw):
        points = [(cx+rx*math.cos(i*math.tau/120), cy+ry*math.sin(i*math.tau/120)) for i in range(120)]
        self.polygon(points, fill)
        if stroke[3]:
            self.polyline(points + [points[0]], sw, stroke)

    def pixels(self):
        # Box filter premultiplied RGB and alpha, then unpremultiply once.
        data = self.data.reshape(self.h, 2, self.w, 2, 4).mean(axis=(1, 3))
        data[:, :, :3] /= np.maximum(data[:, :, 3:4], 1e-8)
        return np.rint(np.clip(data, 0, 1) * 255).astype(np.uint8)


FONT_CACHE = {}
FONT_INPUT = None


def font_mesh(text):
    import bpy
    global FONT_INPUT
    if FONT_INPUT is None:
        bundled = Path(bpy.app.binary_path).resolve().parent / '5.2/datafiles/fonts/Inter.woff2'
        if not bundled.is_file():
            raise RuntimeError('Expected Blender-bundled Inter.woff2; system fonts are not permitted')
        FONT_INPUT = bpy.data.fonts.load(str(bundled), check_existing=True)
    if text not in FONT_CACHE:
        curve = bpy.data.curves.new('printable_inter', 'FONT')
        curve.font = FONT_INPUT
        curve.body, curve.size, curve.resolution_u = text, 1, 12
        obj = bpy.data.objects.new('printable_inter', curve)
        bpy.context.collection.objects.link(obj)
        graph = bpy.context.evaluated_depsgraph_get()
        mesh = bpy.data.meshes.new_from_object(obj.evaluated_get(graph))
        mesh.calc_loop_triangles()
        vertices = np.array([(v.co.x, v.co.y) for v in mesh.vertices])
        tris = [tuple(tri.vertices) for tri in mesh.loop_triangles]
        FONT_CACHE[text] = (vertices, tris)
        bpy.data.objects.remove(obj, do_unlink=True)
        bpy.data.curves.remove(curve)
        bpy.data.meshes.remove(mesh)
    return FONT_CACHE[text]


def draw_text(canvas, node, text, seed):
    a = node.attrib
    if a.get('data-wrap') == 'words':
        # Opt-in wrapping preserves request strings and cap height, rather
        # than squeezing long briefing paragraphs into an unreadable line.
        size = float(a.get('font-size', '48'))
        maximum = float(a['data-width'])
        def measure(value):
            if a.get('data-lettering') == 'stroke':
                return strokes(value, size, seed)[1]
            vertices, _ = font_mesh(value)
            caps, _ = font_mesh('H')
            return (vertices[:, 0].max() - min(0, vertices[:, 0].min())) * size / caps[:, 1].max()
        lines, current = [], ''
        for token in re.findall(r'\S+\s*', text):
            candidate = current + token
            if current and measure(candidate.rstrip()) > maximum:
                lines.append(current.rstrip())
                current = token
            else:
                current = candidate
        if current:
            lines.append(current.rstrip())
        start = len(canvas.text)
        leading = float(a.get('data-leading', str(size * 1.5)))
        for index, line in enumerate(lines):
            assert measure(line) <= maximum, f'Unbreakable text: {line}'
            copy = ET.fromstring(ET.tostring(node))
            del copy.attrib['data-wrap']
            copy.attrib['y'] = str(float(a['y']) + index * leading)
            draw_text(canvas, copy, line, seed + index * 97)
        records = canvas.text[start:]
        if a.get('data-height'):
            assert size + (len(lines)-1)*leading <= float(a['data-height']), f'Text exceeds reserved field: {text}'
        canvas.text[start:] = [{**records[0], 'text': text, 'lines': lines,
                               'width_px': max(r['width_px'] for r in records),
                               'line_baselines_px': [float(a['y'])+i*leading for i in range(len(lines))]}]
        return
    x, baseline, size = [float(a.get(key, default)) for key, default in (('x', '0'), ('y', '0'), ('font-size', '48'))]
    color = rgba(a.get('fill', '#222222'), float(a.get('opacity', '1')))
    maximum = float(a.get('data-width', str(canvas.w)))
    if a.get('data-lettering') == 'stencil':
        from rack_stencil import draw
        width = draw(canvas, text, x, baseline, size, maximum, color)
        factor, cap = 1, size
    elif a.get('data-lettering') == 'stroke':
        geometry, width = strokes(text, size, seed, float(a.get('data-slant', '.10')))
        factor = min(1, maximum / width)
        offset = width * factor / 2 if a.get('text-anchor') == 'middle' else 0
        penwidth = float(a.get('stroke-width', str(size * .045)))
        arrow_start = min(px for path in geometry[-3:] for px, _ in path) if a.get('data-arrow-tip') else 0
        arrow_end = max(px for path in geometry[-3:] for px, _ in path) if a.get('data-arrow-tip') else 1
        for i, path in enumerate(geometry):
            is_arrow = a.get('data-arrow-ink') and i >= len(geometry)-3
            ink = rgba(a['data-arrow-ink']) if is_arrow else color
            points = [(x + px * factor - offset, baseline-size+py) for px, py in path]
            if is_arrow and a.get('data-arrow-tip'):
                start = x + arrow_start * factor - offset
                extent = float(a['data-arrow-tip']) - start
                points = [(start + (px-arrow_start)/(arrow_end-arrow_start)*extent, baseline-size+py) for px, py in path]
            canvas.polyline(points, penwidth, ink, seed + i)
        cap = size
    else:
        vertices, tris = font_mesh(text)
        # Calibrate actual cap height from the bundled font's H outline.
        cap_vertices, _ = font_mesh('H')
        cap_unit = cap_vertices[:, 1].max()
        vertices = vertices.copy() * (size / cap_unit)
        width = vertices[:, 0].max() - min(0, vertices[:, 0].min())
        factor = min(1, maximum / width)
        offset = width * factor / 2 if a.get('text-anchor') == 'middle' else 0
        vertices[:, 0] = x + vertices[:, 0] * factor - offset
        vertices[:, 1] = baseline - vertices[:, 1]
        for tri in tris:
            canvas.polygon(vertices[list(tri)], color)
        # Faux bold via a tiny second impression, without altering letter spacing.
        if a.get('font-weight') == 'bold':
            vertices[:, 0] += size * .018
            for tri in tris:
                canvas.polygon(vertices[list(tri)], color)
        cap = size
    canvas.text.append({'id': next(iter(node), node).get('id'), 'text': text,
                        'cap_height_px': cap, 'width_px': width * factor,
                        'cap_height_25_px': cap / 4})


def render_nodes(canvas, nodes, strings, page, seed):
    for index, node in enumerate(nodes):
        tag = node.tag.split('}')[-1]
        a = node.attrib
        if a.get('data-page') and a['data-page'] != page:
            continue
        color = rgba(a.get('fill', '#000000'), float(a.get('opacity', '1')))
        stroke = rgba(a.get('stroke', 'none'), float(a.get('opacity', '1')))
        sw = float(a.get('stroke-width', '2'))
        f = lambda key, default=0: float(a.get(key, default))
        if tag == 'g':
            render_nodes(canvas, list(node), strings, page, seed + index * 7)
        elif tag == 'text':
            content = ''.join(node.itertext()).strip()
            found = re.fullmatch(r'\{\{(\d+)\}\}', content)
            content = strings[int(found[1])] if found else content
            draw_text(canvas, node, content, seed + index * 97)
        elif tag == 'rect':
            canvas.rect(f('x'), f('y'), f('width'), f('height'), f('rx'), color, stroke, sw)
        elif tag in ('circle', 'ellipse'):
            canvas.ellipse(f('cx'), f('cy'), f('r') if tag == 'circle' else f('rx'),
                           f('r') if tag == 'circle' else f('ry'), color, stroke, sw)
        elif tag in ('polyline', 'polygon'):
            points = [tuple(map(float, p.split(','))) for p in a['points'].split()]
            if tag == 'polygon':
                canvas.polygon(points, color)
                points += [points[0]]
            canvas.polyline(points, sw, stroke)
        elif tag == 'line':
            canvas.line((f('x1'), f('y1')), (f('x2'), f('y2')), sw, stroke)
        else:
            raise ValueError(f'Unsupported SVG tag: {tag}')


def request_strings(doc_id):
    request = (ROOT / 'assets/requests/printables' / (doc_id + '.md')).read_text()
    if doc_id == 'whiteboard_marker_layer':
        strings = re.search(r'```\n(.*?)\n```', request, re.S)[1].splitlines()
    else:
        # Backticks also mark paths/node names; exact display text is identified
        # by the list or the screen request's semantic labels.
        strings = re.findall(r'^- (?:small: )?`([^`]+)`', request, re.M)
        if doc_id == 'laptop_screen_login':
            strings = re.findall(r'`([^`]+)`', request)[2:]
        elif doc_id == 'rack_stencil':
            strings = re.findall(r'`(RACK \d{3})`', request)
        elif doc_id == 'network_diagram_laminated':
            strings = re.findall(r'`([^`]+)`', request.split('A laminated A4 network diagram', 1)[1])
        elif doc_id == 'work_order':
            strings = re.findall(r'`([^`]+)`', request.split('Exact text', 1)[1])
    return strings


def preview(pixels):
    h, w = pixels.shape[:2]
    # Nearest quarter size, including non-multiple-of-four request dimensions.
    oh, ow = round(h / 4), round(w / 4)
    data = pixels.astype(np.float32) / 255
    data[:, :, :3] *= data[:, :, 3:4]
    rows = np.array_split(np.arange(h), oh)
    cols = np.array_split(np.arange(w), ow)
    data = np.stack([data[r].mean(axis=0) for r in rows])
    data = np.stack([data[:, c].mean(axis=1) for c in cols], axis=1)
    data[:, :, :3] /= np.maximum(data[:, :, 3:4], 1e-8)
    return np.rint(np.clip(data, 0, 1) * 255).astype(np.uint8)


def on_white(pixels):
    data = pixels.astype(np.float32) / 255
    alpha = data[:, :, 3:4]
    data[:, :, :3] = data[:, :, :3] * alpha + .97 * (1 - alpha)
    data[:, :, 3] = 1
    return np.rint(data * 255).astype(np.uint8)


def on_black_plate(pixels):
    """Review backing only; the delivered stencil contains paint and no plate."""
    data = pixels.astype(np.float32) / 255
    alpha = data[:, :, 3:4]
    data[:, :, :3] = data[:, :, :3] * alpha + .035 * (1 - alpha)
    data[:, :, 3] = 1
    return np.rint(data * 255).astype(np.uint8)


def source_hash():
    paths = sorted(p for p in HERE.rglob('*') if p.suffix in ('.py', '.svg', '.sh') and '__pycache__' not in p.parts)
    digest = hashlib.sha256()
    for path in paths:
        digest.update(str(path.relative_to(HERE)).encode())
        digest.update(path.read_bytes())
    return digest.hexdigest()


def build(doc_id):
    import bpy
    strings = request_strings(doc_id)
    template = ET.parse(HERE / 'templates' / (doc_id + '.svg')).getroot()
    records, all_text = [], []
    for index, (page, w, h, kind) in enumerate(DOCUMENTS[doc_id]):
        canvas = Canvas(w, h, kind in ('marker', 'stencil'))
        render_nodes(canvas, list(template), strings, page, 417 + index)
        if kind == 'stencil':
            from rack_stencil import apply_wear
            apply_wear(canvas, 62)
        else:
            surface.apply(canvas.data, kind, 2019 + index)
        pixels = canvas.pixels()
        if kind == 'stencil':
            # Faint spray can quantize to zero alpha; remove its hidden RGB.
            pixels[pixels[:, :, 3] == 0] = 0
            assert np.all(pixels[:, :, :3][pixels[:, :, 3] == 0] == 0), 'Blank stencil texels must have zero RGB'
            assert not np.any(pixels[:80, :, 3]) and not np.any(pixels[-60:, :, 3]), 'Stencil clipped'
        elif kind != 'marker':
            assert np.all(pixels[:, :, 3] == 255), f'{page}: must be opaque'
        else:
            # Keep the whole UV placement interior mathematically empty; ink
            # border sits outside these limits, including antialiasing footprint.
            x0, x1 = math.ceil(.58*w), math.floor(.88*w)
            y0, y1 = math.ceil(.52*h), math.floor(.80*h)
            assert not np.any(pixels[y0:y1+1, x0:x1+1, 3]), 'UV rectangle interior contains ink'
        out = ROOT / 'game/rooms/night_shift/assets/docs' / (page + '.png')
        small = ROOT / 'assets/previews/printables' / (page + '_25.png')
        write_png(out, pixels)
        review_pixels = on_black_plate(pixels) if kind == 'stencil' else on_white(pixels) if kind == 'marker' else pixels
        write_png(small, preview(review_pixels))
        if kind == 'marker':
            write_png(ROOT / 'assets/cache/printables' / (page + '_on_white.png'), review_pixels)
        elif kind == 'stencil':
            write_png(ROOT / 'assets/cache/printables' / (page + '_on_black.png'), review_pixels)
        text = [t['text'] for t in canvas.text]
        all_text.extend(text)
        records.append({'path': str(out.relative_to(ROOT)), 'size': [w, h], 'color_space': 'sRGB',
                        'rgba': True, 'opaque': kind not in ('marker', 'stencil'),
                        'sha256': hashlib.sha256(out.read_bytes()).hexdigest(),
                        'preview': str(small.relative_to(ROOT)),
                        'preview_background': 'black blanking plate for legibility' if kind == 'stencil' else 'white enamel for legibility' if kind == 'marker' else 'document',
                        'preview_sha256': hashlib.sha256(small.read_bytes()).hexdigest(),
                        'text': canvas.text})
        print(f'BUILT {page}: {w}x{h}, {len(text)} text lines', flush=True)
    assert set(strings).issubset(all_text), f'{doc_id}: missing request text: {set(strings) - set(all_text)}'
    assert set(CRITICAL[doc_id]).issubset(all_text), f'{doc_id}: missing critical text'
    metadata = {'asset_id': doc_id, 'blender_version': bpy.app.version_string, 'source_sha256': source_hash(),
                'request_sha256': hashlib.sha256((ROOT / 'assets/requests/printables' / (doc_id+'.md')).read_bytes()).hexdigest(),
                'renderer': 'CPU SVG rasterizer; Blender-bundled Inter outlines / original stroke alphabet; 2x AA',
                'printed_font': 'Blender 5.2 bundled Inter.woff2 (OFL-1.1)',
                'seed': 417, 'outputs': records}
    if doc_id == 'rack_stencil':
        metadata.update(renderer='CPU SVG rasterizer; original polygon stencil lettering; 2x AA',
                        printed_font='none; original drawn stencil contours', wear_seed=62,
                        physical_size_m=[.42, .14])
    meta = ROOT / 'assets/meta/printables' / (doc_id + '.json')
    meta.parent.mkdir(parents=True, exist_ok=True)
    meta.write_text(json.dumps(metadata, indent=2, sort_keys=True) + '\n')


def main():
    import bpy
    if not bpy.app.background or bpy.app.version[:2] != (5, 2):
        raise RuntimeError('Run using Blender 5.2.x headless')
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('documents', nargs='*', choices=list(DOCUMENTS))
    args = parser.parse_args(sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else [])
    for doc_id in args.documents or DOCUMENTS:
        build(doc_id)


if __name__ == '__main__':
    status = 0
    try:
        main()
    except SystemExit as exc:
        status = exc.code if isinstance(exc.code, int) else 1
    except BaseException:
        traceback.print_exc()
        status = 1
    sys.stdout.flush()
    sys.stderr.flush()
    # Same shutdown hygiene as tools/blender/common/cli.py.
    os._exit(status)
