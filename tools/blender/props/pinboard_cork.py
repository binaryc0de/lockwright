"""Office cork pinboard: original baked PBR and stroke lettering, no downloads.

Deterministic Blender 5.2 headless build; one serialized CPU process, 4 threads.
Run tools/blender/build_assets.sh pinboard_cork. Entry point: build(out_dir).
"""
from array import array
import math
from pathlib import Path
import random
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
from common.materials import base_texture, image_from_pixels, material, normal_texture, orm_texture
from common.preview import render_previews
from common.scene import reset_scene

ASSET_ID = 'pinboard_cork'
SEED = 72026
CORK_FRONT_Z = -.0165
# Godot X/Y of six unused pins and one pin holding the header.
PIN_LAYOUT = [(-.405, .19), (-.49, -.225), (-.055, -.20),
              (.48, .225), (.44, -.22), (.06, .19), (0, .355)]
PIN_COLORS = [(.065, .13, .21, 1), (.38, .045, .022, 1), (.40, .26, .035, 1),
              (.09, .17, .075, 1), (.065, .13, .21, 1), (.38, .045, .022, 1),
              (.38, .045, .022, 1)]


def godot(point):
    return (point[0], -point[2], point[1])


class Surface:
    """Small explicit shader builder. All coordinates are metres, in Blender."""
    def __init__(self, part, color, roughness, metallic=0):
        self.mat = material(ASSET_ID, part, color, roughness=roughness, metallic=metallic)
        self.tree = self.mat.node_tree
        self.bsdf = self.tree.nodes.get('Principled BSDF')
        self.position = self.node('ShaderNodeNewGeometry').outputs['Position']
        self.axes = self.node('ShaderNodeSeparateXYZ', Vector=self.position)
        self.color = color
        self.roughness = roughness
        self.metallic = metallic

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

    def math(self, operation, a, b=None):
        node = self.node('ShaderNodeMath')
        node.operation = operation
        self.set(node.inputs[0], a)
        if b is not None:
            self.set(node.inputs[1], b)
        return node.outputs[0]

    def scaled(self, scales):
        node = self.node('ShaderNodeVectorMath')
        node.operation = 'MULTIPLY'
        self.set(node.inputs[0], self.position)
        self.set(node.inputs[1], scales)
        return node.outputs[0]

    def noise(self, scales, detail=2):
        noise = self.node('ShaderNodeTexNoise', Vector=self.scaled(scales), Scale=1.0,
                          Detail=detail, Roughness=.68)
        return noise.outputs['Fac']

    def mix(self, fac, a, b):
        return self.node('ShaderNodeMixRGB', Fac=fac, Color1=a, Color2=b).outputs[0]

    def ramp(self, fac, stops):
        node = self.node('ShaderNodeValToRGB', Fac=fac)
        ramp = node.color_ramp
        ramp.elements.remove(ramp.elements[1])
        ramp.elements[0].position, ramp.elements[0].color = stops[0]
        for position, color in stops[1:]:
            ramp.elements.new(position).color = color
        return node.outputs['Color']

    def finish(self, color, roughness, height, strength, distance):
        self.color, self.roughness = color, roughness
        self.set(self.bsdf.inputs['Base Color'], color)
        self.set(self.bsdf.inputs['Roughness'], roughness)
        bump = self.node('ShaderNodeBump', Height=height, Strength=strength, Distance=distance)
        self.tree.links.new(bump.outputs['Normal'], self.bsdf.inputs['Normal'])


GLYPHS = {'I': [[(0, 1), (0.6, 1)], [(0.3, 1), (0.3, 0)], [(0, 0), (0.6, 0)]], 'T': [[(0, 1), (0.6, 1)], [(0.3, 1), (0.3, 0)]], 'N': [[(0, 0), (0, 1), (0.6, 0), (0.6, 1)]], 'O': [[(0.13, 0), (0.47, 0), (0.6, 0.17), (0.6, 0.83), (0.47, 1), (0.13, 1), (0, 0.83), (0, 0.17), (0.13, 0)]], 'C': [[(0.6, 0.89), (0.45, 1), (0.15, 1), (0, 0.8), (0, 0.2), (0.15, 0), (0.45, 0), (0.6, 0.11)]], 'E': [[(0.6, 1), (0, 1), (0, 0), (0.6, 0)], [(0, 0.5), (0.47, 0.5)]], 'S': [[(0.6, 0.9), (0.46, 1), (0.14, 1), (0, 0.83), (0, 0.67), (0.15, 0.54), (0.45, 0.46), (0.6, 0.33), (0.6, 0.17), (0.46, 0), (0.14, 0), (0, 0.1)]]}


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


