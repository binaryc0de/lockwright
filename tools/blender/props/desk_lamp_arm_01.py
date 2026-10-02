"""Reduce Poly Haven's CC0 lamp without changing its source placement or UV atlas.

Offline, deterministic Blender 5.2 build. Use build_assets.sh for the shared
Blender process lock and CPU-only, four-thread preview rendering.
"""
from array import array
import hashlib
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
from common.geometry import active
from common.preview import render_previews
from common.scene import reset_scene

ASSET_ID = 'desk_lamp_arm_01'
SEED = 100201
SOURCE = ROOT / 'game/assets/core/third_party/polyhaven/desk_lamp_arm_01/desk_lamp_arm_01_1k.gltf'
ATTRIBUTION = {'title': 'Desk Lamp Arm 01', 'author': 'Poly Haven', 'license': 'CC0',
               'url': 'https://polyhaven.com/a/desk_lamp_arm_01',
               'source': str(SOURCE.relative_to(ROOT))}


def triangles(obj):
    return sum(len(p.vertices) - 2 for p in obj.data.polygons)


def bounds(objects):
    points = [obj.matrix_world @ v.co for obj in objects for v in obj.data.vertices]
    return [min(p[i] for p in points) for i in range(3)], [max(p[i] for p in points) for i in range(3)]


def apply(obj, modifier):
    active(obj)
    bpy.ops.object.modifier_apply(modifier=modifier.name)


def reduce_component(obj):
    """Keep low-density arms/springs/rim; reduce oversampled isolated surfaces.

    Loose components include normal/UV splits. Never weld/reunwrap, so UV seams
    and hard normal boundaries cannot collapse into neighbouring surfaces.
    """
    before = triangles(obj)
    low, high = bounds([obj])
    size = [high[i] - low[i] for i in range(3)]
    category, ratio = 'arm_spring_rim', 1.0
    if low[2] < 0:
        category, ratio = 'underside_clamp', .22 if before > 100 else .7
    elif obj.data.materials[obj.data.polygons[0].material_index].name.endswith('_light'):
        category, ratio = 'bulb', .40
    elif size[0] > .10 and before > 1000:
        category, ratio = 'shade_surface', .48
    elif before > 300:
        category, ratio = 'dense_joint_hardware', .32
    elif before > 100 and max(size) < .025:
        category, ratio = 'small_fastener', .40
    # Coplanar tessellation is removed first; delimit UVs and source normals.
    if len(obj.data.polygons) > 3:
        dissolve = obj.modifiers.new('hidden_planar_detail', 'DECIMATE')
        dissolve.decimate_type = 'DISSOLVE'
        dissolve.angle_limit = math.radians(.1)
        dissolve.delimit = {'UV', 'NORMAL', 'MATERIAL', 'SHARP'}
        apply(obj, dissolve)
    if ratio < 1 and triangles(obj) > 20:
        modifier = obj.modifiers.new('surface_reduction', 'DECIMATE')
        modifier.decimate_type = 'COLLAPSE'
        modifier.ratio = ratio
        modifier.use_collapse_triangulate = True
        apply(obj, modifier)
    triangulate = obj.modifiers.new('export_triangles', 'TRIANGULATE')
    triangulate.keep_custom_normals = True
    apply(obj, triangulate)
    return {'category': category, 'before': before, 'after': triangles(obj)}


def join_parts(objects, name):
    # All source components share the same identity transform and origin.
    active(objects[0])
    if len(objects) > 1:
        for obj in objects:
            obj.select_set(True)
        bpy.ops.object.join()
    obj = bpy.context.view_layer.objects.active
    obj.name = obj.data.name = name
    # Remove unused material slots, keeping exactly the source material.
    used = sorted({p.material_index for p in obj.data.polygons})
    materials = [obj.data.materials[i] for i in used]
    indices = {old: new for new, old in enumerate(used)}
    for p in obj.data.polygons:
        p.material_index = indices[p.material_index]
    obj.data.materials.clear()
    for mat in materials:
        obj.data.materials.append(mat)
    return obj


def comparison(previews, source, objects, views):
    """Render source under the identical studio and compose via Blender pixels."""
    for obj in objects:
        obj.hide_render = True
    source.hide_render = False
    scratch = ROOT / 'assets/cache' / ASSET_ID / 'source'
    render_previews(ASSET_ID, scratch, [source], views, seed=SEED)
    source.hide_render = True
    for obj in objects:
        obj.hide_render = False
    # Left = source, right = reduced; upper row full lamp, lower row joint detail.
    canvas = bpy.data.images.new(f'T_{ASSET_ID}_comparison', width=2048, height=2048, alpha=False)
    pixels = array('f', [0.0]) * (2048 * 2048 * 4)
    for row, view in ((1, 'iso'), (0, 'detail')):
        for col, directory in ((0, scratch), (1, previews)):
            img = bpy.data.images.load(str(directory / f'{ASSET_ID}_{view}.png'), check_existing=False)
            src = array('f', [0.0]) * (1024 * 1024 * 4)
            img.pixels.foreach_get(src)
            for y in range(1024):
                start = ((row * 1024 + y) * 2048 + col * 1024) * 4
                pixels[start:start + 4096] = src[y * 4096:(y + 1) * 4096]
            bpy.data.images.remove(img)
    canvas.pixels.foreach_set(pixels)
    canvas.filepath_raw = str(previews / f'{ASSET_ID}_comparison.png')
    canvas.file_format = 'PNG'
    canvas.save()
    bpy.data.images.remove(canvas)


