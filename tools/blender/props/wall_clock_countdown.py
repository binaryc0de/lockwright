"""Industrial UPS runtime display. Original geometry, stroke lettering and PBR.

Blender 5.2, deterministic headless build, no downloads or external modules.
Run tools/blender/build_assets.sh wall_clock_countdown (serialized, CPU, 4 threads).
Window intentionally blank: SessionClock owns the live countdown digits.
"""
from array import array
import math
from pathlib import Path
import sys

import bpy
from mathutils import Vector

sys.dont_write_bytecode = True
TOOLS = Path(__file__).resolve().parents[1]
ROOT = TOOLS.parents[1]
sys.path.insert(0, str(TOOLS))
from common.cli import run_cli
from common.export import export_glb, write_metadata
from common.geometry import active, box, join_static, mesh_object, triangulate
from common.materials import base_texture, image_from_pixels, material, normal_texture, orm_texture, texture_node
from common.preview import render_previews
from common.scene import reset_scene

ASSET_ID = 'wall_clock_countdown'
SEED = 601026
SCREEN_CENTRE = (0, .012, -.047)
SCREEN_SIZE = (.400, .095)


class Surface:
    """Explicit procedural shader, subsequently baked to portable PBR maps."""
    def __init__(self, part, color, roughness):
        self.mat = material(ASSET_ID, part, color, roughness=roughness)
        self.tree = self.mat.node_tree
        self.bsdf = self.tree.nodes.get('Principled BSDF')
        self.position = self.node('ShaderNodeNewGeometry').outputs['Position']
        self.axes = self.node('ShaderNodeSeparateXYZ', Vector=self.position)

    def set(self, socket, value):
        if hasattr(value, 'node'):
            self.tree.links.new(value, socket)
        else:
            socket.default_value = value

    def node(self, kind, **inputs):
        node = self.tree.nodes.new(kind)
        for name, value in inputs.items():
            self.set(node.inputs[name], value)
        return node

    def math(self, op, a, b=None):
        node = self.node('ShaderNodeMath')
        node.operation = op
        self.set(node.inputs[0], a)
        if b is not None:
            self.set(node.inputs[1], b)
        return node.outputs[0]

    def noise(self, scales, detail=2):
        node = self.node('ShaderNodeVectorMath')
        node.operation = 'MULTIPLY'
        self.set(node.inputs[0], self.position)
        self.set(node.inputs[1], scales)
        return self.node('ShaderNodeTexNoise', Vector=node.outputs[0], Scale=1,
                         Detail=detail, Roughness=.7).outputs['Fac']

    def mix(self, fac, a, b):
        return self.node('ShaderNodeMixRGB', Fac=fac, Color1=a, Color2=b).outputs[0]

    def finish(self, color, rough, metal, height, distance):
        self.color, self.roughness, self.metallic = color, rough, metal
        self.set(self.bsdf.inputs['Base Color'], color)
        self.set(self.bsdf.inputs['Roughness'], rough)
        self.set(self.bsdf.inputs['Metallic'], metal)
        bump = self.node('ShaderNodeBump', Height=height, Strength=.32, Distance=distance)
        self.tree.links.new(bump.outputs['Normal'], self.bsdf.inputs['Normal'])