def bake_surface(part, surf, components, cache):
    """Unwrap one material globally, bake four passes, transfer exact UV loops.

    The temporary mesh uses world coordinates, so grain/wear are continuous.
    Islands never overlap; packing and baking both reserve an 8 pixel margin.
    Only the AO pass uses rays. Base colour / packed RM are emission bakes;
    normals are Cycles tangent NORMAL bakes of the procedural microstructure.
    """
    size = 2048 if part == 'cork' else 1024
    vertices, faces, smooth = [], [], []
    for obj in components:
        offset = len(vertices)
        vertices.extend(tuple(obj.matrix_world @ v.co) for v in obj.data.vertices)
        faces.extend(tuple(offset + v for v in poly.vertices) for poly in obj.data.polygons)
        smooth.extend(poly.use_smooth for poly in obj.data.polygons)
    temp = mesh_object('bake_surface-noimp', vertices, faces, surf.mat)
    for poly, flag in zip(temp.data.polygons, smooth):
        poly.use_smooth = flag
    active(temp)
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.uv.smart_project(angle_limit=math.radians(66), island_margin=8 / size,
                             margin_method='FRACTION', area_weight=0.0, scale_to_bounds=True)
    bpy.ops.uv.average_islands_scale()
    bpy.ops.uv.pack_islands(rotate=True, margin_method='FRACTION', margin=8 / size)
    bpy.ops.object.mode_set(mode='OBJECT')
    source_uv = temp.data.uv_layers.active.data
    cursor = 0
    for obj in components:
        uv = obj.data.uv_layers.new(name='UVMap')
        for loop in uv.data:
            loop.uv = source_uv[cursor].uv
            cursor += 1
    if cursor != len(source_uv):
        raise RuntimeError('UV loop transfer mismatch')
    # Avoid duplicate surfaces in the ray-traced AO pass.
    for obj in components:
        obj.hide_render = True
    scene = bpy.context.scene
    scene.cycles.samples = 16
    scene.render.bake.margin = 8
    scene.render.bake.use_clear = True
    scene.render.bake.use_selected_to_active = False
    scene.render.bake.normal_space = 'TANGENT'
    scene.world = bpy.data.worlds.new('bake_world-noimp')
    tree = surf.tree
    output = next(n for n in tree.nodes if n.type == 'OUTPUT_MATERIAL')
    emitter = surf.node('ShaderNodeEmission', Strength=1.0)
    target = surf.node('ShaderNodeTexImage')
    tree.nodes.active = target
    images = {}

    def bake(map_name, kind, color=None, non_color=False):
        image = bpy.data.images.new(f'T_{ASSET_ID}_{part}_{map_name}', width=size, height=size, alpha=False)
        image.colorspace_settings.name = 'Non-Color' if non_color else 'sRGB'
        target.image = image
        tree.nodes.active = target
        if kind == 'EMIT':
            surf.set(emitter.inputs['Color'], color)
            tree.links.new(emitter.outputs[0], output.inputs['Surface'])
        else:
            tree.links.new(surf.bsdf.outputs[0], output.inputs['Surface'])
        active(temp)
        print(f'BAKE {part} {map_name}: {size}px, {kind}, CPU, 8px margin', flush=True)
        bpy.ops.object.bake(type=kind)
        images[map_name] = image
        return image

    bake('base_color', 'EMIT', surf.color)
    rm = surf.node('ShaderNodeCombineColor', Red=1.0, Green=surf.roughness, Blue=surf.metallic)
    orm = bake('orm', 'EMIT', rm.outputs[0], non_color=True)
    bake('normal', 'NORMAL', non_color=True)
    ao = bake('ao_work', 'AO', non_color=True)
    packed = array('f', [0]) * (size * size * 4)
    occlusion = array('f', [0]) * len(packed)
    orm.pixels.foreach_get(packed)
    ao.pixels.foreach_get(occlusion)
    # Keep AO subtle, especially in the clean melamine tray.
    for index in range(0, len(packed), 4):
        packed[index] = .45 + .55 * occlusion[index]
        packed[index + 3] = 1
    orm.pixels.foreach_set(packed)
    bpy.data.images.remove(ao)
    del images['ao_work']
    for name, image in images.items():
        image.file_format = 'PNG'
        image.filepath_raw = str(cache / f'{image.name}.png')
        image.save()
        image.pack()
    # Replace the procedural graph with glTF-compatible Principled + textures.
    for node in list(tree.nodes):
        if node not in (surf.bsdf, output):
            tree.nodes.remove(node)
    tree.links.new(surf.bsdf.outputs[0], output.inputs['Surface'])
    base_texture(surf.mat, images['base_color'])
    orm_texture(surf.mat, images['orm'])
    normal_texture(surf.mat, images['normal'])
    for obj in components:
        obj.hide_render = False
    bpy.data.objects.remove(temp, do_unlink=True)
    return [{'name': image.name, 'size': list(image.size), 'map': name,
             'material': surf.mat.name, 'embedded': True}
            for name, image in sorted(images.items())]



