"""KESTREL KP-4: deterministic wall-mounted, independently pressable keypad.

Run: blender -b --threads 4 -noaudio --python-exit-code 1 --python
     tools/blender/props/keypad_4.py -- --out game/assets/core/props
No downloads, fonts, UI, GPU compute, or external Python dependencies.
"""
from array import array
import math
from pathlib import Path
import random
import sys

import bpy

sys.dont_write_bytecode = True
TOOLS = Path(__file__).resolve().parents[1]
ROOT = TOOLS.parents[1]
sys.path.insert(0, str(TOOLS))

from common.export import export_glb, write_metadata
from common.cli import run_cli
from common.geometry import active, box, join_static, mesh_object, triangulate, uv_front
from common.materials import base_texture, image_from_pixels, material, normal_texture, orm_texture
from common.preview import render_previews
from common.scene import reset_scene

ASSET_ID = 'keypad_4'
SEED = 4026

# Original rounded stroke alphabet. Coordinates have a 0.60 x 1 em cell;
# rasterising these paths avoids a dependency on host or bundled font files.
GLYPHS = {
    '0': [[(.13, 0), (.47, 0), (.60, .17), (.60, .83), (.47, 1), (.13, 1), (0, .83), (0, .17), (.13, 0)]],
    '1': [[(.08, .78), (.30, 1), (.30, 0)], [(.08, 0), (.53, 0)]],
    '2': [[(0, .82), (.13, 1), (.47, 1), (.60, .82), (.60, .66), (0, .10), (0, 0), (.60, 0)]],
    '3': [[(0, .93), (.15, 1), (.47, 1), (.60, .85), (.60, .65), (.44, .50), (.22, .50)], [(.44, .50), (.60, .35), (.60, .15), (.47, 0), (.15, 0), (0, .07)]],
    '4': [[(.46, 0), (.46, 1), (0, .32), (.60, .32)]],
    '5': [[(.60, 1), (0, 1), (0, .55), (.44, .55), (.60, .39), (.60, .15), (.45, 0), (.13, 0), (0, .10)]],
    '6': [[(.55, .92), (.40, 1), (.17, 1), (0, .79), (0, .17), (.15, 0), (.45, 0), (.60, .17), (.60, .40), (.45, .55), (.15, .55), (0, .40)]],
    '7': [[(0, 1), (.60, 1), (.17, 0)]],
    '8': [[(.15, .50), (0, .67), (0, .85), (.15, 1), (.45, 1), (.60, .85), (.60, .67), (.45, .50), (.15, .50), (0, .33), (0, .15), (.15, 0), (.45, 0), (.60, .15), (.60, .33), (.45, .50)]],
    '9': [[(.05, .08), (.20, 0), (.43, 0), (.60, .21), (.60, .83), (.45, 1), (.15, 1), (0, .83), (0, .60), (.15, .45), (.45, .45), (.60, .60)]],
    'C': [[(.60, .89), (.45, 1), (.15, 1), (0, .80), (0, .20), (.15, 0), (.45, 0), (.60, .11)]],
    'L': [[(0, 1), (0, 0), (.60, 0)]],
    'R': [[(0, 0), (0, 1), (.43, 1), (.60, .85), (.60, .65), (.43, .50), (0, .50)], [(.30, .50), (.60, 0)]],
    'E': [[(.60, 1), (0, 1), (0, 0), (.60, 0)], [(0, .50), (.47, .50)]],
    'N': [[(0, 0), (0, 1), (.60, 0), (.60, 1)]],
    'T': [[(0, 1), (.60, 1)], [(.30, 1), (.30, 0)]],
    'K': [[(0, 0), (0, 1)], [(.60, 1), (0, .43), (.60, 0)]],
    'S': [[(.60, .90), (.46, 1), (.14, 1), (0, .83), (0, .67), (.15, .54), (.45, .46), (.60, .33), (.60, .17), (.46, 0), (.14, 0), (0, .10)]],
    'U': [[(0, 1), (0, .17), (.15, 0), (.45, 0), (.60, .17), (.60, 1)]],
    'P': [[(0, 0), (0, 1), (.43, 1), (.60, .85), (.60, .65), (.43, .50), (0, .50)]],
    '-': [[(.05, .5), (.55, .5)]],
}


