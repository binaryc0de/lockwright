"""Original contract task chair: shaped upholstery, moulded nylon and steel.

Run through tools/blender/build_assets.sh office_chair, or:
blender -b --threads 4 -noaudio --python-exit-code 1 --python
tools/blender/props/office_chair.py -- --out game/assets/core/props
Deterministic geometry and procedural-to-texture PBR bakes; no downloads.
"""
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
from common.geometry import box, join_static, mesh_object, triangulate
from common.materials import base_texture, material, normal_texture, orm_texture
from common.preview import render_previews
from common.scene import reset_scene

ASSET_ID = 'office_chair'
SEED = 7319
TEX_SIZE = 2048


def smooth(obj):
    for face in obj.data.polygons:
        face.use_smooth = True
    return obj


def signed_power(value, power):
    return math.copysign(abs(value) ** power, value)


def tube(name, path, radii, mat, sides=10, closed=False):
    """Parallel cross sections along a path, with real rounded section edges."""
    vertices, faces = [], []
    points = [Vector(point) for point in path]
    previous_u = None
    for i, point in enumerate(points):
        previous = points[(i - 1) % len(points)] if closed or i else points[0]
        following = points[(i + 1) % len(points)] if closed or i < len(points) - 1 else points[-1]
        tangent = (following - previous).normalized()
        # Parallel transport prevents the cross section from flipping when
        # a loop goes from horizontal to vertical at its rounded corners.
        if previous_u is None:
            guide = Vector((0, 0, 1)) if abs(tangent.z) < .95 else Vector((0, 1, 0))
            u = tangent.cross(guide).normalized()
        else:
            u = (previous_u - tangent * previous_u.dot(tangent)).normalized()
        previous_u = u
        v = tangent.cross(u).normalized()
        radius = radii[i] if isinstance(radii, list) else radii
        rx, ry = radius if isinstance(radius, tuple) else (radius, radius)
        for j in range(sides):
            angle = math.tau * j / sides
            vertices.append(point + u * math.cos(angle) * rx + v * math.sin(angle) * ry)
    count = len(points) if closed else len(points) - 1
    for i in range(count):
        next_i = (i + 1) % len(points)
        for j in range(sides):
            faces.append((i * sides + j, i * sides + (j + 1) % sides,
                          next_i * sides + (j + 1) % sides, next_i * sides + j))
    if not closed:
        faces.extend((tuple(reversed(range(sides))), tuple(range((len(points) - 1) * sides, len(points) * sides))))
    return smooth(mesh_object(name, vertices, faces, mat))


def lathe(name, center, axis, profile, mat, count=32):
    """Turned rings, chamfered hubs and rounded castor treads, not cylinders."""
    direction = Vector(axis).normalized()
    u = direction.cross(Vector((0, 0, 1)) if abs(direction.z) < .95 else Vector((0, 1, 0))).normalized()
    v = direction.cross(u)
    vertices, faces = [], []
    for offset, radius in profile:
        for i in range(count):
            a = math.tau * i / count
            vertices.append(Vector(center) + direction * offset + radius * (u * math.cos(a) + v * math.sin(a)))
    for ring in range(len(profile) - 1):
        for i in range(count):
            j = (i + 1) % count
            faces.append((ring * count + i, ring * count + j, (ring + 1) * count + j, (ring + 1) * count + i))
    faces.extend((tuple(reversed(range(count))), tuple(range((len(profile) - 1) * count, len(profile) * count))))
    obj = mesh_object(name, vertices, faces, mat)
    for face in obj.data.polygons:
        face.use_smooth = len(face.vertices) == 4
    return obj


