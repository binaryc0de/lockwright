"""3 kVA UPS and external battery cabinet; original CPU-baked PBR asset.

Deterministic Blender 5.2 build(out_dir), no network or external resources.
Structural references: accepted exit_door_maglock and exit_keypad_6.
All geometry coordinates are Blender metres; +Y front exports as Godot -Z.
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
from common.materials import base_texture, material, normal_texture, orm_texture, image_from_pixels
from common.preview import render_previews
from common.scene import reset_scene
ASSET_ID = 'ups_tower'
SEED = 310026

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
    size = 2048 if part == 'body' else 1024
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
    # Soft ray-traced crevice occlusion; preserve readability in dim light.
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

# Original lowercase k required by the exact 3kVA legend.
GLYPHS['k'] = [[(0, 0), (0, 1)], [(.55, .65), (0, .29), (.55, 0)]]
GLYPHS['Y'] = [[(0, 1), (.30, .52), (.60, 1)], [(.30, .52), (.30, 0)]]
GLYPHS['B'] = [[(0, 0), (0, 1), (.42, 1), (.60, .84), (.60, .66), (.42, .50), (0, .50)],
               [(.42, .50), (.60, .34), (.60, .16), (.42, 0), (0, 0)]]


def band(s, value, centre, width):
    return s.math('MAXIMUM', 0, s.math('SUBTRACT', 1, s.math('DIVIDE',
        s.math('ABSOLUTE', s.math('SUBTRACT', value, centre)), width)))


def surfaces():
    body = Surface('body', (.010, .014, .018), .65)
    body.bsdf.inputs['Specular IOR Level'].default_value = .32
    grain = body.noise((1700, 1700, 1700))
    broad = body.noise((20, 14, 17))
    color = body.mix(broad, (.007, .011, .015, 1), (.014, .019, .024, 1))
    x, y, z = (body.axes.outputs[a] for a in ('X', 'Y', 'Z'))
    top = body.math('GREATER_THAN', z, .892)
    dust = body.math('MULTIPLY', top, body.noise((38, 28, 18)))
    color = body.mix(body.math('MULTIPLY', dust, .23), color, (.16, .14, .11, 1))
    # Real wear locations: bottom corners, exposed folded edges, button rub.
    edge = 0
    for centre in (-.347, -.103, -.047, .347):
        edge = body.math('MAXIMUM', edge, band(body, x, centre, .004))
    edge = body.math('MULTIPLY', edge, body.math('GREATER_THAN', body.math('ABSOLUTE', y), .245))
    low = body.math('LESS_THAN', z, .23)
    chip = body.math('MULTIPLY', edge, body.math('GREATER_THAN',
        body.noise((340, 30, 280)), .60))
    chip = body.math('MULTIPLY', chip, body.math('MAXIMUM', low, .20))
    color = body.mix(chip, color, (.22, .24, .25, 1))
    front = body.math('GREATER_THAN', y, .27)
    shoe = body.math('MULTIPLY', low, body.noise((17, 40, 80)))
    scratch = body.math('MULTIPLY', front, body.math('MULTIPLY', shoe,
        body.math('GREATER_THAN', body.noise((7, 12, 1600)), .73)))
    color = body.mix(body.math('MULTIPLY', scratch, .48), color, (.10, .115, .12, 1))
    polish = body.math('MULTIPLY', band(body, x, -.225, .095),
        band(body, z, .691, .024))
    rough = body.math('SUBTRACT', body.math('ADD', .50, body.math('MULTIPLY', grain, .15)),
        body.math('MULTIPLY', polish, .20))
    rough = body.math('ADD', rough, body.math('MULTIPLY', dust, .18))
    body.metallic = body.math('MULTIPLY', chip, .9)
    body.set(body.bsdf.inputs['Metallic'], body.metallic)
    body.finish(color, rough, grain, .25, .000095)

    metal = Surface('metal', (.19, .21, .22), .37, 1)
    brush = metal.noise((32, 4500, 3400))
    stain = metal.noise((26, 20, 26))
    color = metal.mix(brush, (.12, .135, .15, 1), (.26, .28, .30, 1))
    color = metal.mix(metal.math('MULTIPLY', stain, .16), color, (.07, .08, .09, 1))
    metal.finish(color, metal.math('ADD', .30, metal.math('MULTIPLY', brush, .16)),
                 brush, .22, .00004)

    label = Surface('print', (.70, .73, .69), .53)
    grain = label.noise((2400, 2400, 2400))
    yellow = label.noise((65, 23, 65))
    color = label.mix(yellow, (.57, .60, .56, 1), (.78, .81, .76, 1))
    label.finish(color, label.math('ADD', .49, label.math('MULTIPLY', grain, .11)),
                 grain, .14, .000025)
    return {'body': body, 'metal': metal, 'print': label}


def radial(name, profile, mat, location, count=24, socket=False):
    vertices = []
    for ring, (r, depth) in enumerate(profile):
        for i in range(count):
            a = math.tau * i / count
            rr = r * (1 + .18 * math.cos(6 * a)) if socket and ring >= 3 else r
            vertices.append((rr * math.cos(a), depth, rr * math.sin(a)))
    faces = []
    for ring in range(len(profile) - 1):
        for i in range(count):
            j = (i + 1) % count
            faces.append(((ring + 1) * count + i, (ring + 1) * count + j,
                          ring * count + j, ring * count + i))
    for start, reverse in ((0, False), ((len(profile) - 1) * count, True)):
        for i in range(1, count - 1):
            face = (start, start + i, start + i + 1)
            faces.append(tuple(reversed(face)) if reverse else face)
    obj = mesh_object(name, vertices, faces, mat, location)
    for f in obj.data.polygons:
        f.use_smooth = len(f.vertices) == 4
    triangulate(obj)
    return obj


def screw(name, x, y, z, mat):
    r = .0033
    return radial(name, [(r * .70, -.0008), (r, 0), (r * .95, .00025),
        (r * .38, .00025), (r * .34, -.00055), (r * .33, -.00065)],
        mat, (x, y, z), count=24, socket=True)


def grille(name, x, y, z, columns, rows, pitch, radius, mat):
    """1.2 mm punched sheet, closed aperture walls, actual eight-sided holes.

    Every cell shares the planar grid visually; back and bore have thickness.
    Quads are triangulated and outward normals recalculated before baking.
    """
    vertices, faces = [], []
    for row in range(rows):
        for col in range(columns):
            cx = x + (col - (columns - 1) / 2) * pitch
            cz = z + (row - (rows - 1) / 2) * pitch
            start = len(vertices)
            for depth in (y - .0012, y):
                for inner in (False, True):
                    for i in range(8):
                        a = math.tau * i / 8
                        rr = radius if inner else pitch / 2 / max(abs(math.cos(a)), abs(math.sin(a)))
                        vertices.append((cx + rr * math.cos(a), depth, cz + rr * math.sin(a)))
            for i in range(8):
                j = (i + 1) % 8
                faces += [(start + 16 + i, start + 16 + j, start + 24 + j, start + 24 + i),
                          (start + i, start + 8 + i, start + 8 + j, start + j),
                          (start + 8 + i, start + 24 + i, start + 24 + j, start + 8 + j)]
    obj = mesh_object(name, vertices, faces, mat)
    triangulate(obj)
    return obj


def cable(name, controls, radius, mat):
    """Catmull-Rom hose with transported cross section and sealed ends."""
    points = [Vector(p) for p in controls]
    padded = [points[0], *points, points[-1]]
    path = []
    for i in range(1, len(padded) - 2):
        a, b, c, d = padded[i-1:i+3]
        for step in range(6):
            t = step / 6
            path.append(.5 * ((2*b) + (-a+c)*t + (2*a-5*b+4*c-d)*t*t + (-a+3*b-3*c+d)*t*t*t))
    path.append(points[-1])
    # Clamp the hose centre above its radius so the floor run rests on y=0 after import.
    path = [Vector((p.x, p.y, max(radius, p.z))) for p in path]
    vertices, faces = [], []
    for i, p in enumerate(path):
        tangent = (path[min(i+1, len(path)-1)] - path[max(0, i-1)]).normalized()
        u = tangent.cross(Vector((1, 0, 0))).normalized()
        v = tangent.cross(u).normalized()
        for j in range(12):
            a = math.tau * j / 12
            vertices.append(tuple(p + radius * (u * math.cos(a) + v * math.sin(a))))
    for i in range(len(path)-1):
        for j in range(12):
            k = (j+1) % 12
            faces.append((i*12+j, i*12+k, (i+1)*12+k, (i+1)*12+j))
    for start, rev in ((0, True), ((len(path)-1)*12, False)):
        for j in range(1, 11):
            face = (start, start+j, start+j+1)
            faces.append(tuple(reversed(face)) if rev else face)
    obj = mesh_object(name, vertices, faces, mat)
    for f in obj.data.polygons:
        f.use_smooth = len(f.vertices) == 4
    triangulate(obj)
    return obj


def cut(target, dimensions, location, bevel=.001):
    cutter = box('recess_cut-noimp', dimensions, None, location, bevel=bevel)
    active(target)
    mod = target.modifiers.new('actual_panel_recess', 'BOOLEAN')
    mod.operation = 'DIFFERENCE'
    mod.solver = 'EXACT'
    mod.object = cutter
    bpy.ops.object.modifier_apply(modifier=mod.name)
    bpy.data.objects.remove(cutter, do_unlink=True)
    triangulate(target)


def geometry(mats):
    parts = []
    def slab(name, dims, pos, finish='body', bevel=.001, segments=3):
        obj = box(name, dims, mats[finish].mat, pos, bevel=bevel, segments=segments)
        triangulate(obj)
        parts.append(obj)
        return obj
    for name, x, width in (('ups', -.225, .25), ('battery', .15, .40)):
        # 40 mm feet, full-height rounded sheet jacket, inset front and rear.
        slab(name+'_jacket', (width, .54, .844), (x, -.010, .466), bevel=.003, segments=4)
        bezel = slab(name+'_front_bezel', (width-.008, .014, .808), (x, .285, .454), bevel=.003, segments=4)
        if name == 'battery':
            cut(bezel, (.324, .04, .416), (x, .285, .401))
            cut(bezel, (.350, .04, .186), (x, .285, .747))
        else:
            cut(bezel, (.204, .04, .319), (x, .285, .463))
        slab(name+'_lid', (width-.002, .552, .012), (x, -.006, .894), bevel=.0018, segments=4)
        # Feet retain the exact base y=0 after Godot axis conversion.
        for xx in (x-width/2+.032, x+width/2-.032):
            for yy in (-.227, .230):
                slab(name+'_rubber_foot', (.050, .068, .04), (xx, yy, .020), bevel=.004)
        slab(name+'_battery_access', (width-.027, .004, .20), (x, .294, .177), bevel=.0013)
        for xx in (x-width/2+.025, x+width/2-.025):
            for zz in (.09, .258, .841):
                parts.append(screw(name+'_front_fastener', xx, .296, zz, mats['metal'].mat))
        # Side access panel has a real reveal below the top lid.
        for xx in (x-width/2+.001, x+width/2-.001):
            slab(name+'_side_fold', (.002, .48, .002), (xx, -.015, .824), bevel=.0004)
        # Rear terminals stay recessed within the prescribed footprint.
        slab(name+'_rear_terminal_plate', (width-.052, .003, .19), (x, -.281, .213), 'metal')
        for dz in (.13, .29):
            slab(name+'_rear_rim', (width-.030, .006, .012), (x, -.287, dz))
        parts.append(radial(name+'_cable_gland', [(.020, 0), (.020, -.009), (.013, -.018)],
                            mats['body'].mat, (x, -.282, .18), count=24))
        parts.append(cable(name+'_power_cable', [(x,-.287,.18), (x,-.289,.135),
            (x+.012,-.282,.082), (x+.020,-.267,.028), (x+.025,-.230,.010),
            (x+.056,-.15,.010), (x+.06,-.075,.010)], .010, mats['body'].mat))
    # UPS top control bezel and inset smoked-glass LCD.
    slab('control_recess', (.187, .006, .16), (-.225, .294, .749), bevel=.0025)
    slab('screen_bezel', (.105, .003, .064), (-.225, .297, .752), 'metal', .002)
    screen_mat = material(ASSET_ID, 'screen', (.013,.029,.030), roughness=.26,
                          emission=((.018,.032,.029), .35))
    screen = box('screen', (.09, .001, .05), screen_mat, (-.225,.299,.752), bevel=.001, segments=3)
    triangulate(screen)
    # Recessed navigation buttons, separate from the illuminated LED bar.
    for x in (-.273, -.241, -.209, -.177):
        slab('button_socket', (.024,.002,.019), (x,.297,.701), 'metal', .003)
        slab('navigation_key', (.020,.002,.015), (x,.299,.701), 'body', .0025)
    slab('led_bar_slot', (.069,.003,.008), (-.225,.296,.819), 'metal', .002)
    for i in range(5):
        slab('status_segment', (.010,.002,.004), (-.251+i*.013,.299,.819), 'print', .0006)
    # A vent grille with bent lips and deep dark openings (not painted stripes).
    slab('ups_vent_shadow', (.206,.002,.318), (-.225,.274,.463), bevel=.002)
    for i in range(23):
        slab('ups_louver', (.199,.009,.0075), (-.225,.291,.308+i*.013), bevel=.0007, segments=2)
    for x in (-.331, -.119):
        slab('ups_vent_side_rail', (.009,.006,.328), (x,.293,.462), bevel=.001)
    # External battery cabinet uses visibly different circular punched steel.
    parts.append(grille('battery_punched_steel', .15,.293,.401,14,18,.023,.0062,mats['metal'].mat))
    for x in (-.020, .320):
        slab('battery_grille_edge', (.014,.006,.438), (x,.291,.401), bevel=.001)
    for z in (.181,.621):
        slab('battery_grille_edge', (.353,.006,.014), (.15,.291,z), bevel=.001)
    slab('relay_control_plate', (.344,.004,.180), (.15,.274,.747), 'metal', .002)
    # Raised printed polyester labels carry original, texture-stamped strokes.
    up = slab('ups_nameplate', (.175,.0006,.039), (-.225,.2992,.630), 'print', .0002)
    up['label'] = 'UPS 3kVA'; up['cap_height'] = .017
    by = slab('bypass_nameplate', (.274,.0006,.041), (.15,.277,.794), 'print', .0002)
    by['label'] = 'BYPASS RELAY'; by['cap_height'] = .020
    # Circular pilot lens with a recessed metal retaining ring.
    parts.append(radial('lamp_retaining_ring', [(.016,0),(.016,.0018),(.0117,.0018),(.0117,0)],
                        mats['metal'].mat, (.227,.277,.726), count=32))
    lamp_mat = material(ASSET_ID, 'lamp', (1,1,1), roughness=.26, emission=((1,1,1),.55))
    lamp = radial('relay_lamp', [(.011,0),(.011,.001),(.010,.0028),(.007,.0045),(.00002,.0052)],
                  lamp_mat, (.227,.277,.726), count=32)
    # Toggle has a physical threaded neck, hex nut, and angled metal lever.
    parts.append(radial('toggle_hex_nut', [(.011,0),(.011,.003),(.006,.003),(.006,0)],
                        mats['metal'].mat, (.069,.277,.726), count=6))
    parts.append(cable('toggle_lever', [(.069,.279,.726),(.069,.285,.730),
                                       (.069,.294,.741)], .0025,mats['metal'].mat))
    # Dress-control fixings and rear enclosure fan guards.
    for x in (.000,.300):
        for z in (.674,.823):
            parts.append(screw('relay_plate_screw', x,.277,z,mats['metal'].mat))
    return parts, screen, lamp


def uv_mapper(obj, size):
    face = max((p for p in obj.data.polygons if p.normal.y>.999), key=lambda p:p.area)
    uv = obj.data.uv_layers.active.data
    loops = list(face.loop_indices)
    p,q,r = [obj.matrix_world @ obj.data.vertices[obj.data.loops[i].vertex_index].co for i in loops[:3]]
    det = (q.x-p.x)*(r.z-p.z)-(r.x-p.x)*(q.z-p.z)
    ua,ub,uc = [uv[i].uv.copy()*size for i in loops[:3]]
    def mapping(point):
        x,z = point
        b=((x-p.x)*(r.z-p.z)-(r.x-p.x)*(z-p.z))/det
        c=((q.x-p.x)*(z-p.z)-(x-p.x)*(q.z-p.z))/det
        return ua+(ub-ua)*b+(uc-ua)*c
    return mapping


def draw_text(mask, size, text, center, height, mapping):
    advance = height*.82
    left = center[0]+(len(text)*advance-.22*height)/2
    bottom = center[1]-height/2
    for i,ch in enumerate(text):
        if ch==' ': continue
        for path in GLYPHS[ch]:
            for a,b in zip(path,path[1:]):
                pa=mapping((left-i*advance-a[0]*height,bottom+a[1]*height))
                pb=mapping((left-i*advance-b[0]*height,bottom+b[1]*height))
                radius=(mapping((height,0))-mapping((0,0))).length*.075
                delta=pb-pa
                for y in range(max(0,math.floor(min(pa.y,pb.y)-radius-1)), min(size,math.ceil(max(pa.y,pb.y)+radius+1))):
                    for x in range(max(0,math.floor(min(pa.x,pb.x)-radius-1)), min(size,math.ceil(max(pa.x,pb.x)+radius+1))):
                        t=max(0,min(1,((x+.5-pa.x)*delta.x+(y+.5-pa.y)*delta.y)/delta.length_squared))
                        d=math.hypot(x+.5-pa.x-t*delta.x,y+.5-pa.y-t*delta.y)
                        alpha=max(0,min(1,radius+.5-d))
                        if alpha: mask[y*size+x]=max(alpha,mask.get(y*size+x,0))


def stamp_labels(part, components, images):
    if part!='print': return
    size=images['base_color'].size[0]
    mask={}
    for obj in components:
        if obj.get('label'):
            draw_text(mask,size,obj['label'],(obj.location.x,obj.location.z),
                      obj['cap_height'],uv_mapper(obj,size))
    for name in ('base_color','orm'):
        data=array('f',[0])*(size*size*4)
        images[name].pixels.foreach_get(data)
        for index,alpha in mask.items():
            for ch in range(3):
                target = .007 if name=='base_color' else (1,.74,0)[ch]
                data[index*4+ch]=data[index*4+ch]*(1-alpha)+target*alpha
        images[name].pixels.foreach_set(data)
    print('STAMP print: UPS 3kVA / BYPASS RELAY, original stroke lettering',flush=True)


def lcd_texture(screen, cache):
    size=512
    mask={}
    # Sparse monochrome diagnostics: no puzzle codes, vendor names or logos.
    mapping=lambda p: Vector((size*(.5-(p[0]+.225)/.09), size*(.5+(p[1]-.752)/.05)))
    draw_text(mask,size,'ONLINE',(-.225,.765),.0063,mapping)
    draw_text(mask,size,'230V',(-.225,.754),.008,mapping)
    pixels=array('f',[0])*(size*size*4)
    for y in range(size):
        for x in range(size):
            alpha=mask.get(y*size+x,0)
            # LCD segmented load indicator and subtle scan lines.
            bars=(90<y<133 and 95<x<416 and (x-95)%65<47)
            if bars: alpha=max(alpha,.70)
            bg=(.008,.020,.019)
            ink=(.24,.46,.36)
            for ch in range(3):
                pixels[(y*size+x)*4+ch]=bg[ch]*(1-alpha)+ink[ch]*alpha
            pixels[(y*size+x)*4+3]=1
    image=image_from_pixels(ASSET_ID,'screen_base_color',size,pixels,cache)
    base_texture(screen.data.materials[0],image)
    tree=screen.data.materials[0].node_tree
    tex=next(n for n in tree.nodes if n.type=='TEX_IMAGE')
    tree.links.new(tex.outputs['Color'],tree.nodes.get('Principled BSDF').inputs['Emission Color'])
    # Dedicated planar UVs: preserve legibility instead of atlas packing LCD.
    uv=screen.data.uv_layers.new(name='UVMap')
    for loop in screen.data.loops:
        point=screen.matrix_world @ screen.data.vertices[loop.vertex_index].co
        uv.data[loop.index].uv=(.5-(point.x+.225)/.09,.5+(point.z-.752)/.05)
    return [{'name':image.name,'size':list(image.size),'map':'base_color_emission',
             'material':screen.data.materials[0].name,'embedded':True}]


def build(out_dir):
    reset_scene(SEED)
    cache=ROOT/'assets/cache'/ASSET_ID
    cache.mkdir(parents=True,exist_ok=True)
    mats=surfaces()
    parts,screen,lamp=geometry(mats)
    bpy.context.view_layer.update()
    textures=[]
    for name,surf in mats.items():
        selected=[o for o in parts if o.data.materials[0]==surf.mat]
        textures.extend(bake_surface(name,surf,selected,cache))
    textures.extend(lcd_texture(screen,cache))
    body=join_static(parts,'body')
    objects=[body,screen,lamp]
    for obj in objects: triangulate(obj)
    bpy.context.view_layer.update()
    glb_path=Path(out_dir).resolve()/f'{ASSET_ID}.glb'
    gltf=export_glb(glb_path,objects)
    if {n['name'] for n in gltf['nodes'] if 'mesh' in n}!={'body','screen','relay_lamp'}:
        raise RuntimeError('Unexpected named parts')
    if gltf.get('animations') or gltf.get('cameras') or gltf.get('skins'):
        raise RuntimeError('Static mesh export contract violated')
    for node in gltf['nodes']:
        if node.get('scale',[1,1,1])!=[1,1,1] or node.get('rotation',[0,0,0,1])!=[0,0,0,1]:
            raise RuntimeError('Unapplied transform')
    meta=write_metadata(ASSET_ID,ROOT/'assets/meta'/f'{ASSET_ID}.json',glb_path,objects,
        Path(__file__),textures,'base_center',extra={
            'glb_path':str(glb_path.relative_to(ROOT)) if glb_path.is_relative_to(ROOT) else str(glb_path),
            'forward':'Blender +Y -> Godot -Z', 'collision':None, 'third_party':[],
            'anchors_godot_m':{'screen_centre':[-.225,.752,-.299], 'screen_size':[.09,.05],
                'screen_front_z':-.2995,'relay_lamp':[.227,.726,-.277],
                'relay_lamp_front_z':-.2822, 'ups_centre_x':-.225,'battery_centre_x':.15},
            'baking':{'engine':'CYCLES','device':'CPU','samples':16,'margin_px':8,
                'maps':'procedural colour/RM emission; tangent normal; ray AO packed ORM; original label strokes stamped in atlas'},
            'render':{'engine':'CYCLES','device':'CPU','samples':32,'denoise':True,'threads':4},
            'labels':['UPS 3kVA','BYPASS RELAY'],
            'origin_reference':'centre of nominal 0.70 x 0.60 footprint, floor y=0',
        })
    if meta['triangles']>60000 or len(meta['materials'])>5:
        raise RuntimeError('Asset budget exceeded')
    if abs(meta['bounds_godot_m']['min'][1])>1e-7:
        raise RuntimeError('Feet not on floor')
    print('PASS geometry: three named meshes, identity rotation/scale, no collisions or animations; feet y=0',flush=True)
    render_previews(ASSET_ID,ROOT/'assets/previews',objects,views={
        'front':{'position':(0,3,.46),'target':(0,0,.46),'scale':1.07},
        'iso':{'position':(-1.55,2.35,1.58),'target':(0,0,.46),'scale':1.22},
        'detail':{'position':(0,2,.97),'target':(0,.295,.745),'scale':.78},
    },seed=SEED)
    print(f'ASSET BUILT: {glb_path}; {meta["triangles"]} triangles; {len(meta["materials"])} materials',flush=True)
    return glb_path


if __name__=='__main__':
    run_cli(build,__doc__)