def draw_text(pixels, size, text, center, height, color, stroke=.12, x_scale=1):
    """Analytic antialiasing around line segments, all in deterministic Python."""
    advance = .82 * height * x_scale
    width = advance * len(text) - .22 * height * x_scale
    left = center[0] - width / 2
    bottom = center[1] - height / 2
    radius = stroke * height / 2
    segments = []
    for index, char in enumerate(text):
        if char == ' ':
            continue
        for path in GLYPHS[char]:
            for a, b in zip(path, path[1:]):
                segments.append((left + index * advance + a[0] * height * x_scale, bottom + a[1] * height,
                                 left + index * advance + b[0] * height * x_scale, bottom + b[1] * height))
    # Accumulate coverage first; overlapping strokes remain the same opacity.
    coverage = {}
    for ax, ay, bx, by in segments:
        dx, dy = bx - ax, by - ay
        length_sq = dx * dx + dy * dy
        for y in range(max(0, math.floor(min(ay, by) - radius - 1)), min(size, math.ceil(max(ay, by) + radius + 1))):
            for x in range(max(0, math.floor(min(ax, bx) - radius - 1)), min(size, math.ceil(max(ax, bx) + radius + 1))):
                t = max(0, min(1, ((x + .5 - ax) * dx + (y + .5 - ay) * dy) / length_sq))
                distance = math.hypot(x + .5 - ax - t * dx, y + .5 - ay - t * dy)
                alpha = max(0, min(1, radius + .5 - distance))
                if alpha:
                    index = (y * size + x) * 4
                    coverage[index] = max(coverage.get(index, 0), alpha)
    for index, alpha in coverage.items():
        for channel in range(3):
            pixels[index + channel] = pixels[index + channel] * (1 - alpha) + color[channel] * alpha


def make_textures(cache):
    size = 1024
    atlas = array('f', [.007, .008, .010, 1]) * (size * size)
    legends = ['1', '2', '3', '4', '5', '6', '7', '8', '9', 'CLR', '0', 'ENT']
    rectangles = {}
    for index, legend in enumerate(legends):
        column, row = index % 4, index // 4
        # 16 pixels of safe padding per cell, including minification.
        x0, y0 = column * 256 + 16, row * 256 + 16
        span = 224
        height = span * (.0035 if len(legend) > 1 else .006) / .013
        draw_text(atlas, size, legend, (x0 + span / 2, y0 + span / 2), height, (.95, .96, .95), stroke=.13, x_scale=.013 / .016)
        rectangles[legend] = (x0 / size, y0 / size, (x0 + span) / size, (y0 + span) / size)
    legend_image = image_from_pixels(ASSET_ID, 'legend_atlas', size, atlas, cache)

    # A non-overlapping box atlas: front is the lower-left half, other faces
    # are packed in small rectangles in the upper half by body_uv().
    size = 1024
    face_size = size // 2
    rng = random.Random(SEED)
    color = array('f')
    orm = array('f')
    normal = array('f')
    for y in range(size):
        for x in range(size):
            variation = rng.uniform(-.004, .004)
            # Light polish on the front perimeter; no heavy wear or dirt.
            edge = min(x, face_size - x, y, face_size - y) if x < face_size and y < face_size else 20
            polish = max(0, 1 - edge / 12) * .015
            base = .060 + variation + polish
            color.extend((base, base * 1.025, base * 1.055, 1))
            orm.extend((1, .57 - polish * 2 + variation, .78, 1))
            normal.extend((.5 + variation * .18, .5 + variation * .18, 1, 1))
    text_center = (face_size / 2, face_size * (.5 - .050 / .115))
    draw_text(color, size, 'KESTREL SECURE KP-4', text_center, face_size * .002 / .115,
              (.12, .125, .13), stroke=.12, x_scale=.115 / .075)
    # Extremely faint grime halo on the plate beside frequently used keys.
    for key_x, key_z in ((.020, .011), (.020, -.005), (.020, -.021), (0, -.037)):
        for y in range(face_size):
            z = (y / face_size - .5) * .115
            if abs(z - key_z) > .009:
                continue
            for x in range(face_size):
                xx = (.5 - x / face_size) * .075
                distance = max(abs(xx - key_x) / .009, abs(z - key_z) / .0075)
                if .94 < distance < 1.14:
                    index = (y * size + x) * 4
                    fade = 1 - .018 * (1 - abs(distance - 1.04) / .10)
                    for channel in range(3):
                        color[index + channel] *= fade
    return rectangles, {
        'legend_atlas': legend_image,
        'body_base_color': image_from_pixels(ASSET_ID, 'body_base_color', size, color, cache),
        'body_orm': image_from_pixels(ASSET_ID, 'body_orm', size, orm, cache, non_color=True),
        'body_normal': image_from_pixels(ASSET_ID, 'body_normal', size, normal, cache, non_color=True),
    }


