"""Binding glTF export settings and metadata computed from the exported file."""
import hashlib
import json
import struct
from datetime import datetime, timezone
from pathlib import Path

import bpy
from mathutils import Vector


def read_glb(path):
    raw = Path(path).read_bytes()
    magic, version, total = struct.unpack_from('<4sII', raw)
    if magic != b'glTF' or version != 2 or total != len(raw):
        raise ValueError('Invalid GLB header')
    length, kind = struct.unpack_from('<II', raw, 12)
    if kind != 0x4E4F534A:
        raise ValueError('Missing GLB JSON chunk')
    return json.loads(raw[20:20 + length])


def export_glb(path, objects):
    if any(obj.type != 'MESH' for obj in objects):
        raise ValueError('Export selection must contain meshes only')
    bpy.ops.object.select_all(action='DESELECT')
    for obj in sorted(objects, key=lambda item: item.name):
        if obj.modifiers:
            raise ValueError(f'Unapplied modifiers: {obj.name}')
        obj.select_set(True)
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.export_scene.gltf(
        filepath=str(path), export_format='GLB', export_apply=True,
        export_yup=True, export_animations=True, export_image_format='AUTO',
        use_selection=True, export_cameras=False, export_lights=False,
        export_texcoords=True, export_normals=True, export_tangents=True,
        export_extras=False, export_materials='EXPORT',
    )
    return read_glb(path)


def write_metadata(asset_id, path, glb_path, objects, script_path, textures, origin, extra=None):
    gltf = read_glb(glb_path)
    accessors = gltf['accessors']
    triangles = 0
    for mesh in gltf['meshes']:
        for primitive in mesh['primitives']:
            if primitive.get('mode', 4) != 4:
                raise ValueError('Only triangle primitives may be exported')
            count = accessors[primitive['indices']]['count'] if 'indices' in primitive else accessors[primitive['attributes']['POSITION']]['count']
            triangles += count // 3
    points = [obj.matrix_world @ Vector(corner) for obj in objects for corner in obj.bound_box]
    minimum = [min(point[i] for point in points) for i in range(3)]
    maximum = [max(point[i] for point in points) for i in range(3)]
    size = [maximum[i] - minimum[i] for i in range(3)]
    source = Path(script_path)
    common = source.parent.parent / 'common'
    pipeline = [source.parent.parent / 'build_assets.sh', *sorted(common.glob('*.py'))]
    data = {
        'asset_id': asset_id,
        'triangles': triangles,
        'materials': sorted(material['name'] for material in gltf['materials']),
        'textures': textures,
        'bounds_m': [round(value, 9) for value in size],  # Blender W,D,H
        'origin': origin,
        'parts': sorted(node['name'] for node in gltf['nodes'] if 'mesh' in node),
        'animations': [animation['name'] for animation in gltf.get('animations', [])],
        'script_sha256': hashlib.sha256(source.read_bytes()).hexdigest(),
        'pipeline_sha256': {str(file.relative_to(source.parent.parent)): hashlib.sha256(file.read_bytes()).hexdigest() for file in pipeline},
        'glb_sha256': hashlib.sha256(Path(glb_path).read_bytes()).hexdigest(),
        'blender_version': bpy.app.version_string,
        'built_at': datetime.now(timezone.utc).isoformat(timespec='seconds'),
        'bounds_godot_m': {
            'min': [round(minimum[0], 9), round(minimum[2], 9), round(-maximum[1], 9)],
            'max': [round(maximum[0], 9), round(maximum[2], 9), round(-minimum[1], 9)],
        },
    }
    if extra:
        data.update(extra)
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(data, indent=2, sort_keys=True) + '\n')
    return data