def rectangle_mask(surf, cx, cz, width, height, feather=.005):
    dx = surf.math('SUBTRACT', surf.math('ABSOLUTE',
                   surf.math('SUBTRACT', surf.axes.outputs['X'], cx)), width / 2)
    dz = surf.math('SUBTRACT', surf.math('ABSOLUTE',
                   surf.math('SUBTRACT', surf.axes.outputs['Z'], cz)), height / 2)
    outside = surf.math('MAXIMUM', dx, dz)
    return surf.math('MINIMUM', 1, surf.math('MAXIMUM', 0,
                     surf.math('SUBTRACT', 1, surf.math('DIVIDE', outside, feather))))


def circle_mask(surf, x, z, radius):
    dx = surf.math('SUBTRACT', surf.axes.outputs['X'], x)
    dz = surf.math('SUBTRACT', surf.axes.outputs['Z'], z)
    distance = surf.math('SQRT', surf.math('ADD', surf.math('MULTIPLY', dx, dx),
                                         surf.math('MULTIPLY', dz, dz)))
    return surf.math('MAXIMUM', 0, surf.math('SUBTRACT', 1,
                                         surf.math('DIVIDE', distance, radius)))


def surfaces(cache):
    cork = Surface('cork', (.39, .23, .11), .87)
    cells = cork.node('ShaderNodeTexVoronoi', Vector=cork.scaled((235, 65, 235)), Scale=1)
    cells.feature = 'F1'
    cells.distance = 'EUCLIDEAN'
    seed_color = cork.node('ShaderNodeRGBToBW', Color=cells.outputs['Color']).outputs[0]
    flakes = cork.ramp(seed_color, [(.08, (.20, .10, .039, 1)),
                                   (.30, (.33, .18, .075, 1)),
                                   (.55, (.45, .275, .125, 1)),
                                   (.82, (.57, .375, .205, 1))])
    # Individual compressed chips have mottled fibres and dark interstices.
    fibre = cork.noise((980, 65, 980), detail=3)
    edges = cork.node('ShaderNodeTexVoronoi', Vector=cork.scaled((235, 65, 235)), Scale=1)
    edges.feature = 'DISTANCE_TO_EDGE'
    cracks = cork.math('MAXIMUM', 0, cork.math('SUBTRACT', 1,
                        cork.math('DIVIDE', edges.outputs['Distance'], .034)))
    flakes = cork.mix(cork.math('MULTIPLY', cracks, .30), flakes, (.10, .052, .019, 1))
    flakes = cork.mix(cork.math('MULTIPLY', fibre, .19), flakes, (.25, .14, .060, 1))
    broad = cork.noise((5, 5, 5), detail=3)
    flakes = cork.mix(cork.math('MULTIPLY', broad, .12), flakes, (.53, .34, .17, 1))
    # The central sun-exposed field is a little lighter than covered margins.
    centre = rectangle_mask(cork, 0, 0, 1.08, .68, .024)
    flakes = cork.mix(cork.math('MULTIPLY', cork.math('SUBTRACT', 1, centre), .18),
                      flakes, (.20, .115, .046, 1))
    old_notices = [(-.305, .085, .30, .235), (-.28, -.235, .30, .145)]
    faded = 0
    for x, z, w, h in old_notices:
        # The reserved WiFi rectangle is never touched by a notice mask.
        assert x + w / 2 + .006 < .10 or x - w / 2 - .006 > .40
        faded = cork.math('MAXIMUM', faded, rectangle_mask(cork, x, z, w, h, .006))
    flakes = cork.mix(cork.math('MULTIPLY', faded, .13), flakes, (.58, .40, .225, 1))
    # Sparse old punctures, concentrated where old notices were pinned.
    holes = [(-.443, .192), (-.165, .185), (-.444, -.024), (-.17, -.025),
             (-.418, -.174), (-.143, -.177), (-.414, -.298), (-.139, -.301),
             (.51, .31), (.36, .275), (.32, -.28), (.10, -.285),
             (-.52, .105), (-.49, .34), (-.035, .258), (-.05, -.335),
             (.52, -.08), (.47, .07), (.08, .05), (.08, -.07)]
    punctures = 0
    rng = random.Random(SEED)
    for x, z in holes:
        assert not (.10 <= x <= .40 and -.10 <= z <= .10)
        punctures = cork.math('MAXIMUM', punctures,
                             circle_mask(cork, x, z, rng.uniform(.00115, .00175)))
    flakes = cork.mix(cork.math('MULTIPLY', punctures, .78), flakes, (.035, .018, .008, 1))
    relief = cork.math('ADD', cork.math('MULTIPLY', seed_color, .35),
                      cork.math('MULTIPLY', fibre, .35))
    relief = cork.math('SUBTRACT', relief, cork.math('MULTIPLY', cracks, .18))
    relief = cork.math('SUBTRACT', relief, cork.math('MULTIPLY', punctures, 1.2))
    rough = cork.math('ADD', .77, cork.math('MULTIPLY', fibre, .20))
    # Medium-brown cork reflectance. Keep grain readable under the shared
    # bright studio and the room's lower illumination, without exposure hacks.
    pigment = cork.node('ShaderNodeMixRGB', Fac=1, Color1=flakes, Color2=(.34, .30, .27, 1))
    pigment.blend_type = 'MULTIPLY'
    cork.finish(pigment.outputs[0], rough, relief, .65, .0015)

    frame = Surface('frame', (.40, .265, .13), .40)
    horizontal = frame.noise((5, 850, 500), detail=3)
    vertical = frame.noise((500, 850, 5), detail=3)
    side = frame.math('GREATER_THAN', frame.math('ABSOLUTE', frame.axes.outputs['X']), .579)
    grain = frame.mix(side, horizontal, vertical)
    color = frame.ramp(grain, [(.15, (.15, .071, .024, 1)),
                              (.37, (.34, .18, .067, 1)),
                              (.63, (.51, .32, .145, 1)),
                              (.86, (.63, .435, .24, 1))])
    fine = frame.noise((2000, 2000, 2000), detail=2)
    # Restrained finish wear along the external edge, no decorative hardware.
    outer = frame.math('MAXIMUM', frame.math('GREATER_THAN',
                       frame.math('ABSOLUTE', frame.axes.outputs['X']), .597),
                       frame.math('GREATER_THAN', frame.math('ABSOLUTE', frame.axes.outputs['Z']), .397))
    wear = frame.math('MULTIPLY', outer, frame.noise((80, 180, 80)))
    color = frame.mix(frame.math('MULTIPLY', wear, .19), color, (.59, .40, .21, 1))
    oak = frame.node('ShaderNodeMixRGB', Fac=1, Color1=color, Color2=(.60, .54, .48, 1))
    oak.blend_type = 'MULTIPLY'
    frame.finish(oak.outputs[0], frame.math('ADD', .34, frame.math('MULTIPLY', fine, .13)),
                 grain, .24, .00012)

    pins = Surface('pins', (.30, .045, .025), .31)
    color = PIN_COLORS[0]
    for (x, z), shade in zip(PIN_LAYOUT, PIN_COLORS):
        color = pins.mix(rectangle_mask(pins, x, z, .025, .025, .001), color, shade)
    # Shafts share the pins material; bake physically different metal response.
    needle = pins.math('LESS_THAN', pins.axes.outputs['Y'], .018)
    color = pins.mix(needle, color, (.49, .53, .57, 1))
    pins.metallic = pins.math('MULTIPLY', needle, .92)
    pins.set(pins.bsdf.inputs['Metallic'], pins.metallic)
    fine = pins.noise((2800, 2800, 2800), detail=2)
    pins.finish(color, pins.math('ADD', .25, pins.math('MULTIPLY', fine, .13)),
                fine, .15, .000023)

    card = Surface('card', (.86, .845, .79), .83)
    size = 1024
    pixels = array('f', [.86, .845, .79, 1]) * (size * size)
    # Atlas long direction covers the 300 mm card width. Letter path plus
    # bold 0.18-em stroke yields exactly 30 mm outer cap height.
    path_height = size * (.030 / 1.18) / .30
    draw_text(pixels, size, 'IT NOTICES', (size / 2, size / 2), path_height,
              (.001, .001, .001), stroke=.18)
    source = image_from_pixels(ASSET_ID, 'card_lettering_source', size, pixels, cache)
    u = card.math('SUBTRACT', .5, card.math('DIVIDE', card.axes.outputs['X'], .30))
    v = card.math('ADD', .5, card.math('DIVIDE', card.math('SUBTRACT', card.axes.outputs['Z'], .33), .30))
    coordinates = card.node('ShaderNodeCombineXYZ', X=u, Y=v, Z=0).outputs[0]
    printed = card.node('ShaderNodeTexImage', Vector=coordinates)
    printed.image = source
    printed.extension = 'EXTEND'
    front = card.math('GREATER_THAN', card.node('ShaderNodeSeparateXYZ',
                     Vector=card.node('ShaderNodeNewGeometry').outputs['Normal']).outputs['Y'], .5)
    print_color = card.mix(front, (.81, .795, .74, 1), printed.outputs['Color'])
    paper_fibre = card.noise((3500, 3500, 3500), detail=2)
    color = card.mix(card.math('MULTIPLY', paper_fibre, .017), print_color, (.49, .46, .38, 1))
    card.finish(color, card.math('ADD', .76, card.math('MULTIPLY', paper_fibre, .15)),
                paper_fibre, .18, .000025)
    return {'cork': cork, 'frame': frame, 'pins': pins, 'card': card}


