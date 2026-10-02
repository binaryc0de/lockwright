"""Eight-port rack patch panel, hanging coded Cat6 leads and stroke tags.

Deterministic Blender 5.2 headless build, original procedural PBR/text only.
Run tools/blender/build_assets.sh patch_panel_8: serialised Cycles CPU, 4 threads.
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

ASSET_ID = 'patch_panel_8'
SEED = 810026
RAIL_Z = -.100
FACE_Z = -.103

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
    size = 2048 if part in ('panel', 'cable') else 1024
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
    # Keep crevice AO subtle so the black socket interiors remain readable.
    for index in range(0, len(packed), 4):
        packed[index] = .45 + .55 * occlusion[index]
        packed[index + 3] = 1
    orm.pixels.foreach_set(packed)
    bpy.data.images.remove(ao)
    del images['ao_work']
    stamp_labels(part, components, images)
    if part == 'cable':
        # Cycles' dense smooth-tube tangent bake can differ by a few ulps at
        # a PNG half-code boundary (observed once, 130 versus 131 in one R
        # sample out of 12.6 million). Canonical two-code intervals retain
        # the physical grain, preserve the neutral 128 code, and avoid that
        # sub-byte numerical drift. The runtime normal decoder normalizes.
        image = images['normal']
        pixels = array('f', [0]) * (size * size * 4)
        image.pixels.foreach_get(pixels)
        for index in range(0, len(pixels), 4):
            for channel in range(3):
                pixels[index + channel] = min(255, max(0, round(pixels[index + channel] * 127.5) * 2)) / 255
        image.pixels.foreach_set(pixels)
        print('CANONICAL cable normals: deterministic two-code micro-normal intervals', flush=True)
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


# Local extension of the accepted keypad's original stroke alphabet.
GLYPHS.update({
    'A': [[(0, 0), (.30, 1), (.60, 0)], [(.12, .38), (.48, .38)]],
    'B': [[(0, 0), (0, 1), (.40, 1), (.60, .84), (.60, .66), (.40, .51), (0, .51)],
          [(.40, .51), (.60, .35), (.60, .16), (.40, 0), (0, 0)]],
    'D': [[(0, 0), (0, 1), (.35, 1), (.60, .75), (.60, .25), (.35, 0), (0, 0)]],
    'Y': [[(0, 1), (.30, .53), (.60, 1)], [(.30, .53), (.30, 0)]],
    '>': [[(.12, .83), (.52, .50), (.12, .17)]],
})


def godot(point):
    return (point[0], -point[2], point[1])


def band(s, socket, centre, width):
    return s.math('MAXIMUM', 0, s.math('SUBTRACT', 1,
                  s.math('DIVIDE', s.math('ABSOLUTE', s.math('SUBTRACT', socket, centre)), width)))


# Ordered as seen from the front. Port 1 is at +X, so front-view numbers
# increase from screen-left to screen-right with the binding +Y/-Z convention.
LEADS = [
    {'name': 'cable_a', 'letter': 'A', 'x': .1575, 'plug_y': -.330, 'loop_y': -.400,
     'color': (.46, .018, .014, 1), 'stripes': 1},
    {'name': 'cable_b', 'letter': 'B', 'x': .0525, 'plug_y': -.350, 'loop_y': -.417,
     'color': (.012, .090, .42, 1), 'stripes': 2},
    {'name': 'cable_c', 'letter': 'C', 'x': -.0525, 'plug_y': -.320, 'loop_y': -.395,
     'color': (.78, .48, .014, 1), 'stripes': 3},
    {'name': 'cable_d', 'letter': 'D', 'x': -.1575, 'plug_y': -.365, 'loop_y': -.425,
     'color': (.022, .29, .060, 1), 'stripes': 0},
]


def surfaces():
    panel = Surface('panel', (.016, .020, .024), .58)
    fine = panel.noise((3700, 3700, 3700))
    broad = panel.noise((38, 19, 43), detail=3)
    color = panel.mix(broad, (.003, .004, .006, 1), (.008, .010, .013, 1))
    x, y = panel.axes.outputs['X'], panel.axes.outputs['Z']
    # Powder coat: patchy bright chips at plate edges, rubbed manager lip,
    # dusty upward-facing lands and tiny service scratches around fixings.
    edge_y = panel.math('MAXIMUM', band(panel, y, .0435, .0013), band(panel, y, -.0435, .0013))
    edge = panel.math('MAXIMUM', panel.math('GREATER_THAN', panel.math('ABSOLUTE', x), .239), edge_y)
    edge = panel.math('MULTIPLY', edge, panel.math('GREATER_THAN', panel.noise((530, 300, 510)), .66))
    rub = panel.math('MULTIPLY', band(panel, y, -.090, .0015), panel.noise((130, 1400, 800)))
    chips = panel.math('MAXIMUM', edge, panel.math('MULTIPLY', rub, .38))
    color = panel.mix(chips, color, (.22, .24, .26, 1))
    # Use the actual normal Z component: fine dust settles on horizontal faces.
    normal = panel.node('ShaderNodeSeparateXYZ', Vector=panel.node('ShaderNodeNewGeometry').outputs['Normal'])
    dust = panel.math('MULTIPLY', panel.math('GREATER_THAN', normal.outputs['Z'], .65), broad)
    color = panel.mix(panel.math('MULTIPLY', dust, .18), color, (.13, .112, .085, 1))
    scratches = panel.math('MULTIPLY', panel.math('GREATER_THAN', panel.noise((18, 1500, 2900)), .73),
                            panel.math('GREATER_THAN', panel.noise((95, 32, 110)), .61))
    color = panel.mix(panel.math('MULTIPLY', scratches, .25), color, (.065, .069, .071, 1))
    panel.metallic = panel.math('MULTIPLY', chips, .9)
    panel.set(panel.bsdf.inputs['Metallic'], panel.metallic)
    panel.finish(color, panel.math('ADD', .49, panel.math('MULTIPLY', fine, .19)),
                 panel.math('SUBTRACT', fine, chips), .24, .000047)

    port = Surface('port', (.045, .050, .055), .49)
    grain = port.noise((6800, 6800, 6800))
    plug = port.math('LESS_THAN', port.axes.outputs['Z'], -.20)
    color = port.mix(grain, (.023, .029, .034, 1), (.038, .043, .049, 1))
    color = port.mix(plug, color, (.28, .31, .32, 1))
    port.finish(color, port.math('ADD', .39, port.math('MULTIPLY', grain, .17)), grain, .20, .000022)

    cable = Surface('cable', (.46, .018, .014), .51)
    fine = cable.noise((4700, 4700, 4700))
    broad = cable.noise((65, 23, 38))
    color = LEADS[3]['color']
    for lead in reversed(LEADS[:3]):
        select = cable.math('GREATER_THAN', cable.axes.outputs['X'], lead['x'] - .0525)
        color = cable.mix(select, color, lead['color'])
    # White identification rings are baked around the whole neck of each
    # jacket, not front-facing floating decals. D intentionally has none.
    rings = 0
    for lead in LEADS:
        lane = cable.math('MULTIPLY',
                          cable.math('GREATER_THAN', band(cable, cable.axes.outputs['X'], lead['x'], .049), 0),
                          cable.math('GREATER_THAN', cable.axes.outputs['Y'], .197))
        lane = cable.math('MULTIPLY', lane,
                          cable.math('LESS_THAN', cable.axes.outputs['X'], lead['x'] + .013))
        for i in range(lead['stripes']):
            height = lead['plug_y'] + .043 + i * .007
            stripe = cable.math('GREATER_THAN', band(cable, cable.axes.outputs['Z'], height, .0018), 0)
            rings = cable.math('MAXIMUM', rings, cable.math('MULTIPLY', lane, stripe))
    color = cable.mix(cable.math('MULTIPLY', broad, .11), color, (.08, .063, .048, 1))
    color = cable.mix(rings, color, (.90, .91, .85, 1))
    cable.finish(color, cable.math('ADD', .43, cable.math('MULTIPLY', fine, .17)), fine, .19, .000032)

    tag = Surface('tag', (.72, .67, .52), .82)
    fibers = tag.noise((5800, 2100, 6200), detail=3)
    drift = tag.noise((110, 45, 80))
    color = tag.mix(drift, (.67, .62, .49, 1), (.82, .79, .65, 1))
    tag.finish(color, tag.math('ADD', .73, tag.math('MULTIPLY', fibers, .16)), fibers, .22, .000025)

    metal = Surface('metal', (.41, .43, .44), .31, 1)
    brush = metal.noise((28, 4200, 3600))
    color = metal.mix(brush, (.34, .36, .38, 1), (.47, .49, .50, 1))
    color = metal.mix(metal.math('LESS_THAN', metal.axes.outputs['Z'], .02), color, (.62, .38, .085, 1))
    # Hardware remains nickel; contact fingers occupy the small X lanes.
    for xx in (-.232, .232):
        color = metal.mix(metal.math('GREATER_THAN', band(metal, metal.axes.outputs['X'], xx, .012), 0),
                          color, (.43, .46, .48, 1))
    metal.finish(color, metal.math('ADD', .26, metal.math('MULTIPLY', brush, .17)), brush, .17, .000013)
    return {'panel': panel, 'port': port, 'cable': cable, 'tag': tag, 'metal': metal}


def cut(target, cutter):
    active(target)
    mod = target.modifiers.new('physical_aperture', 'BOOLEAN')
    mod.operation = 'DIFFERENCE'
    mod.solver = 'EXACT'
    mod.object = cutter
    bpy.ops.object.modifier_apply(modifier=mod.name)
    bpy.data.objects.remove(cutter, do_unlink=True)


def tube(name, points, radius, mat, sides=12):
    """Parallel-transport rings on a deterministic centreline (Godot metres)."""
    pts = [Vector(godot(p)) for p in points]
    vertices, faces = [], []
    u = Vector((1, 0, 0))
    for j, p in enumerate(pts):
        tangent = (pts[min(j + 1, len(pts) - 1)] - pts[max(0, j - 1)]).normalized()
        u = (u - tangent * u.dot(tangent)).normalized()
        v = tangent.cross(u).normalized()
        vertices.extend(tuple(p + radius * (math.cos(i * math.tau / sides) * u +
                                            math.sin(i * math.tau / sides) * v)) for i in range(sides))
        if j:
            for i in range(sides):
                k = (i + 1) % sides
                faces.append(((j - 1) * sides + i, (j - 1) * sides + k, j * sides + k, j * sides + i))
    # Closed fan caps, explicitly triangulated before baking.
    for start, reverse in ((0, True), ((len(pts) - 1) * sides, False)):
        for i in range(1, sides - 1):
            f = (start, start + i, start + i + 1)
            faces.append(tuple(reversed(f)) if reverse else f)
    obj = mesh_object(name, vertices, faces, mat)
    for face in obj.data.polygons:
        face.use_smooth = len(face.vertices) == 4
    return obj


def catmull(points, steps=12):
    pts = [Vector(p) for p in points]
    result = []
    for i in range(len(pts) - 1):
        a, b, c, d = pts[max(0, i - 1)], pts[i], pts[i + 1], pts[min(len(pts) - 1, i + 2)]
        for j in range(steps):
            t = j / steps
            result.append(tuple(.5 * ((2 * b) + (-a + c) * t + (2 * a - 5 * b + 4 * c - d) * t * t +
                                      (-a + 3 * b - 3 * c + d) * t * t * t)))
    result.append(tuple(pts[-1]))
    return result


def geometry(mats):
    groups = {'panel': [], **{lead['name']: [] for lead in LEADS}}
    def slab(group, name, size, point, finish, radius=.0003, segments=3):
        obj = box(name, (size[0], size[2], size[1]), mats[finish].mat, godot(point),
                  bevel=radius, segments=segments)
        groups[group].append(obj)
        return obj

    # Folded 1 mm steel chassis: rear face exactly at zero, open volume behind
    # the plate. No solid black block obstructs the socket openings.
    slab('panel', 'rear_shell', (.440, .083, .001), (0, 0, -.0005), 'panel')
    for y in (-.041, .041):
        slab('panel', 'folded_shell', (.440, .001, .099), (0, y, -.0505), 'panel')
    for x in (-.2195, .2195):
        slab('panel', 'chassis_side', (.001, .081, .099), (x, 0, -.0505), 'panel')
    plate = slab('panel', 'rack_faceplate', (.483, .089, .002), (0, 0, -.101), 'panel', .00035, 4)
    # The central rolled face stands 1 mm proud of the 2 mm mounting ears.
    face = slab('panel', 'front_land', (.452, .087, .001), (0, 0, -.1025), 'panel', .00022, 3)
    ports = []
    for i in range(8):
        x = .21 - i * .06
        ports.append([round(x, 6), .008, FACE_Z - .0015])
        for obj in (plate, face):
            cut(obj, box('port_hole-noimp', (.024, .013, .020), None, godot((x, .008, -.102))))
        # Ring of moulded plastic, true rectangular RJ45 opening with a
        # lowered latch keyway; internal cheeks are 12 mm deep.
        bezel = slab('panel', 'keystone_flange', (.030, .026, .004), (x, .008, -.1035), 'port', .0006, 4)
        cut(bezel, box('socket_void-noimp', (.020, .022, .015), None, godot((x, .009, -.101))))
        cut(bezel, box('latch_void-noimp', (.008, .022, .004), None, godot((x, -.0002, -.101))))
        for dx in (-.011, .011):
            slab('panel', 'socket_wall', (.002, .017, .014), (x + dx, .009, -.095), 'port', .0002)
        slab('panel', 'socket_roof', (.020, .002, .014), (x, .0175, -.095), 'port', .0002)
        slab('panel', 'socket_floor', (.020, .002, .014), (x, -.0015, -.095), 'port', .0002)
        slab('panel', 'socket_back', (.020, .020, .001), (x, .008, -.0875), 'port', .0001)
        for n in range(8):
            xx = x + (n - 3.5) * .002
            groups['panel'].append(tube('gold_contact', [(xx, .0171, -.091), (xx, .0135, -.097),
                                                         (xx, .0125, -.0995)], .00025, mats['metal'].mat, 8))
        legend = slab('panel', 'number_land', (.025, .016, .00012), (x, -.025, -.10306), 'panel', .00005)
        legend['legend'] = str(i + 1)
        legend['legend_center'] = [-x, -.025]
        legend['legend_height'] = .012
    title = slab('panel', 'title_land', (.137, .012, .00012), (.145, .032, -.10306), 'panel', .00005)
    title['legend'] = 'P1 -> UPS BYPASS'
    title['legend_center'] = [-.145, .032]
    title['legend_height'] = .009
    # Slotted mounting ears and recessed pan-head cross screws.
    for x in (-.232, .232):
        for y in (-.030, .030):
            cut(plate, box('ear_slot-noimp', (.0065, .012, .011), None, godot((x, y, -.101)), bevel=.0025, segments=4))
            head = tube('mount_screw', [(x, y, -.102), (x, y, -.104)], .0037, mats['metal'].mat, 24)
            groups['panel'].append(head)
            for w, h in ((.0047, .0008), (.0008, .0047)):
                cut(head, box('driver-noimp', (w, .0014, h), None, godot((x, y, -.104))))
    # 1U manager: rear strip, rounded lower lip, four open D-shaped guide
    # rings. The metal strip is part of panel; leads remain independent.
    manager = slab('panel', 'manager_back', (.483, .0445, .002), (0, -.06725, -.101), 'panel', .00035, 4)
    slab('panel', 'manager_shelf', (.447, .002, .058), (0, -.0905, -.129), 'panel', .0004, 4)
    slab('panel', 'manager_front_lip', (.447, .014, .002), (0, -.0845, -.158), 'panel', .0007, 4)
    for x in (-.232, .232):
        cut(manager, box('manager_slot-noimp', (.0065, .012, .011), None,
                         godot((x, -.06725, -.101)), bevel=.0025, segments=4))
        head = tube('manager_screw', [(x, -.06725, -.102), (x, -.06725, -.104)],
                    .0037, mats['metal'].mat, 24)
        groups['panel'].append(head)
        for w, h in ((.0047, .0008), (.0008, .0047)):
            cut(head, box('driver-noimp', (w, .0014, h), None, godot((x, -.06725, -.104))))
    for lead in LEADS:
        x, py, ly = lead['x'], lead['plug_y'], lead['loop_y']
        ring = [(x - .038, -.057, -.104), (x - .038, -.057, -.148),
                (x - .030, -.052, -.166), (x + .030, -.052, -.166),
                (x + .038, -.057, -.148), (x + .038, -.057, -.104)]
        groups['panel'].append(tube('manager_guide', catmull(ring, 6), .0025, mats['panel'].mat, 12))
        for dx in (-.038, .038):
            slab('panel', 'guide_foot', (.011, .018, .003), (x + dx, -.060, -.1035), 'panel')
        # Natural slack U with a curling return toward the dangling connector.
        route = [(x - .024, -.056, -.109), (x - .025, -.053, -.141),
                 (x - .026, -.074, -.172), (x - .030, -.235, -.177),
                 (x - .028, ly + .022, -.177), (x - .012, ly, -.181),
                 (x + .016, ly + .005, -.187), (x + .029, ly + .040, -.194),
                 (x + .027, py + .068, -.196), (x + .010, py + .062, -.202),
                 (x + .005, py + .046, -.209), (x + .005, py + .025, -.209)]
        path = catmull(route)
        length = sum((Vector(b) - Vector(a)).length for a, b in zip(path, path[1:])) + .025
        if not .5 <= length <= .7:
            raise RuntimeError(f'{lead["name"]} length {length:.4f} is outside 0.5–0.7 m')
        lead['length_m'] = round(length, 6)
        groups[lead['name']].append(tube('cat6_jacket', path, .0031, mats['cable'].mat, 12))
        px = x + .005
        # Moulded boot with stepped strain relief and a flexible latch cover.
        slab(lead['name'], 'boot', (.014, .018, .014), (px, py + .018, -.209), 'cable', .002, 5)
        for j in range(4):
            slab(lead['name'], 'boot_rib', (.015, .0012, .015), (px, py + .013 + j * .0032, -.209), 'cable', .0005, 3)
        plug = slab(lead['name'], 'rj45_shell', (.012, .026, .013), (px, py - .002, -.209), 'port', .00055, 4)
        # Eight contact pads and moulded divider grooves on the plug front.
        for j in range(8):
            xx = px + (j - 3.5) * .00125
            slab(lead['name'], 'plug_contact', (.0007, .006, .00035), (xx, py - .0095, -.21565), 'metal', .0001)
        slab(lead['name'], 'plug_seam', (.0115, .0008, .0003), (px, py + .0025, -.21555), 'port', .0001)
        slab(lead['name'], 'release_latch', (.004, .019, .0016), (px, py + .004, -.217), 'port', .00065, 3)
        slab(lead['name'], 'latch_tip', (.006, .003, .002), (px, py + .012, -.218), 'port', .0006, 3)
        # Cut a tie hole through a stiff paper luggage-style tag. The tag is
        # front facing, separated sideways so its letter and rings both read.
        tx, ty = px + .022, py + .009
        tag = slab(lead['name'], 'paper_tag', (.028, .029, .0005), (tx, ty, -.2168), 'tag', .00018, 3)
        hole = tube('tag_hole-noimp', [(tx - .009, ty + .009, -.213), (tx - .009, ty + .009, -.221)], .00125, None, 16)
        cut(tag, hole)
        tag['legend'] = lead['letter']
        tag['legend_center'] = [-tx + .001, ty - .001]
        tag['legend_height'] = .015
        tag['handwritten'] = True
        tie = [(px, py + .031, -.208), (px + .010, py + .029, -.221),
               (tx - .009, ty + .009, -.218), (tx - .009, ty + .009, -.215),
               (px + .008, py + .028, -.203), (px, py + .031, -.208)]
        groups[lead['name']].append(tube('tag_tie', catmull(tie, 5), .00045, mats['tag'].mat, 8))
    for pieces in groups.values():
        for obj in pieces:
            triangulate(obj)
    return groups, ports


def text_segments(text, center, height, handwritten=False):
    advance = .82 * height
    width = advance * len(text) - .22 * height
    left, bottom = center[0] - width / 2, center[1] - height / 2
    for i, char in enumerate(text):
        if char == ' ':
            continue
        for path in GLYPHS[char]:
            for a, b in zip(path, path[1:]):
                def point(v):
                    xx = v[0] + (.065 * v[1] if handwritten else 0)
                    return (-left - i * advance - xx * height, bottom + v[1] * height)
                yield point(a), point(b)


def uv_mapper(obj, size):
    face = max((f for f in obj.data.polygons if f.normal.y > .999), key=lambda f: f.area)
    loops = list(face.loop_indices)
    uv = obj.data.uv_layers.active.data
    p, q, r = [obj.matrix_world @ obj.data.vertices[obj.data.loops[i].vertex_index].co for i in loops[:3]]
    det = (q.x - p.x) * (r.z - p.z) - (r.x - p.x) * (q.z - p.z)
    if abs(det) < 1e-12:
        raise RuntimeError('Degenerate label UV')
    ua, ub, uc = [uv[i].uv.copy() * size for i in loops[:3]]
    def mapping(point):
        x, z = point
        b = ((x - p.x) * (r.z - p.z) - (r.x - p.x) * (z - p.z)) / det
        c = ((q.x - p.x) * (z - p.z) - (x - p.x) * (q.z - p.z)) / det
        return ua + (ub - ua) * b + (uc - ua) * c
    return mapping


def stamp_labels(part, components, images):
    if part not in ('panel', 'tag'):
        return
    size = images['base_color'].size[0]
    mask = {}
    for obj in components:
        if not obj.get('legend'):
            continue
        mapping = uv_mapper(obj, size)
        for text, center, height in [(obj['legend'], obj['legend_center'], obj['legend_height'])]:
            vx = mapping((height, 0)) - mapping((0, 0))
            vy = mapping((0, height)) - mapping((0, 0))
            radius = min(vx.length, vy.length) * (.058 if part == 'tag' else .05)
            if min(vx.length, vy.length) < 12:
                raise RuntimeError(f'Undersized legend in atlas: {text}')
            for a, b in text_segments(text, center, height, obj.get('handwritten', False)):
                pa, pb = mapping(a), mapping(b)
                delta = pb - pa
                for yy in range(max(0, math.floor(min(pa.y, pb.y) - radius - 1)), min(size, math.ceil(max(pa.y, pb.y) + radius + 1))):
                    for xx in range(max(0, math.floor(min(pa.x, pb.x) - radius - 1)), min(size, math.ceil(max(pa.x, pb.x) + radius + 1))):
                        t = max(0, min(1, ((xx + .5 - pa.x) * delta.x + (yy + .5 - pa.y) * delta.y) / delta.length_squared))
                        distance = math.hypot(xx + .5 - pa.x - t * delta.x, yy + .5 - pa.y - t * delta.y)
                        alpha = max(0, min(1, radius + .5 - distance))
                        if alpha:
                            index = yy * size + xx
                            mask[index] = max(mask.get(index, 0), alpha)
    buffers = {}
    for name, image in images.items():
        data = array('f', [0]) * (size * size * 4)
        image.pixels.foreach_get(data)
        buffers[name] = data
    ink = (.014, .021, .028) if part == 'tag' else (.91, .92, .86)
    for index, alpha in mask.items():
        i = index * 4
        for ch in range(3):
            buffers['base_color'][i + ch] = buffers['base_color'][i + ch] * (1 - alpha) + ink[ch] * alpha
        buffers['orm'][i + 1] = buffers['orm'][i + 1] * (1 - alpha) + .7 * alpha
        buffers['orm'][i + 2] *= 1 - alpha
    for name, image in images.items():
        image.pixels.foreach_set(buffers[name])
    print(f'STAMP {part}: original stroke legends in unique baked UV islands', flush=True)


def build(out_dir):
    reset_scene(SEED)
    cache = ROOT / 'assets/cache' / ASSET_ID
    cache.mkdir(parents=True, exist_ok=True)
    mats = surfaces()
    print('BUILD geometry: 2U patch panel, 1U manager, eight keystones, four tagged Cat6 leads', flush=True)
    groups, ports = geometry(mats)
    bpy.context.view_layer.update()
    components = [obj for pieces in groups.values() for obj in pieces]
    textures = []
    for part, surf in mats.items():
        selected = [obj for obj in components if obj.data.materials[0] == surf.mat]
        textures.extend(bake_surface(part, surf, selected, cache))
    objects = [join_static(pieces, name, origin=(0, 0, 0)) for name, pieces in groups.items()]
    for obj in objects:
        triangulate(obj)
    bpy.context.view_layer.update()
    glb_path = Path(out_dir).resolve() / f'{ASSET_ID}.glb'
    gltf = export_glb(glb_path, objects)
    nodes = {n['name']: n for n in gltf['nodes'] if 'mesh' in n}
    if set(nodes) != set(groups) or gltf.get('animations') or gltf.get('cameras'):
        raise RuntimeError('Unexpected exported parts/animation/camera')
    for name, node in nodes.items():
        if node.get('scale', [1, 1, 1]) != [1, 1, 1] or node.get('rotation', [0, 0, 0, 1]) != [0, 0, 0, 1]:
            raise RuntimeError(f'Unapplied transform: {name}')
        if node.get('translation', [0, 0, 0]) != [0, 0, 0]:
            raise RuntimeError(f'Origin drift: {name}')
    meta = write_metadata(ASSET_ID, ROOT / 'assets/meta' / f'{ASSET_ID}.json', glb_path,
                          objects, Path(__file__), textures, 'mount_plane_center', extra={
        'origin_reference': 'centre of rear panel face, Godot (0,0,0); rack mounting ears at z=-0.100',
        'forward': 'Blender +Y -> Godot -Z',
        'collision': None,
        'anchors_godot_m': {'rail_plane_z': RAIL_Z, 'front_face_z': FACE_Z},
        'panel_dimensions_wdh_m': [.483, .103, .089],
        'port_centres_godot_m': ports,
        'cables': [{k: v for k, v in lead.items() if k in ('name', 'letter', 'stripes', 'length_m')} for lead in LEADS],
        'legend_cap_heights_m': {'ports': .012, 'title': .009, 'tags': .015},
        'legend_font': 'owner-made sans stroke alphabet, slanted marker tags; no fonts or downloads',
        'baking': {'engine': 'CYCLES', 'device': 'CPU', 'samples': 16, 'margin_px': 8,
                   'maps': 'procedural emission base/RM, tangent normals, ray AO packed ORM; original raster stroke legends'},
        'render': {'engine': 'CYCLES', 'device': 'CPU', 'samples': 32, 'denoise': True, 'threads': 4},
        'third_party': [],
        'glb_path': str(glb_path.relative_to(ROOT)) if glb_path.is_relative_to(ROOT) else str(glb_path),
    })
    if meta['triangles'] > 60000 or len(meta['materials']) > 5 or len(meta['textures']) != 15:
        raise RuntimeError('Request budget exceeded or missing baked maps')
    if abs(meta['bounds_godot_m']['max'][2]) > 1e-6 or abs(sum((meta['bounds_godot_m'][key][0] for key in ('min', 'max')))) > 1e-6:
        raise RuntimeError('Rear-face mount origin mismatch')
    print('PASS geometry: 5 named parts; rear z=0; rail z=-0.100; face z=-0.103; 60mm port pitch; applied transforms', flush=True)
    print('PASS cable lengths: ' + ', '.join(f'{p["letter"]}={p["length_m"]:.3f}m/{p["stripes"]} stripes' for p in LEADS), flush=True)
    render_previews(ASSET_ID, ROOT / 'assets/previews', objects, views={
        'front': {'position': (0, 1.5, -.215), 'target': (0, .12, -.215), 'scale': .60},
        'iso': {'position': (-.70, 1.6, .30), 'target': (0, .11, -.210), 'scale': .65},
        'detail': {'position': (0, 1.5, -.312), 'target': (0, .21, -.312), 'scale': .46},
    }, seed=SEED)
    print(f'ASSET BUILT: {glb_path}; {meta["triangles"]} triangles; {len(meta["materials"])} materials', flush=True)
    return glb_path


if __name__ == '__main__':
    run_cli(build, __doc__)