def surfaces():
    body = Surface('body', (.030, .034, .039), .61)
    grain = body.noise((2300, 2300, 2300), 3)
    broad = body.noise((35, 35, 35), 3)
    paint = body.mix(broad, (.004, .005, .0065, 1), (.008, .0095, .012, 1))
    # Chipping is restricted to perimeter edges and sparse spots, in metres.
    edge_x = body.math('GREATER_THAN', body.math('ABSOLUTE', body.axes.outputs['X']), .228)
    edge_z = body.math('GREATER_THAN', body.math('ABSOLUTE', body.axes.outputs['Z']), .078)
    edge = body.math('MAXIMUM', edge_x, edge_z)
    chips = body.math('MULTIPLY', edge, body.math('GREATER_THAN', body.noise((420, 320, 450), 3), .71))
    paint = body.mix(chips, paint, (.115, .125, .13, 1))
    # Thin, discontinuous dust accumulation on the upward-facing top edge.
    normal = body.node('ShaderNodeNewGeometry').outputs['Normal']
    nz = body.node('ShaderNodeSeparateXYZ', Vector=normal).outputs['Z']
    top = body.math('MULTIPLY', body.math('GREATER_THAN', nz, .65),
                    body.math('GREATER_THAN', body.axes.outputs['Z'], .077))
    dust = body.math('MULTIPLY', top, body.math('MULTIPLY', broad, .25))
    paint = body.mix(dust, paint, (.17, .155, .13, 1))
    rough = body.math('ADD', .53, body.math('MULTIPLY', grain, .20))
    rough = body.math('ADD', rough, body.math('MULTIPLY', dust, .22))
    brush = body.noise((55, 4000, 4000))
    steel = body.mix(brush, (.20, .225, .24, 1), (.32, .35, .37, 1))
    # A temporary vertex attribute differentiates hardware and gasket within
    # one body atlas. It is removed after the bake; GLB has only three materials.
    attr = body.node('ShaderNodeAttribute')
    attr.attribute_name = 'finish_kind'
    kind = body.node('ShaderNodeSeparateColor', Color=attr.outputs['Color']).outputs['Red']
    metal_mask = body.math('MULTIPLY', body.math('GREATER_THAN', kind, .3), body.math('LESS_THAN', kind, .8))
    rubber = body.math('GREATER_THAN', kind, .8)
    color = body.mix(metal_mask, paint, steel)
    color = body.mix(rubber, color, (.008, .009, .010, 1))
    rough = body.mix(metal_mask, rough, body.math('ADD', .30, body.math('MULTIPLY', brush, .14)))
    rough = body.mix(rubber, rough, (.73, .73, .73, 1))
    # MixRGB yields a color; SeparateColor preserves scalar RM channels.
    rough = body.node('ShaderNodeSeparateColor', Color=rough).outputs['Red']
    metallic = body.math('MAXIMUM', body.math('MULTIPLY', metal_mask, .95), body.math('MULTIPLY', chips, .7))
    body.finish(color, rough, metallic, grain, .00015)

    screen = Surface('screen', (.030, .003, .006), .23)
    smears = screen.noise((22, 22, 60), 4)
    fine = screen.noise((3000, 3000, 3000))
    # Opaque smoked acrylic: portable glTF, no transmission sorting artifacts.
    color = screen.mix(screen.math('MULTIPLY', smears, .13),
                       (.008, .0006, .0012, 1), (.014, .0012, .0022, 1))
    screen.finish(color, screen.math('ADD', .19, screen.math('MULTIPLY', smears, .09)), 0,
                  fine, .000004)
    return body, screen


def tag_finish(obj, value):
    attr = obj.data.color_attributes.new(name='finish_kind', type='FLOAT_COLOR', domain='POINT')
    for item in attr.data:
        item.color = (value, value, value, 1)


def cut(obj, cutter, label):
    active(obj)
    modifier = obj.modifiers.new(label, 'BOOLEAN')
    modifier.operation = 'DIFFERENCE'
    modifier.solver = 'EXACT'
    modifier.object = cutter
    bpy.ops.object.modifier_apply(modifier=modifier.name)
    bpy.data.objects.remove(cutter, do_unlink=True)


def screw(x, z, index, mat):
    count = 48
    angle_offset = (.17, -.34, .28, -.19)[index]
    verts = []
    for ring in range(5):
        for i in range(count):
            angle = math.tau * i / count + angle_offset
            if ring < 2:
                radius, depth = ((.0032, .0498), (.0029, .0508))[ring]
            else:
                radius = .00112 * (1 + .21 * math.cos(6 * (angle - angle_offset)))
                depth = (.0508, .04995, .0498)[ring - 2]
            verts.append((x + radius * math.cos(angle), depth, z + radius * math.sin(angle)))
    faces = []
    for ring in range(4):
        for i in range(count):
            j = (i + 1) % count
            faces.append((ring * count + i, ring * count + j,
                          (ring + 1) * count + j, (ring + 1) * count + i))
    for start, reverse in ((0, True), (count * 4, False)):
        for i in range(1, count - 1):
            face = (start, start + i, start + i + 1)
            faces.append(tuple(reversed(face)) if reverse else face)
    obj = mesh_object(f'corner_screw_{index}', verts, faces, mat)
    for face in obj.data.polygons:
        face.use_smooth = len(face.vertices) == 4
    return obj


