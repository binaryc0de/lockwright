"""Principled-only PBR materials and generated, embedded PNG textures."""
from array import array
from pathlib import Path

import bpy


def material(asset_id, part, color, metallic=0.0, roughness=0.5, emission=None):
    mat = bpy.data.materials.new(f'M_{asset_id}_{part}')
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get('Principled BSDF')
    bsdf.inputs['Base Color'].default_value = (*color, 1.0)
    bsdf.inputs['Metallic'].default_value = metallic
    bsdf.inputs['Roughness'].default_value = roughness
    if emission:
        bsdf.inputs['Emission Color'].default_value = (*emission[0], 1.0)
        bsdf.inputs['Emission Strength'].default_value = emission[1]
    mat.diffuse_color = (*color, 1.0)
    return mat


def image_from_pixels(asset_id, map_name, size, pixels, cache_dir, non_color=False):
    if len(pixels) != size * size * 4:
        raise ValueError(f'Invalid pixel buffer for {map_name}')
    image = bpy.data.images.new(f'T_{asset_id}_{map_name}', width=size, height=size, alpha=True)
    image.colorspace_settings.name = 'Non-Color' if non_color else 'sRGB'
    image.pixels.foreach_set(array('f', pixels))
    image.file_format = 'PNG'
    path = Path(cache_dir) / f'{image.name}.png'
    path.parent.mkdir(parents=True, exist_ok=True)
    image.filepath_raw = str(path)
    image.save()
    image.pack()
    return image


def texture_node(mat, image):
    node = mat.node_tree.nodes.new('ShaderNodeTexImage')
    node.image = image
    node.interpolation = 'Linear'
    node.extension = 'EXTEND'
    return node


def base_texture(mat, image):
    node = texture_node(mat, image)
    mat.node_tree.links.new(node.outputs['Color'], mat.node_tree.nodes.get('Principled BSDF').inputs['Base Color'])


def orm_texture(mat, image):
    # Name/group recognized by the glTF exporter: preserve occlusion in R.
    tree = mat.node_tree
    texture = texture_node(mat, image)
    separate = tree.nodes.new('ShaderNodeSeparateColor')
    tree.links.new(texture.outputs['Color'], separate.inputs['Color'])
    bsdf = tree.nodes.get('Principled BSDF')
    tree.links.new(separate.outputs['Green'], bsdf.inputs['Roughness'])
    tree.links.new(separate.outputs['Blue'], bsdf.inputs['Metallic'])
    group = bpy.data.node_groups.get('glTF Material Output')
    if group is None:
        group = bpy.data.node_groups.new('glTF Material Output', 'ShaderNodeTree')
        group.interface.new_socket(name='Occlusion', in_out='INPUT', socket_type='NodeSocketFloat')
    output = tree.nodes.new('ShaderNodeGroup')
    output.node_tree = group
    tree.links.new(separate.outputs['Red'], output.inputs['Occlusion'])


def normal_texture(mat, image, strength=1.0):
    tree = mat.node_tree
    texture = texture_node(mat, image)
    normal = tree.nodes.new('ShaderNodeNormalMap')
    normal.inputs['Strength'].default_value = strength
    tree.links.new(texture.outputs['Color'], normal.inputs['Color'])
    tree.links.new(normal.outputs['Normal'], tree.nodes.get('Principled BSDF').inputs['Normal'])
