"""Ladder tray kit: folded galvanised steel, mixed Cat6/power and velcro drop.

Owner-made, deterministic Blender 5.2 script; no network or external assets.
Structural/baking references: accepted exit_door_maglock and exit_keypad_6.
Run tools/blender/build_assets.sh cable_tray_kit (flock, CPU, four threads).
All geometry below is specified in Godot metres, then converted to Blender.
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
from common.materials import base_texture, material, normal_texture, orm_texture
from common.preview import render_previews
from common.scene import reset_scene

ASSET_ID = 'cable_tray_kit'
SEED = 621026


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

    def finish(self, color, roughness, height, strength, distance):
        self.color, self.roughness = color, roughness
        self.set(self.bsdf.inputs['Base Color'], color)
        self.set(self.bsdf.inputs['Roughness'], roughness)
        bump = self.node('ShaderNodeBump', Height=height, Strength=strength, Distance=distance)
        self.tree.links.new(bump.outputs['Normal'], self.bsdf.inputs['Normal'])



def bake_surface(part, surf, components, cache):
    """Unwrap one material globally, bake four passes, transfer exact UV loops.

    The temporary mesh uses world coordinates, so grain/wear are continuous.
    Islands never overlap; packing and baking both reserve an 8 pixel margin.
    Only the AO pass uses rays. Base colour / packed RM are emission bakes;
    normals are Cycles tangent NORMAL bakes of the procedural microstructure.
    """
    size = 1024
    vertices, faces, smooth, colors, thread_axes = [], [], [], [], []
    for obj in components:
        offset = len(vertices)
        vertices.extend(tuple(obj.matrix_world @ v.co) for v in obj.data.vertices)
        faces.extend(tuple(offset + v for v in poly.vertices) for poly in obj.data.polygons)
        smooth.extend(poly.use_smooth for poly in obj.data.polygons)
        colors.extend([(*obj.get('jacket_color', (.1, .1, .1)), obj.get('thread_mask', 0))] * len(obj.data.loops))
        centre = obj.matrix_world @ obj.data.vertices[0].co if obj.get('thread_mask') else Vector((0, 0, 0))
        if obj.get('thread_mask'):
            # Mean of the first tube ring is its exact vertical thread axis.
            centre = sum((obj.matrix_world @ v.co for v in obj.data.vertices[:12]), Vector()) / 12
        thread_axes.extend([tuple(centre)] * len(obj.data.loops))
    temp = mesh_object('bake_surface-noimp', vertices, faces, surf.mat)
    for poly, flag in zip(temp.data.polygons, smooth):
        poly.use_smooth = flag
    attribute = temp.data.color_attributes.new(name='jacket_color', type='FLOAT_COLOR', domain='CORNER')
    attribute.data.foreach_set('color', array('f', (ch for color in colors for ch in color)))
    axis_attr = temp.data.attributes.new(name='thread_axis', type='FLOAT_VECTOR', domain='CORNER')
    axis_attr.data.foreach_set('vector', array('f', (ch for axis in thread_axes for ch in axis)))
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
    # Soft ray-traced crevice occlusion; preserve readability in dim light.
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


def surfaces():
    metal = Surface('metal', (.48, .51, .53), .40, 1)
    # Hot-dip zinc spangle, oxide bloom, fine handling abrasion; no rust flakes.
    cells = metal.node('ShaderNodeTexVoronoi', Vector=metal.scaled((210, 210, 210)), Scale=1)
    cell_value = metal.node('ShaderNodeRGBToBW', Color=cells.outputs['Color']).outputs[0]
    grain = metal.noise((3100, 3100, 3100))
    bloom = metal.noise((15, 17, 12))
    scratches = metal.math('MULTIPLY', metal.math('GREATER_THAN', metal.noise((8, 1400, 550)), .73),
                           metal.math('GREATER_THAN', metal.noise((33, 33, 33)), .56))
    color = metal.mix(cell_value, (.39, .415, .435, 1), (.52, .55, .57, 1))
    color = metal.mix(metal.math('MULTIPLY', bloom, .15), color, (.30, .33, .34, 1))
    color = metal.mix(metal.math('MULTIPLY', scratches, .40), color, (.65, .67, .68, 1))
    rough = metal.math('ADD', .30, metal.math('MULTIPLY', cell_value, .22))
    rough = metal.math('ADD', rough, metal.math('MULTIPLY', bloom, .08))
    # Rod-only helical M8 threads, transferred to the tangent normal atlas.
    attr = metal.node('ShaderNodeVertexColor')
    attr.layer_name = 'jacket_color'
    thread = metal.math('MULTIPLY', metal.axes.outputs['Z'], math.tau / .002)
    axis_attr = metal.node('ShaderNodeAttribute')
    axis_attr.attribute_name = 'thread_axis'
    relative = metal.node('ShaderNodeVectorMath')
    relative.operation = 'SUBTRACT'
    metal.set(relative.inputs[0], metal.position)
    metal.set(relative.inputs[1], axis_attr.outputs['Vector'])
    local = metal.node('ShaderNodeSeparateXYZ', Vector=relative.outputs['Vector'])
    angle = metal.math('ARCTAN2', local.outputs['Y'], local.outputs['X'])
    thread = metal.math('SINE', metal.math('SUBTRACT', thread, angle))
    height = metal.math('ADD', grain, metal.math('MULTIPLY',
                        metal.math('MULTIPLY', attr.outputs['Alpha'], thread), 7))
    metal.finish(color, rough, height, .40, .00011)

    cables = Surface('cables', (.018, .075, .22), .56)
    tint = cables.node('ShaderNodeVertexColor')
    tint.layer_name = 'jacket_color'
    grain = cables.noise((3800, 3800, 3800))
    rub = cables.math('GREATER_THAN', cables.noise((35, 210, 38)), .70)
    dirt = cables.noise((32, 29, 34))
    color = cables.mix(cables.math('MULTIPLY', dirt, .11), tint.outputs['Color'], (.035, .034, .033, 1))
    color = cables.mix(cables.math('MULTIPLY', rub, .12), color, (.31, .32, .33, 1))
    rough = cables.math('SUBTRACT', cables.math('ADD', .48, cables.math('MULTIPLY', grain, .15)),
                         cables.math('MULTIPLY', rub, .16))
    cables.finish(color, rough, grain, .24, .000025)

    velcro = Surface('velcro', (.012, .013, .015), .88)
    axes = velcro.axes.outputs
    warp = velcro.math('SINE', velcro.math('MULTIPLY', axes['X'], 23000))
    weft = velcro.math('SINE', velcro.math('MULTIPLY', axes['Z'], 23000))
    weave = velcro.math('MULTIPLY', warp, weft)
    fibers = velcro.noise((5800, 5800, 5800))
    color = velcro.mix(fibers, (.008, .009, .011, 1), (.023, .025, .028, 1))
    velcro.finish(color, .86, velcro.math('ADD', weave, fibers), .50, .00006)
    return {'metal': metal, 'cables': cables, 'velcro': velcro}


def slab(name, dimensions, position, mat, bevel=.0005):
    # Godot W,H,D -> Blender W,D,H. Applied dimensions, zero rotation.
    return box(name, (dimensions[0], dimensions[2], dimensions[1]), mat,
               godot(position), bevel=bevel, segments=1)


def extrude(name, profile, start, end, mat, axis='X', bevel=0):
    """Closed sheet profile extruded along X or Z in Godot, no zero-thickness faces."""
    def point(d, pair):
        return godot((d, pair[0], pair[1]) if axis == 'X' else (pair[0], pair[1], d))
    count = len(profile)
    vertices = [point(d, p) for d in (start, end) for p in profile]
    faces = [(i, (i + 1) % count, (i + 1) % count + count, i + count) for i in range(count)]
    faces += [tuple(reversed(range(count))), tuple(range(count, count * 2))]
    obj = mesh_object(name, vertices, faces, mat)
    triangulate(obj)
    if bevel:
        active(obj)
        mod = obj.modifiers.new('fold_edge_radius', 'BEVEL')
        mod.width, mod.segments = bevel, 1
        bpy.ops.object.modifier_apply(modifier=mod.name)
        mod = obj.modifiers.new('sheet_normals', 'WEIGHTED_NORMAL')
        mod.keep_sharp = True
        bpy.ops.object.modifier_apply(modifier=mod.name)
    return obj


def tube(name, points, radius, mat, sides=8, tint=None):
    """Parallel-transport tube with fan caps. No curve/modifier left at export."""
    points = [Vector(godot(p)) for p in points]
    vertices, faces = [], []
    old_u = None
    for j, point in enumerate(points):
        tangent = (points[min(j + 1, len(points) - 1)] - points[max(j - 1, 0)]).normalized()
        if old_u is None:
            u = tangent.cross(Vector((0, 0, 1)))
            if u.length < .1:
                u = tangent.cross(Vector((0, 1, 0)))
        else:
            u = old_u - tangent * old_u.dot(tangent)
        u.normalize()
        v = tangent.cross(u).normalized()
        old_u = u
        for i in range(sides):
            angle = math.tau * i / sides
            vertices.append(tuple(point + radius * (math.cos(angle) * u + math.sin(angle) * v)))
    for j in range(len(points) - 1):
        for i in range(sides):
            k = (i + 1) % sides
            faces.append((j * sides + i, j * sides + k, (j + 1) * sides + k, (j + 1) * sides + i))
    for start, reverse in ((0, True), ((len(points) - 1) * sides, False)):
        for i in range(1, sides - 1):
            face = (start, start + i, start + i + 1)
            faces.append(tuple(reversed(face)) if reverse else face)
    obj = mesh_object(name, vertices, faces, mat)
    for face in obj.data.polygons:
        face.use_smooth = len(face.vertices) == 4
    if tint:
        obj['jacket_color'] = tint
    return obj


def annulus(name, x, z, low, high, outer, inner, mat, sides=12):
    # Hollow washers/hex nuts. Threaded rods pass through real bores.
    vertices = [godot((x + r * math.cos(i * math.tau / sides), y,
                      z + r * math.sin(i * math.tau / sides)))
                for y, r in ((low, outer), (high, outer), (low, inner), (high, inner))
                for i in range(sides)]
    faces = []
    for i in range(sides):
        k = (i + 1) % sides
        faces.extend([(i, k, sides + k, sides + i),
                      (2 * sides + k, 2 * sides + i, 3 * sides + i, 3 * sides + k),
                      (k, i, 2 * sides + i, 2 * sides + k),
                      (sides + i, sides + k, 3 * sides + k, 3 * sides + i)])
    return mesh_object(name, vertices, faces, mat)


# Linear RGB jacket pigments, all baked into one material/atlas.
JACKETS = [(.012, .060, .22), (.015, .10, .30), (.22, .245, .26),
           (.43, .31, .018), (.011, .015, .020), (.018, .075, .24),
           (.28, .30, .315), (.012, .10, .25), (.016, .020, .026),
           (.018, .075, .24), (.20, .23, .25), (.014, .090, .28)]


def strap(name, centre, rx, rz, width, mat, vertical=False, phase=0):
    """Closed 1.1 mm fabric band with a separately folded overlap tail."""
    sides = 16
    x, y, z = centre
    verts = []
    for side in (-1, 1):
        for inner in (False, True):
            for i in range(sides):
                a = math.tau * i / sides + phase
                r1, r2 = rx - (.0011 if inner else 0), rz - (.0011 if inner else 0)
                p = (x + r1 * math.cos(a), y + side * width / 2, z + r2 * math.sin(a)) if vertical else (
                    x + side * width / 2, y + r1 * math.cos(a), z + r2 * math.sin(a))
                verts.append(godot(p))
    faces = []
    for i in range(sides):
        k = (i + 1) % sides
        faces.extend([(i, k, 2 * sides + k, 2 * sides + i),
                      (sides + k, sides + i, 3 * sides + i, 3 * sides + k),
                      (k, i, sides + i, sides + k),
                      (2 * sides + i, 2 * sides + k, 3 * sides + k, 3 * sides + i)])
    obj = mesh_object(name, verts, faces, mat)
    for face in obj.data.polygons:
        face.use_smooth = True
    tail = slab(name + '_overlap', (.015, width, .002) if vertical else (width, .002, .020),
                (x + rx + .005, y, z) if vertical else (x, y + rx + .001, z + .012), mat, .0003)
    return [obj, tail]


def tray(length, mats):
    metal, cables, velcro = [mats[k].mat for k in ('metal', 'cables', 'velcro')]
    pieces = []
    # Inward-facing 100 mm C channels, 2 mm sheet with 22 mm lips.
    for side in (-1, 1):
        outer, inner = side * .150, side * .128
        profile = [(0, outer), (0, inner), (.002, inner), (.002, outer - side * .002),
                   (.098, outer - side * .002), (.098, inner), (.100, inner), (.100, outer)]
        pieces.append(extrude('folded_side_channel', profile, -length / 2, length / 2, metal, bevel=.0004))
    # Real open-bottom hat-section rungs on 200 mm centres.
    rung_profile = [(-.021, .009), (-.013, .009), (-.013, .023), (.013, .023),
                    (.013, .009), (.021, .009), (.021, .011), (.015, .011),
                    (.015, .025), (-.015, .025), (-.015, .011), (-.021, .011)]
    rungs = int(length / .2)
    for i in range(rungs):
        x = -length / 2 + .1 + i * .2
        profile = [(a + x, b) for a, b in rung_profile]
        pieces.append(extrude('pressed_rung', profile, -.148, .148, metal, axis='Z', bevel=.0004))
    pieces.append(slab('trapeze_bearer', (.045, .009, .294), (0, .0065, 0), metal))
    for z in (-.137, .137):
        rod = tube('threaded_hanger', [(0, .007, z), (0, .350, z)], .004, metal, sides=12)
        rod['thread_mask'] = 1
        pieces.append(rod)
        for low, high, radius, sides in ((.011, .013, .009, 12), (.013, .020, .0074, 6),
                                         (.323, .330, .0074, 6), (.330, .332, .009, 12)):
            pieces.append(annulus('hanger_nut' if sides == 6 else 'hanger_washer', 0, z, low, high,
                                  radius, .00415, metal, sides))
    # Recessed end splice plates, with domed rivet heads inside the envelope.
    for side in (-1, 1):
        for end in (-1, 1):
            x = end * (length / 2 - .043)
            pieces.append(slab('splice_plate', (.082, .055, .0018), (x, .055, side * .1468), metal))
            for dx in (-.026, .026):
                pieces.append(tube('splice_rivet', [(x + dx, .055, side * .147),
                                                    (x + dx, .055, side * .1493)], .0031, metal, sides=10))
    # Ten parallel conductors and two slightly raised service runs.
    for i, color in enumerate(JACKETS):
        count = 15 if length == 1 else 25
        points = []
        z0 = (i - 4.5) * .013 if i < 10 else (i - 10.5) * .016
        y0 = .0302 if i < 10 else .040
        radius = .0043 if i in (4, 8) else .0032
        for j in range(count):
            t = j / (count - 1)
            x = length * (t - .5)
            # Zero slope at the cut ends; modest drift and settled cable slack.
            ease = math.sin(math.pi * t) ** 2
            z = z0 + .0023 * ease * math.sin(t * math.tau + i * .68)
            y = y0 + .0012 * ease * (1 + math.sin(t * math.tau * length + i))
            points.append((x, y, z))
        pieces.append(tube('cat6' if radius < .004 else 'power', points, radius, cables, tint=color))
    for x in (-length * .31, length * .31):
        pieces.extend(strap('reusable_cable_tie', (x, .032, 0), .013, .066, .012, velcro))
    return pieces


def drop(mats):
    pieces = []
    for i, color in enumerate(JACKETS):
        # Quarter-turn waterfall then a free-hanging metre cable bundle.
        xoff, zoff = (i % 3 - 1) * .010, (i // 3 - 1.5) * .011
        radius = .0043 if i in (4, 8) else .0032
        bend = .112 + xoff
        points = []
        for j in range(8):
            a = j / 7 * math.pi / 2
            points.append((-bend + bend * math.sin(a) + xoff, .996 - bend + bend * math.cos(a), zoff))
        upper_y = .996 - bend
        for j in range(1, 22):
            t = j / 21
            # More play below the last tie; straight, square cut ends at y=0.
            sway = math.sin(math.pi * t) ** 2
            x = xoff + .011 * sway * math.sin(t * math.pi * 2 + i * .19)
            z = zoff + .0045 * sway * math.sin(t * math.pi * 2 + i * .41)
            points.append((x, upper_y * (1 - t), z))
        pieces.append(tube('drop_jacket', points, radius, mats['cables'].mat, tint=color))
    for y in (.15, .43, .72):
        pieces.extend(strap('drop_velcro', (0, y, 0), .027, .025, .018, mats['velcro'].mat, vertical=True))
    # Base-centre in X/Z; all cut ends on the y=0 plane.
    bpy.context.view_layer.update()
    coords = [obj.matrix_world @ v.co for obj in pieces for v in obj.data.vertices]
    cx = (min(p.x for p in coords) + max(p.x for p in coords)) / 2
    cy = (min(p.y for p in coords) + max(p.y for p in coords)) / 2
    bottom, top = min(p.z for p in coords), max(p.z for p in coords)
    for obj in pieces:
        obj.location -= Vector((cx, cy, 0))
        for vertex in obj.data.vertices:
            world_y = vertex.co.z + obj.location.z
            vertex.co.z = (world_y - bottom) / (top - bottom) - obj.location.z
    return pieces


def bounds_godot(obj):
    coords = [obj.matrix_world @ v.co for v in obj.data.vertices]
    return {'min': [round(min(p.x for p in coords), 7), round(min(p.z for p in coords), 7),
                    round(-max(p.y for p in coords), 7)],
            'max': [round(max(p.x for p in coords), 7), round(max(p.z for p in coords), 7),
                    round(-min(p.y for p in coords), 7)]}


def build(out_dir):
    reset_scene(SEED)
    cache = ROOT / 'assets/cache' / ASSET_ID
    cache.mkdir(parents=True, exist_ok=True)
    mats = surfaces()
    groups = {'tray_1m': tray(1.0, mats), 'tray_2m': tray(2.0, mats), 'drop_1m': drop(mats)}
    # Temporarily space parts during baking: prevents the co-located kit from
    # casting spurious AO on itself. Exported origins are all exactly zero.
    offsets = {'tray_1m': Vector((0, 0, 0)), 'tray_2m': Vector((0, 2, 0)), 'drop_1m': Vector((0, 4, 0))}
    for name, pieces in groups.items():
        for obj in pieces:
            obj.location += offsets[name]
            triangulate(obj)
    bpy.context.view_layer.update()
    components = [o for pieces in groups.values() for o in pieces]
    triangles = sum(len(o.data.polygons) for o in components)
    print(f'GEOMETRY {triangles} triangles; 3 parts; folded sheet, 12 cable runs each, M8 hangers', flush=True)
    if triangles > 20000:
        raise RuntimeError(f'Geometry budget exceeded: {triangles}')
    textures = []
    for part, surf in mats.items():
        selected = [o for o in components if o.data.materials[0] == surf.mat]
        textures.extend(bake_surface(part, surf, selected, cache))
    objects = []
    for name, pieces in groups.items():
        for obj in pieces:
            obj.location -= offsets[name]
        objects.append(join_static(pieces, name, origin=(0, 0, 0)))
    for obj in objects:
        triangulate(obj)
    bpy.context.view_layer.update()
    bounds = {o.name: bounds_godot(o) for o in objects}
    for obj in objects:
        b = bounds[obj.name]
        if obj.location.length > 1e-9 or abs(b['min'][1]) > .001:
            raise RuntimeError(f'Origin/base plane mismatch: {obj.name}: {b}')
        if any(abs(b['min'][i] + b['max'][i]) > .001 for i in (0, 2)):
            raise RuntimeError(f'Part is not base-centred: {obj.name}: {b}')
    glb_path = Path(out_dir).resolve() / f'{ASSET_ID}.glb'
    gltf = export_glb(glb_path, objects)
    nodes = {n['name']: n for n in gltf['nodes'] if 'mesh' in n}
    if set(nodes) != set(groups) or gltf.get('animations') or gltf.get('cameras'):
        raise RuntimeError('Unexpected export names/animation/camera')
    for name, node in nodes.items():
        if any(abs(v) > 1e-8 for v in node.get('translation', [0, 0, 0])) or node.get('scale', [1, 1, 1]) != [1, 1, 1] or node.get('rotation', [0, 0, 0, 1]) != [0, 0, 0, 1]:
            raise RuntimeError(f'Unapplied transform on {name}')
    meta = write_metadata(ASSET_ID, ROOT / 'assets/meta' / f'{ASSET_ID}.json', glb_path,
                          objects, Path(__file__), textures, 'base_center', extra={
        'part_bounds_godot_m': bounds,
        'part_origins_godot_m': {name: [0, 0, 0] for name in groups},
        'origin_reference': 'Every part at zero: tray underside y=0; drop bottom cut ends y=0',
        'forward': 'Straight tray lengths along Godot X; Blender +Y -> Godot -Z',
        'collision': 'none',
        'cable_runs_per_part': 12,
        'rung_pitch_m': .2,
        'baking': {'engine': 'CYCLES', 'device': 'CPU', 'samples': 16, 'margin_px': 8,
                   'maps': 'procedural base colour, tangent normal, ray AO packed with roughness and metallic'},
        'render': {'engine': 'CYCLES', 'device': 'CPU', 'samples': 32, 'denoise': True, 'threads': 4},
        'preview_layout_only_godot_m': {'tray_1m': [0, .68, .25], 'tray_2m': [0, .12, .25], 'drop_1m': [1.32, .12, .15]},
        'glb_path': str(glb_path.relative_to(ROOT)) if glb_path.is_relative_to(ROOT) else str(glb_path),
    })
    if meta['triangles'] > 20000 or len(meta['materials']) != 3:
        raise RuntimeError('Export budget exceeded')
    print('PASS kit: all three mesh transforms at zero; tray bases y=0; no collision or animation', flush=True)
    preview_offsets = {name: Vector(godot(pos)) for name, pos in meta['preview_layout_only_godot_m'].items()}
    for obj in objects:
        obj.location += preview_offsets[obj.name]
    bpy.context.view_layer.update()
    try:
        render_previews(ASSET_ID, ROOT / 'assets/previews', objects, views={
            'front': {'position': godot((.2, 3.0, -3.2)), 'target': godot((.15, .57, .05)), 'scale': 2.72},
            'iso': {'position': godot((2.8, 2.8, -3.4)), 'target': godot((.15, .60, .04)), 'scale': 2.72},
            'detail': {'position': godot((0, .85, .95)), 'target': godot((0, .155, .25)), 'scale': .53},
        }, seed=SEED)
    finally:
        for obj in objects:
            obj.location -= preview_offsets[obj.name]
    print(f'ASSET BUILT: {glb_path}; {meta["triangles"]} triangles; {len(meta["materials"])} materials', flush=True)
    return glb_path


if __name__ == '__main__':
    run_cli(build, __doc__)