# Original condensed technical stroke alphabet. No system/bundled fonts.
GLYPHS = {
    'U': [[(0, 1), (0, .16), (.12, 0), (.48, 0), (.6, .16), (.6, 1)]],
    'P': [[(0, 0), (0, 1), (.45, 1), (.6, .85), (.6, .65), (.45, .5), (0, .5)]],
    'S': [[(.6, .9), (.45, 1), (.15, 1), (0, .85), (0, .65), (.15, .52), (.45, .48), (.6, .35), (.6, .15), (.45, 0), (.15, 0), (0, .1)]],
    'R': [[(0, 0), (0, 1), (.45, 1), (.6, .85), (.6, .65), (.45, .5), (0, .5)], [(.3, .5), (.6, 0)]],
    'N': [[(0, 0), (0, 1), (.6, 0), (.6, 1)]],
    'T': [[(0, 1), (.6, 1)], [(.3, 1), (.3, 0)]],
    'I': [[(.3, 0), (.3, 1)], [(0, 1), (.6, 1)], [(0, 0), (.6, 0)]],
    'M': [[(0, 0), (0, 1), (.3, .5), (.6, 1), (.6, 0)]],
    'E': [[(.6, 1), (0, 1), (0, 0), (.6, 0)], [(0, .5), (.48, .5)]],
    'h': [[(0, 0), (0, 1)], [(0, .5), (.15, .65), (.43, .65), (.6, .5), (.6, 0)]],
    'm': [[(0, 0), (0, .65)], [(0, .5), (.15, .65), (.3, .5), (.3, 0)], [(.3, .5), (.45, .65), (.6, .5), (.6, 0)]],
    's': [[(.6, .58), (.45, .65), (.13, .65), (0, .53), (.13, .37), (.45, .28), (.6, .15), (.45, 0), (.13, 0), (0, .07)]],
    ':': [[(.3, .18), (.3, .20)], [(.3, .5), (.3, .52)]],
}


def lettering_texture(cache, mat):
    """Analytically antialiased original paths: union coverage avoids overlaps."""
    size = 1024
    pixels = array('f', [.80, .82, .79, 0]) * (size * size)
    def draw(text, cy, height, stroke):
        x_scale = (1024 / .16) / (384 / .024)
        advance = .82 * height * x_scale
        width = advance * len(text) - .22 * height * x_scale
        left, bottom = size / 2 - width / 2, cy - height / 2
        radius = height * stroke / 2
        for index, char in enumerate(text):
            if char == ' ':
                continue
            for path in GLYPHS[char]:
                for a, b in zip(path, path[1:]):
                    ax, ay = left + index * advance + a[0] * height * x_scale, bottom + a[1] * height
                    bx, by = left + index * advance + b[0] * height * x_scale, bottom + b[1] * height
                    dx, dy = bx - ax, by - ay
                    length_sq = dx * dx / (x_scale * x_scale) + dy * dy
                    for y in range(max(0, math.floor(min(ay, by) - radius - 1)), min(size, math.ceil(max(ay, by) + radius + 1))):
                        for x in range(max(0, math.floor(min(ax, bx) - radius * x_scale - 1)), min(size, math.ceil(max(ax, bx) + radius * x_scale + 1))):
                            t = max(0, min(1, ((x + .5 - ax) * dx / (x_scale * x_scale) + (y + .5 - ay) * dy) / length_sq))
                            distance = math.hypot((x + .5 - ax - t * dx) / x_scale, y + .5 - ay - t * dy)
                            alpha = max(0, min(1, radius + .5 - distance))
                            i = (y * size + x) * 4 + 3
                            pixels[i] = max(pixels[i], alpha)
    # Each cell is mapped to a 0.16 x 0.024 m rectangle; 14mm / 7mm caps.
    draw('UPS RUNTIME', 256, 384 * .014 / .024, .085)
    draw('h:mm:ss', 768, 384 * .007 / .024, .08)
    image = image_from_pixels(ASSET_ID, 'print_base_color', size, pixels, cache)
    node = texture_node(mat, image)
    bsdf = mat.node_tree.nodes.get('Principled BSDF')
    mat.node_tree.links.new(node.outputs['Color'], bsdf.inputs['Base Color'])
    mat.node_tree.links.new(node.outputs['Alpha'], bsdf.inputs['Alpha'])
    mat.surface_render_method = 'DITHERED'
    return {'name': image.name, 'size': list(image.size), 'map': 'base_color_alpha',
            'material': mat.name, 'embedded': True}


