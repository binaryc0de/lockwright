"""Emergency steel exit door, hinge-pivoted leaf, CPU-baked worn PBR finishes.

Owner-made deterministic Blender 5.2 asset. No downloads or network.
Run tools/blender/build_assets.sh exit_door_maglock (flock, CPU, 4 threads).
All authored dimensions below are Godot metres; +Y Blender faces Godot -Z.
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

ASSET_ID = 'exit_door_maglock'
SEED = 210026
LED_ANCHOR = (.948, 2.068, -.0708)
LABEL_ANCHOR = (.50, 1.27, .0045)


def godot(point):
    return (point[0], -point[2], point[1])


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



def cylinder(name, a, b, radius, mat, count=40):
    """Closed round bar, with a real rounded end profile; endpoints in Godot."""
    a, b = Vector(godot(a)), Vector(godot(b))
    axis = (b - a).normalized()
    u = axis.cross(Vector((0, 0, 1)))
    if u.length < .01:
        u = axis.cross(Vector((0, 1, 0)))
    u.normalize()
    v = axis.cross(u).normalized()
    length = (b - a).length
    roundover = min(radius * .35, length * .30)
    profile = [(0, radius - roundover), (.293 * roundover, radius - .293 * roundover),
               (roundover, radius), (length - roundover, radius),
               (length - .293 * roundover, radius - .293 * roundover),
               (length, radius - roundover)]
    verts = [tuple(a + axis * d + r * (math.cos(i * math.tau / count) * u +
                                     math.sin(i * math.tau / count) * v))
             for d, r in profile for i in range(count)]
    faces = []
    for ring in range(len(profile) - 1):
        for i in range(count):
            j = (i + 1) % count
            faces.append((ring * count + i, ring * count + j,
                          (ring + 1) * count + j, (ring + 1) * count + i))
    # Explicit fan caps: no n-gons go into the UV bake.
    for start, reverse in [(0, True), ((len(profile) - 1) * count, False)]:
        for i in range(1, count - 1):
            face = (start, start + i, start + i + 1)
            faces.append(tuple(reversed(face)) if reverse else face)
    obj = mesh_object(name, verts, faces, mat)
    for face in obj.data.polygons:
        face.use_smooth = len(face.vertices) == 4
    return obj



def bake_surface(part, surf, components, cache):
    """Unwrap one material globally, bake four passes, transfer exact UV loops.

    The temporary mesh uses world coordinates, so grain/wear are continuous.
    Islands never overlap; packing and baking both reserve an 8 pixel margin.
    Only the AO pass uses rays. Base colour / packed RM are emission bakes;
    normals are Cycles tangent NORMAL bakes of the procedural microstructure.
    """
    size = 2048 if part in ('leaf', 'frame', 'metal') else 512
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


def rect(surf, x0, x1, y0, y1):
    x, y = surf.axes.outputs['X'], surf.axes.outputs['Z']
    return surf.math('MULTIPLY', surf.math('MULTIPLY', surf.math('GREATER_THAN', x, x0),
                    surf.math('LESS_THAN', x, x1)), surf.math('MULTIPLY',
                    surf.math('GREATER_THAN', y, y0), surf.math('LESS_THAN', y, y1)))


def stroke(surf, a, b, radius):
    """Analytic capsule for original running-person sticker artwork."""
    x = surf.math('SUBTRACT', surf.axes.outputs['X'], a[0])
    y = surf.math('SUBTRACT', surf.axes.outputs['Z'], a[1])
    dx, dy = b[0] - a[0], b[1] - a[1]
    t = surf.math('DIVIDE', surf.math('ADD', surf.math('MULTIPLY', x, dx),
                  surf.math('MULTIPLY', y, dy)), dx * dx + dy * dy)
    t = surf.math('MINIMUM', 1, surf.math('MAXIMUM', 0, t))
    xx = surf.math('SUBTRACT', x, surf.math('MULTIPLY', t, dx))
    yy = surf.math('SUBTRACT', y, surf.math('MULTIPLY', t, dy))
    return surf.math('LESS_THAN', surf.math('ADD', surf.math('MULTIPLY', xx, xx),
                     surf.math('MULTIPLY', yy, yy)), radius * radius)


def surfaces():
    leaf = Surface('leaf', (.19, .26, .31), .48)
    x, y = leaf.axes.outputs['X'], leaf.axes.outputs['Z']
    micro = leaf.noise((780, 780, 780))
    broad = leaf.noise((9, 13, 9), detail=3)
    coat = leaf.mix(broad, (.165, .222, .269, 1), (.194, .258, .307, 1))
    # Thin chips along real sheet-metal edges; scale is in metres.
    edge_x = leaf.math('MINIMUM', leaf.math('ABSOLUTE', leaf.math('SUBTRACT', x, .01)),
                       leaf.math('ABSOLUTE', leaf.math('SUBTRACT', x, .99)))
    edge_y = leaf.math('MINIMUM', leaf.math('ABSOLUTE', y),
                       leaf.math('ABSOLUTE', leaf.math('SUBTRACT', y, 2.08)))
    edge = leaf.math('LESS_THAN', leaf.math('MINIMUM', edge_x, edge_y), .0045)
    edge = leaf.math('MULTIPLY', edge, leaf.math('GREATER_THAN', leaf.noise((170, 110, 170)), .55))
    # Stretched scratches, dark shoe rubs below the kick plate, oily hand wear
    # around the panic bar. The flat integration label area stays clean.
    front = leaf.math('GREATER_THAN', leaf.axes.outputs['Y'], -.008)
    push = leaf.math('MULTIPLY', band(leaf, y, 1.045, .19), front)
    shoe = leaf.math('MULTIPLY', band(leaf, y, .38, .19), front)
    streak = leaf.math('GREATER_THAN', leaf.noise((7, 180, 650), detail=2), .70)
    scratches = leaf.math('MULTIPLY', leaf.math('MAXIMUM', push, shoe), streak)
    scuff = leaf.math('MULTIPLY', leaf.math('MAXIMUM', push, shoe), leaf.noise((28, 8, 26)))
    coat = leaf.mix(leaf.math('MULTIPLY', scuff, .55), coat, (.025, .033, .038, 1))
    hand_rub = leaf.math('MULTIPLY', band(leaf, x, .80, .16), band(leaf, y, 1.102, .11))
    hand_rub = leaf.math('MULTIPLY', front, leaf.math('MULTIPLY', hand_rub, leaf.noise((55, 8, 33))))
    coat = leaf.mix(leaf.math('MULTIPLY', hand_rub, .65), coat, (.027, .036, .042, 1))
    # Physical scrape paths in the texture, concentrated where bags, rings
    # and boot toes contact the door; no random marks in the label area.
    scrape = 0
    for a, b, radius in [
        ((.76, 1.121), (.852, 1.103), .0012),
        ((.70, 1.142), (.784, 1.134), .0008),
        ((.792, 1.079), (.884, 1.057), .0013),
        ((.597, 1.092), (.642, 1.085), .0007),
        ((.216, 1.075), (.258, 1.061), .0008),
        ((.725, .886), (.778, .867), .0011),
        ((.252, .412), (.372, .398), .0013),
        ((.47, .461), (.559, .438), .0015),
        ((.58, .403), (.679, .391), .0010),
        ((.713, .385), (.80, .374), .0013),
    ]:
        scrape = leaf.math('MAXIMUM', scrape, stroke(leaf, a, b, radius))
    scrape = leaf.math('MULTIPLY', scrape, front)
    fragmented = leaf.math('MULTIPLY', scrape, leaf.math('GREATER_THAN', leaf.noise((390, 35, 250)), .39))
    coat = leaf.mix(scrape, coat, (.042, .05, .053, 1))
    coat = leaf.mix(fragmented, coat, (.26, .275, .28, 1))
    chips = leaf.math('MAXIMUM', fragmented, leaf.math('MAXIMUM', edge, leaf.math('MULTIPLY', scratches, .70)))
    coat = leaf.mix(chips, coat, (.255, .272, .277, 1))
    rough = leaf.math('ADD', .43, leaf.math('MULTIPLY', micro, .13))
    rough = leaf.math('SUBTRACT', rough, leaf.math('MULTIPLY', push, .17))
    rough = leaf.math('ADD', rough, leaf.math('MULTIPLY', shoe, .09))
    leaf.metallic = leaf.math('MULTIPLY', chips, .92)
    leaf.set(leaf.bsdf.inputs['Metallic'], leaf.metallic)
    height = leaf.math('SUBTRACT', leaf.math('MULTIPLY', micro, .4), leaf.math('MULTIPLY', chips, .5))
    leaf.finish(coat, rough, height, .28, .00016)

    frame = Surface('frame', (.065, .078, .088), .57)
    grain = frame.noise((700, 700, 700))
    patch = frame.noise((23, 14, 20))
    color = frame.mix(patch, (.048, .058, .065, 1), (.072, .085, .095, 1))
    low = frame.math('LESS_THAN', frame.axes.outputs['Z'], .32)
    rubbed = frame.math('MULTIPLY', low, frame.noise((15, 130, 130)))
    color = frame.mix(frame.math('MULTIPLY', rubbed, .28), color, (.027, .028, .029, 1))
    frame.finish(color, frame.math('ADD', .49, frame.math('MULTIPLY', grain, .13)), grain, .22, .00012)

    metal = Surface('metal', (.55, .57, .58), .30, metallic=1)
    brush = metal.noise((9, 3600, 2400), detail=2)
    patches = metal.noise((34, 12, 30))
    base = metal.mix(brush, (.46, .48, .49, 1), (.60, .62, .63, 1))
    base = metal.mix(metal.math('MULTIPLY', patches, .11), base, (.20, .22, .23, 1))
    kicks = band(metal, metal.axes.outputs['Z'], .20, .20)
    scratches = metal.math('GREATER_THAN', metal.noise((6, 80, 950)), .70)
    base = metal.mix(metal.math('MULTIPLY', kicks, scratches), base, (.29, .32, .33, 1))
    rough = metal.math('ADD', .25, metal.math('MULTIPLY', brush, .17))
    rough = metal.math('ADD', rough, metal.math('MULTIPLY', kicks, .10))
    metal.finish(base, rough, brush, .23, .000065)

    sticker = Surface('sticker', (.012, .30, .11), .22)
    # Original text-free exit graphic: doorway, running figure, directional arrow.
    artwork = rect(sticker, .398, .403, 1.452, 1.538)
    artwork = sticker.math('MAXIMUM', artwork, rect(sticker, .423, .428, 1.452, 1.538))
    artwork = sticker.math('MAXIMUM', artwork, rect(sticker, .398, .428, 1.533, 1.538))
    paths = [((.490, 1.512), (.508, 1.490), .008),
             ((.495, 1.509), (.475, 1.502), .006),
             ((.475, 1.502), (.464, 1.518), .005),
             ((.502, 1.499), (.527, 1.503), .005),
             ((.508, 1.491), (.493, 1.471), .006),
             ((.493, 1.471), (.472, 1.466), .005),
             ((.508, 1.491), (.526, 1.476), .006),
             ((.526, 1.476), (.533, 1.452), .005),
             ((.489, 1.531), (.4891, 1.531), .009),
             ((.555, 1.495), (.602, 1.495), .004),
             ((.602, 1.495), (.587, 1.507), .004),
             ((.602, 1.495), (.587, 1.483), .004)]
    for a, b, r in paths:
        artwork = sticker.math('MAXIMUM', artwork, stroke(sticker, a, b, r))
    texture = sticker.noise((450, 450, 450))
    color = sticker.mix(artwork, (.008, .25, .08, 1), (.88, .92, .86, 1))
    sticker.finish(color, sticker.math('ADD', .20, sticker.math('MULTIPLY', texture, .045)), texture, .12, .00003)
    return {'leaf': leaf, 'frame': frame, 'metal': metal, 'sticker': sticker}


def screw(name, point, mat, radius=.0035):
    """Low-profile screw with a physically recessed cruciform driver slot."""
    x, y, z = point
    obj = cylinder(name, (x, y, z + .0013), (x, y, z), radius, mat, count=20)
    # Real void, not a painted black cross.
    for dims in ((radius * 1.30, .00075, .0012), (.00075, radius * 1.30, .0012)):
        cutter = box('driver_cut-noimp', (dims[0], dims[2], dims[1]), None,
                     godot((x, y, z + .00015)))
        active(obj)
        modifier = obj.modifiers.new('driver_recess', 'BOOLEAN')
        modifier.operation = 'DIFFERENCE'
        modifier.solver = 'EXACT'
        modifier.object = cutter
        bpy.ops.object.modifier_apply(modifier=modifier.name)
        bpy.data.objects.remove(cutter, do_unlink=True)
    triangulate(obj)
    return obj


def geometry(mats):
    groups = {name: [] for name in ('leaf', 'frame', 'maglock', 'maglock_led')}
    fixed_boxes = []
    def slab(group, name, dims, pos, finish='metal', radius=.0007, segments=4):
        obj = box(name, (dims[0], dims[2], dims[1]), mats[finish].mat,
                  godot(pos), bevel=radius, segments=segments)
        groups[group].append(obj)
        if group in ('frame', 'maglock'):
            fixed_boxes.append((name, tuple(pos[i] - dims[i] / 2 for i in range(3)),
                                tuple(pos[i] + dims[i] / 2 for i in range(3))))
        return obj

    slab('leaf', 'steel_leaf', (.98, 2.08, .05), (.50, 1.04, .030), 'leaf', .0015, 5)
    # Pressed frame sections. Hinge-side return has a 78 mm relief pocket:
    # an unrelieved jamb at x=0 would intersect the specified thick leaf sweep.
    for x in (-.025, 1.025):
        slab('frame', 'architrave_jamb', (.05, 2.10, .015), (x, 1.05, -.0075), 'frame', .001, 4)
    slab('frame', 'architrave_head', (1.10, .05, .015), (.50, 2.125, -.0075), 'frame', .001, 4)
    slab('frame', 'hinge_return_relief', (.002, 2.10, .10), (-.079, 1.05, .05), 'frame', .00035, 3)
    slab('frame', 'hinge_return_fold', (.08, 2.10, .002), (-.04, 1.05, -.001), 'frame', .0003, 3)
    slab('frame', 'latch_return', (.002, 2.10, .10), (1.001, 1.05, .05), 'frame', .00035, 3)
    slab('frame', 'head_return', (1.082, .002, .10), (.461, 2.101, .05), 'frame', .00035, 3)
    # Small pressed rebate on free jamb, outside both the leaf and its sweep.
    slab('frame', 'latch_rebate', (.012, 2.10, .003), (1.008, 1.05, .074), 'frame', .0004, 3)
    for y in (.26, 1.04, 1.83):
        slab('leaf', 'hinge_wing_leaf', (.058, .072, .002), (.045, y, .0038), 'metal', .0005)
        slab('frame', 'hinge_wing_jamb', (.036, .072, .002), (-.026, y, -.017), 'metal', .0005)
        for index in range(5):
            part = 'leaf' if index % 2 else 'frame'
            a, b = y - .035 + index * .014, y - .0214 + index * .014
            groups[part].append(cylinder('hinge_knuckle', (0, a, 0), (0, b, 0), .006, mats['metal'].mat, count=24))
        for yy in (y - .022, y + .022):
            groups['leaf'].append(screw('hinge_screw', (.051, yy, .0027), mats['metal'].mat, .0026))
            groups['frame'].append(screw('jamb_screw', (-.028, yy, -.0181), mats['metal'].mat, .0026))

    # Panic hardware: cast end blocks, backing spine and rounded touch bar.
    slab('leaf', 'panic_spine', (.738, .065, .007), (.50, 1.00, .001), 'metal', .002, 5)
    for x in (.14, .86):
        slab('leaf', 'panic_cap', (.063, .090, .050), (x, 1.00, -.020), 'frame', .007, 6)
        slab('leaf', 'cap_trim', (.051, .072, .0015), (x, 1.00, -.0454), 'metal', .002, 5)
        for y in (.973, 1.027):
            groups['leaf'].append(screw('panic_screw', (x, y, -.0464), mats['metal'].mat, .003))
    slab('leaf', 'panic_touch_bar', (.678, .037, .027), (.50, 1.00, -.0315), 'metal', .0045, 6)
    slab('leaf', 'kick_plate', (.88, .305, .003), (.50, .2075, .0035), 'metal', .001, 5)
    for x in (.075, .50, .925):
        for y in (.070, .345):
            groups['leaf'].append(screw('kick_screw', (x, y, .0012), mats['metal'].mat, .0028))
    slab('leaf', 'armature_shim', (.398, .052, .002), (.750, 2.034, .004), 'frame', .0005)
    slab('leaf', 'armature_plate', (.400, .048, .007), (.750, 2.036, -.0005), 'metal', .0012, 5)
    for x in (.585, .750, .915):
        groups['leaf'].append(screw('armature_fixing', (x, 2.036, -.0052), mats['metal'].mat, .0034))
    slab('leaf', 'exit_sticker', (.240, .120, .00035), (.50, 1.495, .00465), 'sticker', .00016, 3)

    # Brushed extrusion with fine side flutes, mounting seam and separate LED.
    slab('maglock', 'magnet_mount_rail', (.460, .008, .055), (.750, 2.096, -.036), 'metal', .001, 4)
    slab('maglock', 'magnet_extrusion', (.444, .057, .065), (.750, 2.0635, -.0375), 'metal', .0018, 5)
    for x in (.524, .976):
        slab('maglock', 'magnet_end_cap', (.008, .062, .065), (x, 2.066, -.0375), 'frame', .0008)
    for y in (2.042, 2.091):
        slab('maglock', 'extrusion_flute', (.427, .0012, .001), (.750, y, -.07015), 'frame', .00025, 3)
    for x in (.552, .920):
        groups['maglock'].append(screw('magnet_screw', (x, 2.067, -.0707), mats['metal'].mat, .0026))
    slab('maglock', 'led_bezel', (.012, .010, .0016), (.948, 2.068, -.0705), 'frame', .002, 5)
    # Surface conduit projects from the head up to the requested ceiling line.
    groups['maglock'].append(cylinder('conduit', (.954, 2.105, -.032), (.954, 2.345, -.032), .005, mats['metal'].mat, count=24))
    for y in (2.115, 2.333):
        groups['maglock'].append(cylinder('conduit_coupler', (.954, y - .009, -.032), (.954, y + .009, -.032), .007, mats['metal'].mat, count=24))
    slab('maglock', 'conduit_saddle', (.026, .012, .004), (.954, 2.235, -.008), 'frame', .001)
    slab('maglock', 'conduit_bracket', (.014, .010, .024), (.954, 2.235, -.022), 'metal', .001)
    ledmat = material(ASSET_ID, 'led', (1, 1, 1), roughness=.20, emission=((1, 1, 1), .65))
    groups['maglock_led'].append(cylinder('status_lens', (.948, 2.068, -.0708), (.948, 2.068, -.0722), .0027, ledmat, count=32))
    for objects in groups.values():
        for obj in objects:
            triangulate(obj)
    return groups, fixed_boxes


def validate_geometry(objects, gltf, fixed_boxes):
    nodes = {node['name']: node for node in gltf['nodes'] if 'mesh' in node}
    if set(nodes) != {'leaf', 'frame', 'maglock', 'maglock_led'}:
        raise RuntimeError('Incorrect exported part names')
    if gltf.get('animations') or gltf.get('cameras'):
        raise RuntimeError('Unexpected animation or camera')
    for name, node in nodes.items():
        if node.get('scale', [1, 1, 1]) != [1, 1, 1] or node.get('rotation', [0, 0, 0, 1]) != [0, 0, 0, 1]:
            raise RuntimeError(f'Unapplied transform: {name}')
    if nodes['leaf'].get('translation', [0, 0, 0]) != [0, 0, 0]:
        raise RuntimeError('Leaf hinge origin drifted')
    # Check a dense solid grid of the specified leaf slab and attached plates
    # against the fixed pressed-frame / maglock boxes throughout the 100° arc.
    # The broad slab grid includes edges; touching hinge bearings is intended.
    moving = [(.01, .99, 0, 2.08, .005, .055),
              (.55, .95, 2.012, 2.060, -.004, .003),
              (.06, .94, .055, .360, .002, .005),
              (.1085, .8915, .955, 1.045, -.045, .005)]
    checks = 0
    for degrees in range(101):
        s, c = math.sin(math.radians(degrees)), math.cos(math.radians(degrees))
        for x0, x1, y0, y1, z0, z1 in moving:
            for ix in range(101):
                x = x0 + (x1 - x0) * ix / 100
                for z in (z0, (z0 + z1) / 2, z1):
                    xx, zz = x * c - z * s, x * s + z * c
                    for name, low, high in fixed_boxes:
                        if y1 <= low[1] + 1e-5 or y0 >= high[1] - 1e-5:
                            continue
                        checks += 1
                        if low[0] + 1e-5 < xx < high[0] - 1e-5 and low[2] + 1e-5 < zz < high[2] - 1e-5:
                            raise RuntimeError(f'Leaf intersects {name} at {degrees} degrees: {xx}, {zz}')
    print(f'PASS geometry: hinge origin (0,0,0), applied transforms; {checks} solid sweep samples, 0–100 degrees into Godot +Z', flush=True)
    return checks


def build(out_dir):
    reset_scene(SEED)
    cache = ROOT / 'assets/cache' / ASSET_ID
    cache.mkdir(parents=True, exist_ok=True)
    mats = surfaces()
    groups, fixed_boxes = geometry(mats)
    bpy.context.view_layer.update()
    components = [obj for pieces in groups.values() for obj in pieces]
    textures = []
    for part, surf in mats.items():
        selected = [obj for obj in components if obj.data.materials[0] == surf.mat]
        textures.extend(bake_surface(part, surf, selected, cache))
    objects = []
    for name, pieces in groups.items():
        origin = godot(LED_ANCHOR) if name == 'maglock_led' else (0, 0, 0)
        obj = join_static(pieces, name, origin=origin)
        triangulate(obj)
        objects.append(obj)
    bpy.context.view_layer.update()
    glb_path = Path(out_dir).resolve() / f'{ASSET_ID}.glb'
    gltf = export_glb(glb_path, objects)
    checks = validate_geometry(objects, gltf, fixed_boxes)
    meta = write_metadata(ASSET_ID, ROOT / 'assets/meta' / f'{ASSET_ID}.json',
                          glb_path, objects, Path(__file__), textures, 'hinge', extra={
        'origin_reference': 'opening hinge edge on wall room-face plane, Godot (0,0,0)',
        'forward': 'Blender +Y -> Godot -Z',
        'collision': None,
        'anchors_godot_m': {'leaf_room_face_z': .005, 'leaf_label_centre': list(LABEL_ANCHOR),
                            'maglock_led': list(LED_ANCHOR)},
        'leaf_slab_godot_m': {'min': [.01, 0, .005], 'max': [.99, 2.08, .055]},
        'label_clear_area_m': [.40, .15],
        'hinge_jamb_relief_m': .078,
        'swing_verification': {'degrees': [0, 100], 'godot_rotation_y_degrees': -100,
                               'direction': 'into corridor, Godot +Z', 'solid_samples': checks},
        'baking': {'engine': 'CYCLES', 'device': 'CPU', 'samples': 16, 'margin_px': 8,
                   'maps': 'procedural color/RM emission, tangent normal, ray-traced AO packed in ORM'},
        'render': {'engine': 'CYCLES', 'device': 'CPU', 'samples': 32, 'denoise': True, 'threads': 4},
        'third_party': [],
        'glb_path': str(glb_path.relative_to(ROOT)) if glb_path.is_relative_to(ROOT) else str(glb_path),
    })
    if meta['triangles'] > 60000 or len(meta['materials']) > 5:
        raise RuntimeError('Request budget exceeded')
    render_previews(ASSET_ID, ROOT / 'assets/previews', objects, views={
        'front': {'position': (.50, 4, 1.175), 'target': (.50, 0, 1.175), 'scale': 2.60},
        'iso': {'position': (-2.4, 4.5, 2.8), 'target': (.48, 0, 1.14), 'scale': 2.70},
        'detail': {'position': (.28, 1.1, 1.87), 'target': (.75, .025, 2.075), 'scale': .66},
    }, seed=SEED)
    print(f'ASSET BUILT: {glb_path}; {meta["triangles"]} triangles; {len(meta["materials"])} materials', flush=True)
    return glb_path


if __name__ == '__main__':
    run_cli(build, __doc__)
