"""Contract-office desk, baked PBR surfaces and a fully modelled sliding tray.

Deterministic Blender 5.2 headless build; no network or external assets.
Run through tools/blender/build_assets.sh desk_3drawer (serialized, 4 threads).
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

ASSET_ID = 'desk_3drawer'
SEED = 31026
DRAWER_ORIGIN = (-.42, .62, -.395)


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

    def ring(self, x, y, radius):
        dx = self.math('SUBTRACT', self.axes.outputs['X'], x)
        dy = self.math('SUBTRACT', self.axes.outputs['Y'], y)
        r = self.math('SQRT', self.math('ADD', self.math('MULTIPLY', dx, dx),
                                      self.math('MULTIPLY', dy, dy)))
        distance = self.math('ABSOLUTE', self.math('SUBTRACT', r, radius))
        ring = self.math('MAXIMUM', 0, self.math('SUBTRACT', 1, self.math('DIVIDE', distance, .0017)))
        # Broken, nearly invisible evaporation mark, only on the top face.
        broken = self.math('MULTIPLY', ring, self.noise((120, 120, 10)))
        return self.math('MULTIPLY', broken,
                         self.math('GREATER_THAN', self.axes.outputs['Z'], .755))

    def finish(self, color, roughness, height, strength, distance):
        self.color, self.roughness = color, roughness
        self.set(self.bsdf.inputs['Base Color'], color)
        self.set(self.bsdf.inputs['Roughness'], roughness)
        bump = self.node('ShaderNodeBump', Height=height, Strength=strength, Distance=distance)
        self.tree.links.new(bump.outputs['Normal'], self.bsdf.inputs['Normal'])


def surfaces():
    top = Surface('top', (.40, .38, .34), .43)
    grain = top.noise((2.8, 210, 50), detail=4)
    pores = top.noise((12, 1600, 80), detail=2)
    wave = top.node('ShaderNodeTexWave', Vector=top.scaled((.30, 1, 1)), Scale=72,
                    Distortion=8, Detail=4, **{'Detail Scale': .75, 'Detail Roughness': .65})
    wave.bands_direction = 'Y'
    fibres = top.math('ADD', top.math('MULTIPLY', grain, .78),
                      top.math('MULTIPLY', wave.outputs['Fac'], .22))
    wood = top.ramp(fibres, [(.12, (.17, .163, .147, 1)),
                              (.38, (.285, .279, .258, 1)),
                              (.60, (.40, .394, .364, 1)),
                              (.86, (.47, .463, .427, 1))])
    wood = top.mix(top.math('MULTIPLY', top.noise((1.4, 14, 8)), .18),
                   wood, (.22, .217, .201, 1))
    normal = top.node('ShaderNodeNewGeometry').outputs['Normal']
    normal_z = top.node('ShaderNodeSeparateXYZ', Vector=normal).outputs['Z']
    side = top.math('LESS_THAN', top.math('ABSOLUTE', normal_z), .80)
    # Dark 2 mm ABS band, including the physically rounded top perimeter.
    color = top.mix(side, wood, (.040, .042, .039, 1))
    rings = top.math('MAXIMUM', top.ring(.44, -.16, .039), top.ring(.56, -.19, .041))
    color = top.mix(top.math('MULTIPLY', rings, .075), color, (.18, .17, .15, 1))
    wrist = top.math('GREATER_THAN', top.axes.outputs['Y'], .359)
    wrist = top.math('MULTIPLY', wrist, top.noise((22, 420, 10)))
    color = top.mix(top.math('MULTIPLY', wrist, .07), color, (.16, .165, .15, 1))
    rough = top.math('ADD', .37, top.math('MULTIPLY', pores, .15))
    rough = top.math('SUBTRACT', rough, top.math('MULTIPLY', wrist, .06))
    rough = top.math('ADD', rough, top.math('MULTIPLY', rings, .10))
    top.finish(color, rough, top.math('ADD', fibres, top.math('MULTIPLY', pores, .20)), .34, .00022)

    carcass = Surface('carcass', (.47, .455, .418), .53)
    stipple = carcass.noise((900, 900, 900), detail=2)
    broad = carcass.noise((8, 8, 8), detail=2)
    coat = carcass.mix(broad, (.335, .323, .299, 1), (.365, .351, .324, 1))
    coat = carcass.mix(carcass.math('MULTIPLY', stipple, .035), coat, (.30, .29, .27, 1))
    # Plinth wear is localised to the recessed bottom cabinet, not every leg.
    low = carcass.math('LESS_THAN', carcass.axes.outputs['Z'], .045)
    pedestal = carcass.math('LESS_THAN', carcass.axes.outputs['X'], -.1)
    front = carcass.math('GREATER_THAN', carcass.axes.outputs['Y'], .28)
    kicks = carcass.math('MULTIPLY', low, carcass.math('MULTIPLY', pedestal, front))
    kicks = carcass.math('MULTIPLY', kicks, carcass.noise((35, 120, 75)))
    coat = carcass.mix(carcass.math('MULTIPLY', kicks, .23), coat, (.15, .15, .14, 1))
    rough = carcass.math('ADD', .48, carcass.math('MULTIPLY', stipple, .13))
    carcass.finish(coat, rough, stipple, .22, .00011)

    metal = Surface('metal', (.62, .65, .66), .28, metallic=1)
    brush = metal.noise((14, 3800, 3800), detail=2)
    brushed = metal.mix(brush, (.48, .51, .53, 1), (.66, .69, .71, 1))
    metal.finish(brushed, metal.math('ADD', .24, metal.math('MULTIPLY', brush, .16)),
                 brush, .25, .000055)

    interior = Surface('interior', (.64, .64, .61), .58)
    fine = interior.noise((1200, 1200, 1200), detail=2)
    inside = interior.mix(fine, (.59, .598, .57, 1), (.65, .655, .63, 1))
    interior.finish(inside, interior.math('ADD', .53, interior.math('MULTIPLY', fine, .11)),
                    fine, .16, .000075)
    return {part: surf for part, surf in [('top', top), ('carcass', carcass),
                                        ('metal', metal), ('interior', interior)]}


def cylinder(name, a, b, radius, mat, count=40):
    """Closed round bar, with a real rounded end profile; endpoints in Godot."""
    a, b = Vector(godot(a)), Vector(godot(b))
    axis = (b - a).normalized()
    u = axis.cross(Vector((0, 0, 1)))
    if u.length < .01:
        u = axis.cross(Vector((0, 1, 0)))
    u.normalize()
    v = axis.cross(u).normalized()
    length = (b - a).length
    roundover = radius * .35
    profile = [(0, radius - roundover), (.293 * roundover, radius - .293 * roundover),
               (roundover, radius), (length - roundover, radius),
               (length - .293 * roundover, radius - .293 * roundover),
               (length, radius - roundover)]
    verts = [tuple(a + axis * d + r * (math.cos(i * math.tau / count) * u +
                                     math.sin(i * math.tau / count) * v))
             for d, r in profile for i in range(count)]
    faces = []
    for ring in range(len(profile) - 1):
        for i in range(count):
            j = (i + 1) % count
            faces.append((ring * count + i, ring * count + j,
                          (ring + 1) * count + j, (ring + 1) * count + i))
    # Explicit fan caps: no n-gons go into the UV bake.
    for start, reverse in [(0, True), ((len(profile) - 1) * count, False)]:
        for i in range(1, count - 1):
            face = (start, start + i, start + i + 1)
            faces.append(tuple(reversed(face)) if reverse else face)
    obj = mesh_object(name, verts, faces, mat)
    for face in obj.data.polygons:
        face.use_smooth = len(face.vertices) == 4
    return obj


def geometry(mats):
    groups = {name: [] for name in ('body', 'drawer_top', 'drawer_mid', 'drawer_file')}
    def slab(part, label, dims, pos, finish='carcass', radius=.0012, segments=5):
        obj = box(label, (dims[0], dims[2], dims[1]), mats[finish].mat,
                  godot(pos), bevel=radius, segments=segments)
        groups[part].append(obj)
        return obj

    slab('body', 'desktop', (1.60, .04, .75), (0, .74, 0), 'top', .002, 6)
    for x, label in [(-.78, 'right_end'), (.78, 'left_end')]:
        slab('body', label, (.04, .72, .70), (x, .36, 0), radius=.0015, segments=6)
    slab('body', 'modesty', (1.52, .40, .02), (0, .50, .325))
    for x, label in [(-.73, 'pedestal_right'), (-.11, 'pedestal_left')]:
        slab('body', label, (.02, .68, .685), (x, .38, -.0325))
    slab('body', 'pedestal_back', (.60, .68, .02), (-.42, .38, .30))
    slab('body', 'pedestal_upper_rail', (.60, .026, .02), (-.42, .707, -.365))
    slab('body', 'kick_plinth', (.62, .04, .61), (-.42, .02, -.015), radius=.0015)
    # Shelves remain below the moving tray, leaving 4 mm vertical clearance.
    slab('body', 'top_shelf', (.60, .012, .62), (-.42, .540, -.015), 'interior', .0006)
    slab('body', 'mid_shelf', (.60, .012, .62), (-.42, .390, -.015), 'interior', .0006)
    # Static telescopic-slide outer channels stay strictly outside the tray.
    for x in (-.718, -.122):
        slab('body', 'slide_outer', (.006, .022, .43), (x, .595, -.145), 'metal', .0006)
        slab('drawer_top', 'slide_inner', (.003, .018, .40),
             (x + (.004 if x < -.42 else -.004), .595, -.145), 'metal', .0004)

    # Rear face is rebated 5 mm. It preserves the 20 mm outer panel thickness
    # and gives precisely 460 mm of clear tray depth behind z=-.380.
    slab('drawer_top', 'front_top', (.60, .14, .015), (-.42, .62, -.3875))
    for x in (-.715, -.125):
        slab('drawer_top', 'front_rebate_side', (.01, .138, .005), (x, .62, -.3775), radius=.0003)
    for y in (.554, .684):
        slab('drawer_top', 'front_rebate_edge', (.58, .008, .005), (-.42, y, -.3775), radius=.0003)
    slab('drawer_top', 'tray_floor', (.58, .01, .47), (-.42, .555, -.145), 'interior', .00035)
    for x in (-.705, -.135):
        slab('drawer_top', 'tray_side', (.01, .11, .47), (x, .615, -.145), 'interior', .00045)
    slab('drawer_top', 'tray_back', (.56, .11, .01), (-.42, .615, .085), 'interior', .00045)
    slab('drawer_mid', 'front_mid', (.60, .14, .02), (-.42, .472, -.385))
    slab('drawer_file', 'front_file', (.60, .342, .02), (-.42, .223, -.385))
    for part, y in [('drawer_top', .62), ('drawer_mid', .472), ('drawer_file', .295)]:
        for x in (-.484, -.356):
            groups[part].append(cylinder('handle_post', (x, y, -.395), (x, y, -.420),
                                         .005, mats['metal'].mat, count=32))
            groups[part].append(cylinder('handle_rose', (x, y, -.395), (x, y, -.398),
                                         .008, mats['metal'].mat, count=32))
        groups[part].append(cylinder('handle_bar', (-.505, y, -.420), (-.335, y, -.420),
                                     .006, mats['metal'].mat, count=48))
    for objects in groups.values():
        for obj in objects:
            triangulate(obj)
    return groups


def bake_surface(part, surf, components, cache):
    """Unwrap one material globally, bake four passes, transfer exact UV loops.

    The temporary mesh uses world coordinates, so grain/wear are continuous.
    Islands never overlap; packing and baking both reserve an 8 pixel margin.
    Only the AO pass uses rays. Base colour / packed RM are emission bakes;
    normals are Cycles tangent NORMAL bakes of the procedural microstructure.
    """
    size = 2048 if part in ('top', 'carcass') else 1024
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


def validate_geometry(objects, gltf, shift):
    expected = {'body', 'drawer_top', 'drawer_mid', 'drawer_file'}
    nodes = {node['name']: node for node in gltf['nodes'] if 'mesh' in node}
    if set(nodes) != expected or gltf.get('animations') or gltf.get('cameras'):
        raise RuntimeError('Unexpected parts, animations or cameras')
    for name, node in nodes.items():
        if node.get('scale', [1, 1, 1]) != [1, 1, 1] or node.get('rotation', [0, 0, 0, 1]) != [0, 0, 0, 1]:
            raise RuntimeError(f'Unapplied transform: {name}')
    anchor = nodes['drawer_top'].get('translation', [0, 0, 0])
    expected_anchor = Vector(DRAWER_ORIGIN) + Vector((shift.x, shift.z, -shift.y))
    if any(abs(a - b) > 1e-7 for a, b in zip(anchor, expected_anchor)):
        raise RuntimeError(f'Incorrect drawer origin: {anchor}')
    body = next(obj for obj in objects if obj.name == 'body')
    # Interior and swept travel bounds in Blender: open tray extends toward +Y.
    lo, hi = Vector((-.7, -.08, .56)) + shift, Vector((-.14, .78, .67)) + shift
    for poly in body.data.polygons:
        vertices = [body.matrix_world @ body.data.vertices[i].co for i in poly.vertices]
        if all(max(v[axis] for v in vertices) > lo[axis] + 1e-5 and
               min(v[axis] for v in vertices) < hi[axis] - 1e-5 for axis in range(3)):
            raise RuntimeError('Static body enters tray or 400 mm swept clearance')
    print('PASS geometry: exact drawer origin; empty tray and 400 mm swept clearance; applied transforms')
    return [round(v, 9) for v in anchor]


def build(out_dir):
    reset_scene(SEED)
    cache = ROOT / 'assets/cache' / ASSET_ID
    cache.mkdir(parents=True, exist_ok=True)
    mats = surfaces()
    groups = geometry(mats)
    bpy.context.view_layer.update()
    components = [obj for objects in groups.values() for obj in objects]
    textures = []
    for part, surf in mats.items():
        selected = [obj for obj in components if obj.data.materials[0] == surf.mat]
        textures.extend(bake_surface(part, surf, selected, cache))
    # 2026-10-02 revision: centre the complete closed asset, including pulls.
    # Rebase only after baking, so procedural textures retain their coordinates.
    points = [obj.matrix_world @ Vector(corner) for obj in components for corner in obj.bound_box]
    minimum = Vector(tuple(min(p[i] for p in points) for i in range(3)))
    maximum = Vector(tuple(max(p[i] for p in points) for i in range(3)))
    shift = Vector((-(minimum.x + maximum.x) / 2,
                    -(minimum.y + maximum.y) / 2, -minimum.z))
    for obj in components:
        obj.location += shift
    bpy.context.view_layer.update()
    objects = []
    for name, pieces in groups.items():
        origin = godot(DRAWER_ORIGIN) if name == 'drawer_top' else (
            godot((-.42, .472, -.395)) if name == 'drawer_mid' else
            godot((-.42, .223, -.395)) if name == 'drawer_file' else (0, 0, 0))
        if name != 'body':
            origin = Vector(origin) + shift
        obj = join_static(pieces, name, origin=origin)
        triangulate(obj)
        objects.append(obj)
    bpy.context.view_layer.update()
    glb_path = Path(out_dir).resolve() / f'{ASSET_ID}.glb'
    gltf = export_glb(glb_path, objects)
    anchor = validate_geometry(objects, gltf, shift)
    body_node = next(node for node in gltf['nodes'] if node['name'] == 'body')
    top_material = next(i for i, mat in enumerate(gltf['materials'])
                        if mat['name'] == f'M_{ASSET_ID}_top')
    desktop_accessors = [gltf['accessors'][primitive['attributes']['POSITION']]
                         for primitive in gltf['meshes'][body_node['mesh']]['primitives']
                         if primitive['material'] == top_material]
    body_translation = body_node.get('translation', [0, 0, 0])
    desktop_y = max(a['max'][1] for a in desktop_accessors) + body_translation[1]
    desktop_front_z = min(a['min'][2] for a in desktop_accessors) + body_translation[2]
    shift_godot = Vector((shift.x, shift.z, -shift.y))
    def shifted(point):
        return [round(v, 9) for v in Vector(point) + shift_godot]
    meta = write_metadata(ASSET_ID, ROOT / 'assets/meta' / f'{ASSET_ID}.json',
                          glb_path, objects, Path(__file__), textures, 'base_center', extra={
        'anchors_godot_m': {'drawer_top': anchor, 'desktop_surface_y': round(desktop_y, 9),
                            'desktop_front_edge_z': round(desktop_front_z, 9)},
        'footprint_godot_m': {'min': shifted((-.80, 0, -.375)), 'max': shifted((.80, .76, .375))},
        'origin_reference': 'base centre of the overall closed bounding-box footprint, including drawer fronts and handles',
        'forward': 'Blender +Y -> Godot -Z',
        'collision': None,
        'drawer_travel_godot_m': [0, 0, -.40],
        'tray_clear_interior_godot_m': {'min': shifted((-.70, .56, -.38)), 'max': shifted((-.14, .67, .08))},
        'baking': {'engine': 'CYCLES', 'device': 'CPU', 'samples': 16, 'margin_px': 8,
                   'maps': 'procedural emission color/RM, tangent normals, ray-traced AO packed into ORM'},
        'render': {'engine': 'CYCLES', 'device': 'CPU', 'samples': 32, 'denoise': True, 'threads': 4},
        'glb_path': str(glb_path.relative_to(ROOT)) if glb_path.is_relative_to(ROOT) else str(glb_path),
    })
    if meta['triangles'] > 60000 or len(meta['materials']) > 4:
        raise RuntimeError('Request budget exceeded')
    views = {
        'front': {'position': (0, 3.4, .96), 'target': (0, 0, .38), 'scale': 1.86},
        'iso': {'position': (-2.8, 3.8, 2.5), 'target': (0, 0, .38), 'scale': 2.05},
        # Camera 45 degrees above the fully extended open tray.
        'detail': {'position': (-1.30, 1.75, 2.126), 'target': (-.42, .54, .63), 'scale': 1.08},
    }
    # Move cameras with the origin revision to preserve the reviewed framing.
    for view in views.values():
        for key in ('position', 'target'):
            view[key] = tuple(Vector(view[key]) + shift)
    # Shared renderer is used for every preview. Close the drawer after the
    # detail render; exported GLB and metadata always describe the closed desk.
    drawer = next(obj for obj in objects if obj.name == 'drawer_top')
    closed = drawer.location.copy()
    # The renderer reads these mappings immediately before each camera view.
    class DetailViews(dict):
        def __getitem__(self, key):
            drawer.location = closed + Vector((0, .40 if key == 'detail' else 0, 0))
            bpy.context.view_layer.update()
            return super().__getitem__(key)
    try:
        render_previews(ASSET_ID, ROOT / 'assets/previews', objects, DetailViews(views), seed=SEED)
    finally:
        drawer.location = closed
        bpy.context.view_layer.update()
    print(f'ASSET BUILT: {glb_path}; {meta["triangles"]} triangles; {len(meta["materials"])} materials')
    return glb_path


if __name__ == '__main__':
    run_cli(build, __doc__)
