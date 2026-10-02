"""KP-6 maglock override keypad and engraved clue plate.

Deterministic Blender 5.2 headless build, original procedural PBR/text only.
Run tools/blender/build_assets.sh exit_keypad_6: serialised Cycles CPU, 4 threads.
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

ASSET_ID = 'exit_keypad_6'
SEED = 61026

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


def bake_surface(part, surf, components, cache):
    """Unwrap one material globally, bake four passes, transfer exact UV loops.

    The temporary mesh uses world coordinates, so grain/wear are continuous.
    Islands never overlap; packing and baking both reserve an 8 pixel margin.
    Only the AO pass uses rays. Base colour / packed RM are emission bakes;
    normals are Cycles tangent NORMAL bakes of the procedural microstructure.
    """
    size = 2048 if part == 'plate' else 1024
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
    stamp_labels(part, components, images)
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


# Add only characters needed for the clue; same original KP-4 stroke design.
GLYPHS.update({
    'A': [[(0, 0), (.30, 1), (.60, 0)], [(.12, .38), (.48, .38)]],
    'M': [[(0, 0), (0, 1), (.30, .47), (.60, 1), (.60, 0)]],
    'G': [[(.60, .88), (.45, 1), (.15, 1), (0, .80), (0, .20), (.15, 0), (.45, 0), (.60, .20), (.60, .47), (.34, .47)]],
    'O': [[(.15, 0), (.45, 0), (.60, .20), (.60, .80), (.45, 1), (.15, 1), (0, .80), (0, .20), (.15, 0)]],
    'V': [[(0, 1), (.30, 0), (.60, 1)]],
    'I': [[(0, 1), (.60, 1)], [(.30, 1), (.30, 0)], [(0, 0), (.60, 0)]],
    'D': [[(0, 0), (0, 1), (.35, 1), (.60, .75), (.60, .25), (.35, 0), (0, 0)]],
    ':': [[(.30, .72), (.30, .75)], [(.30, .25), (.30, .28)]],
    '+': [[(0, .50), (.60, .50)], [(.30, .20), (.30, .80)]],
})


def surfaces():
    body = Surface('body', (.075, .083, .090), .49, .22)
    fine = body.noise((3200, 3200, 3200))
    broad = body.noise((38, 38, 38))
    coat = body.mix(broad, (.051, .059, .065, 1), (.065, .072, .078, 1))
    # Cast perimeter is rubbed smooth, with small, scattered bright scuffs.
    x = body.math('ABSOLUTE', body.axes.outputs['X'])
    z = body.math('ABSOLUTE', body.axes.outputs['Z'])
    edge = body.math('MAXIMUM', body.math('GREATER_THAN', x, .0578),
                     body.math('GREATER_THAN', z, .0878))
    scuff = body.math('MULTIPLY', edge, body.noise((180, 2100, 220)))
    coat = body.mix(body.math('MULTIPLY', scuff, .38), coat, (.17, .19, .20, 1))
    rough = body.math('SUBTRACT', body.math('ADD', .47, body.math('MULTIPLY', fine, .10)),
                      body.math('MULTIPLY', scuff, .22))
    body.finish(coat, rough, fine, .24, .000065)

    key = Surface('key', (.012, .014, .015), .69)
    grain = key.noise((5600, 5600, 5600))
    wear = 0.0
    # Polished thumb contact on exactly the requested frequently used caps.
    for x, z in ((.028, .017), (.028, -.005), (.028, -.027), (0, -.049), (-.028, -.049)):
        dx = key.math('DIVIDE', key.math('SUBTRACT', key.axes.outputs['X'], x), .008)
        dz = key.math('DIVIDE', key.math('SUBTRACT', key.axes.outputs['Z'], z), .006)
        r = key.math('ADD', key.math('MULTIPLY', dx, dx), key.math('MULTIPLY', dz, dz))
        wear = key.math('MAXIMUM', wear, key.math('MAXIMUM', 0, key.math('SUBTRACT', 1, r)))
    base = key.mix(grain, (.010, .012, .014, 1), (.014, .016, .018, 1))
    base = key.mix(key.math('MULTIPLY', wear, .45), base, (.022, .025, .027, 1))
    rough = key.math('SUBTRACT', key.math('ADD', .65, key.math('MULTIPLY', grain, .15)),
                     key.math('MULTIPLY', wear, .29))
    height = key.math('MULTIPLY', grain, key.math('SUBTRACT', 1, key.math('MULTIPLY', wear, .70)))
    key.finish(base, rough, height, .20, .000035)

    plate = Surface('plate', (.53, .56, .58), .36, 1)
    brush = plate.noise((18, 6000, 6000), detail=2)
    drift = plate.noise((28, 28, 28))
    brushed = plate.mix(brush, (.39, .415, .435, 1), (.51, .54, .56, 1))
    brushed = plate.mix(plate.math('MULTIPLY', drift, .09), brushed, (.31, .33, .35, 1))
    # Sparse hairline service scratches, in the steel's brushing direction.
    scratch = plate.math('GREATER_THAN', plate.noise((7, 2000, 1600)), .77)
    scratch = plate.math('MULTIPLY', scratch,
                         plate.math('GREATER_THAN', plate.noise((35, 35, 35)), .57))
    brushed = plate.mix(plate.math('MULTIPLY', scratch, .20), brushed, (.60, .62, .64, 1))
    rough = plate.math('ADD', .31, plate.math('MULTIPLY', brush, .14))
    plate.finish(brushed, rough, brush, .28, .000022)

    screw = Surface('screw', (.45, .47, .49), .30, 1)
    machined = screw.noise((1700, 1700, 1700))
    screw.finish(screw.mix(machined, (.35, .38, .40, 1), (.46, .49, .51, 1)),
                 screw.math('ADD', .26, screw.math('MULTIPLY', machined, .12)),
                 machined, .16, .000020)
    return {'body': body, 'key': key, 'plate': plate, 'screw': screw}


def cut(target, cutter):
    active(target)
    mod = target.modifiers.new('physical_recess', 'BOOLEAN')
    mod.operation = 'DIFFERENCE'
    mod.solver = 'EXACT'
    mod.object = cutter
    bpy.ops.object.modifier_apply(modifier=mod.name)
    bpy.data.objects.remove(cutter, do_unlink=True)


def radial_mesh(name, profile, mat, location, count=48, socket=False):
    vertices = []
    for ring, (radius, depth) in enumerate(profile):
        for i in range(count):
            a = i * math.tau / count
            r = radius * (1 + .19 * math.cos(6 * a)) if socket and ring >= 3 else radius
            vertices.append((r * math.cos(a), depth, r * math.sin(a)))
    faces = []
    for ring in range(len(profile) - 1):
        for i in range(count):
            j = (i + 1) % count
            faces.append((ring * count + i, ring * count + j,
                          (ring + 1) * count + j, (ring + 1) * count + i))
    faces += [tuple(reversed(range(count))), tuple(range((len(profile) - 1) * count, len(profile) * count))]
    faces = [tuple(reversed(face)) for face in faces]
    obj = mesh_object(name, vertices, faces, mat, location)
    for face in obj.data.polygons:
        face.use_smooth = len(face.vertices) == 4
    return obj


def fastener(name, x, z, front, mat, radius=.0030):
    # Sloping countersunk rim, fine flat land, real recessed Torx socket.
    profile = [(radius * .78, front - .0010), (radius, front - .00015),
               (radius * .95, front), (radius * .39, front),
               (radius * .37, front - .00075), (radius * .36, front - .00085)]
    return radial_mesh(name, profile, mat, (x, 0, z), socket=True)


def geometry(mats):
    groups = {'body': [], 'label_plate': []}
    body_parts = groups['body']
    case = box('cast_housing', (.120, .025, .180), mats['body'].mat,
               (0, .0155, 0), bevel=.0025, segments=5)
    cut(case, box('display_cut-noimp', (.088, .006, .023), None,
                  (0, .028, .057), bevel=.00085, segments=4))
    # Real clearance pockets leave each key cap independently movable.
    layout = [['1', '2', '3'], ['4', '5', '6'], ['7', '8', '9'], ['CLR', '0', 'ENT']]
    keys = []
    for row, legends in enumerate(layout):
        print(f'GEOMETRY key row {row + 1}/4', flush=True)
        for column, legend in enumerate(legends):
            x, z = .028 - column * .028, .017 - row * .022
            cut(case, box('key_pocket-noimp', (.024, .004, .019), None,
                          (x, .028, z), bevel=.0011, segments=3))
            socket = box('key_gasket', (.0238, .0018, .0188), mats['key'].mat,
                         (x, .0264, z), bevel=.0010, segments=3)
            body_parts.append(socket)
            name = 'btn_clear' if legend == 'CLR' else 'btn_enter' if legend == 'ENT' else f'btn_{legend}'
            key = box(name, (.022, .004, .017), mats['key'].mat,
                      (x, .030, z), bevel=.0012, segments=4)
            # Object translation is the base centre on the 28 mm housing face.
            for vertex in key.data.vertices:
                vertex.co.y += .002
            key.location.y = .028
            key['legend'] = legend
            keys.append(key)
    body_parts.append(case)
    body_parts.append(box('rear_mount', (.115, .003, .175), mats['body'].mat,
                          (0, .0015, 0), bevel=.0007, segments=3))
    # The closed seam at y=.003 is a physical step, not a painted line.
    body_parts.append(box('screen_gasket', (.0876, .0014, .0226), mats['key'].mat,
                          (0, .0259, .057), bevel=.0007))
    for i, (x, z) in enumerate(((-.051, -.079), (.051, -.079), (-.051, .079), (.051, .079))):
        cut(case, radial_mesh('screw_seat-noimp', [(.002, .0264), (.0031, .0285)], None, (x, 0, z)))
        body_parts.append(fastener(f'housing_screw_{i}', x, z, .02795, mats['screw'].mat))

    print('GEOMETRY keypad done; cut clue plate countersinks', flush=True)
    plate = box('engraved_plate', (.36, .004, .13), mats['plate'].mat,
                (0, .002, .32), bevel=.00045, segments=4)
    plate['clue'] = True
    groups['label_plate'].append(plate)
    for i, (x, z) in enumerate(((-.164, .270), (.164, .270), (-.164, .370), (.164, .370))):
        # Through-hole and tapered countersink are actual mesh recesses.
        cut(plate, radial_mesh('plate_seat-noimp', [(.0016, -.001), (.0016, .0028), (.00335, .0045)], None, (x, 0, z)))
        groups['label_plate'].append(fastener(f'plate_screw_{i}', x, z, .00395, mats['screw'].mat, radius=.00325))

    screen_mat = material(ASSET_ID, 'screen', (.005, .011, .013), roughness=.25)
    # Blank smoked glass, unpowered until Godot overlays six runtime characters.
    screen = box('screen', (.085, .0006, .020), screen_mat, (0, .0267, .057), bevel=.0003, segments=3)
    led_mat = material(ASSET_ID, 'led', (1, 1, 1), roughness=.25, emission=((1, 1, 1), .65))
    dome_profile = [(0.002, 0), (.002, .0002), (.0019, .0007), (.0015, .0013), (.0008, .0017), (.00002, .0019)]
    led = radial_mesh('led_status', dome_profile, led_mat, (-.050, .028, .057), count=32)
    body_parts.append(radial_mesh('led_ring', [(.0027, .0277), (.00265, .028), (.00205, .028), (.00205, .0277)],
                                  mats['screw'].mat, (-.050, 0, .057), count=32))
    return groups, keys, [screen, led]


def text_segments(text, center, height, x_scale=1):
    advance = .82 * height * x_scale
    width = advance * len(text) - .22 * height * x_scale
    left, bottom = center[0] - width / 2, center[1] - height / 2
    for i, char in enumerate(text):
        if char == ' ':
            continue
        for path in GLYPHS[char]:
            for a, b in zip(path, path[1:]):
                # Screen-right is -X in Blender when viewing the +Y face.
                yield (-left - i * advance - a[0] * height * x_scale, bottom + a[1] * height), (-left - i * advance - b[0] * height * x_scale, bottom + b[1] * height)


def uv_mapper(obj, size):
    # Largest planar front face defines the affine mapping into its UV island.
    # Smart unwrap preserves all coplanar faces as one island, including holes.
    face = max((f for f in obj.data.polygons if f.normal.y > .999), key=lambda f: f.area)
    loops = list(face.loop_indices)
    uv = obj.data.uv_layers.active.data
    points = [obj.matrix_world @ obj.data.vertices[obj.data.loops[i].vertex_index].co for i in loops]
    for a in range(1, len(points) - 1):
        p, q, r = points[0], points[a], points[a + 1]
        det = (q.x - p.x) * (r.z - p.z) - (r.x - p.x) * (q.z - p.z)
        if abs(det) > 1e-12:
            ua, ub, uc = [uv[loops[j]].uv.copy() * size for j in (0, a, a + 1)]
            def mapping(point):
                x, z = point
                b = ((x - p.x) * (r.z - p.z) - (r.x - p.x) * (z - p.z)) / det
                c = ((q.x - p.x) * (z - p.z) - (x - p.x) * (q.z - p.z)) / det
                return ua + (ub - ua) * b + (uc - ua) * c
            return mapping
    raise RuntimeError('Degenerate front UV mapping')


def stamp_labels(part, components, images):
    """Rasterise original strokes into baked maps in their actual UV islands.

    Plate engraving has black fill, nonmetal roughness and depressed stroke
    borders in the tangent normal map. Key legends are neutral translucent ink.
    """
    if part not in ('key', 'plate'):
        return
    size = images['base_color'].size[0]
    mask = {}
    for obj in components:
        if 'legend' in obj:
            legend = obj['legend']
            labels = [(legend, (-obj.location.x, obj.location.z), .0045 if len(legend) > 1 else .0075)]
        elif obj.get('clue'):
            labels = [('MAGLOCK OVERRIDE:', (0, .343), .022), ('SITE + RACK', (0, .297), .022)]
        else:
            continue
        mapping = uv_mapper(obj, size)
        for text, center, height in labels:
            # Geometric scale from the affine mapping, independent of island rotation.
            vx = mapping((height, 0)) - mapping((0, 0))
            vz = mapping((0, height)) - mapping((0, 0))
            radius = min(vx.length, vz.length) * (.050 if part == 'plate' else .065)
            for a, b in text_segments(text, center, height):
                pa, pb = mapping(a), mapping(b)
                delta = pb - pa
                denom = delta.length_squared
                for y in range(max(0, math.floor(min(pa.y, pb.y) - radius - 1)), min(size, math.ceil(max(pa.y, pb.y) + radius + 1))):
                    for x in range(max(0, math.floor(min(pa.x, pb.x) - radius - 1)), min(size, math.ceil(max(pa.x, pb.x) + radius + 1))):
                        t = max(0, min(1, ((x + .5 - pa.x) * delta.x + (y + .5 - pa.y) * delta.y) / denom))
                        distance = math.hypot(x + .5 - pa.x - t * delta.x, y + .5 - pa.y - t * delta.y)
                        alpha = max(0, min(1, radius + .5 - distance))
                        if alpha:
                            index = y * size + x
                            mask[index] = max(mask.get(index, 0), alpha)
    buffers = {}
    for name, image in images.items():
        pixels = array('f', [0]) * (size * size * 4)
        image.pixels.foreach_get(pixels)
        buffers[name] = pixels
    for index, alpha in mask.items():
        i = index * 4
        ink = (.006, .007, .008) if part == 'plate' else (.85, .89, .88)
        for ch in range(3):
            buffers['base_color'][i + ch] = buffers['base_color'][i + ch] * (1 - alpha) + ink[ch] * alpha
        buffers['orm'][i + 1] = buffers['orm'][i + 1] * (1 - alpha) + (.83 if part == 'plate' else .51) * alpha
        buffers['orm'][i + 2] *= 1 - alpha
    # Tangent-space groove lips survive GLB export; 0.15 mm black-filled engraving.
    if part == 'plate':
        neighbours = set(mask)
        for i in list(mask):
            neighbours.update((i - 1, i + 1, i - size, i + size))
        for index in neighbours:
            if not 0 <= index < size * size:
                continue
            dx = mask.get(index + 1, 0) - mask.get(index - 1, 0)
            dy = mask.get(index + size, 0) - mask.get(index - size, 0)
            if dx or dy:
                v = Vector((dx * .32, dy * .32, 1)).normalized()
                for ch in range(3):
                    buffers['normal'][index * 4 + ch] = .5 + .5 * v[ch]
    for name, image in images.items():
        image.pixels.foreach_set(buffers[name])
    print(f'STAMP {part}: original stroke legends in baked UV atlas', flush=True)


def build(out_dir):
    reset_scene(SEED)
    cache = ROOT / 'assets/cache' / ASSET_ID
    cache.mkdir(parents=True, exist_ok=True)
    print('BUILD geometry: keypad, key pockets and countersunk plate', flush=True)
    mats = surfaces()
    groups, keys, extras = geometry(mats)
    print('BUILD geometry complete; begin CPU surface baking', flush=True)
    bpy.context.view_layer.update()
    components = [o for pieces in groups.values() for o in pieces] + keys
    textures = []
    for part, surf in mats.items():
        selected = [o for o in components if o.data.materials[0] == surf.mat]
        textures.extend(bake_surface(part, surf, selected, cache))
    objects = [join_static(pieces, name, origin=(0, .002, .32) if name == 'label_plate' else (0, 0, 0))
               for name, pieces in groups.items()] + keys + extras
    # Housing collision excludes the clue plate and individually animated keys.
    collision = box('body-colonly', (.12, .028, .18), None, (0, .014, 0))
    for vertex in collision.data.vertices:
        vertex.co.y += .014
    collision.location.y = 0
    objects.append(collision)
    for obj in objects:
        triangulate(obj)
    bpy.context.view_layer.update()
    glb_path = Path(out_dir).resolve() / f'{ASSET_ID}.glb'
    gltf = export_glb(glb_path, objects)
    nodes = {n['name']: n for n in gltf['nodes'] if 'mesh' in n}
    expected = {'body', 'body-colonly', 'screen', 'led_status', 'label_plate',
                'btn_clear', 'btn_enter', *[f'btn_{i}' for i in range(10)]}
    if set(nodes) != expected or gltf.get('animations') or gltf.get('cameras'):
        raise RuntimeError('Unexpected mesh names, animations or cameras')
    key_origins = {key.name: [round(key.location.x, 9), round(key.location.z, 9), -.028] for key in keys}
    for name, node in nodes.items():
        if node.get('scale', [1, 1, 1]) != [1, 1, 1] or node.get('rotation', [0, 0, 0, 1]) != [0, 0, 0, 1]:
            raise RuntimeError(f'Unapplied transform: {name}')
        if name in key_origins and any(abs(a - b) > 1e-7 for a, b in zip(node.get('translation', [0, 0, 0]), key_origins[name])):
            raise RuntimeError(f'Wrong key base origin: {name}')
    meta = write_metadata(ASSET_ID, ROOT / 'assets/meta' / f'{ASSET_ID}.json',
                          glb_path, objects, Path(__file__), textures, 'mount_plane_center', extra={
        'anchors_godot_m': {'screen_centre': [0, .057, -.027], 'screen_size': [.085, .020],
                            'plate_centre': [0, .32, -.002]},
        'housing_bounds_godot_m': {'min': [-.060, -.090, -.028], 'max': [.060, .090, 0]},
        'key_origins_godot_m': key_origins,
        'key_press_travel_godot_m': [0, 0, .0025],
        'origin_reference': 'centre of keypad rear mounting face; plate rear shares z=0',
        'forward': 'Blender +Y -> Godot -Z',
        'collision': {'part': 'body-colonly', 'shape': 'box', 'bounds_m': [.120, .028, .180]},
        'legend_font': 'original KP-4 sans stroke alphabet, extended for clue, no external fonts',
        'baking': {'engine': 'CYCLES', 'device': 'CPU', 'samples': 16, 'margin_px': 8,
                   'maps': 'procedural emission colour/RM, tangent normals, ray AO packed ORM; engraving stamped in baked UV atlas'},
        'render': {'engine': 'CYCLES', 'device': 'CPU', 'samples': 32, 'denoise': True, 'threads': 4},
        'glb_path': str(glb_path.relative_to(ROOT)) if glb_path.is_relative_to(ROOT) else str(glb_path),
    })
    if meta['triangles'] > 60000 or len(meta['materials']) > 6:
        raise RuntimeError('Request budget exceeded')
    print('PASS geometry: 17 named parts; mount z=0; independent key bases z=-0.028; applied transforms', flush=True)
    render_previews(ASSET_ID, ROOT / 'assets/previews', objects, views={
        'front': {'position': (0, 1.5, .148), 'target': (0, .014, .148), 'scale': .54},
        'iso': {'position': (-.70, 1.6, .67), 'target': (0, .012, .15), 'scale': .58},
        'detail': {'position': (0, 1.5, .32), 'target': (0, .004, .32), 'scale': .405},
    }, seed=SEED)
    print(f'ASSET BUILT: {glb_path}; {meta["triangles"]} triangles; {len(meta["materials"])} materials', flush=True)
    return glb_path


if __name__ == '__main__':
    run_cli(build, __doc__)
