"""Scene reset, seed and CPU safety policy shared by every prop."""
import random

import bpy


def reset_scene(seed=0):
    if not bpy.app.background:
        raise RuntimeError("Asset scripts must run with Blender -b")
    if bpy.app.version[:2] != (5, 2):
        raise RuntimeError(f"Blender 5.2.x required, found {bpy.app.version_string}")
    random.seed(seed)
    for obj in list(bpy.data.objects):
        bpy.data.objects.remove(obj, do_unlink=True)
    for collection in (bpy.data.meshes, bpy.data.curves, bpy.data.materials,
                       bpy.data.images, bpy.data.cameras, bpy.data.lights,
                       bpy.data.actions, bpy.data.worlds):
        for block in list(collection):
            collection.remove(block)
    scene = bpy.context.scene
    scene.render.engine = 'CYCLES'
    scene.cycles.device = 'CPU'
    scene.cycles.samples = 32
    scene.cycles.use_denoising = True
    scene.cycles.seed = seed
    scene.cycles.use_animated_seed = False
    scene.render.threads_mode = 'FIXED'
    scene.render.threads = 4
    # Do not enumerate GPU devices or enable any compute backend.
    cycles = bpy.context.preferences.addons.get('cycles')
    if cycles:
        cycles.preferences.compute_device_type = 'NONE'
    scene.unit_settings.system = 'METRIC'
    scene.unit_settings.scale_length = 1.0
    scene.render.fps = 24
    scene.frame_set(0)
    return scene