def cushion(name, mat, back=False):
    """Superellipse lofts: rolled waterfall edge, depressed seat, lumbar bow."""
    count = 64
    vertices, faces, welt = [], [], []
    # profile runs from back/bottom, over the edge, across the front/top.
    profile = [(.18, -.025), (.78, -.027), (.94, -.023), (1, -.012),
               (1, .002), (.97, .016), (.88, .025), (.65, .029), (.36, .027), (.10, .025)]
    for ring, (scale, depth) in enumerate(profile):
        for i in range(count):
            a = math.tau * i / count
            cx = signed_power(math.cos(a), .50)
            cy = signed_power(math.sin(a), .50)
            if back:
                x, z = .23 * scale * cx, .7975 + .2025 * scale * cy
                # Top slopes away; the lower front face provides lumbar support.
                y = -.205 - .19 * (z - .60) + depth
                y += .021 * math.exp(-((z - .687) / .075) ** 2) * (1 - .3 * cx * cx)
                y -= .009 * (1 - scale)  # slight hollow for the spine
                p = (x, y, z)
            else:
                x, y = .24 * scale * cx, .23 * scale * cy
                # The broad sitting area has a shallow compressed bowl.
                z = .439 + depth - .006 * math.exp(-((x / .17) ** 2 + (y / .16) ** 2))
                z -= .006 * max(0, cy) * scale  # soft waterfall under thighs
                p = (x, y, z)
            vertices.append(p)
            if ring == 4:
                welt.append(p)
    for ring in range(len(profile) - 1):
        for i in range(count):
            j = (i + 1) % count
            faces.append((ring * count + i, ring * count + j, (ring + 1) * count + j, (ring + 1) * count + i))
    faces.extend((tuple(reversed(range(count))), tuple(range((len(profile) - 1) * count, len(profile) * count))))
    return smooth(mesh_object(name, vertices, faces, mat)), tube(name + '_welt', welt, .00125, mat, sides=6, closed=True)


class Shader:
    """Small node builder for metre-based, bakeable surface detail."""
    def __init__(self, mat):
        self.tree = mat.node_tree
        self.bsdf = self.tree.nodes.get('Principled BSDF')
        self.position = self.tree.nodes.new('ShaderNodeNewGeometry').outputs['Position']
        xyz = self.tree.nodes.new('ShaderNodeSeparateXYZ')
        self.tree.links.new(self.position, xyz.inputs[0])
        self.x, self.y, self.z = (xyz.outputs[i] for i in range(3))

    def put(self, socket, value):
        if isinstance(value, (float, int)):
            socket.default_value = value
        else:
            self.tree.links.new(value, socket)

    def math(self, op, a, b=0):
        node = self.tree.nodes.new('ShaderNodeMath')
        node.operation = op
        self.put(node.inputs[0], a)
        self.put(node.inputs[1], b)
        return node.outputs[0]

    def noise(self, scale, detail=2):
        node = self.tree.nodes.new('ShaderNodeTexNoise')
        self.tree.links.new(self.position, node.inputs['Vector'])
        node.inputs['Scale'].default_value = scale
        node.inputs['Detail'].default_value = detail
        node.inputs['Roughness'].default_value = .72
        return node.outputs['Fac']

    def gaussian(self, coord, center, width):
        distance = self.math('DIVIDE', self.math('SUBTRACT', coord, center), width)
        square = self.math('MULTIPLY', distance, distance)
        return self.math('EXPONENT', self.math('MULTIPLY', square, -1))

    def color(self, level, tint):
        node = self.tree.nodes.new('ShaderNodeCombineXYZ')
        for i, factor in enumerate(tint):
            self.tree.links.new(self.math('MULTIPLY', level, factor), node.inputs[i])
        return node.outputs[0]

    def finish(self, color, roughness, metallic, height, distance):
        self.tree.links.new(color, self.bsdf.inputs['Base Color'])
        self.put(self.bsdf.inputs['Roughness'], roughness)
        self.put(self.bsdf.inputs['Metallic'], metallic)
        bump = self.tree.nodes.new('ShaderNodeBump')
        self.put(bump.inputs['Height'], height)
        bump.inputs['Distance'].default_value = distance
        bump.inputs['Strength'].default_value = .65
        self.tree.links.new(bump.outputs['Normal'], self.bsdf.inputs['Normal'])
        return color, roughness, metallic