def lettering(label, cx, cz, mat, rect):
    # A single decal plane per label: no coplanar overlapping stroke meshes.
    width, height = .16, .024
    obj = mesh_object('printed_' + label, [(width / 2, 0, -height / 2),
                      (-width / 2, 0, -height / 2), (-width / 2, 0, height / 2),
                      (width / 2, 0, height / 2)], [(0, 1, 2, 3)], mat, (cx, .0501, cz))
    uv = obj.data.uv_layers.new(name='UVMap')
    u0, v0, u1, v1 = rect
    for item, point in zip(uv.data, ((u0, v0), (u1, v0), (u1, v1), (u0, v1))):
        item.uv = point
    return obj


def geometry(body_surf, screen_surf, print_mat):
    housing = box('housing', (.46, .0485, .16), body_surf.mat,
                  (0, .02575, 0), bevel=.0018, segments=5)
    # True recess, not a window laid over a solid front face.
    cutter = box('window_cut-noimp', (.406, .013, .101), None,
                 (0, .0495, .012), bevel=.00065, segments=3)
    cut(housing, cutter, 'window_pocket')
    for side in (-1, 1):
        for row in range(5):
            cutter = box('vent_cut-noimp', (.006, .023, .0021), None,
                         (side * .229, .025, -.021 + row * .009), bevel=.00065, segments=3)
            cut(housing, cutter, 'vent_pocket')
    rear = box('rear_plate', (.452, .0015, .152), body_surf.mat,
               (0, .00075, 0), bevel=.0005, segments=3)
    socket = box('window_gasket', (.4054, .0025, .1004), body_surf.mat,
                 (0, .04425, .012), bevel=.0006, segments=3)
    pieces = [housing, rear, socket]
    for index, (x, z) in enumerate(((-.217, -.066), (.217, -.066), (-.217, .067), (.217, .067))):
        pieces.append(screw(x, z, index, body_surf.mat))
    for obj in pieces:
        tag_finish(obj, 1 if obj == socket else .5 if obj.name.startswith('corner_screw') else 0)
        triangulate(obj)
    body = join_static(pieces, 'body', origin=(0, 0, 0))
    # Boolean cutters can leave an unused empty material slot. All structural
    # faces use the same shader; discard that slot before baking.
    body.data.materials.clear()
    body.data.materials.append(body_surf.mat)
    for face in body.data.polygons:
        face.material_index = 0
    # Plane has full 0..1 UV coverage and origin exactly at its visible centre.
    w, h = SCREEN_SIZE
    screen = mesh_object('screen', [(w / 2, 0, -h / 2), (-w / 2, 0, -h / 2),
                                    (-w / 2, 0, h / 2), (w / 2, 0, h / 2)],
                         [(0, 1, 2, 3)], screen_surf.mat,
                         (SCREEN_CENTRE[0], -SCREEN_CENTRE[2], SCREEN_CENTRE[1]))
    uv = screen.data.uv_layers.new(name='UVMap')
    for item, point in zip(uv.data, ((0, 0), (1, 0), (1, 1), (0, 1))):
        item.uv = point
    triangulate(screen)
    caption = lettering('caption', 0, -.055, print_mat, (.0, .0625, 1, .4375))
    # Crop the legend to its own 64mm rectangle, keeping identical texel scale.
    legend = lettering('legend', -.166, -.055, print_mat, (.30, .5625, .70, .9375))
    for v in legend.data.vertices:
        v.co.x *= .4
    for obj in (caption, legend):
        triangulate(obj)
    return body, screen, [caption, legend]