def body_uv(obj):
    uv = obj.data.uv_layers.new(name='UVMap')
    def primary(face):
        n, c = face.normal, face.center
        return ((abs(n.y) > .999 and abs(c.y) > .0059)
                or (abs(n.x) > .999 and abs(c.x) > .0374)
                or (abs(n.z) > .999 and abs(c.z) > .0574))
    small_faces = [face.index for face in obj.data.polygons if not primary(face)]
    columns = max(1, math.ceil(math.sqrt(len(small_faces))))
    small_slots = {index: slot for slot, index in enumerate(small_faces)}
    # Main faces get distinct atlas islands; bevel strips use a reserved area.
    for face in obj.data.polygons:
        n = face.normal
        if face.index not in small_slots and n.y > .999:
            rect, axes, sizes, flip = (0, 0, .5, .5), (0, 2), (.075, .115), True
        elif face.index not in small_slots and n.y < -.999:
            rect, axes, sizes, flip = (.52, 0, 1, .48), (0, 2), (.075, .115), False
        elif face.index not in small_slots and n.x > .999:
            rect, axes, sizes, flip = (0, .52, .2, .98), (1, 2), (.012, .115), False
        elif face.index not in small_slots and n.x < -.999:
            rect, axes, sizes, flip = (.22, .52, .42, .98), (1, 2), (.012, .115), True
        elif face.index not in small_slots and n.z > .999:
            rect, axes, sizes, flip = (.44, .52, .98, .64), (0, 1), (.075, .012), False
        elif face.index not in small_slots and n.z < -.999:
            rect, axes, sizes, flip = (.44, .66, .98, .78), (0, 1), (.075, .012), False
        else:
            # Every bevel and internal recess polygon has its own island.
            slot = small_slots[face.index]
            column, row = slot % columns, slot // columns
            u, v = .45 + column * .53 / columns, .82 + row * .16 / columns
            rect = (u + .001, v + .001, u + .53 / columns - .001, v + .16 / columns - .001)
            dominant = max(range(3), key=lambda index: abs(n[index]))
            axes = tuple(index for index in range(3) if index != dominant)
            coords = [obj.data.vertices[index].co for index in face.vertices]
            bounds = [(min(vertex[axis] for vertex in coords), max(vertex[axis] for vertex in coords)) for axis in axes]
            for loop in face.loop_indices:
                vertex = obj.data.vertices[obj.data.loops[loop].vertex_index].co
                values = [(vertex[axis] - lo) / max(hi - lo, 1e-10) for axis, (lo, hi) in zip(axes, bounds)]
                uv.data[loop].uv = (rect[0] + values[0] * (rect[2] - rect[0]), rect[1] + values[1] * (rect[3] - rect[1]))
            continue
        for loop in face.loop_indices:
            v = obj.data.vertices[obj.data.loops[loop].vertex_index].co
            a, b = .5 + v[axes[0]] / sizes[0], .5 + v[axes[1]] / sizes[1]
            if flip:
                a = 1 - a
            uv.data[loop].uv = (rect[0] + a * (rect[2] - rect[0]), rect[1] + b * (rect[3] - rect[1]))