def procedural_materials():
    fabric = material(ASSET_ID, 'fabric', (.028, .030, .033), roughness=.86)
    s = Shader(fabric)
    # Coarse contract upholstery at 2.6 mm pitch, with over/under alternation.
    # This pitch has enough texels per thread after the non-overlapping bake.
    cross = s.math('ADD', s.y, s.z)
    warp = s.math('SINE', s.math('MULTIPLY', s.x, math.tau / .0026))
    weft = s.math('SINE', s.math('MULTIPLY', cross, math.tau / .0026))
    woven = s.math('MULTIPLY', warp, weft)
    fiber = s.noise(1050, 2)
    front = s.math('MULTIPLY', s.gaussian(s.y, .199, .045), s.gaussian(s.z, .453, .032))
    mottling = s.noise(28, 3)
    level = s.math('ADD', .0048, s.math('MULTIPLY', mottling, .0025))
    level = s.math('ADD', level, s.math('MULTIPLY', woven, .0017))
    level = s.math('ADD', level, s.math('MULTIPLY', front, .0035))
    rough = s.math('SUBTRACT', .93, s.math('MULTIPLY', front, .09))
    # Front-edge pill clusters are irregular and denser where clothing rubs.
    pills = s.math('POWER', s.noise(1150), 5)
    height = s.math('ADD', s.math('MULTIPLY', woven, .30), s.math('MULTIPLY', fiber, .18))
    height = s.math('ADD', height, s.math('MULTIPLY', front, s.math('MULTIPLY', pills, .45)))
    fabric_values = s.finish(s.color(level, (.95, .98, 1.02)), rough, 0, height, .00085)

    plastic = material(ASSET_ID, 'plastic', (.019, .021, .024), roughness=.64)
    s = Shader(plastic)
    grain = s.noise(850, 2)
    broad = s.noise(48, 3)
    low = s.math('LESS_THAN', s.z, .18)
    # Settled pale dust is strongest on upward-facing star-base surfaces.
    geo = s.tree.nodes.new('ShaderNodeSeparateXYZ')
    normal = next(node for node in s.tree.nodes if node.type == 'NEW_GEOMETRY').outputs['Normal']
    s.tree.links.new(normal, geo.inputs[0])
    up = s.math('MAXIMUM', geo.outputs['Z'], 0)
    dust = s.math('MULTIPLY', low, s.math('MULTIPLY', up, broad))
    wheel = s.math('LESS_THAN', s.z, .064)
    level = s.math('ADD', .003, s.math('MULTIPLY', broad, .003))
    level = s.math('ADD', level, s.math('MULTIPLY', dust, .012))
    level = s.math('ADD', level, s.math('MULTIPLY', wheel, .013))
    rubbed = s.math('MULTIPLY', s.gaussian(s.z, .660, .023), s.gaussian(s.y, .03, .14))
    rough = s.math('SUBTRACT', s.math('ADD', .66, s.math('MULTIPLY', grain, .14)), s.math('MULTIPLY', rubbed, .18))
    plastic_values = s.finish(s.color(level, (.98, 1.01, 1.04)), rough, 0, grain, .00028)

    metal = material(ASSET_ID, 'metal', (.35, .37, .40), metallic=1, roughness=.26)
    s = Shader(metal)
    noise = s.noise(360, 2)
    upper = s.math('GREATER_THAN', s.z, .315)
    column = s.math('MULTIPLY', upper, s.gaussian(s.x, 0, .045))
    level = s.math('ADD', .038, s.math('MULTIPLY', column, .34))
    level = s.math('ADD', level, s.math('MULTIPLY', noise, .012))
    rough = s.math('SUBTRACT', .42, s.math('MULTIPLY', column, .20))
    metal_values = s.finish(s.color(level, (.95, .98, 1.04)), rough, 1, noise, .000045)
    return [(fabric, fabric_values), (plastic, plastic_values), (metal, metal_values)]