def miter_rail(name, polygon, mat):
    vertices = [(x, d, z) for d in (0, .020) for x, z in polygon]
    faces = [(3, 2, 1, 0), (4, 5, 6, 7)]
    faces.extend((i, (i + 1) % 4, (i + 1) % 4 + 4, i + 4) for i in range(4))
    obj = mesh_object(name, vertices, faces, mat)
    triangulate(obj)
    active(obj)
    bevel = obj.modifiers.new('oak_roundover', 'BEVEL')
    bevel.width, bevel.segments = .0008, 4
    bevel.affect = 'EDGES'
    bevel.angle_limit = math.radians(25)
    bevel.limit_method = 'ANGLE'
    bpy.ops.object.modifier_apply(modifier=bevel.name)
    for face in obj.data.polygons:
        face.use_smooth = max(abs(n) for n in face.normal) < .999
    normal = obj.modifiers.new('weighted_normals', 'WEIGHTED_NORMAL')
    normal.keep_sharp = True
    bpy.ops.object.modifier_apply(modifier=normal.name)
    return obj


def lathe(name, x, z, depth, profile, mat, count=32):
    vertices = [(x + r * math.cos(i * math.tau / count), depth + y,
                 z + r * math.sin(i * math.tau / count))
                for y, r in profile for i in range(count)]
    faces = []
    for ring in range(len(profile) - 1):
        for i in range(count):
            j = (i + 1) % count
            faces.append((ring * count + i, ring * count + j,
                          (ring + 1) * count + j, (ring + 1) * count + i))
    for start, reverse in [(0, True), ((len(profile) - 1) * count, False)]:
        for i in range(1, count - 1):
            face = (start, start + i, start + i + 1)
            faces.append(tuple(reversed(face)) if reverse else face)
    obj = mesh_object(name, vertices, faces, mat)
    for face in obj.data.polygons:
        face.use_smooth = len(face.vertices) == 4
    return obj


