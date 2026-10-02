"""1024 px neutral-grey studio previews. Cycles CPU only, never Eevee."""
from pathlib import Path

import bpy
from mathutils import Vector


def point_at(obj, target):
    obj.rotation_euler = (Vector(target) - obj.location).to_track_quat('-Z', 'Y').to_euler()


def render_previews(asset_id, out_dir, objects, views, seed=0):
    scene = bpy.context.scene
    scene.render.engine = 'CYCLES'
    scene.cycles.device = 'CPU'
    scene.cycles.samples = 32
    scene.cycles.use_denoising = True
    scene.cycles.seed = seed
    scene.cycles.use_adaptive_sampling = True
    scene.cycles.adaptive_threshold = 0.04
    scene.cycles.max_bounces = 4
    scene.render.threads_mode = 'FIXED'
    scene.render.threads = 4
    scene.render.resolution_x = 1024
    scene.render.resolution_y = 1024
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = 'PNG'
    scene.render.image_settings.color_mode = 'RGB'
    scene.render.film_transparent = False
    scene.view_settings.view_transform = 'AgX'
    world = bpy.data.worlds.new('studio_world-noimp')
    world.use_nodes = True
    world.node_tree.nodes['Background'].inputs['Color'].default_value = (0.18, 0.18, 0.18, 1)
    world.node_tree.nodes['Background'].inputs['Strength'].default_value = 0.4
    scene.world = world
    helpers = []
    camera_data = bpy.data.cameras.new('preview_camera-noimp')
    camera_data.type = 'ORTHO'
    camera_data.clip_start = 0.001
    camera_data.clip_end = 10
    camera = bpy.data.objects.new('preview_camera-noimp', camera_data)
    scene.collection.objects.link(camera)
    scene.camera = camera
    helpers.append(camera)
    # Scale the studio relative to a 115 mm reference prop. Light energy
    # scales by area, preserving illumination for other metre-sized assets.
    points = [obj.matrix_world @ Vector(corner) for obj in objects for corner in obj.bound_box]
    minimum = Vector([min(point[i] for point in points) for i in range(3)])
    maximum = Vector([max(point[i] for point in points) for i in range(3)])
    centre = (minimum + maximum) / 2
    factor = max(maximum - minimum) / .115
    for name, position, power, size in (
        ('key', (0.13, 0.18, 0.18), 3.0, 0.15),
        ('fill', (-0.14, 0.12, 0.025), 1.2, 0.12),
        ('rim', (-0.035, -0.10, 0.16), 2.0, 0.10),
    ):
        data = bpy.data.lights.new(f'{name}-noimp', 'AREA')
        data.energy = power * factor * factor
        data.shape = 'DISK'
        data.size = size * factor
        light = bpy.data.objects.new(f'{name}-noimp', data)
        scene.collection.objects.link(light)
        light.location = centre + Vector((position[0], position[1] - .01, position[2])) * factor
        point_at(light, centre)
        helpers.append(light)
    for obj in objects:
        obj.hide_render = obj.name.endswith(('-col', '-colonly', '-convcol'))
    directory = Path(out_dir)
    directory.mkdir(parents=True, exist_ok=True)
    try:
        for name in ('front', 'iso', 'detail'):
            view = views[name]
            camera.location = view['position']
            camera_data.ortho_scale = view['scale']
            point_at(camera, view.get('target', (0, 0.012, 0)))
            scene.render.filepath = str(directory / f'{asset_id}_{name}.png')
            if scene.cycles.device != 'CPU' or scene.render.engine != 'CYCLES':
                raise RuntimeError('Preview rendering is restricted to Cycles CPU')
            bpy.ops.render.render(write_still=True)
    finally:
        for helper in helpers:
            bpy.data.objects.remove(helper, do_unlink=True)
        for obj in objects:
            obj.hide_render = False