def bake_maps(mat, values, objects, cache):
    """Bake one non-overlapping material atlas, including tangent-space bump."""
    bpy.ops.object.select_all(action='DESELECT')
    for obj in objects:
        obj.select_set(True)
    bpy.context.view_layer.objects.active = objects[0]
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.uv.smart_project(angle_limit=math.radians(66), island_margin=.005, area_weight=.3)
    bpy.ops.uv.pack_islands(rotate=True, margin_method='FRACTION', margin=8 / TEX_SIZE)
    bpy.ops.object.mode_set(mode='OBJECT')
    scene = bpy.context.scene
    scene.cycles.samples = 16
    scene.render.bake.margin = 8
    scene.render.bake.use_clear = True
    scene.render.bake.use_selected_to_active = False
    tree = mat.node_tree
    output = tree.nodes.get('Material Output')
    bsdf = tree.nodes.get('Principled BSDF')
    emission = tree.nodes.new('ShaderNodeEmission')
    image_node = tree.nodes.new('ShaderNodeTexImage')
    image_node.name = 'bake_target'
    tree.nodes.active = image_node
    part = mat.name.removeprefix('M_office_chair_')
    images = {}
    for map_name in ('base_color', 'normal', 'orm'):
        image = bpy.data.images.new(f'T_{ASSET_ID}_{part}_{map_name}', width=TEX_SIZE, height=TEX_SIZE, alpha=False)
        image.colorspace_settings.name = 'sRGB' if map_name == 'base_color' else 'Non-Color'
        image_node.image = image
        tree.nodes.active = image_node
        if map_name == 'normal':
            tree.links.new(bsdf.outputs[0], output.inputs['Surface'])
            bpy.ops.object.bake(type='NORMAL', normal_space='TANGENT')
        else:
            if map_name == 'base_color':
                tree.links.new(values[0], emission.inputs['Color'])
            else:
                combine = tree.nodes.new('ShaderNodeCombineXYZ')
                combine.inputs[0].default_value = 1.0
                if isinstance(values[1], (int, float)):
                    combine.inputs[1].default_value = values[1]
                else:
                    tree.links.new(values[1], combine.inputs[1])
                if isinstance(values[2], (int, float)):
                    combine.inputs[2].default_value = values[2]
                else:
                    tree.links.new(values[2], combine.inputs[2])
                tree.links.new(combine.outputs[0], emission.inputs['Color'])
            tree.links.new(emission.outputs[0], output.inputs['Surface'])
            bpy.ops.object.bake(type='EMIT')
        cache.mkdir(parents=True, exist_ok=True)
        image.filepath_raw = str(cache / (image.name + '.png'))
        image.file_format = 'PNG'
        image.save()
        image.pack()
        images[map_name] = image
    # Only the baked Principled network is exported. No procedural shader
    # approximation in glTF, no UV tiling or shader dependency in Godot.
    tree.nodes.clear()
    bsdf = tree.nodes.new('ShaderNodeBsdfPrincipled')
    output = tree.nodes.new('ShaderNodeOutputMaterial')
    tree.links.new(bsdf.outputs[0], output.inputs['Surface'])
    base_texture(mat, images['base_color'])
    normal_texture(mat, images['normal'])
    orm_texture(mat, images['orm'])
    return images