def paper(mat):
    # Closed 450-micron card; lower edge curls 0.8 mm away from the cork.
    columns, rows = 16, 6
    vertices = []
    for back in (True, False):
        for row in range(rows + 1):
            z = .295 + .070 * row / rows
            curl = .0008 * ((.355 - z) / .060) ** 2
            for col in range(columns + 1):
                x = -.15 + .30 * col / columns
                bow = .00012 * (x / .15) ** 2
                vertices.append((x, .0166 + curl + bow + (0 if back else .00045), z))
    layer = (columns + 1) * (rows + 1)
    faces = []
    for row in range(rows):
        for col in range(columns):
            a = row * (columns + 1) + col
            face = (a, a + 1, a + columns + 2, a + columns + 1)
            faces.append(tuple(reversed(face)))
            faces.append(tuple(v + layer for v in face))
    perimeter = list(range(columns + 1))
    perimeter += [row * (columns + 1) + columns for row in range(1, rows + 1)]
    perimeter += [rows * (columns + 1) + col for col in range(columns - 1, -1, -1)]
    perimeter += [row * (columns + 1) for row in range(rows - 1, 0, -1)]
    for a, b in zip(perimeter, perimeter[1:] + perimeter[:1]):
        faces.append((a, b, b + layer, a + layer))
    return mesh_object('printed_card', vertices, faces, mat)


