"""Original emergency exit lightbox: reproducible Blender 5.2 / Cycles CPU.

Only this asset's source and outputs are written. PBR baker adapted locally
from the accepted exit_keypad_6, so concurrent asset changes cannot affect it.
The safety pictogram is original vector artwork, not a certified sign design.
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
from common.geometry import active, box, join_static, mesh_object, triangulate, uv_front
from common.materials import base_texture, material, normal_texture, orm_texture, image_from_pixels, texture_node
from common.preview import render_previews
from common.scene import reset_scene

ASSET_ID = 'exit_sign_lightbox'
SEED = 701001

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


def housing_surface():
    surf = Surface('housing', (.73, .715, .64), .44)
    fine = surf.noise((4200, 4200, 4200))
    ageing = surf.noise((22, 22, 22))
    color = surf.mix(ageing, (.69, .676, .60, 1), (.77, .75, .67, 1))
    # Slight warm ageing and accumulated dust, restrained at sign scale.
    top = surf.math('GREATER_THAN', surf.axes.outputs['Z'], .069)
    dust = surf.math('MULTIPLY', top, surf.noise((360, 95, 240)))
    color = surf.mix(surf.math('MULTIPLY', dust, .10), color, (.47, .44, .35, 1))
    rough = surf.math('ADD', .41, surf.math('MULTIPLY', fine, .11))
    surf.finish(color, rough, fine, .18, .000035)
    return surf


def difference(target, cutter):
    active(target)
    mod = target.modifiers.new('physical_recess', 'BOOLEAN')
    mod.operation = 'DIFFERENCE'
    mod.solver = 'EXACT'
    mod.object = cutter
    bpy.ops.object.modifier_apply(modifier=mod.name)
    bpy.data.objects.remove(cutter, do_unlink=True)


def disc(name, radius, depth, mat, location, segments=48):
    # Cylinder along Z for the recessed underside controls.
    vertices = [(radius * math.cos(i * math.tau / segments),
                 radius * math.sin(i * math.tau / segments), z)
                for z in (-depth / 2, depth / 2) for i in range(segments)]
    faces = [tuple(reversed(range(segments))), tuple(range(segments, 2 * segments))]
    for i in range(segments):
        j = (i + 1) % segments
        faces.append((i, j, segments + j, segments + i))
    obj = mesh_object(name, vertices, faces, mat, location)
    for poly in obj.data.polygons:
        poly.use_smooth = len(poly.vertices) == 4
    return obj


def geometry(surf, face_mat, led_mat):
    parts = []
    rear = box('rear_shell', (.36, .014, .15), surf.mat, (0, .007, 0),
               bevel=.004, segments=5)
    parts.append(rear)
    bezel = box('front_shell', (.36, .0355, .15), surf.mat, (0, .03225, 0),
                bevel=.004, segments=5)
    difference(bezel, box('diffuser_recess-noimp', (.332, .030, .122), None,
                         (0, .047, 0), bevel=.002, segments=5))
    # Physical test-button and LED bores; the controls remain inside 150 mm H.
    difference(bezel, disc('test_bore-noimp', .0042, .010, None,
                           (-.111, .031, -.075)))
    difference(bezel, disc('led_bore-noimp', .0021, .010, None,
                           (-.091, .031, -.075)))
    # Moulded front-cover latch slots, visible along the underside.
    for x in (-.143, .143):
        difference(bezel, box('latch_slot-noimp', (.009, .0030, .005), None,
                             (x, .026, -.075), bevel=.0005, segments=2))
    parts.append(bezel)
    button = disc('test_button', .00355, .003, surf.mat, (-.111, .031, -.0730))
    parts.append(button)
    # Raised test dot is a tactile mark; no text or extra exported mesh node.
    parts.append(disc('test_dot', .0007, .00035, surf.mat, (-.111, .031, -.07455), 24))
    # Two rear keyhole pockets support believable flush wall mounting.
    for x in (-.115, .115):
        difference(rear, box('mount_slot-noimp', (.006, .004, .013), None,
                            (x, 0, .023), bevel=.0013, segments=3))
    lens = disc('charge_led', .00165, .0027, led_mat, (-.091, .031, -.0730))
    face = box('face', (.330, .002, .120), face_mat, (0, .0475, 0),
               bevel=.0006, segments=3)
    uv_front(face, (0, 0, 1, 1), other_rect=(.006, .006, .007, .007),
             width=.330, height=.120)
    return parts, lens, face


def raster_pictogram(cache):
    """Antialiased vector paths, defined in a 330 x 120 mm sign coordinate space.

    White left arrow, left doorway, and a person running left. Scanline-fill
    at 2x resolution then box-filter into the requested 1024 px texture.
    Raster origin is bottom left, matching the face's upright UV projection.
    """
    size, sample = 1024, 2
    high = size * sample
    mask = bytearray(high * high)

    def polygon(points):
        points = [(x / 330 * high, y / 120 * high) for x, y in points]
        low = max(0, int(min(y for x, y in points)))
        top = min(high, math.ceil(max(y for x, y in points)))
        for row in range(low, top):
            y = row + .5
            crosses = []
            for (x0, y0), (x1, y1) in zip(points, points[1:] + points[:1]):
                if min(y0, y1) <= y < max(y0, y1):
                    crosses.append(x0 + (y - y0) * (x1 - x0) / (y1 - y0))
            crosses.sort()
            for left, right in zip(crosses[0::2], crosses[1::2]):
                start, end = max(0, math.ceil(left - .5)), min(high, math.ceil(right - .5))
                mask[row * high + start:row * high + end] = bytes([255]) * (end - start)

    # The arrow remains visually separate from the escape-route pictogram.
    polygon([(20, 60), (49, 87), (49, 70), (97, 70), (97, 50), (49, 50), (49, 33)])
    # Open doorway: continuous jamb/header, bottom level with the running foot.
    polygon([(128, 14), (138, 14), (138, 97), (158, 97), (158, 14),
             (168, 14), (168, 106), (128, 106)])
    polygon([(209 + 9 * math.cos(i * math.tau / 64),
              91 + 9 * math.sin(i * math.tau / 64)) for i in range(64)])
    polygon([(212, 79), (225, 77), (244, 51), (232, 43), (215, 62), (207, 72)])
    polygon([(216, 78), (220, 69), (202, 58), (178, 58), (178, 67), (198, 67)])
    polygon([(220, 73), (239, 88), (261, 76), (257, 68), (240, 77), (227, 66)])
    polygon([(233, 51), (241, 42), (212, 33), (199, 14), (190, 19), (206, 43)])
    polygon([(237, 52), (265, 33), (286, 34), (286, 24), (261, 23), (230, 42)])
    pixels = array('f', [0]) * (size * size * 4)
    for row in range(size):
        for col in range(size):
            i = (row * size + col) * 4
            hi = (row * sample) * high + col * sample
            coverage = sum(mask[hi + dy * high + dx] for dy in range(sample)
                           for dx in range(sample)) / (255 * sample * sample)
            # Smooth, even diffuser: green ground, warm neutral white ink.
            green, white = (.007, .245, .050), (.83, .88, .82)
            for channel in range(3):
                pixels[i + channel] = green[channel] * (1 - coverage) + white[channel] * coverage
            pixels[i + 3] = 1
    return image_from_pixels(ASSET_ID, 'face_pictogram', size, pixels, cache)


def validate(objects):
    bpy.context.view_layer.update()
    assert sorted(obj.name for obj in objects) == ['face', 'housing']
    points = [obj.matrix_world @ Vector(c) for obj in objects for c in obj.bound_box]
    minimum = [min(v[i] for v in points) for i in range(3)]
    maximum = [max(v[i] for v in points) for i in range(3)]
    for got, want in zip(minimum + maximum, [-.18, 0, -.075, .18, .05, .075]):
        if abs(got - want) > .000001:
            raise RuntimeError(f'Dimension mismatch: {minimum}..{maximum}')
    for obj in objects:
        if obj.modifiers or tuple(obj.rotation_euler) != (0, 0, 0) or tuple(obj.scale) != (1, 1, 1):
            raise RuntimeError(f'Unapplied transforms: {obj.name}')
        if any(len(poly.vertices) != 3 for poly in obj.data.polygons):
            raise RuntimeError('Only triangles at export')
    print('PASS geometry: 0.360 x 0.150 x 0.050 m; back z=0; two parts; identity transforms; no collision', flush=True)


def build(out_dir):
    reset_scene(SEED)
    cache = ROOT / 'assets/cache' / ASSET_ID
    cache.mkdir(parents=True, exist_ok=True)
    surf = housing_surface()
    face_mat = material(ASSET_ID, 'face', (.1, .3, .1), roughness=.48)
    face_bsdf = face_mat.node_tree.nodes.get('Principled BSDF')
    face_bsdf.inputs['Specular IOR Level'].default_value = .18
    face_bsdf.inputs['Emission Strength'].default_value = .85
    pictogram = raster_pictogram(cache)
    node = texture_node(face_mat, pictogram)
    face_mat.node_tree.links.new(node.outputs['Color'], face_bsdf.inputs['Base Color'])
    face_mat.node_tree.links.new(node.outputs['Color'], face_bsdf.inputs['Emission Color'])
    led_mat = material(ASSET_ID, 'led', (.04, .36, .08), roughness=.27,
                       emission=((.04, .36, .08), .4))
    components, lens, face = geometry(surf, face_mat, led_mat)
    textures = bake_surface('housing', surf, components, cache)
    textures.append({'name': pictogram.name, 'size': list(pictogram.size),
                     'map': 'base_color_and_emission', 'material': face_mat.name, 'embedded': True})
    housing = join_static([*components, lens], 'housing')
    # Static mount-centre origins on both named parts, with all geometry applied.
    for vertex in face.data.vertices:
        vertex.co += face.location
    face.location = (0, 0, 0)
    objects = [housing, face]
    for obj in objects:
        triangulate(obj)
    validate(objects)
    path = Path(out_dir) / f'{ASSET_ID}.glb'
    export_glb(path, objects)
    metadata = write_metadata(ASSET_ID, ROOT / 'assets/meta' / f'{ASSET_ID}.json',
                              path, objects, __file__, textures, 'mount_plane_center',
                              extra={'anchors_godot_m': {'face_surface_centre': [0, 0, -.0485],
                                     'face_size': [.330, .120],
                                     'test_button': [-.111, -.0745, -.031],
                                     'charge_led': [-.091, -.07435, -.031]},
                                     'emission_strength': {'face': .85, 'led': .4},
                                     'pictogram': 'original left arrow, left doorway, left-running figure',
                                     'preview_renderer': 'Cycles CPU; 32 samples; 4 threads'})
    if metadata['triangles'] > 20000 or len(metadata['materials']) > 3:
        raise RuntimeError('Budget exceeded')
    render_previews(ASSET_ID, ROOT / 'assets/previews', objects, {
        'front': {'position': (0, .7, 0), 'target': (0, .025, 0), 'scale': .435},
        'iso': {'position': (-.40, .65, .28), 'target': (0, .025, 0), 'scale': .43},
        'detail': {'position': (-.26, .40, -.25), 'target': (-.075, .026, -.027), 'scale': .26},
    }, SEED)
    validate(objects)
    print(f'ASSET BUILT: {path}; {metadata["triangles"]} triangles; '
          f'{len(metadata["materials"])} materials; {len(metadata["textures"])} embedded textures', flush=True)


if __name__ == '__main__':
    run_cli(build, __doc__)
