"""Office certificate frame: mitred plastic moulding, paper and faint glass.

Deterministic Blender 5.2 headless build, no downloads or external assets.
Run tools/blender/build_assets.sh certificate_frame (serialized, four threads).
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

ASSET_ID = 'certificate_frame'
SEED = 41726
GLASS_DEPTH = .012
PICTURE_DEPTH = .008


class Surface:
    """Explicit world-space procedural source, replaced by baked PBR maps."""
    def __init__(self, part, color, roughness):
        self.mat = material(ASSET_ID, part, color, roughness=roughness)
        self.tree = self.mat.node_tree
        self.bsdf = self.tree.nodes.get('Principled BSDF')
        self.position = self.node('ShaderNodeNewGeometry').outputs['Position']
        self.axes = self.node('ShaderNodeSeparateXYZ', Vector=self.position)

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

    def math(self, operation, a, b):
        node = self.node('ShaderNodeMath')
        node.operation = operation
        self.set(node.inputs[0], a)
        self.set(node.inputs[1], b)
        return node.outputs[0]

    def noise(self, scale, detail=2):
        return self.node('ShaderNodeTexNoise', Vector=self.position,
                         Scale=scale, Detail=detail, Roughness=.68).outputs['Fac']

    def mix(self, factor, a, b):
        return self.node('ShaderNodeMixRGB', Fac=factor, Color1=a, Color2=b).outputs[0]

    def finish(self, color, roughness, height, distance):
        self.color, self.roughness = color, roughness
        self.set(self.bsdf.inputs['Base Color'], color)
        self.set(self.bsdf.inputs['Roughness'], roughness)
        bump = self.node('ShaderNodeBump', Height=height, Strength=.28, Distance=distance)
        self.tree.links.new(bump.outputs['Normal'], self.bsdf.inputs['Normal'])


def surfaces():
    moulding = Surface('moulding', (.022, .024, .025), .39)
    fine = moulding.noise(2400)
    broad = moulding.noise(38)
    coat = moulding.mix(broad, (.012, .014, .015, 1), (.025, .027, .028, 1))
    # Settled dust is strongest on the upward-facing outer edge, fading down
    # the front's top rail. It is sparse enough to retain black plastic.
    top = moulding.math('MAXIMUM', 0, moulding.math('DIVIDE',
        moulding.math('SUBTRACT', moulding.axes.outputs['Z'], .204), .016))
    dust = moulding.math('MULTIPLY', top, moulding.math('MULTIPLY', broad, .19))
    coat = moulding.mix(dust, coat, (.23, .21, .175, 1))
    # Localised handling scuffs near the lower screen-right mitred corner.
    centre = moulding.node('ShaderNodeVectorMath')
    centre.operation = 'DISTANCE'
    moulding.set(centre.inputs[0], moulding.position)
    moulding.set(centre.inputs[1], (-.158, .017, -.209))
    corner = moulding.math('MAXIMUM', 0, moulding.math('SUBTRACT', 1,
        moulding.math('DIVIDE', centre.outputs['Value'], .028)))
    scaled = moulding.node('ShaderNodeVectorMath')
    scaled.operation = 'MULTIPLY'
    moulding.set(scaled.inputs[0], moulding.position)
    moulding.set(scaled.inputs[1], (700, 140, 8500))
    scratches = moulding.node('ShaderNodeTexNoise', Vector=scaled.outputs['Vector'],
                             Scale=1.0, Detail=2).outputs['Fac']
    scuff = moulding.math('MULTIPLY', corner,
        moulding.math('GREATER_THAN', scratches, .63))
    coat = moulding.mix(moulding.math('MULTIPLY', scuff, .27), coat,
                        (.105, .105, .099, 1))
    rear = moulding.math('LESS_THAN', moulding.axes.outputs['Y'], .003)
    rough = moulding.math('ADD', .31, moulding.math('MULTIPLY', fine, .13))
    rough = moulding.math('ADD', rough, moulding.math('MULTIPLY', dust, .7))
    rough = moulding.math('ADD', rough, moulding.math('MULTIPLY', scuff, .19))
    rough = moulding.mix(rear, rough, (.76, .76, .76, 1))
    moulding.finish(coat, rough,
        moulding.math('SUBTRACT', fine, moulding.math('MULTIPLY', scuff, .45)), .00009)

    picture = Surface('picture', (.87, .86, .83), .81)
    grain = picture.noise(3100)
    paper = picture.mix(picture.noise(30), (.86, .855, .832, 1), (.90, .893, .865, 1))
    picture.finish(paper, picture.math('ADD', .77,
        picture.math('MULTIPLY', grain, .09)), grain, .000035)
    return moulding, picture


def moulding_geometry(mat):
    # Swept 20 mm moulding section, with rounded outer nose, shallow crown,
    # inner bead, glass rebate and a recessed back. Actual cross section,
    # rather than four bevelled rectangular blocks.
    profile = [(0, .0012), (0, .0134), (.00015, .01455),
               (.00055, .01555), (.00115, .01645), (.0019, .0172),
               (.0028, .01775), (.0038, .018), (.006, .018),
               (.010, .0175), (.014, .0166), (.0165, .0156),
               (.0174, .0154), (.018, .01555), (.0186, .0156),
               (.0192, .0153), (.0197, .0147), (.020, .0138),
               (.020, .003), (.006, .003), (.006, 0), (.0012, 0)]
    rails = []
    for side in range(4):
        vertices = []
        for inset, depth in profile:
            x, z = .17 - inset, .22 - inset
            corners = [Vector((-x, depth, -z)), Vector((x, depth, -z)),
                       Vector((x, depth, z)), Vector((-x, depth, z))]
            a, b = corners[side], corners[(side + 1) % 4]
            direction = (b - a).normalized()
            # 0.12 mm real mitre joint: separate closed sections, not a decal.
            vertices.extend((tuple(a + direction * .00006), tuple(b - direction * .00006)))
        count = len(profile)
        faces = [(2 * i, 2 * i + 1, 2 * ((i + 1) % count) + 1,
                  2 * ((i + 1) % count)) for i in range(count)]
        faces.extend([tuple(reversed(range(0, 2 * count, 2))),
                      tuple(range(1, 2 * count, 2))])
        obj = mesh_object(f'rail_{side}', vertices, faces, mat)
        # Keep caps flat and the profile smooth. Weighted normals preserve
        # long straight surfaces while the small roundovers catch studio light.
        for face in obj.data.polygons:
            face.use_smooth = face.index < count
        triangulate(obj)
        rails.append(obj)
    backing = box('backing', (.307, .0025, .407), mat,
                  (0, .00125, 0), bevel=.00035, segments=4)
    rails.append(backing)
    obj = join_static(rails, 'moulding')
    triangulate(obj)
    active(obj)
    normal = obj.modifiers.new('weighted_normals', 'WEIGHTED_NORMAL')
    normal.keep_sharp = True
    normal.weight = 50
    bpy.ops.object.modifier_apply(modifier=normal.name)
    return obj


def document_quad(name, depth, mat):
    obj = mesh_object(name, [(-.15, 0, -.20), (.15, 0, -.20),
                            (.15, 0, .20), (-.15, 0, .20)],
                      [(0, 3, 2), (0, 2, 1)], mat, (0, depth, 0))
    uv = obj.data.uv_layers.new(name='UVMap')
    # From +Y in Blender / -Z in Godot, screen-right is -X, as in uv_front.
    for loop in obj.data.loops:
        vertex = obj.data.vertices[loop.vertex_index].co
        uv.data[loop.index].uv = (.5 - vertex.x / .30, .5 + vertex.z / .40)
    return obj


def bake_surface(obj, surf, size, cache, unwrap=False):
    active(obj)
    if unwrap:
        bpy.ops.object.mode_set(mode='EDIT')
        bpy.ops.mesh.select_all(action='SELECT')
        bpy.ops.uv.smart_project(angle_limit=math.radians(66), island_margin=8 / size,
                                 margin_method='FRACTION', scale_to_bounds=True)
        bpy.ops.uv.average_islands_scale()
        bpy.ops.uv.pack_islands(rotate=True, margin_method='FRACTION', margin=8 / size)
        bpy.ops.object.mode_set(mode='OBJECT')
    scene = bpy.context.scene
    scene.cycles.samples = 16
    scene.render.bake.margin = 8
    scene.render.bake.use_clear = True
    scene.render.bake.use_selected_to_active = False
    scene.render.bake.normal_space = 'TANGENT'
    tree = surf.tree
    output = next(node for node in tree.nodes if node.type == 'OUTPUT_MATERIAL')
    emitter = surf.node('ShaderNodeEmission', Strength=1.0)
    target = surf.node('ShaderNodeTexImage')
    images = {}
    for name, kind, color in [('base_color', 'EMIT', surf.color),
                             ('orm', 'EMIT', None), ('normal', 'NORMAL', None)]:
        image = bpy.data.images.new(f'T_{ASSET_ID}_{obj.name}_{name}',
                                    width=size, height=size, alpha=False)
        image.colorspace_settings.name = 'sRGB' if name == 'base_color' else 'Non-Color'
        target.image = image
        tree.nodes.active = target
        if name == 'orm':
            color = surf.node('ShaderNodeCombineColor', Red=1.0,
                             Green=surf.roughness, Blue=0.0).outputs[0]
        if kind == 'EMIT':
            surf.set(emitter.inputs['Color'], color)
            tree.links.new(emitter.outputs[0], output.inputs['Surface'])
        else:
            tree.links.new(surf.bsdf.outputs[0], output.inputs['Surface'])
        print(f'BAKE {obj.name} {name}: {size}px, {kind}, CPU, 8px margin', flush=True)
        bpy.ops.object.bake(type=kind)
        images[name] = image
    # Geometric AO packed into R, as on the accepted desk. Paper stays evenly
    # lit: no baked shadow can obscure a later replacement certificate texture.
    if unwrap:
        ao = bpy.data.images.new('ao_work-noimp', width=size, height=size, alpha=False)
        ao.colorspace_settings.name = 'Non-Color'
        target.image = ao
        tree.nodes.active = target
        bpy.ops.object.bake(type='AO')
        packed = array('f', [0]) * (size * size * 4)
        occlusion = array('f', [0]) * len(packed)
        images['orm'].pixels.foreach_get(packed)
        ao.pixels.foreach_get(occlusion)
        for index in range(0, len(packed), 4):
            packed[index] = .55 + .45 * occlusion[index]
            packed[index + 3] = 1
        images['orm'].pixels.foreach_set(packed)
        bpy.data.images.remove(ao)
    for image in images.values():
        image.file_format = 'PNG'
        image.filepath_raw = str(cache / f'{image.name}.png')
        image.save()
        image.pack()
    for node in list(tree.nodes):
        if node not in (surf.bsdf, output):
            tree.nodes.remove(node)
    tree.links.new(surf.bsdf.outputs[0], output.inputs['Surface'])
    base_texture(surf.mat, images['base_color'])
    orm_texture(surf.mat, images['orm'])
    normal_texture(surf.mat, images['normal'])
    return [{'name': image.name, 'size': list(image.size), 'map': name,
             'material': surf.mat.name, 'embedded': True}
            for name, image in sorted(images.items())]


def validate_export(gltf, objects):
    nodes = {node['name']: node for node in gltf['nodes'] if 'mesh' in node}
    if set(nodes) != {'moulding', 'picture', 'glass'} or gltf.get('animations'):
        raise RuntimeError('Unexpected exported parts or animations')
    for node in nodes.values():
        if node.get('rotation', [0, 0, 0, 1]) != [0, 0, 0, 1] or node.get('scale', [1, 1, 1]) != [1, 1, 1]:
            raise RuntimeError('Unapplied exported transforms')
    for name, depth in [('picture', PICTURE_DEPTH), ('glass', GLASS_DEPTH)]:
        node = nodes[name]
        if any(abs(a - b) > 1e-7 for a, b in zip(node['translation'], [0, 0, -depth])):
            raise RuntimeError(f'Incorrect anchor for {name}')
        primitive = gltf['meshes'][node['mesh']]['primitives'][0]
        position = gltf['accessors'][primitive['attributes']['POSITION']]
        if any(abs(a - b) > 1e-7 for a, b in zip(position['min'], [-.15, -.20, 0])) or any(
                abs(a - b) > 1e-7 for a, b in zip(position['max'], [.15, .20, 0])):
            raise RuntimeError(f'Incorrect document bounds for {name}')
    glass = next(mat for mat in gltf['materials'] if mat['name'] == f'M_{ASSET_ID}_glass')
    if glass.get('alphaMode') != 'BLEND' or glass['pbrMetallicRoughness']['baseColorFactor'][3] > .08:
        raise RuntimeError('Glass must remain faint and alpha blended')
    for obj in objects:
        if any(len(face.vertices) != 3 for face in obj.data.polygons):
            raise RuntimeError('Non-triangle topology')
    print('PASS geometry: 300 x 400 mm upright UV quads; 4 mm separation; mount origin; three parts; faint BLEND glass')


def build(out_dir):
    reset_scene(SEED)
    cache = ROOT / 'assets/cache' / ASSET_ID
    cache.mkdir(parents=True, exist_ok=True)
    moulding_surface, picture_surface = surfaces()
    moulding = moulding_geometry(moulding_surface.mat)
    textures = bake_surface(moulding, moulding_surface, 1024, cache, unwrap=True)
    picture = document_quad('picture', PICTURE_DEPTH, picture_surface.mat)
    moulding.hide_render = True
    textures.extend(bake_surface(picture, picture_surface, 512, cache))
    moulding.hide_render = False
    glass_mat = material(ASSET_ID, 'glass', (.94, .97, 1), roughness=.20)
    bsdf = glass_mat.node_tree.nodes.get('Principled BSDF')
    bsdf.inputs['Alpha'].default_value = .055
    bsdf.inputs['IOR'].default_value = 1.45
    bsdf.inputs['Specular IOR Level'].default_value = .28
    glass_mat.diffuse_color = (.94, .97, 1, .055)
    glass_mat.surface_render_method = 'DITHERED'
    glass_mat.use_transparency_overlap = False
    glass = document_quad('glass', GLASS_DEPTH, glass_mat)
    objects = [moulding, picture, glass]
    bpy.context.view_layer.update()
    glb_path = Path(out_dir).resolve() / f'{ASSET_ID}.glb'
    gltf = export_glb(glb_path, objects)
    validate_export(gltf, objects)
    meta = write_metadata(ASSET_ID, ROOT / 'assets/meta' / f'{ASSET_ID}.json',
                          glb_path, objects, Path(__file__), textures,
                          origin='mount_plane_center', extra={
        'anchors_godot_m': {'picture_centre': [0, 0, -PICTURE_DEPTH]},
        'glass_centre_godot_m': [0, 0, -GLASS_DEPTH],
        'glass_picture_separation_m': .004,
        'picture_size_m': [.30, .40],
        'picture_uv': '0..1, v up; u increases toward screen-right (-X when viewed from Godot -Z)',
        'forward': 'Blender +Y -> Godot -Z',
        'origin_reference': 'centre of the back mounting face, Godot z=0',
        'collision': None,
        'glass': {'alpha_mode': 'BLEND', 'opacity': .055, 'roughness': .20,
                  'metallic': 0, 'ior': 1.45},
        'baking': {'engine': 'CYCLES', 'device': 'CPU', 'samples': 16, 'margin_px': 8,
                   'maps': 'procedural base colour/RM, tangent normal; moulding AO packed in ORM R'},
        'render': {'engine': 'CYCLES', 'device': 'CPU', 'samples': 32,
                   'denoise': True, 'threads': 4},
        'glb_path': str(glb_path.relative_to(ROOT)) if glb_path.is_relative_to(ROOT) else str(glb_path),
    })
    if meta['triangles'] > 20000 or len(meta['materials']) != 3:
        raise RuntimeError('Request budget exceeded')
    if any(abs(a - b) > 1e-6 for a, b in zip(meta['bounds_m'], [.34, .018, .44])):
        raise RuntimeError('Outer frame dimensions differ from request')
    views = {
        'front': {'position': (0, 1.1, 0), 'target': (0, .009, 0), 'scale': .51},
        'iso': {'position': (-.58, .95, .44), 'target': (0, .009, 0), 'scale': .55},
        'detail': {'position': (-.27, .43, -.10), 'target': (-.134, .010, -.182), 'scale': .135},
    }
    render_previews(ASSET_ID, ROOT / 'assets/previews', objects, views, seed=SEED)
    print(f'ASSET BUILT: {glb_path}; {meta["triangles"]} triangles; {len(meta["materials"])} materials')
    return glb_path


if __name__ == '__main__':
    run_cli(build, __doc__)