def bake_surface(obj, surf, cache, unwrap=True):
    """Cycles CPU color, ORM, tangent normal and AO passes; 8px bake margin."""
    size = 1024
    active(obj)
    if unwrap:
        bpy.ops.object.mode_set(mode='EDIT')
        bpy.ops.mesh.select_all(action='SELECT')
        bpy.ops.uv.smart_project(angle_limit=math.radians(66), island_margin=8 / size,
                                 margin_method='FRACTION', area_weight=0, scale_to_bounds=True)
        bpy.ops.uv.average_islands_scale()
        bpy.ops.uv.pack_islands(rotate=True, margin_method='FRACTION', margin=8 / size)
        bpy.ops.object.mode_set(mode='OBJECT')
    scene = bpy.context.scene
    scene.cycles.samples = 16
    scene.render.bake.margin = 8
    scene.render.bake.use_clear = True
    scene.render.bake.use_selected_to_active = False
    scene.render.bake.normal_space = 'TANGENT'
    tree = surf.tree
    output = next(n for n in tree.nodes if n.type == 'OUTPUT_MATERIAL')
    emitter = surf.node('ShaderNodeEmission', Strength=1)
    target = surf.node('ShaderNodeTexImage')
    images = {}

    def bake(name, kind, color=None, non_color=False):
        image = bpy.data.images.new(f'T_{ASSET_ID}_{obj.name}_{name}', width=size, height=size, alpha=False)
        image.colorspace_settings.name = 'Non-Color' if non_color else 'sRGB'
        target.image = image
        tree.nodes.active = target
        if kind == 'EMIT':
            surf.set(emitter.inputs['Color'], color)
            tree.links.new(emitter.outputs[0], output.inputs['Surface'])
        else:
            tree.links.new(surf.bsdf.outputs[0], output.inputs['Surface'])
        active(obj)
        print(f'BAKE {obj.name} {name}: 1024px, {kind}, CPU, 8px margin', flush=True)
        bpy.ops.object.bake(type=kind)
        images[name] = image
        return image

    bake('base_color', 'EMIT', surf.color)
    rm = surf.node('ShaderNodeCombineColor', Red=1, Green=surf.roughness, Blue=surf.metallic)
    orm = bake('orm', 'EMIT', rm.outputs[0], True)
    bake('normal', 'NORMAL', non_color=True)
    ao = bake('ao_work', 'AO', non_color=True)
    pixels = array('f', [0]) * (size * size * 4)
    occlusion = array('f', [0]) * len(pixels)
    orm.pixels.foreach_get(pixels)
    ao.pixels.foreach_get(occlusion)
    for i in range(0, len(pixels), 4):
        pixels[i], pixels[i + 3] = .40 + .60 * occlusion[i], 1
    orm.pixels.foreach_set(pixels)
    bpy.data.images.remove(ao)
    del images['ao_work']
    for image in images.values():
        image.file_format = 'PNG'
        image.filepath_raw = str(cache / f'{image.name}.png')
        image.save()
        image.pack()
    for node in list(tree.nodes):
        if node not in (surf.bsdf, output):
            tree.nodes.remove(node)
    tree.links.new(surf.bsdf.outputs[0], output.inputs['Surface'])
    base_texture(surf.mat, images['base_color'])
    orm_texture(surf.mat, images['orm'])
    normal_texture(surf.mat, images['normal'])
    if 'finish_kind' in obj.data.color_attributes:
        obj.data.color_attributes.remove(obj.data.color_attributes['finish_kind'])
    return [{'name': im.name, 'size': list(im.size), 'map': name,
             'material': surf.mat.name, 'embedded': True} for name, im in sorted(images.items())]