def build(out_dir):
    reset_scene(SEED)
    cache = ROOT / 'assets/cache' / ASSET_ID
    material_specs = procedural_materials()
    fabric, plastic, metal = (spec[0] for spec in material_specs)
    groups = {('base', plastic): [], ('base', metal): [],
              ('seat', fabric): [], ('seat', plastic): [], ('seat', metal): []}
    def add(group, obj):
        groups[(group, obj.data.materials[0])].append(obj)
        return obj

    # A rotationally balanced five-star base. The asymmetric pentagon is
    # centred later on its exact bounding footprint, as the request requires.
    add('base', lathe('star_hub', (0, 0, 0), (0, 0, 1),
        [(.095, .057), (.106, .063), (.14, .048), (.149, .042)], plastic, 40))
    for i in range(5):
        angle = math.pi / 2 + i * math.tau / 5
        radial = Vector((math.cos(angle), math.sin(angle), 0))
        tangent = Vector((-math.sin(angle), math.cos(angle), 0))
        path = [radial * r + Vector((0, 0, z)) for r, z in
                ((.031, .122), (.07, .119), (.135, .112), (.205, .098), (.267, .083))]
        arm = tube(f'star_arm_{i}', path,
            [(.030, .018), (.027, .019), (.022, .017), (.019, .014), (.020, .012)], plastic, 10)
        add('base', arm)
        # Twin wheels swivel at deliberately different believable angles.
        caster_angle = angle + (.14, -.24, .31, -.17, .20)[i]
        axle = Vector((math.cos(caster_angle + math.pi / 2), math.sin(caster_angle + math.pi / 2), 0))
        center = radial * .286 + Vector((0, 0, .031))
        add('base', lathe(f'caster_stem_{i}', radial * .267, (0, 0, 1),
            [(.044, .011), (.077, .011), (.080, .009)], metal, 16))
        add('base', tube(f'caster_fork_{i}',
            [radial * .267 + Vector((0, 0, .073)), center + Vector((0, 0, .020))], .016, plastic, 10))
        for side in (-1, 1):
            wheel_center = center + axle * side * .0165
            profile = [(-.0095, .023), (-.008, .029), (-.005, .031),
                       (.005, .031), (.008, .029), (.0095, .023)]
            add('base', lathe(f'caster_{i}_{side}', wheel_center, axle, profile, plastic, 28))
            add('base', lathe(f'caster_hub_{i}_{side}', wheel_center + axle * side * .010,
                axle, [(-.001, .010), (.001, .011), (.002, .009)], plastic, 20))

    # Telescoping column, collar and the genuinely narrower exposed piston.
    add('base', lathe('gas_sleeve', (0, 0, 0), (0, 0, 1),
        [(.142, .035), (.151, .037), (.172, .035), (.300, .032), (.319, .029)], plastic, 40))
    add('base', lathe('gas_piston', (0, 0, 0), (0, 0, 1),
        [(.302, .022), (.306, .024), (.383, .024), (.387, .022)], metal, 40))
    add('base', lathe('gas_collar', (0, 0, 0), (0, 0, 1),
        [(.306, .029), (.308, .031), (.319, .031), (.322, .029)], plastic, 40))

    # Upholstered seat and separate padded back, with sewn perimeter welts.
    for obj in cushion('seat_cushion', fabric):
        add('seat', obj)
    for obj in cushion('back_cushion', fabric, back=True):
        add('seat', obj)
    add('seat', box('seat_underpan', (.448, .428, .031), plastic, (0, -.005, .405), .013, 4))
    add('seat', box('tilt_mechanism', (.168, .205, .041), metal, (0, -.020, .375), .009, 3))
    # Reclined, bowed shell lies behind the upholstery, plus a lower yoke.
    shell, _ = cushion('back_shell', plastic, back=True)
    for vertex in shell.data.vertices:
        vertex.co.y -= .022
        vertex.co.x *= .995
        vertex.co.z = .7975 + (vertex.co.z - .7975) * .995
    add('seat', shell)
    # Drop the unused secondary shell welt, made by the shared loft routine.
    bpy.data.objects.remove(_, do_unlink=True)
    for side in (-1, 1):
        add('seat', tube(f'back_support_{side}',
            [(side * .07, -.12, .382), (side * .07, -.231, .430),
             (side * .085, -.269, .548), (side * .13, -.269, .694)],
            [(.014, .012), (.014, .012), (.012, .012), (.014, .010)], plastic, 10))
        # Closed loop arms, opening clearly visible below soft-touch top pads.
        path = [(side * .282, y, z) for y, z in
                ((-.135, .422), (-.18, .44), (-.19, .49), (-.184, .578),
                 (-.168, .625), (-.14, .642), (.12, .642), (.154, .625),
                 (.166, .59), (.15, .46), (.132, .434), (.104, .422))]
        add('seat', tube(f'loop_arm_{side}', path, (.016, .014), plastic, 10, closed=True))
        add('seat', box(f'arm_pad_{side}', (.064, .292, .032), plastic,
            (side * .282, -.012, .644), .014, 5))
        # The mounting webs and recessed bolts read under a desk light.
        add('seat', box(f'arm_bracket_{side}', (.086, .075, .020), metal,
            (side * .229, -.119, .413), .005, 3))
        for y in (-.119, .104):
            add('seat', lathe(f'arm_bolt_{side}_{y}', (side * .276, y, .423), (1, 0, 0),
                [(-.004, .007), (.004, .007), (.005, .005)], metal, 12))
    add('seat', tube('height_lever', [(.074, .062, .377), (.167, .091, .36), (.218, .12, .36)], .006, metal, 12))
    add('seat', box('height_lever_grip', (.056, .025, .020), plastic, (.224, .124, .36), .008, 4))
    add('seat', lathe('tension_knob', (0, .080, .346), (0, 0, 1),
        [(-.013, .025), (-.010, .031), (.006, .031), (.011, .027)], plastic, 32))
    # Shallow underside ribbing and exposed mechanism screw heads.
    for x in (-.145, -.085, .085, .145):
        add('seat', box(f'pan_rib_{x}', (.008, .25, .008), plastic, (x, -.014, .387), .003, 2))
    for x in (-.059, .059):
        for y in (-.08, .04):
            add('seat', lathe(f'mechanism_screw_{x}_{y}', (x, y, .352), (0, 0, 1),
                [(-.002, .006), (.001, .006), (.002, .0045)], metal, 12))

    buckets = []
    for (group, mat), objects in groups.items():
        obj = join_static(objects, group + '_' + mat.name.removeprefix('M_office_chair_'))
        triangulate(obj)
        buckets.append((group, mat, obj))
    bpy.context.view_layer.update()
    # Centre the *entire* footprint exactly; floor remains Z=0. Seat swivel
    # remains on the gas-axis even when that axis isn't the AABB centre.
    points = [obj.matrix_world @ v.co for _, _, obj in buckets for v in obj.data.vertices]
    offset = Vector((-(min(p.x for p in points) + max(p.x for p in points)) / 2,
                     -(min(p.y for p in points) + max(p.y for p in points)) / 2, -min(p.z for p in points)))
    for _, _, obj in buckets:
        for vertex in obj.data.vertices:
            vertex.co += offset
    bpy.context.view_layer.update()

    images = []
    for mat, values in material_specs:
        baked = bake_maps(mat, values, [obj for _, bucket_mat, obj in buckets if bucket_mat == mat], cache)
        images.extend(baked.values())
    base = join_static([obj for group, _, obj in buckets if group == 'base'], 'base')
    pivot = (offset.x, offset.y, .383 + offset.z)
    seat = join_static([obj for group, _, obj in buckets if group == 'seat'], 'seat', pivot)
    objects = [base, seat]
    for obj in objects:
        triangulate(obj)
    bpy.context.view_layer.update()
    out = Path(out_dir).resolve()
    glb_path = out / f'{ASSET_ID}.glb'
    gltf = export_glb(glb_path, objects)
    for node in gltf['nodes']:
        if node.get('rotation', [0, 0, 0, 1]) != [0, 0, 0, 1] or node.get('scale', [1, 1, 1]) != [1, 1, 1]:
            raise RuntimeError(f'Unapplied transform on {node["name"]}')
    textures = [{'name': image.name, 'size': list(image.size), 'embedded': True}
                for image in sorted(images, key=lambda item: item.name)]
    meta = write_metadata(ASSET_ID, ROOT / 'assets/meta' / f'{ASSET_ID}.json',
        glb_path, objects, Path(__file__), textures, origin='base_center', extra={
            'forward': 'Blender +Y -> Godot -Z',
            'anchors_godot_m': {
                'swivel_axis': [round(pivot[0], 9), round(pivot[2], 9), round(-pivot[1], 9)],
                'floor_origin': [0, 0, 0],
            },
            'collision': None,
            'bake': {'method': 'procedural_to_texture', 'margin_px': 8, 'samples': 16,
                     'uv_layout': 'non_overlapping_per_material', 'normal_space': 'tangent'},
            'render': {'engine': 'CYCLES', 'device': 'CPU', 'samples': 32, 'denoise': True, 'threads': 4},
            'glb_path': str(glb_path.relative_to(ROOT)) if glb_path.is_relative_to(ROOT) else str(glb_path),
        })
    if meta['triangles'] > 20000 or len(meta['materials']) > 4 or set(meta['parts']) != {'base', 'seat'}:
        raise RuntimeError(f'Asset request budget or part mismatch: {meta["triangles"]}, {meta["parts"]}')
    render_previews(ASSET_ID, ROOT / 'assets/previews', objects, views={
        'front': {'position': (0, 2.5, .70), 'target': (0, 0, .50), 'scale': 1.15},
        'iso': {'position': (1.6, 2.2, 1.65), 'target': (0, 0, .49), 'scale': 1.24},
        'detail': {'position': (.72, 1.1, .87), 'target': (.04, .065, .486), 'scale': .56},
    }, seed=SEED)
    print(f'ASSET BUILT: {glb_path}; {meta["triangles"]} triangles; {len(meta["materials"])} materials')
    return glb_path


if __name__ == '__main__':
    run_cli(build, __doc__)