def screw(name, x, z, mat):
    count = 48
    vertices = []
    # Front head bevel, real six-lobed recessed socket, closed back.
    for ring in range(5):
        for index in range(count):
            angle = index * math.tau / count
            if ring < 2:
                radius, depth = ((.0023, .0156), (.0021, .0164))[ring]
            else:
                radius = .00083 * (1 + .22 * math.cos(6 * angle))
                depth = (.0164, .01575, .0155)[ring - 2]
            vertices.append((x + math.cos(angle) * radius, depth, z + math.sin(angle) * radius))
    faces = []
    for ring in range(4):
        for i in range(count):
            j = (i + 1) % count
            faces.append((ring * count + i, ring * count + j, (ring + 1) * count + j, (ring + 1) * count + i))
    faces.extend((tuple(reversed(range(count))), tuple(range(4 * count, 5 * count))))
    obj = mesh_object(name, vertices, faces, mat)
    uv_front(obj, (.84, .84, .90, .90))
    return obj


def led_dome(mat):
    count, rings = 32, 8
    vertices = [(0, .002, 0)]
    for ring in range(1, rings + 1):
        theta = math.pi / 2 * ring / rings
        for i in range(count):
            angle = math.tau * i / count
            vertices.append((.002 * math.sin(theta) * math.cos(angle),
                             .002 * math.cos(theta), .002 * math.sin(theta) * math.sin(angle)))
    faces = [(0, 1 + i, 1 + (i + 1) % count) for i in range(count)]
    for ring in range(rings - 1):
        a, b = 1 + ring * count, 1 + (ring + 1) * count
        for i in range(count):
            j = (i + 1) % count
            faces.append((a + i, b + i, b + j, a + j))
    faces.append(tuple(reversed(range(1 + (rings - 1) * count, 1 + rings * count))))
    obj = mesh_object('led_status', vertices, faces, mat, (-.026, .016, .048))
    for face in obj.data.polygons:
        face.use_smooth = len(face.vertices) < count
    return obj


