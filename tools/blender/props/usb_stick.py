"""Scuffed orange swivel USB-A stick; original baked PBR and handwritten tape.

Blender 5.2 headless, deterministic, no network. CPU previews, four threads.
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
from common.materials import base_texture, material, normal_texture, orm_texture
from common.preview import render_previews
from common.scene import reset_scene

ASSET_ID = 'usb_stick'
SEED = 5819026

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
    size = 1024
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
    # Keep baked occlusion gentle around small connector and swivel details.
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


def surfaces():
    plastic = Surface('plastic', (.52, .11, .013), .62)
    grain = plastic.noise((18000, 18000, 18000))
    broad = plastic.noise((170, 170, 170))
    scratches = plastic.math('MULTIPLY', plastic.math('GREATER_THAN', plastic.noise((9500, 95, 450)), .73),
                             plastic.math('GREATER_THAN', broad, .48))
    edge = plastic.math('GREATER_THAN', plastic.math('ABSOLUTE', plastic.axes.outputs['X']), .0086)
    wear = plastic.math('MULTIPLY', edge, plastic.noise((1800, 2200, 800)))
    color = plastic.mix(broad, (.12, .014, .001, 1), (.25, .045, .003, 1))
    color = plastic.mix(plastic.math('MULTIPLY', scratches, .34), color, (.40, .11, .018, 1))
    color = plastic.mix(plastic.math('MULTIPLY', wear, .28), color, (.36, .081, .011, 1))
    # Two integral dark-polymer regions: seam gasket and connector tongue.
    seam = plastic.math('LESS_THAN', plastic.math('ABSOLUTE', plastic.math('SUBTRACT', plastic.axes.outputs['Z'], .00435)), .000095)
    tongue = plastic.math('GREATER_THAN', plastic.axes.outputs['Y'], .0301)
    dark = plastic.math('MAXIMUM', seam, tongue)
    color = plastic.mix(dark, color, (.015, .018, .017, 1))
    height = plastic.math('SUBTRACT', grain, plastic.math('MULTIPLY', scratches, .35))
    plastic.finish(color, plastic.math('SUBTRACT', plastic.math('ADD', .59, plastic.math('MULTIPLY', grain, .14)), plastic.math('MULTIPLY', wear, .16)), height, .22, .000024)

    metal = Surface('metal', (.43, .46, .48), .38, 1)
    brush = metal.noise((9000, 75, 8000))
    scratch = metal.math('MULTIPLY', metal.math('GREATER_THAN', metal.noise((5500, 60, 3200)), .76),
                         metal.math('GREATER_THAN', metal.noise((260, 260, 260)), .49))
    color = metal.mix(brush, (.32, .345, .37, 1), (.48, .50, .52, 1))
    color = metal.mix(metal.math('MULTIPLY', scratch, .28), color, (.66, .68, .69, 1))
    # Gold only on the four contact bars within the connector, all one metal material.
    gold = metal.math('MULTIPLY', metal.math('GREATER_THAN', metal.axes.outputs['Y'], .031),
                      metal.math('MULTIPLY', metal.math('GREATER_THAN', metal.axes.outputs['Z'], .00355),
                                 metal.math('LESS_THAN', metal.axes.outputs['Z'], .00390)))
    color = metal.mix(gold, color, (.56, .34, .071, 1))
    metal.finish(color, metal.math('ADD', .30, metal.math('MULTIPLY', brush, .16)), brush, .22, .000009)

    label = Surface('label', (.79, .77, .68), .78)
    fibre = label.noise((15500, 13500, 9000))
    drift = label.noise((100, 140, 140))
    edge = label.math('MAXIMUM', label.math('GREATER_THAN', label.math('ABSOLUTE', label.axes.outputs['X']), .0040),
                      label.math('GREATER_THAN', label.math('ABSOLUTE', label.math('ADD', label.axes.outputs['Y'], .0025)), .0160))
    color = label.mix(label.math('MULTIPLY', drift, .16), (.83, .80, .71, 1), (.65, .61, .48, 1))
    color = label.mix(label.math('MULTIPLY', edge, .34), color, (.41, .32, .19, 1))
    label.finish(color, label.math('ADD', .75, label.math('MULTIPLY', fibre, .13)), fibre, .18, .000012)
    return {'plastic': plastic, 'metal': metal, 'label': label}


def cut(target, cutter):
    active(target)
    mod = target.modifiers.new('physical_cut', 'BOOLEAN')
    mod.operation = 'DIFFERENCE'
    mod.solver = 'EXACT'
    mod.object = cutter
    bpy.ops.object.modifier_apply(modifier=mod.name)
    bpy.data.objects.remove(cutter, do_unlink=True)


def cylinder(name, radius, depth, mat, location, axis='Z', count=40):
    vertices = []
    for side in (-1, 1):
        for i in range(count):
            angle = 2 * math.pi * i / count
            p = (radius * math.cos(angle), radius * math.sin(angle), side * depth / 2)
            if axis == 'X':
                p = (p[2], p[0], p[1])
            vertices.append(p)
    faces = [tuple(reversed(range(count))), tuple(range(count, 2 * count))]
    faces += [(i, (i+1) % count, (i+1) % count + count, i+count) for i in range(count)]
    obj = mesh_object(name, vertices, faces, mat, location)
    for face in obj.data.polygons[2:]:
        face.use_smooth = True
    return obj


def geometry(surfs):
    groups = {part: [] for part in surfs}
    p, m, l = (surfs[part].mat for part in ('plastic', 'metal', 'label'))
    upper = box('orange_upper', (.019, .058, .00465), p, (0, 0, .006675), bevel=.0011, segments=5)
    lower = box('orange_lower', (.019, .058, .0042), p, (0, 0, .0021), bevel=.0011, segments=5)
    gasket = box('mould_seam', (.0184, .0574, .00015), p, (0, 0, .004275), bevel=.00007, segments=2)
    groups['plastic'] += [upper, lower, gasket]
    for shell in groups['plastic']:
        cut(shell, cylinder('keyring_cut-noimp', .00205, .014, None, (0, -.0237, .0045), count=48))
    # Local missing edge flake, not uniformly distressed plastic.
    chip = box('edge_chip-noimp', (.00125, .00195, .0011), None, (.0093, -.0112, .0085), bevel=.0003)
    cut(upper, chip)
    # U-shaped swivel folded 180 degrees back: side cheeks and narrow windowed plates.
    for z in (.00048, .00930):
        plate = box('swivel_plate', (.0204, .049, .00042), m, (0, -.0031, z), bevel=.00018, segments=3)
        cut(plate, box('label_window-noimp', (.0125, .036, .003), None, (0, -.0025, z), bevel=.0014, segments=5))
        cut(plate, cylinder('ring_clearance-noimp', .00245, .003, None, (0, -.0237, z), count=48))
        # A subtle 0.20 mm lift on the back-left corner gives the steel a physical bend.
        for v in plate.data.vertices:
            world = v.co + plate.location
            if world.y < -.018 and world.x < 0:
                v.co.z += .00020 * min(1, (-world.y - .018)/.009) * (-world.x/.0102)
        groups['metal'].append(plate)
    for x in (-.01005, .01005):
        cheek = box('swivel_cheek', (.00040, .0465, .0088), m, (x, -.0020, .00485), bevel=.00018, segments=3)
        # Pivot pin passes through both steel and moulded plastic.
        cut(cheek, cylinder('pivot_bore-noimp', .00155, .003, None, (x, .019, .0048), axis='X'))
        groups['metal'].append(cheek)
        groups['metal'].append(cylinder('pivot_rivet', .00172, .00065, m, (x, .019, .0048), axis='X'))
        groups['metal'].append(cylinder('rivet_centre', .00070, .00012, m, (x + math.copysign(.00039, x), .019, .0048), axis='X', count=24))
    # USB-A shell: four thin walls; hollow open front and real retention holes.
    for z in (.00195, .00635):
        wall = box('connector_wall', (.012, .0122, .00030), m, (0, .035, z), bevel=.00010, segments=2)
        if z > .004:
            for x in (-.00315, .00315):
                cut(wall, box('retention_cut-noimp', (.00185, .0024, .001), None, (x, .0356, z), bevel=.00016, segments=3))
        groups['metal'].append(wall)
    for x in (-.00585, .00585):
        groups['metal'].append(box('connector_side', (.0003, .0122, .0044), m, (x, .035, .00415), bevel=.00010, segments=2))
    groups['plastic'].append(box('contact_tongue', (.0106, .0107, .0014), p, (0, .0349, .00292), bevel=.0002, segments=3))
    for x in (-.0035, -.00117, .00117, .0035):
        groups['metal'].append(box('gold_contact', (.00105, .0072, .00014), m, (x, .03555, .00369), bevel=.00005, segments=2))
    # Thin tape strip with cut corners and a slightly lifted rear corner.
    outline = [(-.0044, -.0191), (.0038, -.0191), (.0044, -.0185), (.0044, .0139),
               (.0038, .0142), (-.0037, .0142), (-.0044, .01365)]
    verts = [(x, y, z) for z in (.00901, .00916) for x, y in outline]
    n = len(outline)
    faces = [tuple(reversed(range(n))), tuple(range(n, 2*n))]
    faces += [(i, (i+1)%n, (i+1)%n+n, i+n) for i in range(n)]
    tape = mesh_object('handwritten_tape', verts, faces, l)
    groups['label'].append(tape)
    return groups


# Original hand-drawn paths. Uppercase initials followed by lowercase marker strokes.
GLYPHS = {
 'M': [[(0,0),(.04,1),(.35,.45),(.68,1),(.72,0)]],
 'R': [[(0,0),(.02,1),(.48,.98),(.68,.84),(.65,.65),(.43,.52),(.02,.52)],[(.35,.52),(.75,0)]],
 '-': [[(.10,.44),(.65,.48)]],
 'b': [[(.08,1),(.02,.03),(.14,.45),(.39,.63),(.60,.54),(.69,.30),(.56,.07),(.29,.01),(.02,.10)]],
 'a': [[(.59,.58),(.36,.65),(.13,.54),(.04,.27),(.13,.03),(.36,.02),(.59,.22),(.59,.62),(.60,.04),(.73,.02)]],
 'c': [[(.59,.56),(.39,.64),(.14,.52),(.04,.26),(.16,.05),(.40,.01),(.62,.12)]],
 'k': [[(.07,1),(.02,0)],[(.62,.66),(.04,.28),(.62,.01)]],
 'u': [[(.05,.64),(.03,.18),(.13,.02),(.35,.01),(.60,.19),(.62,.63),(.61,.02),(.73,.01)]],
 'p': [[(.04,-.30),(.07,.62),(.09,.12),(.22,.03),(.45,.04),(.64,.21),(.64,.43),(.47,.62),(.27,.60),(.08,.44)]],
 's': [[(.60,.56),(.38,.64),(.14,.55),(.11,.39),(.31,.30),(.53,.22),(.59,.09),(.43,0),(.20,.01),(.05,.08)]],
}


def label_mapping(obj, size):
    face = max((p for p in obj.data.polygons if p.normal.z > .999), key=lambda p: p.area)
    loops = list(face.loop_indices)
    points = [obj.matrix_world @ obj.data.vertices[obj.data.loops[i].vertex_index].co for i in loops]
    uv = obj.data.uv_layers.active.data
    p, q, r = points[:3]
    det = (q.x-p.x)*(r.y-p.y)-(r.x-p.x)*(q.y-p.y)
    ua, ub, uc = [uv[i].uv.copy()*size for i in loops[:3]]
    def mapping(point):
        x, y = point
        b = ((x-p.x)*(r.y-p.y)-(r.x-p.x)*(y-p.y))/det
        c = ((q.x-p.x)*(y-p.y)-(x-p.x)*(q.y-p.y))/det
        return ua+(ub-ua)*b+(uc-ua)*c
    return mapping


def stamp_labels(part, components, images):
    if part != 'label':
        return
    size = images['base_color'].size[0]
    mapping = label_mapping(components[0], size)
    rng = random.Random(SEED)
    segments = []
    text = 'MR - backups'
    height, advance = .00355, .00263
    left = -.00245 - (len(text)-1)*advance/2 - .0012
    for index, ch in enumerate(text):
        if ch == ' ':
            continue
        baseline = rng.uniform(-.00012, .00012)
        angle = rng.uniform(-.055, .055)
        for path in GLYPHS[ch]:
            pts = []
            for a, b in path:
                a += .13*b  # casual right lean
                horizontal = a*height + index*advance + left
                vertical = (b-.42)*height + baseline + angle*a*height
                pts.append(mapping((-vertical, horizontal)))
            segments += list(zip(pts, pts[1:]))
    radius = (mapping((0,0))-mapping((.00014,0))).length
    mask = {}
    for a, b in segments:
        delta = b-a
        for y in range(max(0,math.floor(min(a.y,b.y)-radius-1)), min(size,math.ceil(max(a.y,b.y)+radius+1))):
            for x in range(max(0,math.floor(min(a.x,b.x)-radius-1)), min(size,math.ceil(max(a.x,b.x)+radius+1))):
                t = max(0,min(1,((Vector((x+.5,y+.5))-a).dot(delta))/delta.length_squared))
                dist = (Vector((x+.5,y+.5))-a-t*delta).length
                alpha = max(0,min(1,radius+.5-dist))
                if alpha:
                    key = y*size+x
                    mask[key] = max(alpha, mask.get(key,0))
    pixels = array('f',[0])*(size*size*4)
    images['base_color'].pixels.foreach_get(pixels)
    for index, alpha in mask.items():
        # Dry marker has mild density variation but remains black and readable.
        opacity = alpha * (.88 + .10*rng.random())
        for channel in range(3):
            pixels[4*index+channel] = pixels[4*index+channel]*(1-opacity)+.003*opacity
    images['base_color'].pixels.foreach_set(pixels)
    images['orm'].pixels.foreach_get(pixels)
    for index, alpha in mask.items():
        pixels[4*index+1] = pixels[4*index+1]*(1-alpha)+.60*alpha
    images['orm'].pixels.foreach_set(pixels)


def build(out_dir):
    reset_scene(SEED)
    cache = ROOT/'assets/cache'/ASSET_ID
    cache.mkdir(parents=True, exist_ok=True)
    surfs = surfaces()
    groups = geometry(surfs)
    bpy.context.view_layer.update()
    textures = []
    for part in ('plastic', 'metal', 'label'):
        textures += bake_surface(part, surfs[part], groups[part], cache)
    objects = [obj for group in groups.values() for obj in group]
    body = join_static(objects, 'body')
    # Overall footprint centre and lowest underside define the requested base origin.
    minimum = Vector([min(v.co[i] for v in body.data.vertices) for i in range(3)])
    maximum = Vector([max(v.co[i] for v in body.data.vertices) for i in range(3)])
    shift = Vector((-(minimum.x+maximum.x)/2, -(minimum.y+maximum.y)/2, -minimum.z))
    for vertex in body.data.vertices:
        vertex.co += shift
    triangulate(body)
    bpy.context.view_layer.update()
    if len(body.data.polygons) > 20000:
        raise RuntimeError('Triangle budget exceeded')
    if body.location.length > 1e-9 or tuple(body.scale) != (1,1,1):
        raise RuntimeError('Unapplied body transforms')
    path = Path(out_dir)/f'{ASSET_ID}.glb'
    export_glb(path, [body])
    meta = write_metadata(ASSET_ID, ROOT/'assets/meta'/f'{ASSET_ID}.json', path, [body], __file__, textures, 'base_center', extra={
        'plastic_body_dimensions_m': [.019,.058,.009],
        'connector_forward_godot': [0,0,-1],
        'label_text': 'MR - backups',
        'collision': 'none',
        'geometry_shift_blender_m': list(shift),
        'preview_renderer': 'Cycles CPU; 32 samples; 4 threads',
        'third_party_assets': [],
    })
    center = Vector((0,0,.0045))
    target = center + Vector((0,0,0))
    views = {
        'front': {'position': (.115,0,.190), 'target': tuple(target), 'scale': .083},
        'iso': {'position': (.085,.105,.110), 'target': tuple(target), 'scale': .088},
        'detail': {'position': (.095,-.010,.175), 'target': tuple(Vector((0,-.003,.006))+shift), 'scale': .054},
    }
    render_previews(ASSET_ID, ROOT/'assets/previews', [body], views, seed=SEED)
    print(f'ASSET BUILT: {path}; {meta["triangles"]} triangles; {len(meta["materials"])} materials', flush=True)


if __name__ == '__main__':
    run_cli(build, 'Build scuffed orange swivel USB stick')