def geometry(mats):
    groups = {'board': [], 'header_card': [], 'pins': []}
    groups['board'].append(box('cork_slab', (1.16, .0165, .76), mats['cork'].mat,
                               (0, .00825, 0), bevel=.0004, segments=3))
    rails = [[(-.600, .400), (.600, .400), (.580, .380), (-.580, .380)],
             [(-.600, -.400), (-.580, -.380), (.580, -.380), (.600, -.400)],
             [(-.600, -.400), (-.600, .400), (-.580, .380), (-.580, -.380)],
             [(.600, -.400), (.580, -.380), (.580, .380), (.600, .400)]]
    for i, polygon in enumerate(rails):
        groups['board'].append(miter_rail(f'oak_rail_{i}', polygon, mats['frame'].mat))
    groups['header_card'].append(paper(mats['card'].mat))
    # Familiar spool shape, real roundovers, fine metal shaft, no floating pins.
    profile = [(0, .0038), (.0004, .0045), (.0012, .0045), (.0018, .0036),
               (.0024, .0025), (.0066, .0025), (.0074, .0035), (.0082, .0042),
               (.0092, .0042), (.0102, .0036), (.0107, .0023)]
    for i, (x, z) in enumerate(PIN_LAYOUT):
        dest = groups['header_card'] if i == 6 else groups['pins']
        depth = .01715 if i == 6 else .0165
        dest.append(lathe(f'pushpin_head_{i}', x, z, depth + .0015, profile, mats['pins'].mat))
        dest.append(lathe(f'pushpin_needle_{i}', x, z, depth - .003,
                          [(0, .00032), (.0047, .00032)], mats['pins'].mat, count=12))
        assert not (.10 <= x <= .40 and -.10 <= z <= .10)
    for objects in groups.values():
        for obj in objects:
            triangulate(obj)
    return groups


def validate_export(gltf):
    nodes = {node['name']: node for node in gltf['nodes'] if 'mesh' in node}
    if set(nodes) != {'board', 'header_card', 'pins'}:
        raise RuntimeError(f'Unexpected named parts: {set(nodes)}')
    if gltf.get('animations') or gltf.get('cameras') or gltf.get('skins'):
        raise RuntimeError('Unexpected animation, camera or skin')
    for name, node in nodes.items():
        if node.get('scale', [1, 1, 1]) != [1, 1, 1] or node.get('rotation', [0, 0, 0, 1]) != [0, 0, 0, 1]:
            raise RuntimeError(f'Unapplied transform: {name}')
        if node.get('translation', [0, 0, 0]) != [0, 0, 0]:
            raise RuntimeError(f'Nonzero mounting origin: {name}')
    # Check board/frame dimensions from the exported position accessors.
    board_primitives = gltf['meshes'][nodes['board']['mesh']]['primitives']
    board_accessors = [gltf['accessors'][p['attributes']['POSITION']] for p in board_primitives]
    low = [min(a['min'][i] for a in board_accessors) for i in range(3)]
    high = [max(a['max'][i] for a in board_accessors) for i in range(3)]
    expected_low, expected_high = [-.60, -.40, -.020], [.60, .40, 0]
    if any(abs(a - b) > 1e-7 for a, b in zip(low + high, expected_low + expected_high)):
        raise RuntimeError(f'Wrong frame bounds: {low}, {high}')
    # A full-board front is intentional; every additional component stays
    # outside the reserved WiFi rectangle, with clearance for its full radius.
    for x, y in PIN_LAYOUT:
        if .10 - .0045 <= x <= .40 + .0045 and -.10 - .0045 <= y <= .10 + .0045:
            raise RuntimeError('Pushpin enters reserved document area')
    # Derive the integration anchor from the actual exported cork primitive.
    mat_index = next(i for i, mat in enumerate(gltf['materials']) if mat['name'] == f'M_{ASSET_ID}_cork')
    primitive = next(p for p in gltf['meshes'][nodes['board']['mesh']]['primitives'] if p['material'] == mat_index)
    anchor = gltf['accessors'][primitive['attributes']['POSITION']]['min'][2]
    if abs(anchor - CORK_FRONT_Z) > 1e-7:
        raise RuntimeError(f'Cork plane moved: {anchor}')
    print('PASS geometry: 1200 x 800 x 20 mm frame; back Z=0; cork front Z=-0.0165; WiFi region clear; 3 applied meshes', flush=True)
    return anchor