def build(out_dir):
    reset_scene(SEED)
    bpy.ops.import_scene.gltf(filepath=str(SOURCE), merge_vertices=True)
    meshes = [obj for obj in bpy.context.scene.objects if obj.type == 'MESH']
    if len(meshes) != 1:
        raise RuntimeError('Expected one source mesh with two materials')
    lamp = meshes[0]
    source = lamp.copy()
    source.data = lamp.data.copy()
    source.name = 'source-noimp'
    bpy.context.scene.collection.objects.link(source)
    source.hide_render = True
    source_bounds = bounds([source])
    source_triangles = triangles(source)
    active(lamp)
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.mesh.separate(type='LOOSE')
    bpy.ops.object.mode_set(mode='OBJECT')
    components = sorted([obj for obj in bpy.context.scene.objects if obj.type == 'MESH' and obj != source], key=lambda o: o.name)
    reduction = [reduce_component(obj) for obj in components]
    groups = [[obj for obj in components if obj.data.materials[obj.data.polygons[0].material_index].name.endswith('_light') == light]
              for light in (False, True)]
    parts = [join_parts(group, name) for group, name in zip(groups, ('lamp', 'lamp_light'))]
    bpy.context.view_layer.update()
    if sum(triangles(obj) for obj in parts) > 12000:
        raise RuntimeError(f'Reduction misses the 12000-triangle target: {sum(triangles(obj) for obj in parts)}')
    for obj in parts:
        if obj.matrix_world != source.matrix_world or not obj.data.uv_layers:
            raise RuntimeError('Source placement or UVs lost')
    glb_path = Path(out_dir) / f'{ASSET_ID}.glb'
    gltf = export_glb(glb_path, parts)
    if {m['name'] for m in gltf['materials']} != {ASSET_ID, ASSET_ID + '_light'}:
        raise RuntimeError('Source materials not preserved')
    textures = [{'name': Path(bpy.path.abspath(img.filepath)).stem,
                 'source_image_name': img.name, 'size': list(img.size), 'embedded': True,
                 'source_sha256': hashlib.sha256(Path(bpy.path.abspath(img.filepath)).read_bytes()).hexdigest()}
                for img in sorted(bpy.data.images, key=lambda i: i.name) if img.source == 'FILE']
    if len(textures) != 3 or any(max(img['size']) > 1024 for img in textures):
        raise RuntimeError('Source must have exactly three textures, at most 1024 px')
    final_bounds = bounds(parts)
    bounds_delta = max(abs(a - b) for source_side, final_side in zip(source_bounds, final_bounds)
                       for a, b in zip(source_side, final_side))
    if bounds_delta > .001:
        raise RuntimeError(f'Silhouette bounds drifted by {bounds_delta} m')
    reduction_summary = []
    for category in sorted({component['category'] for component in reduction}):
        group = [component for component in reduction if component['category'] == category]
        reduction_summary.append({'category': category, 'components': len(group),
                                  'source_triangles': sum(c['before'] for c in group),
                                  'reduced_triangles': sum(c['after'] for c in group)})
    extra = {'glb_path': str(glb_path.relative_to(ROOT)) if glb_path.is_relative_to(ROOT) else str(glb_path),
             'attribution': ATTRIBUTION, 'source_triangles': source_triangles,
             'source_bounds_blender_m': source_bounds, 'reduction': reduction_summary,
             'max_bounds_delta_m': bounds_delta,
             'origin_reference': 'Unmodified Poly Haven source origin at desk clamp; underside extends below mounting height',
             'render': {'engine': 'CYCLES', 'device': 'CPU', 'threads': 4, 'samples': 32},
             'source_files_sha256': {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
                                     for p in sorted(SOURCE.parent.rglob('*')) if p.suffix in ('.gltf', '.bin', '.jpg')}}
    meta = write_metadata(ASSET_ID, ROOT / f'assets/meta/{ASSET_ID}.json', glb_path, parts,
                          __file__, textures, 'source_clamp', extra=extra)
    previews = ROOT / 'assets/previews'
    # +Y faces Godot -Z, retaining the CC0 source orientation.
    views = {
        'front': {'position': (1.1, 1.6, .68), 'target': (-.0176, -.0103, .36), 'scale': 1.02},
        'iso': {'position': (1.8, 1.05, 1.30), 'target': (-.0176, -.0103, .36), 'scale': 1.02},
        'detail': {'position': (.65, -.70, .67), 'target': (0, -.16, .37), 'scale': .48},
    }
    render_previews(ASSET_ID, previews, parts, views, seed=SEED)
    comparison(previews, source, parts, views)
    print(f'SOURCE: {source_triangles} triangles; source origin and identity transforms preserved')
    print(f'ASSET BUILT: {glb_path}; {meta["triangles"]} triangles; 2 materials; 2 parts')


if __name__ == '__main__':
    run_cli(build, __doc__)
