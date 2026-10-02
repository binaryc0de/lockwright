"""Welded security-cage panel kit, original PBR textures, CPU-only build.

Three independently placeable meshes export at (0,0,0). Preview placement is
applied only after export. No network, downloads, fonts or external artwork.
Surface/bake structure follows accepted exit_door_maglock and exit_keypad_6.
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
from common.materials import base_texture, image_from_pixels, material, normal_texture, orm_texture
from common.preview import render_previews
from common.scene import reset_scene

ASSET_ID = 'cage_partition_kit'
SEED = 420026
SPECS = [('panel_1200', 1.2, 2.8, -.98, 0),
         ('panel_400', .4, 2.8, -.05, 0),
         ('header_1000', 1.0, .7, .86, 2.1)]

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
    size = 2048 if part == 'frame' else 1024
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



def band(surf, value, centre, width):
    return surf.math('MAXIMUM', 0, surf.math('SUBTRACT', 1,
        surf.math('DIVIDE', surf.math('ABSOLUTE', surf.math('SUBTRACT', value, centre)), width)))


def surfaces():
    frame = Surface('frame', (.040, .045, .050), .57, .08)
    grain = frame.noise((420, 420, 420))
    broad = frame.noise((22, 22, 22))
    scratch = frame.math('GREATER_THAN', frame.noise((14, 160, 480)), .67)
    hand = band(frame, frame.axes.outputs['Z'], 1.17, .40)
    contact = frame.math('MULTIPLY', hand, frame.noise((90, 90, 90)))
    # Fine hand-height marks are sparse; surrounding coating remains intact.
    scuff = frame.math('MULTIPLY', contact, scratch)
    coat = frame.mix(broad, (.016, .020, .025, 1), (.027, .033, .039, 1))
    # Rubbed outside corners reveal small discontinuous steel flecks.
    edges = 0.0
    for _, width, _, ox, _ in SPECS:
        for x in (ox - width / 2 + .0018, ox - width / 2 + .0382,
                  ox + width / 2 - .0382, ox + width / 2 - .0018):
            edges = frame.math('MAXIMUM', edges,
                               band(frame, frame.axes.outputs['X'], x, .0018))
    chips = frame.math('MULTIPLY', edges,
                      frame.math('GREATER_THAN', frame.noise((100, 80, 320)), .66))
    chips = frame.math('MULTIPLY', chips, frame.math('ADD', .14, hand))
    scuff = frame.math('MAXIMUM', scuff, chips)
    coat = frame.mix(frame.math('MULTIPLY', scuff, .62), coat, (.19, .20, .21, 1))
    rough = frame.math('SUBTRACT', frame.math('ADD', .52, frame.math('MULTIPLY', grain, .15)),
                       frame.math('MULTIPLY', contact, .13))
    frame.finish(coat, rough, grain, .32, .00015)
    metal = Surface('metal', (.30, .32, .34), .34, 1)
    machine = metal.noise((2200, 2200, 60))
    metal.finish(metal.mix(machine, (.25, .27, .28, 1), (.37, .39, .41, 1)),
                 metal.math('ADD', .29, metal.math('MULTIPLY', machine, .16)),
                 machine, .18, .000025)
    return frame, metal


def mesh_material(cache):
    """Analytic four-cell wire tile. Transparent holes carry zero alpha.

    World pitch 50 mm / wire diameter 4 mm; tangent normals describe round
    wire cross-sections and flattened spot-welds at the grid intersections.
    The texture repeats; frame/metal UV bakes use non-overlapping atlases.
    """
    size, tile, radius = 1024, .2, .002
    mat = material(ASSET_ID, 'mesh', (.037, .042, .047), metallic=.10, roughness=.56)
    mat.use_backface_culling = False
    mat.surface_render_method = 'DITHERED'
    # Blender 5 alpha threshold represented by Math GREATER_THAN -> glTF MASK.
    base, orm, normal = array('f'), array('f'), array('f')
    for y in range(size):
        py = (y + .5) / size * tile
        dy = (py + .025) % .05 - .025
        for x in range(size):
            px = (x + .5) / size * tile
            dx = (px + .025) % .05 - .025
            distance = min(abs(dx), abs(dy))
            alpha = max(0, min(1, .5 + (radius - distance) * size / tile))
            # Integer hash: deterministic dust and coating grain, never RNG state.
            h = ((x * 73856093) ^ (y * 19349663) ^ SEED) & 1023
            grain = h / 1023
            drift = .5 + .5 * math.sin(px * 73 + math.sin(py * 52))
            c = .027 + .008 * grain + .007 * drift
            base.extend((c, c * 1.12, c * 1.25, alpha))
            weld = abs(dx) < radius * 1.25 and abs(dy) < radius * 1.25
            orm.extend((.92 if weld else 1, .48 + grain * .14, .08, 1))
            if abs(dy) < radius:  # Horizontal wire lies above the vertical wire.
                slope = max(-.94, min(.94, dy / radius))
                nx, ny = 0, slope * (.48 if weld else .86)
            else:
                slope = max(-.94, min(.94, dx / radius))
                nx, ny = slope * .86, 0
            nz = math.sqrt(max(.01, 1 - nx * nx - ny * ny))
            normal.extend((.5 + .5 * nx, .5 + .5 * ny, .5 + .5 * nz, 1))
    images = {}
    for name, buf in [('base_color', base), ('orm', orm), ('normal', normal)]:
        images[name] = image_from_pixels(ASSET_ID, 'mesh_' + name, size, buf, cache,
                                         non_color=name != 'base_color')
    base_texture(mat, images['base_color'])
    tree = mat.node_tree
    tex = next(n for n in tree.nodes if n.type == 'TEX_IMAGE')
    threshold = tree.nodes.new('ShaderNodeMath')
    threshold.operation = 'GREATER_THAN'
    threshold.inputs[1].default_value = .5
    tree.links.new(tex.outputs['Alpha'], threshold.inputs[0])
    tree.links.new(threshold.outputs[0], tree.nodes.get('Principled BSDF').inputs['Alpha'])
    orm_texture(mat, images['orm'])
    normal_texture(mat, images['normal'])
    for node in tree.nodes:
        if node.type == 'TEX_IMAGE':
            node.extension = 'REPEAT'
    return mat, [{'name': im.name, 'size': list(im.size), 'map': name,
                  'material': mat.name, 'embedded': True} for name, im in sorted(images.items())]


def radial(name, location, profile, mat, count=24, socket=False, vertical=False):
    vertices = []
    for ring, (r, depth) in enumerate(profile):
        for i in range(count):
            a = math.tau * i / count
            radius = r * (1 + .15 * math.cos(a * 6)) if socket and ring >= 3 else r
            point = (radius * math.cos(a), depth, radius * math.sin(a))
            if vertical:
                point = (point[0], point[2], point[1])
            vertices.append(point)
    faces = []
    for ring in range(len(profile) - 1):
        for i in range(count):
            j = (i + 1) % count
            faces.append((ring * count + i, (ring + 1) * count + i,
                          (ring + 1) * count + j, ring * count + j))
    # Both profiles end at zero-radius caps; triangulation removes n-gons.
    faces += [tuple(reversed(range(count))),
              tuple(range((len(profile) - 1) * count, len(profile) * count))]
    obj = mesh_object(name, vertices, faces, mat, location)
    for face in obj.data.polygons:
        face.use_smooth = len(face.vertices) == 4
    return obj


def tube(name, dims, loc, mat):
    return box(name, dims, mat, loc, bevel=.0015, segments=3)


def geometry(frame, metal, mesh):
    groups = {}
    for name, w, h, ox, oz in SPECS:
        parts = []
        floor = name != 'header_1000'
        bottom = .008 if floor else 0
        for side in (-1, 1):
            x = ox + side * (w / 2 - .02)
            parts.append(tube('upright', (.04, .04, h - bottom),
                              (x, 0, oz + (h + bottom) / 2), frame.mat))
            if floor:
                # Inward-biased plate stays entirely within nominal panel width.
                foot_x = ox + side * (w / 2 - .045)
                parts.append(box('anchor_plate', (.09, .09, .008), frame.mat,
                                 (foot_x, 0, .004), bevel=.001, segments=3))
                for depth in (-.032, .032):
                    parts.append(radial('anchor_washer', (foot_x, depth, .008),
                        [(.008, 0), (.008, .0014), (.004, .0014), (.004, 0)],
                        metal.mat, count=24, vertical=True))
                    parts.append(radial('anchor_hex', (foot_x, depth, .0094),
                        [(.005, 0), (.0057, .0005), (.0057, .0045), (.0048, .0052)],
                        metal.mat, count=6, vertical=True))
            # M6 fixing heads are real recessed sockets on both faces.
            heights = (.25, h / 2, h - .25) if floor else (.14, h - .14)
            for z in heights:
                for facing in (-1, 1):
                    profile = [(.0045, .0199), (.0046, .0205), (.0040, .0210),
                               (.0020, .0210), (.0018, .0201)]
                    obj = radial('fixing_socket', (x, 0, oz + z), profile,
                                 metal.mat, count=24, socket=True)
                    if facing == -1:
                        for v in obj.data.vertices:
                            v.co.y *= -1
                    parts.append(obj)
        for z in (bottom + .02, h - .02):
            parts.append(tube('crossrail', (w - .08, .04, .04),
                              (ox, 0, oz + z), frame.mat))
        # Small raised corner weld beads, flattened and coated over.
        for x in (ox - w / 2 + .04, ox + w / 2 - .04):
            for z in (oz + bottom + .034, oz + h - .034):
                parts.append(box('corner_weld', (.006, .003, .018), frame.mat,
                                  (x, .0196, z), bevel=.0014, segments=3))
        x0, x1, z0, z1 = ox - w / 2 + .035, ox + w / 2 - .035, oz + bottom + .035, oz + h - .035
        # +Y front, explicitly ordered quad; no solid backing surface.
        sheet = mesh_object('wire_sheet', [(x0, 0, z0), (x0, 0, z1),
                                          (x1, 0, z1), (x1, 0, z0)], [(0, 1, 2, 3)], mesh)
        uv = sheet.data.uv_layers.new(name='UVMap')
        for loop in sheet.data.loops:
            v = sheet.data.vertices[loop.vertex_index].co
            uv.data[loop.index].uv = ((v.x - ox) / .2, (v.z - oz) / .2)
        parts.append(sheet)
        # Two unobtrusive black cable ties; strips wrap around an actual wire.
        if floor:
            for local_x, local_z in ((-.10 if w > .5 else 0, 1.05), (.10 if w > .5 else 0, 1.75)):
                x, z = ox + local_x, oz + local_z
                for depth in (-.0033, .0033):
                    parts.append(box('tie_strap', (.004, .0014, .025), frame.mat,
                                      (x, depth, z), bevel=.0005, segments=2))
                for dz in (-.012, .012):
                    parts.append(box('tie_return', (.004, .0075, .0014), frame.mat,
                                      (x, 0, z + dz), bevel=.0004, segments=2))
                parts.append(box('tie_head', (.007, .004, .006), frame.mat,
                                  (x, .005, z - .010), bevel=.0006, segments=2))
                tail = box('tie_tail', (.004, .0014, .028), frame.mat,
                           (x, .005, z - .027), bevel=.0004, segments=2)
                parts.append(tail)
        groups[name] = parts
    return groups


def build(out_dir):
    reset_scene(SEED)
    cache = ROOT / 'assets/cache' / ASSET_ID
    cache.mkdir(parents=True, exist_ok=True)
    print('BUILD: three security panels, 40 mm frames, 50 mm / 4 mm cutout wire', flush=True)
    frame, metal = surfaces()
    mesh, textures = mesh_material(cache)
    groups = geometry(frame, metal, mesh)
    bpy.context.view_layer.update()
    components = [o for parts in groups.values() for o in parts]
    for part, surf in [('frame', frame), ('metal', metal)]:
        selected = [o for o in components if o.data.materials[0] == surf.mat]
        textures.extend(bake_surface(part, surf, selected, cache))
    objects = []
    for name, w, h, ox, oz in SPECS:
        obj = join_static(groups[name], name, origin=(ox, 0, oz))
        obj.location = (0, 0, 0)
        triangulate(obj)
        objects.append(obj)
    bpy.context.view_layer.update()
    path = Path(out_dir).resolve() / f'{ASSET_ID}.glb'
    gltf = export_glb(path, objects)
    if {n['name'] for n in gltf['nodes'] if 'mesh' in n} != {s[0] for s in SPECS}:
        raise RuntimeError('Export mesh names differ from requested kit')
    if gltf.get('animations') or gltf.get('cameras'):
        raise RuntimeError('Unexpected exported animation/camera')
    for node in gltf['nodes']:
        if any(abs(v) > 1e-8 for v in node.get('translation', [0, 0, 0])):
            raise RuntimeError('All exported parts must overlap at the origin')
        if node.get('scale', [1, 1, 1]) != [1, 1, 1] or node.get('rotation', [0, 0, 0, 1]) != [0, 0, 0, 1]:
            raise RuntimeError('Unapplied part transform')
    cutout = next(m for m in gltf['materials'] if m['name'].endswith('_mesh'))
    if cutout.get('alphaMode') != 'MASK' or cutout.get('doubleSided') is not True:
        raise RuntimeError(f'Wire mesh must export alpha MASK and doubleSided: {cutout}')
    meta = write_metadata(ASSET_ID, ROOT / 'assets/meta' / f'{ASSET_ID}.json',
        path, objects, Path(__file__), textures, 'base_center', extra={
            'part_bounds_godot_m': {
                m['name']: {bound: [round((min if bound == 'min' else max)(
                    gltf['accessors'][p['attributes']['POSITION']][bound][i]
                    for p in m['primitives']), 9) for i in range(3)]
                    for bound in ('min', 'max')} for m in gltf['meshes']},
            'part_triangles': {m['name']: sum(gltf['accessors'][p['indices']]['count'] // 3
                for p in m['primitives']) for m in gltf['meshes']},
            'part_origins_godot_m': {name: [0, 0, 0] for name, *_ in SPECS},
            'forward': 'Blender +Y -> Godot -Z; cutout visible from both sides',
            'wire': {'pitch_m': .05, 'diameter_m': .004, 'texture_tile_m': .2,
                     'alpha_mode': 'MASK', 'alpha_cutoff': cutout.get('alphaCutoff', .5),
                     'double_sided': True, 'nominal_open_area_percent': 84.64},
            'collision': 'none; room-owned box colliders',
            'baking': {'engine': 'CYCLES', 'device': 'CPU', 'samples': 16, 'margin_px': 8,
                       'maps': 'frame and metal emission base/RM, tangent normal, ray AO packed ORM; analytic wire tile'},
            'render': {'engine': 'CYCLES', 'device': 'CPU', 'samples': 32, 'threads': 4},
            'glb_path': str(path.relative_to(ROOT)) if path.is_relative_to(ROOT) else str(path),
        })
    if meta['triangles'] > 20000 or len(meta['materials']) > 3:
        raise RuntimeError('Request budget exceeded')
    print('PASS structure: 3 independent meshes at origin; cutout MASK; double-sided; no collisions', flush=True)
    # Studio placement is temporary; never exported, never included in metadata.
    try:
        for obj, (_, _, _, ox, oz) in zip(objects, SPECS):
            obj.location = (ox, 0, oz)
        bpy.context.view_layer.update()
        render_previews(ASSET_ID, ROOT / 'assets/previews', objects, views={
            'front': {'position': (-.11, 5.5, 1.40), 'target': (-.11, 0, 1.40), 'scale': 3.30},
            'iso': {'position': (-4.2, 5.8, 3.9), 'target': (-.11, 0, 1.4), 'scale': 3.50},
            'detail': {'position': (-1.85, 2, 1.25), 'target': (-1.34, 0, 1.18), 'scale': .72},
        }, seed=SEED)
    finally:
        for obj in objects:
            obj.location = (0, 0, 0)
    print(f'ASSET BUILT: {path}; {meta["triangles"]} triangles; {len(meta["materials"])} materials', flush=True)
    return path


if __name__ == '__main__':
    run_cli(build, __doc__)