def validate(gltf, body, screen):
    nodes = {n['name']: n for n in gltf['nodes'] if 'mesh' in n}
    if set(nodes) != {'body', 'screen'} or gltf.get('animations'):
        raise RuntimeError('Unexpected parts or animations')
    for name, node in nodes.items():
        if node.get('scale', [1, 1, 1]) != [1, 1, 1] or node.get('rotation', [0, 0, 0, 1]) != [0, 0, 0, 1]:
            raise RuntimeError(f'Unapplied transform: {name}')
    if any(abs(a - b) > 1e-7 for a, b in zip(nodes['screen']['translation'], SCREEN_CENTRE)):
        raise RuntimeError('Incorrect screen origin')
    if any(abs(v) > 1e-7 for v in nodes['body'].get('translation', [0, 0, 0])):
        raise RuntimeError('Body origin must be at mounting-plane centre')
    if abs(min((body.matrix_world @ v.co).y for v in body.data.vertices)) > 1e-7:
        raise RuntimeError('Back mounting face must be y=0 in Blender')
    coords = [item.uv for item in screen.data.uv_layers.active.data]
    if min(p.x for p in coords) != 0 or max(p.x for p in coords) != 1 or min(p.y for p in coords) != 0 or max(p.y for p in coords) != 1:
        raise RuntimeError('Screen UV must fill 0..1')
    if any(p.normal.y < .999 for p in screen.data.polygons):
        raise RuntimeError('Screen must face Blender +Y / Godot -Z')
    print('PASS geometry: mount-plane origin; 400x95mm window recessed 3mm; screen-centre anchor; UV 0..1; applied transforms')


def build(out_dir):
    reset_scene(SEED)
    cache = ROOT / 'assets/cache' / ASSET_ID
    cache.mkdir(parents=True, exist_ok=True)
    body_surf, screen_surf = surfaces()
    print_mat = material(ASSET_ID, 'print', (.80, .82, .79), roughness=.72)
    print_texture = lettering_texture(cache, print_mat)
    body, screen, printing = geometry(body_surf, screen_surf, print_mat)
    bpy.context.view_layer.update()
    textures = bake_surface(body, body_surf, cache)
    textures.extend(bake_surface(screen, screen_surf, cache, unwrap=False))
    textures.append(print_texture)
    body = join_static([body, *printing], 'body')
    triangulate(body)
    bpy.context.view_layer.update()
    objects = [body, screen]
    glb_path = Path(out_dir).resolve() / f'{ASSET_ID}.glb'
    gltf = export_glb(glb_path, objects)
    validate(gltf, body, screen)
    # Zero emission by default. A dark blank panel is the exported rest state;
    # runtime digits may use a red emissive overlay without a baked time value.
    meta = write_metadata(ASSET_ID, ROOT / 'assets/meta' / f'{ASSET_ID}.json',
                          glb_path, objects, Path(__file__), textures, 'mount_plane_center', extra={
        'anchors_godot_m': {'screen_centre': list(SCREEN_CENTRE), 'screen_size': list(SCREEN_SIZE)},
        'housing_size_godot_m': [.46, .16, .05],
        'origin_reference': 'centre of back mounting face at Godot z=0',
        'forward': 'Blender +Y -> Godot -Z', 'collision': None,
        'screen_recess_m': .003, 'screen_uv': [0, 0, 1, 1],
        'caption_cap_height_m': .014, 'lettering': 'original condensed stroke paths, no fonts',
        'baking': {'engine': 'CYCLES', 'device': 'CPU', 'samples': 16, 'margin_px': 8,
                   'maps': 'procedural color/RM, tangent normals, ray-traced AO packed into ORM'},
        'render': {'engine': 'CYCLES', 'device': 'CPU', 'samples': 32, 'denoise': True, 'threads': 4},
        'glb_path': str(glb_path.relative_to(ROOT)) if glb_path.is_relative_to(ROOT) else str(glb_path),
    })
    if meta['triangles'] > 20000 or len(meta['materials']) > 3:
        raise RuntimeError('Request budget exceeded')
    render_previews(ASSET_ID, ROOT / 'assets/previews', objects, views={
        'front': {'position': (0, .75, 0), 'target': (0, .025, 0), 'scale': .55},
        'iso': {'position': (-.42, .72, .34), 'target': (0, .025, 0), 'scale': .55},
        'detail': {'position': (-.30, .68, .16), 'target': (-.125, .045, -.013), 'scale': .255},
    }, seed=SEED)
    print(f'ASSET BUILT: {glb_path}; {meta["triangles"]} triangles; {len(meta["materials"])} materials', flush=True)
    return glb_path


if __name__ == '__main__':
    run_cli(build, __doc__)