def build(out_dir):
    reset_scene(SEED)
    cache = ROOT / 'assets/cache' / ASSET_ID
    cache.mkdir(parents=True, exist_ok=True)
    mats = surfaces(cache)
    groups = geometry(mats)
    bpy.context.view_layer.update()
    components = [obj for group in groups.values() for obj in group]
    textures = []
    for part, surf in mats.items():
        selected = [obj for obj in components if obj.data.materials[0] == surf.mat]
        textures.extend(bake_surface(part, surf, selected, cache))
    objects = [join_static(pieces, name) for name, pieces in groups.items()]
    for obj in objects:
        triangulate(obj)
    bpy.context.view_layer.update()
    glb_path = Path(out_dir).resolve() / f'{ASSET_ID}.glb'
    gltf = export_glb(glb_path, objects)
    anchor = validate_export(gltf)
    meta = write_metadata(ASSET_ID, ROOT / 'assets/meta' / f'{ASSET_ID}.json',
                          glb_path, objects, Path(__file__), textures, 'mount_plane_center', extra={
        'anchors_godot_m': {'cork_front_z': round(anchor, 9)},
        'origin_reference': 'centre of the back mounting face; Godot Z=0',
        'forward': 'Blender +Y -> Godot -Z',
        'board_outer_dimensions_godot_m': [1.20, .80, .020],
        'header_card_dimensions_m': [.30, .07, .00045],
        'header_card_center_godot_xy_m': [0, .33],
        'header_letter_cap_height_m': .030,
        'wifi_clear_area_godot_m': {'x': [.10, .40], 'y': [-.10, .10]},
        'pushpin_count': len(PIN_LAYOUT),
        'collision': None,
        'lettering': 'original bold sans stroke rasterizer; IT NOTICES only',
        'baking': {'engine': 'CYCLES', 'device': 'CPU', 'samples': 16, 'margin_px': 8,
                   'maps': 'procedural emission colour/RM; tangent normal; ray-traced AO in ORM R'},
        'render': {'engine': 'CYCLES', 'device': 'CPU', 'samples': 32, 'denoise': True, 'threads': 4},
        'glb_path': str(glb_path.relative_to(ROOT)) if glb_path.is_relative_to(ROOT) else str(glb_path),
    })
    if meta['triangles'] > 20000 or len(meta['materials']) != 4:
        raise RuntimeError('Request budget exceeded')
    render_previews(ASSET_ID, ROOT / 'assets/previews', objects, views={
        'front': {'position': (0, 2.8, 0), 'target': (0, .015, 0), 'scale': 1.38},
        'iso': {'position': (1.4, 2.6, 1.15), 'target': (0, .015, 0), 'scale': 1.46},
        'detail': {'position': (0, 1.4, .70), 'target': (0, .017, .29), 'scale': .56},
    }, seed=SEED)
    print(f'ASSET BUILT: {glb_path}; {meta["triangles"]} triangles; {len(meta["materials"])} materials', flush=True)
    return glb_path


if __name__ == '__main__':
    run_cli(build, __doc__)