def build(out_dir):
    reset_scene(SEED)
    cache = ROOT / 'assets/cache' / ASSET_ID
    rectangles, images = make_textures(cache)
    body_mat = material(ASSET_ID, 'body', (.055, .060, .065), metallic=.78, roughness=.57)
    base_texture(body_mat, images['body_base_color'])
    orm_texture(body_mat, images['body_orm'])
    normal_texture(body_mat, images['body_normal'], strength=.25)
    key_mat = material(ASSET_ID, 'key', (.008, .010, .012), roughness=.74)
    base_texture(key_mat, images['legend_atlas'])
    screen_mat = material(ASSET_ID, 'screen', (.003, .006, .008), metallic=0, roughness=.29)
    led_mat = material(ASSET_ID, 'led', (.85, .85, .85), roughness=.22, emission=((1, 1, 1), .65))
    screw_mat = material(ASSET_ID, 'screw', (.16, .17, .18), metallic=.9, roughness=.30)

    # Rear plinth: 4 mm. Cast front housing: 12 mm. Key caps: 6 mm.
    housing = box('housing', (.075, .012, .115), body_mat, (0, .010, 0), bevel=.0016, segments=4)
    cutter = box('display_cut-noimp', (.052, .007, .016), None, (0, .0165, .032), bevel=.0008, segments=3)
    active(housing)
    cut = housing.modifiers.new('display_recess', 'BOOLEAN')
    cut.operation = 'DIFFERENCE'
    cut.solver = 'EXACT'
    cut.object = cutter
    bpy.ops.object.modifier_apply(modifier=cut.name)
    bpy.data.objects.remove(cutter, do_unlink=True)
    body_uv(housing)
    plinth = box('rear_plinth', (.070, .004, .110), key_mat, (0, .002, 0), bevel=.0005)
    uv_front(plinth, (.84, .84, .90, .90), (.84, .84, .90, .90))
    static = [housing, plinth]
    for i, (x, z) in enumerate(((-.031, -.051), (.031, -.051), (-.031, .051), (.031, .051))):
        static.append(screw(f'screw_{i}', x, z, screw_mat))
    # Socket lip sits inside the true housing recess, window 1 mm behind face.
    recess = box('screen_socket', (.0518, .003, .0158), key_mat, (0, .0133, .032), bevel=.00065)
    uv_front(recess, (.84, .84, .90, .90), (.84, .84, .90, .90))
    static.append(recess)
    body = join_static(static, 'body')
    screen = box('screen', (.050, .0008, .014), screen_mat, (0, .0146, .032), bevel=.00035)
    led = led_dome(led_mat)
    objects = [body, screen, led]
    layout = [['1', '2', '3'], ['4', '5', '6'], ['7', '8', '9'], ['CLR', '0', 'ENT']]
    key_origins = {}
    for row, legends in enumerate(layout):
        for column, legend in enumerate(legends):
            name = 'btn_clear' if legend == 'CLR' else 'btn_enter' if legend == 'ENT' else f'btn_{legend}'
            x, z = .020 - column * .020, .011 - row * .016
            key = box(name, (.016, .006, .013), key_mat, (x, .016, z), bevel=.0009, segments=3)
            uv_front(key, rectangles[legend], (.84, .84, .90, .90), width=.016, height=.013)
            # Origin is at the base of each key, while front face sits at +6 mm.
            for vertex in key.data.vertices:
                vertex.co.y += .003
            objects.append(key)
            key_origins[name] = [round(x, 9), round(z, 9), -.016]
    collision = box('body-colonly', (.075, .022, .115), None, (0, .011, 0))
    # Collision's object origin is the shared mounting plane centre, too.
    for vertex in collision.data.vertices:
        vertex.co.y += .011
    collision.location.y = 0
    objects.append(collision)
    for obj in objects:
        triangulate(obj)
    bpy.context.view_layer.update()
    out = Path(out_dir).resolve()
    glb_path = out / f'{ASSET_ID}.glb'
    gltf = export_glb(glb_path, objects)
    for node in gltf['nodes']:
        if node.get('scale', [1, 1, 1]) != [1, 1, 1] or node.get('rotation', [0, 0, 0, 1]) != [0, 0, 0, 1]:
            raise RuntimeError(f'Unapplied exported transform: {node["name"]}')
        if node['name'] in key_origins:
            if any(abs(a - b) > 1e-7 for a, b in zip(node.get('translation', [0, 0, 0]), key_origins[node['name']])):
                raise RuntimeError(f'Wrong exported key origin: {node["name"]}')
    textures = [{'name': image.name, 'size': list(image.size), 'map': name, 'embedded': True}
                for name, image in sorted(images.items())]
    meta = write_metadata(
        ASSET_ID, ROOT / 'assets/meta' / f'{ASSET_ID}.json', glb_path, objects,
        Path(__file__), textures, origin='mount_plane_center', extra={
            'forward': 'Blender +Y -> Godot -Z',
            'key_origins_godot_m': key_origins,
            'collision': {'part': 'body-colonly', 'shape': 'box', 'bounds_m': [.075, .022, .115]},
            'render': {'engine': 'CYCLES', 'device': 'CPU', 'samples': 32, 'denoise': True, 'threads': 4},
            'legend_font': 'original_bold_sans_stroke_atlas',
            'glb_path': str(glb_path.relative_to(ROOT)) if glb_path.is_relative_to(ROOT) else str(glb_path),
        })
    if meta['triangles'] > 20000 or len(meta['materials']) > 5:
        raise RuntimeError('Asset exceeds the request budget')
    expected = {'body', 'body-colonly', 'screen', 'led_status', 'btn_clear', 'btn_enter', *[f'btn_{i}' for i in range(10)]}
    if set(meta['parts']) != expected:
        raise RuntimeError(f'Unexpected exported mesh names: {meta["parts"]}')
    render_previews(ASSET_ID, ROOT / 'assets/previews', objects, views={
        'front': {'position': (0, .32, 0), 'target': (0, .010, 0), 'scale': .145},
        'iso': {'position': (.18, .28, .16), 'target': (0, .010, 0), 'scale': .15},
        'detail': {'position': (0, .28, -.013), 'target': (0, .018, -.013), 'scale': .090},
    }, seed=SEED)
    print(f'ASSET BUILT: {glb_path}; {meta["triangles"]} triangles; {len(meta["materials"])} materials')
    return glb_path


if __name__ == '__main__':
    run_cli(build, __doc__)
