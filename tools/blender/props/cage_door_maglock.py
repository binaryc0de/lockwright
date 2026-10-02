"""Security cage door: 40 mm powder-coated tubes and 50 mm cutout weld mesh.

Owner-made, deterministic Blender 5.2, no network or third-party assets.
Structural reference: accepted exit_door_maglock / exit_keypad_6 scripts.
Run build_assets.sh cage_door_maglock: flock, Cycles CPU, four threads.
All authored geometry is Godot metres; Blender +Y becomes Godot -Z.
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
from common.materials import base_texture, material, normal_texture, orm_texture, image_from_pixels
from common.preview import render_previews
from common.scene import reset_scene

ASSET_ID = 'cage_door_maglock'
SEED = 520026
LED_ANCHOR = (.741, 2.05, -.1114)
LABEL_ANCHOR = (.85, 2.05, -.110)


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
    size = 2048 if part in ('frame', 'metal') else 512
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


def surfaces():
    frame = Surface('frame', (.040, .045, .050), .57)
    x, y = frame.axes.outputs['X'], frame.axes.outputs['Z']
    grain = frame.noise((1800, 1800, 1800))
    broad = frame.noise((22, 18, 27), detail=3)
    coat = frame.mix(broad, (.029, .034, .039, 1), (.042, .047, .051, 1))
    hand = frame.math('MULTIPLY', band(frame, x, .92, .10), band(frame, y, 1.05, .20))
    boots = frame.math('MULTIPLY', frame.math('LESS_THAN', y, .26), frame.noise((9, 40, 75)))
    coat = frame.mix(frame.math('MULTIPLY', boots, .28), coat, (.012, .015, .017, 1))
    wear = 0
    # Individual boot and ring scrapes, with broken exposed-steel centres.
    for a, b, radius in [((.19, .071), (.30, .063), .0012),
                         ((.45, .16), (.53, .142), .0011),
                         ((.73, .19), (.84, .181), .0013),
                         ((.91, .11), (.97, .088), .001),
                         ((.927, 1.14), (.939, 1.10), .0008),
                         ((.939, 1.01), (.948, .97), .0008),
                         ((.035, 1.23), (.043, 1.19), .0007),
                         ((.743, 1.979), (.80, 1.97), .0009)]:
        wear = frame.math('MAXIMUM', wear, stroke(frame, a, b, radius))
    fragmented = frame.math('MULTIPLY', wear, frame.math('GREATER_THAN', frame.noise((350, 90, 210)), .42))
    coat = frame.mix(wear, coat, (.012, .014, .016, 1))
    coat = frame.mix(fragmented, coat, (.26, .28, .29, 1))
    frame.metallic = frame.math('MULTIPLY', fragmented, .85)
    frame.set(frame.bsdf.inputs['Metallic'], frame.metallic)
    rough = frame.math('SUBTRACT', frame.math('ADD', .49, frame.math('MULTIPLY', grain, .16)),
                       frame.math('MULTIPLY', hand, .14))
    height = frame.math('SUBTRACT', grain, frame.math('MULTIPLY', wear, .6))
    frame.finish(coat, rough, height, .28, .00013)

    metal = Surface('metal', (.55, .58, .60), .32, metallic=1)
    brush = metal.noise((14, 3200, 2500))
    stain = metal.noise((32, 6, 23), detail=3)
    color = metal.mix(brush, (.43, .46, .48, 1), (.60, .63, .65, 1))
    color = metal.mix(metal.math('MULTIPLY', stain, .16), color, (.24, .26, .27, 1))
    handle = band(metal, metal.axes.outputs['Z'], 1.05, .09)
    rough = metal.math('SUBTRACT', metal.math('ADD', .25, metal.math('MULTIPLY', brush, .20)),
                       metal.math('MULTIPLY', handle, .13))
    metal.finish(color, rough, brush, .28, .000065)

    sticker = Surface('sticker', (.65, .43, .012), .43)
    diagonal = sticker.math('ADD', sticker.axes.outputs['X'], sticker.axes.outputs['Z'])
    stripes = sticker.math('GREATER_THAN', sticker.math('PINGPONG',
                            sticker.math('MULTIPLY', diagonal, 50), 1), .5)
    grunge = sticker.noise((200, 200, 200))
    color = sticker.mix(stripes, (.008, .010, .011, 1), (.70, .46, .012, 1))
    color = sticker.mix(sticker.math('MULTIPLY', grunge, .10), color, (.29, .25, .15, 1))
    sticker.finish(color, sticker.math('ADD', .36, sticker.math('MULTIPLY', grunge, .12)),
                   grunge, .13, .000025)
    return {'frame': frame, 'metal': metal, 'sticker': sticker}


def weld_mesh(cache):
    """Rasterise a unique sheet atlas: round 4 mm wires on a 50 mm grid.

    Open cells have zero alpha. Weld intersections swell slightly; cylindrical
    shading and tiny pitting are exported tangent normals, rather than paint.
    A Round node makes the exporter emit MASK with a 0.5 alpha cutoff.
    """
    size = 2048
    pixels = {key: array('f', [0]) * (size * size * 4) for key in ('base_color', 'normal', 'orm')}
    width, height = .90, 1.79
    xs = [((.05 + (i + .5) * width / size + .025) % .05) - .025 for i in range(size)]
    ys = [((.25 + (i + .5) * height / size + .025) % .05) - .025 for i in range(size)]
    opaque = 0
    for row, dy in enumerate(ys):
        for column, dx in enumerate(xs):
            index = (row * size + column) * 4
            dv, dh = abs(dx), abs(dy)
            distance = min(dv, dh)
            weld = dv < .003 and dh < .003
            radius = .00225 if weld else .002
            # Analytic coverage on the pixel footprint, including the margin.
            alpha = max(0, min(1, .5 + (radius - distance) / (width / size)))
            opaque += alpha >= .5
            noise = ((row * 73856093 ^ column * 19349663 ^ SEED) & 1023) / 1023
            shade = .027 + .011 * noise + (.006 if weld else 0)
            pixels['base_color'][index:index + 4] = array('f', (shade, shade * 1.12, shade * 1.25, alpha))
            nx = max(-.85, min(.85, dx / radius * .80)) if dv < dh else 0
            ny = max(-.85, min(.85, dy / radius * .80)) if dh <= dv else 0
            if not alpha:
                nx = ny = 0
            nz = math.sqrt(max(.01, 1 - nx * nx - ny * ny))
            pixels['normal'][index:index + 4] = array('f', (.5 + nx * .5, .5 + ny * .5, .5 + nz * .5, 1))
            pixels['orm'][index:index + 4] = array('f', (.84 if weld else 1, .50 + .14 * noise, .05, 1))
    mat = material(ASSET_ID, 'mesh', (.033, .039, .044), roughness=.56)
    images = {name: image_from_pixels(ASSET_ID, 'mesh_' + name, size, values, cache,
                                     non_color=name != 'base_color') for name, values in pixels.items()}
    base_texture(mat, images['base_color'])
    orm_texture(mat, images['orm'])
    normal_texture(mat, images['normal'])
    tree = mat.node_tree
    texture = next(node for node in tree.nodes if node.type == 'TEX_IMAGE' and node.image == images['base_color'])
    clip = tree.nodes.new('ShaderNodeMath')
    clip.operation = 'ROUND'
    tree.links.new(texture.outputs['Alpha'], clip.inputs[0])
    tree.links.new(clip.outputs[0], tree.nodes.get('Principled BSDF').inputs['Alpha'])
    mat.surface_render_method = 'DITHERED'
    mat.use_backface_culling = False
    plane = mesh_object('weld_mesh_sheet', [godot(p) for p in
                         ((.05, .25, 0), (.95, .25, 0), (.95, 2.04, 0), (.05, 2.04, 0))],
                         [(0, 3, 2, 1)], mat)
    uv = plane.data.uv_layers.new(name='UVMap')
    for loop in plane.data.loops:
        uv.data[loop.index].uv = ((0, 0), (1, 0), (1, 1), (0, 1))[loop.vertex_index]
    textures = [{'name': image.name, 'size': list(image.size), 'map': name,
                 'material': mat.name, 'embedded': True} for name, image in sorted(images.items())]
    return plane, textures, 1 - opaque / (size * size)


def geometry(mats):
    groups = {name: [] for name in ('leaf', 'frame', 'maglock', 'maglock_led')}
    moving_boxes, fixed_boxes = [], []

    def slab(group, name, dims, pos, finish='frame', radius=.0007, segments=3):
        obj = box(name, (dims[0], dims[2], dims[1]), mats[finish].mat,
                  godot(pos), bevel=radius, segments=segments)
        groups[group].append(obj)
        bounds = (name, tuple(pos[i] - dims[i] / 2 for i in range(3)),
                  tuple(pos[i] + dims[i] / 2 for i in range(3)))
        (moving_boxes if group == 'leaf' else fixed_boxes).append(bounds)
        return obj

    for x in (.03, .97):
        slab('leaf', 'leaf_stile', (.04, 2.08, .04), (x, 1.04, 0), radius=.0012)
    for y in (.02, 2.06):
        slab('leaf', 'leaf_rail', (.90, .04, .04), (.50, y, 0), radius=.0012)
    slab('leaf', 'kick_plate', (.90, .25, .003), (.50, .125, .002), radius=.0006)
    slab('leaf', 'kick_top_fold', (.90, .008, .015), (.50, .248, .005), radius=.0005)
    slab('leaf', 'lock_zone_plate', (.26, .15, .004), (.85, 2.005, -.001), radius=.001)
    slab('leaf', 'armature_spacer', (.25, .043, .021), (.85, 2.036, -.0305), radius=.0007)
    slab('leaf', 'armature_plate', (.26, .048, .009), (.85, 2.036, -.0455), 'metal', .0010, 4)
    for x in (.749, .850, .951):
        groups['leaf'].append(screw('armature_bolt', (x, 2.036, -.0508), mats['metal'].mat, .003))
    slab('leaf', 'hazard_strip', (.215, .022, .0004), (.85, 1.956, -.0033), 'sticker', .00017)
    for x in (.079, .50, .921):
        for y in (.035, .222):
            groups['leaf'].append(screw('kick_fixing', (x, y, -.0005), mats['metal'].mat, .0023))

    # The hinge post is offset 35 mm toward the office. A coplanar square
    # post would intersect a 40 mm thick leaf after 90 degrees around (0,0).
    # Both posts retain the specified x and full 40 x 40 mm section.
    slab('frame', 'hinge_post', (.04, 2.10, .04), (-.02, 1.05, -.035), radius=.0012)
    slab('frame', 'strike_post', (.04, 2.10, .04), (1.02, 1.05, 0), radius=.0012)
    for x, z in ((-.02, -.035), (1.02, 0)):
        slab('frame', 'tube_cap', (.039, .003, .039), (x, 2.0985, z), radius=.0008)
    for y in (.23, 1.05, 1.83):
        slab('frame', 'hinge_post_wing', (.027, .074, .002), (-.0235, y, -.056), 'metal', .0005)
        slab('frame', 'hinge_offset_web', (.012, .074, .050), (-.012, y, -.029), 'metal', .0005)
        slab('leaf', 'hinge_leaf_wing', (.054, .074, .002), (.033, y, -.021), 'metal', .0005)
        slab('leaf', 'hinge_leaf_web', (.007, .074, .025), (.0135, y, -.009), 'metal', .0004)
        for index in range(5):
            group = 'leaf' if index % 2 else 'frame'
            groups[group].append(cylinder('hinge_knuckle', (0, y - .036 + index * .0144, 0),
                                         (0, y - .0223 + index * .0144, 0), .0055,
                                         mats['metal'].mat, count=24))
        groups['frame'].append(cylinder('hinge_pin', (0, y - .039, 0), (0, y + .039, 0),
                                       .0024, mats['metal'].mat, count=20))
        for yy in (y - .023, y + .023):
            groups['leaf'].append(screw('hinge_leaf_fixing', (.045, yy, -.022), mats['metal'].mat, .0024))
            groups['frame'].append(screw('hinge_post_fixing', (-.024, yy, -.057), mats['metal'].mat, .0024))

    # Tubular U-shaped pull with polished hand-contact section and rosettes.
    for yy in (.98, 1.12):
        slab('leaf', 'pull_mount_tab', (.081, .030, .003), (.9345, yy, -.0215), radius=.0007)
        slab('leaf', 'pull_rosette', (.025, .024, .003), (.90, yy, -.0245), 'metal', .002, 4)
        groups['leaf'].append(cylinder('pull_standoff', (.90, yy, -.026), (.90, yy, -.082),
                                      .006, mats['metal'].mat, count=32))
    groups['leaf'].append(cylinder('pull_grip', (.90, .98, -.082), (.90, 1.12, -.082),
                                  .007, mats['metal'].mat, count=40))
    moving_boxes.append(('pull_envelope', (.8875, .968, -.089), (.9125, 1.132, -.020)))

    # Small raised weld seams at tube joins and mesh retainers, all physical.
    for x in (.051, .949):
        for y in (.041, 2.039):
            groups['leaf'].append(cylinder('tube_weld', (x - .010, y, -.0205),
                                          (x + .010, y, -.0205), .0008,
                                          mats['frame'].mat, count=12))
    for x in (.056, .944):
        for y in (.42, .82, 1.42, 1.87):
            slab('leaf', 'mesh_retainer', (.011, .025, .004), (x, y, -.004), radius=.0004)
            groups['leaf'].append(screw('mesh_retainer_fixing', (x, y, -.0066), mats['metal'].mat, .0018))

    # L-bracket is a fixed 4 mm folded strap tied to the strike-post office
    # face. Its cage-side face touches the armature only in the closed pose.
    slab('maglock', 'bracket_mount_leg', (.04, .110, .004), (1.018, 2.045, -.024), 'metal', .0006)
    slab('maglock', 'bracket_overhead_leg', (.309, .004, .077), (.8875, 2.088, -.0625), 'metal', .0006)
    slab('maglock', 'magnet_extrusion', (.234, .060, .060), (.85, 2.05, -.080), 'metal', .0013, 4)
    for x in (.729, .971):
        slab('maglock', 'magnet_end_cap', (.008, .060, .060), (x, 2.05, -.080), radius=.0008)
    # Extrusion flutes sit proud by 0.2 mm; centre remains free for Label3D.
    for y in (2.024, 2.076):
        slab('maglock', 'extrusion_flute', (.227, .001, .0004), (.85, y, -.1102), radius=.00015)
    for x in (.764, .937):
        groups['maglock'].append(screw('magnet_fixing', (x, 2.05, -.1107), mats['metal'].mat, .0022))
    for y in (2.005, 2.078):
        groups['maglock'].append(screw('bracket_fixing', (1.018, y, -.027), mats['metal'].mat, .003))
    slab('maglock', 'led_bezel', (.009, .009, .001), (.741, 2.05, -.1105), radius=.0015)
    groups['maglock'].append(cylinder('conduit', (1.012, 2.090, -.060), (1.012, 2.36, -.060),
                                     .0045, mats['metal'].mat, count=24))
    for y in (2.102, 2.343):
        groups['maglock'].append(cylinder('conduit_coupler', (1.012, y - .007, -.060),
                                         (1.012, y + .007, -.060), .006, mats['metal'].mat, count=24))
    slab('maglock', 'conduit_saddle', (.022, .012, .003), (1.012, 2.21, -.055), radius=.0005)
    ledmat = material(ASSET_ID, 'led', (1, 1, 1), roughness=.20, emission=((1, 1, 1), .65))
    groups['maglock_led'].append(cylinder('status_lens', LED_ANCHOR, (.741, 2.05, -.1127),
                                         .0027, ledmat, count=32))
    for pieces in groups.values():
        for obj in pieces:
            triangulate(obj)
    return groups, moving_boxes, fixed_boxes


def validate_swing(moving, fixed):
    """Separating-axis test of complete solid section envelopes every 0.5°.

    Four separating axes give an exact rectangle overlap test in XZ. This
    tests whole volumes, not sparse vertex samples. Bearing contact is the
    intended exception: concentric barrels/pins are excluded from boxes.
    """
    checks = 0
    for half_degree in range(201):
        angle = math.radians(half_degree / 2)
        c, s = math.cos(angle), math.sin(angle)
        axes = ((1, 0), (0, 1), (c, s), (-s, c))
        for moving_name, low, high in moving:
            points = [(x * c - z * s, x * s + z * c)
                      for x in (low[0], high[0]) for z in (low[2], high[2])]
            for fixed_name, flo, fhi in fixed:
                if high[1] <= flo[1] + 1e-6 or low[1] >= fhi[1] - 1e-6:
                    continue
                checks += 1
                stationary = [(x, z) for x in (flo[0], fhi[0]) for z in (flo[2], fhi[2])]
                separated = False
                for ax, az in axes:
                    mp = [x * ax + z * az for x, z in points]
                    fp = [x * ax + z * az for x, z in stationary]
                    if max(mp) <= min(fp) + 1e-6 or max(fp) <= min(mp) + 1e-6:
                        separated = True
                        break
                if not separated:
                    raise RuntimeError(f'Swing overlap: {moving_name} / {fixed_name} at {half_degree / 2} degrees')
    print(f'PASS swing: {checks} complete solid section pairs, 0–100 degrees into Godot +Z', flush=True)
    return checks


def build(out_dir):
    reset_scene(SEED)
    cache = ROOT / 'assets/cache' / ASSET_ID
    cache.mkdir(parents=True, exist_ok=True)
    mats = surfaces()
    groups, moving, fixed = geometry(mats)
    checks = validate_swing(moving, fixed)
    bpy.context.view_layer.update()
    components = [obj for pieces in groups.values() for obj in pieces]
    textures = []
    for part, surf in mats.items():
        selected = [obj for obj in components if obj.data.materials[0] == surf.mat]
        textures.extend(bake_surface(part, surf, selected, cache))
    sheet, mesh_textures, open_fraction = weld_mesh(cache)
    textures.extend(mesh_textures)
    groups['leaf'].append(sheet)
    objects = []
    for name, pieces in groups.items():
        origin = godot(LED_ANCHOR) if name == 'maglock_led' else (0, 0, 0)
        obj = join_static(pieces, name, origin=origin)
        triangulate(obj)
        objects.append(obj)
    bpy.context.view_layer.update()
    glb_path = Path(out_dir).resolve() / f'{ASSET_ID}.glb'
    gltf = export_glb(glb_path, objects)
    nodes = {node['name']: node for node in gltf['nodes'] if 'mesh' in node}
    if set(nodes) != {'leaf', 'frame', 'maglock', 'maglock_led'} or gltf.get('animations') or gltf.get('cameras'):
        raise RuntimeError('Unexpected exported parts, animation or camera')
    for name, node in nodes.items():
        if node.get('scale', [1, 1, 1]) != [1, 1, 1] or node.get('rotation', [0, 0, 0, 1]) != [0, 0, 0, 1]:
            raise RuntimeError(f'Unapplied transform: {name}')
    if nodes['leaf'].get('translation', [0, 0, 0]) != [0, 0, 0]:
        raise RuntimeError('Leaf hinge origin drifted')
    mesh_mat = next(mat for mat in gltf['materials'] if mat['name'] == f'M_{ASSET_ID}_mesh')
    if mesh_mat.get('alphaMode') != 'MASK' or not mesh_mat.get('doubleSided'):
        raise RuntimeError('Mesh must export as double-sided alpha cutout')
    if not .82 < open_fraction < .87:
        raise RuntimeError('Mesh cells are insufficiently open')
    meta = write_metadata(ASSET_ID, ROOT / 'assets/meta' / f'{ASSET_ID}.json', glb_path,
                          objects, Path(__file__), textures, 'hinge', extra={
        'anchors_godot_m': {'maglock_label_centre': list(LABEL_ANCHOR), 'maglock_led': list(LED_ANCHOR)},
        'origin_reference': 'hinge vertical axis at floor level, Godot (0,0,0)',
        'forward': 'Blender +Y -> Godot -Z (office side)',
        'collision': None,
        'leaf_frame_bounds_godot_m': {'min': [.01, 0, -.02], 'max': [.99, 2.08, .02]},
        'hinge_post_offset_godot_z_m': -.035,
        'label_clear_area_m': [.13, .037],
        'weld_mesh': {'pitch_m': .05, 'wire_diameter_m': .004, 'alpha_mode': 'MASK',
                      'alpha_cutoff': .5, 'double_sided': True, 'open_fraction': round(open_fraction, 6)},
        'swing_verification': {'degrees': [0, 100], 'step_degrees': .5, 'solid_pairs': checks,
                               'godot_rotation_y_degrees': -100, 'direction': 'into cage, Godot +Z'},
        'baking': {'engine': 'CYCLES', 'device': 'CPU', 'samples': 16, 'margin_px': 8,
                   'maps': 'procedural color/RM emission, tangent normals, ray AO packed in ORM; analytic mesh atlas'},
        'render': {'engine': 'CYCLES', 'device': 'CPU', 'samples': 32, 'denoise': True, 'threads': 4},
        'third_party': [],
        'glb_path': str(glb_path.relative_to(ROOT)) if glb_path.is_relative_to(ROOT) else str(glb_path),
    })
    if meta['triangles'] > 60000 or len(meta['materials']) > 5:
        raise RuntimeError('Request budget exceeded')
    print('PASS export: four named meshes; hinge origin; MASK double-sided mesh; no animations/collision', flush=True)
    render_previews(ASSET_ID, ROOT / 'assets/previews', objects, views={
        'front': {'position': (.50, 4, 1.18), 'target': (.50, 0, 1.18), 'scale': 2.58},
        'iso': {'position': (-2.4, 4.5, 2.8), 'target': (.48, 0, 1.16), 'scale': 2.65},
        'detail': {'position': (1.13, 1.05, 2.24), 'target': (.87, .06, 2.087), 'scale': .49},
    }, seed=SEED)
    print(f'ASSET BUILT: {glb_path}; {meta["triangles"]} triangles; {len(meta["materials"])} materials', flush=True)
    return glb_path


if __name__ == '__main__':
    run_cli(build, __doc__)
