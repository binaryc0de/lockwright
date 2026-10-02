"""Office shell dressing: seven independently instanced, overlapping parts.

Blender 5.2 headless, Cycles CPU only, fixed seed, no external assets/network.
The exported kit is at mounting origins; only baking/previews use a spread.
Run tools/blender/build_assets.sh office_trim_kit (flock, --threads 4).
"""
from array import array
import math
from pathlib import Path
import sys

import bpy
from mathutils import Matrix, Vector

sys.dont_write_bytecode = True
TOOLS = Path(__file__).resolve().parents[1]
ROOT = TOOLS.parents[1]
sys.path.insert(0, str(TOOLS))
from common.cli import run_cli
from common.export import export_glb, write_metadata
from common.geometry import active, box, join_static, mesh_object, triangulate
from common.materials import material, base_texture, normal_texture, orm_texture
from common.preview import render_previews
from common.scene import reset_scene

ASSET_ID = 'office_trim_kit'
SEED = 602026
WHITE = (.73, .705, .64, 1)
PAINT = (.79, .785, .755, 1)
DARK = (.013, .014, .012, 1)
LAYOUT = {'vent_600': (-.35, .27, 0), 'emergency_light': (.34, .42, 0),
          'outlet_double': (.24, .15, 0), 'light_switch': (.45, .15, 0),
          'smoke_detector': (.34, -.075, 0), 'smoke_led': (.34, -.075, 0),
          'skirting_1m': (0, -.43, 0)}


def bl(point):
    """Godot metres -> Blender (+Y forward)."""
    return Vector((point[0], -point[2], point[1]))


def tint(obj, color):
    layer = obj.data.color_attributes.new(name='finish_color', type='FLOAT_COLOR', domain='CORNER')
    for datum in layer.data:
        datum.color = color
    return obj


class Surface:
    """Procedural finish baked into portable base/normal/ORM texture maps."""
    def __init__(self, part, roughness, metallic=0, emission=0):
        self.mat = material(ASSET_ID, part, (1, 1, 1), roughness=roughness,
                            metallic=metallic, emission=((1, 1, 1), emission) if emission else None)
        self.tree = self.mat.node_tree
        self.bsdf = self.tree.nodes.get('Principled BSDF')
        self.metallic = metallic
        self.emission = emission
        pos = self.node('ShaderNodeNewGeometry').outputs['Position']
        xyz = self.node('ShaderNodeSeparateXYZ', Vector=pos)
        # X-independent paint finish: horizontal stretching of the skirting
        # does not elongate wood grain, dirt patches or conspicuous markings.
        if part == 'paint':
            coord = self.node('ShaderNodeCombineXYZ', X=0, Y=xyz.outputs['Y'], Z=xyz.outputs['Z']).outputs[0]
        else:
            coord = pos
        broad = self.node('ShaderNodeTexNoise', Vector=coord, Scale=35, Detail=3).outputs['Fac']
        micro = self.node('ShaderNodeTexNoise', Vector=coord, Scale=1800 if part == 'metal' else 1100,
                          Detail=2, Roughness=.7).outputs['Fac']
        color = self.node('ShaderNodeVertexColor')
        color.layer_name = 'finish_color'
        variation = self.math('ADD', .93, self.math('MULTIPLY', broad, .07))
        self.color = self.node('ShaderNodeMixRGB', Fac=1, Color1=color.outputs['Color'], Color2=variation)
        self.color.blend_type = 'MULTIPLY'
        self.color = self.color.outputs[0]
        if part == 'plastic':
            ao = self.node('ShaderNodeAmbientOcclusion', Distance=.0025)
            ao.samples = 8
            dirt = self.math('MULTIPLY', self.math('SUBTRACT', 1, ao.outputs['AO']), .12)
            self.color = self.node('ShaderNodeMixRGB', Fac=dirt, Color1=self.color,
                                   Color2=(.22, .205, .17, 1)).outputs[0]
        # A faint rubbed lower band with a few tiny paint scuffs, constant X.
        if part == 'paint':
            low = self.math('LESS_THAN', xyz.outputs['Z'], -.40)
            patches = self.math('GREATER_THAN', broad, .59)
            self.color = self.node('ShaderNodeMixRGB', Fac=self.math('MULTIPLY', low,
                                  self.math('MULTIPLY', patches, .13)), Color1=self.color,
                                  Color2=(.24, .245, .22, 1)).outputs[0]
        self.roughness = self.math('ADD', roughness - .045, self.math('MULTIPLY', micro, .09))
        self.set(self.bsdf.inputs['Base Color'], self.color)
        self.set(self.bsdf.inputs['Roughness'], self.roughness)
        bump = self.node('ShaderNodeBump', Height=micro, Strength=.22,
                         Distance=.000045 if part == 'metal' else .00009)
        self.set(self.bsdf.inputs['Normal'], bump.outputs[0])

    def set(self, socket, value):
        if hasattr(value, 'node'):
            self.tree.links.new(value, socket)
        else:
            socket.default_value = value

    def node(self, kind, **inputs):
        node = self.tree.nodes.new(kind)
        for key, value in inputs.items():
            self.set(node.inputs[key], value)
        return node

    def math(self, operation, a, b):
        node = self.node('ShaderNodeMath')
        node.operation = operation
        self.set(node.inputs[0], a)
        self.set(node.inputs[1], b)
        return node.outputs[0]


def slab(label, dims, pos, surf, color=WHITE, bevel=.0007, segments=1):
    # Stay below the half-thickness clamp: an exactly clamped bevel can
    # collapse the tiny corner faces of thin gaskets into zero-area triangles.
    bevel = min(bevel, min(dims) * .45)
    return tint(box(label, (dims[0], dims[2], dims[1]), surf.mat, bl(pos),
                    bevel=bevel, segments=segments), color)


def lathe(label, centre, direction, profile, surf, color=WHITE, count=40, capped=True):
    """Axis/radial profile in Godot metres; rounded or hollow revolved shells."""
    c, axis = bl(centre), bl(direction).normalized()
    u = axis.cross(Vector((0, 0, 1)))
    if u.length < .01:
        u = axis.cross(Vector((1, 0, 0)))
    u.normalize()
    v = axis.cross(u)
    verts = [c + axis * d + radius * (math.cos(i * math.tau / count) * u +
             math.sin(i * math.tau / count) * v) for d, radius in profile for i in range(count)]
    faces = []
    for ring in range(len(profile) - 1):
        for i in range(count):
            j = (i + 1) % count
            faces.append((ring * count + i, ring * count + j,
                          (ring + 1) * count + j, (ring + 1) * count + i))
    if capped:
        for start, reverse in [(0, True), ((len(profile) - 1) * count, False)]:
            for i in range(1, count - 1):
                face = (start, start + i, start + i + 1)
                faces.append(tuple(reversed(face)) if reverse else face)
    obj = mesh_object(label, verts, faces, surf.mat)
    for face in obj.data.polygons:
        face.use_smooth = len(face.vertices) == 4
    return tint(obj, color)


def boolean(obj, cutter):
    active(obj)
    mod = obj.modifiers.new('recess', 'BOOLEAN')
    mod.operation, mod.solver, mod.object = 'DIFFERENCE', 'EXACT', cutter
    bpy.ops.object.modifier_apply(modifier=mod.name)
    bpy.data.objects.remove(cutter, do_unlink=True)


def screw(label, x, y, d, mats, radius=.0025):
    # Actual recessed slotted screw; the dark slot floor is geometry.
    head = lathe(label, (x, y, -d), (0, 0, -1),
                 [(0, radius), (.0004, radius), (.00075, radius * .86)],
                 mats['metal'], (.57, .59, .60, 1), count=24)
    cutter = slab('slot-noimp', (radius * 1.45, .00055, .001),
                  (x, y, -d - .0008), mats['metal'], bevel=0)
    boolean(head, cutter)
    return head


def geometry(mats):
    groups = {name: [] for name in LAYOUT}
    p, paint, metal, lamp, led = (mats[k] for k in ('plastic', 'paint', 'metal', 'lamp', 'led'))
    # Extruded pencil/ogee profile; all height/depth details constant in X.
    profile = [(0, 0), (.012, 0), (.014, .001), (.015, .003), (.015, .073),
               (.0148, .076), (.014, .078), (.012, .080), (.010, .082),
               (.0088, .0845), (.0086, .087), (.0093, .090), (.0105, .092),
               (.0109, .094), (.0102, .096), (.0088, .098), (.0065, .100), (0, .100)]
    verts = [bl((x, h, -d)) for x in (-.5, .5) for d, h in profile]
    n = len(profile)
    faces = [(i, (i + 1) % n, (i + 1) % n + n, i + n) for i in range(n)]
    faces.extend([tuple(reversed(range(n))), tuple(range(n, 2 * n))])
    skirting = tint(mesh_object('mdf_profile', verts, faces, paint.mat), PAINT)
    for face in skirting.data.polygons[:n]:
        face.use_smooth = .073 < profile[face.index][1] < .1
    groups['skirting_1m'].append(skirting)

    outlet = groups['outlet_double']
    outlet.append(slab('socket_back', (.140, .080, .0018), (0, 0, -.0009), p,
                       (.40, .39, .35, 1), .0006))
    plate = slab('socket_plate', (.146, .086, .006), (0, 0, -.0048), p, bevel=.0025, segments=5)
    outlet.append(plate)
    for x in (-.033, .033):
        socket = lathe('socket_insert', (x, -.010, -.0065), (0, 0, -1),
                       [(0, .0205), (.001, .0205), (.002, .0195)], p, count=48)
        for dx in (-.009, .009):
            cutter = lathe('pin_cut-noimp', (x + dx, -.013, -.006), (0, 0, -1),
                           [(-.002, .0023), (.008, .0023)], p, count=24)
            plate_cutter = cutter.copy()
            plate_cutter.data = cutter.data.copy()
            bpy.context.scene.collection.objects.link(plate_cutter)
            boolean(plate, plate_cutter)
            boolean(socket, cutter)
            outlet.append(lathe('pin_void', (x + dx, -.013, -.0062), (0, 0, -1),
                                [(0, .00225), (.0002, .00225)], p, DARK, count=20))
        cutter = slab('earth_cut-noimp', (.006, .002, .01), (x, .001, -.008), p, bevel=.0003)
        plate_cutter = cutter.copy()
        plate_cutter.data = cutter.data.copy()
        bpy.context.scene.collection.objects.link(plate_cutter)
        boolean(plate, plate_cutter)
        boolean(socket, cutter)
        outlet.append(socket)
        outlet.append(slab('earth_void', (.0058, .0018, .0004), (x, .001, -.0063), p, DARK, .0001))
        outlet.append(slab('rocker_gap', (.0158, .0138, .0005), (x, .027, -.0079), p, DARK, .0007))
        rocker = slab('socket_rocker', (.014, .0115, .002), (x, .027, -.0088), p, bevel=.0008)
        outlet.append(rocker)
        outlet.append(slab('on_mark', (.004, .0008, .00015), (x, .0308, -.00987), p,
                           (.33, .08, .053, 1), .00007))
    for x in (-.063, .063):
        outlet.append(screw('socket_screw', x, 0, .0079, mats))

    switch = groups['light_switch']
    switch.append(slab('switch_back', (.081, .081, .0018), (0, 0, -.0009), p,
                       (.39, .38, .34, 1), .0008))
    switch.append(slab('switch_plate', (.086, .086, .0058), (0, 0, -.0047), p, bevel=.0023, segments=5))
    switch.append(slab('rocker_shadow', (.032, .052, .0005), (0, 0, -.00765), p, DARK, .001))
    rocker = slab('single_rocker', (.028, .048, .003), (0, 0, -.0081), p, bevel=.0012, segments=4)
    # Tilt around its own horizontal pivot without violating the 10 mm envelope.
    for vertex in rocker.data.vertices:
        vertex.co = Matrix.Rotation(math.radians(1.1), 3, 'X') @ vertex.co
    switch.append(rocker)
    for x in (-.034, .034):
        switch.append(screw('switch_screw', x, 0, .0077, mats, .0024))

    vent = groups['vent_600']
    vent.append(slab('duct_dark_void', (.562, .562, .001), (0, 0, -.0015), p, DARK, .001))
    # White powder-coated rolled frame with a recessed lip, four visible fixings.
    for y in (-.2875, .2875):
        vent.append(slab('grille_frame_h', (.595, .020, .020), (0, y, -.010), paint, PAINT, .0013))
    for x in (-.2875, .2875):
        vent.append(slab('grille_frame_v', (.020, .555, .020), (x, 0, -.010), paint, PAINT, .0013))
    for x in (-.267, .267):
        vent.append(slab('grille_inner_lip', (.005, .535, .005), (x, 0, -.015), paint, PAINT, .0006))
    for i in range(23):
        y = (i - 11) * .0235
        blade = slab('louvre', (.528, .0185, .0014), (0, y, -.0122), paint,
                     (.69, .685, .65, 1), .00045, 1)
        # 27 degree return-air vanes, open black gaps between blades.
        rotation = Matrix.Rotation(math.radians(27), 3, 'X')
        for vertex in blade.data.vertices:
            vertex.co = rotation @ vertex.co
        vent.append(blade)
    vent.append(slab('grille_spine', (.006, .535, .004), (0, 0, -.0175), paint, PAINT, .0005))
    for x in (-.287, .287):
        for y in (-.235, .235):
            vent.append(screw('grille_screw', x, y, .0182, mats, .003))

    detector = groups['smoke_detector']
    detector.append(lathe('detector_mount', (0, 0, 0), (0, 0, -1),
                          [(0, .053), (.001, .055), (.003, .055), (.0045, .053)], p, count=64))
    detector.append(lathe('detector_lower', (0, 0, 0), (0, 0, -1),
                          [(.0045, .0523), (.006, .053), (.012, .053), (.014, .0518)], p, count=64))
    detector.append(lathe('vent_shadow', (0, 0, 0), (0, 0, -1),
                          [(.0135, .048), (.027, .048)], p, DARK, count=64))
    # Open radial vents with 32 rounded ribs rather than painted slot lines.
    for i in range(32):
        angle = math.tau * i / 32
        rib = slab('detector_vent_rib', (.0045, .0055, .013),
                   (.050 * math.cos(angle), .050 * math.sin(angle), -.0205), p, bevel=.0007, segments=1)
        rotation = Matrix.Rotation(angle, 3, 'Y')
        for vertex in rib.data.vertices:
            vertex.co = rotation @ vertex.co
        detector.append(rib)
    detector.append(lathe('detector_crown', (0, 0, 0), (0, 0, -1),
                          [(.027, .0518), (.030, .052), (.034, .0505), (.039, .046),
                           (.042, .037), (.044, .025), (.0446, .012)], p, count=64))
    detector.append(lathe('test_button_rim', (0, 0, -.0447), (0, 0, -1),
                          [(0, .010), (.00015, .010)], p, (.41, .40, .36, 1), count=32))
    detector.append(lathe('test_button', (0, 0, -.0449), (0, 0, -1),
                          [(0, .0085), (.00010, .0085)], p, count=32))
    # LED origin is the lens base on the detector, its one explicit exception.
    smoke_pos = (.023, -.019, -.0425)
    detector.append(lathe('led_recess', smoke_pos, (0, 0, -1),
                          [(0, .0024), (.0007, .0024)], p, DARK, count=24))
    smoke = lathe('smoke_led', smoke_pos, (0, 0, -1),
                 [(.0007, .00155), (.0012, .00155), (.0016, .00115), (.00185, .0003)],
                 led, (1, 1, 1, 1), count=24)
    groups['smoke_led'].append(smoke)

    emergency = groups['emergency_light']
    emergency.append(slab('battery_case', (.30, .12, .070), (0, 0, -.035), p, bevel=.005, segments=5))
    emergency.append(slab('lid_seam', (.291, .111, .0015), (0, 0, -.0705), p,
                          (.30, .29, .25, 1), .003))
    emergency.append(slab('battery_lid', (.294, .114, .009), (0, 0, -.0755), p, bevel=.003, segments=4))
    emergency.append(slab('lid_moulding', (.192, .046, .001), (0, 0, -.080), p,
                          (.67, .65, .59, 1), .003))
    for x in (-.134, .134):
        for y in (-.044, .044):
            emergency.append(screw('lid_screw', x, y, .0793, mats, .0024))
    for x, color in [(-.014, (.028, .40, .047, 1)), (0, (.045, .007, .005, 1))]:
        emergency.append(lathe('charge_led_rim', (x, -.035, -.0797), (0, 0, -1),
                               [(0, .0029), (.0006, .0029)], p, DARK, count=24))
        emergency.append(lathe('charge_led', (x, -.035, -.080), (0, 0, -1),
                               [(0, .0021), (.0008, .0021), (.0013, .0007)], led, color, count=24))
    anchors = {}
    for sign, side in [(-1, 'left'), (1, 'right')]:
        lens = Vector((sign * .105, .118, -.100))
        direction = Vector((sign * math.sin(math.pi / 6) * math.cos(math.pi / 6),
                            -math.sin(math.pi / 6), -math.cos(math.pi / 6) ** 2))
        anchors[f'emergency_lamp_{side}'] = list(lens + direction * .00012)
        anchors[f'emergency_lamp_dir_{side}'] = list(direction)
        emergency.append(lathe('lamp_pedestal', (sign * .103, .057, -.041), (0, 1, 0),
                               [(0, .012), (.003, .012), (.005, .008), (.026, .007)], p, count=32))
        neck_a = Vector((sign * .103, .080, -.041))
        neck_b = Vector((sign * .105, .093, -.066))
        emergency.append(lathe('lamp_neck', neck_a, neck_b - neck_a,
                               [(0, .006), ((neck_b - neck_a).length, .006)], p, count=24))
        emergency.append(lathe('pivot_barrel', (sign * .105 - .013, .093, -.066), (1, 0, 0),
                               [(0, .011), (.026, .011)], p, count=32))
        emergency.append(lathe('lamp_shell', lens, direction,
                               [(-.042, .010), (-.039, .017), (-.031, .024), (-.010, .031),
                                (-.002, .032), (0, .0315)], p, count=48))
        # Concave chrome bowl around a prismatic frosted lens; turned lip.
        emergency.append(lathe('chrome_reflector', lens, direction,
                               [(-.026, .005), (-.020, .012), (-.012, .022), (-.003, .028),
                                (0, .0308), (.001, .0308), (.0013, .0285), (.0003, .0275)],
                               metal, (.78, .79, .80, 1), count=48, capped=False))
        profile = [(-.001, .0268), (0, .0268)]
        # Lens front has real concentric diffusion ridges, below 0.5 mm relief.
        for i in range(8):
            r = .0265 - i * .00325
            profile.extend([(.00012, r), (.00040, r - .0007), (.00012, max(.0005, r - .0013))])
        profile.append((.00012, .0004))
        emergency.append(lathe('lamp_lens', lens, direction, profile, lamp,
                               (.88, .90, .88, 1), count=32))
    for pieces in groups.values():
        for obj in pieces:
            triangulate(obj)
            used = {i for face in obj.data.polygons for i in face.vertices}
            if len(used) != len(obj.data.vertices):
                raise RuntimeError(f'Loose geometry: {obj.name}')
            if any(face.area < 1e-14 for face in obj.data.polygons):
                raise RuntimeError(f'Zero-area triangle: {obj.name}')
    return groups, anchors, smoke_pos


def bake_surface(part, surf, components, cache):
    """Global non-overlapping UV islands, 8 px gutter, procedural texture bake."""
    size = 1024 if part in ('paint', 'plastic', 'metal') else 512
    vertices, faces, smooth, colors = [], [], [], []
    for obj in components:
        offset = len(vertices)
        vertices.extend(tuple(obj.matrix_world @ v.co) for v in obj.data.vertices)
        faces.extend(tuple(offset + i for i in poly.vertices) for poly in obj.data.polygons)
        smooth.extend(poly.use_smooth for poly in obj.data.polygons)
        colors.extend(tuple(d.color) for d in obj.data.color_attributes['finish_color'].data)
    temp = mesh_object('bake_surface-noimp', vertices, faces, surf.mat)
    color = temp.data.color_attributes.new(name='finish_color', type='FLOAT_COLOR', domain='CORNER')
    for datum, value in zip(color.data, colors):
        datum.color = value
    for poly, flag in zip(temp.data.polygons, smooth):
        poly.use_smooth = flag
    active(temp)
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.uv.smart_project(angle_limit=math.radians(66), island_margin=8 / size,
                             margin_method='FRACTION', area_weight=0, scale_to_bounds=True)
    bpy.ops.uv.average_islands_scale()
    bpy.ops.uv.pack_islands(rotate=True, margin_method='FRACTION', margin=8 / size)
    bpy.ops.object.mode_set(mode='OBJECT')
    cursor = 0
    for obj in components:
        uv = obj.data.uv_layers.new(name='UVMap')
        for loop in uv.data:
            loop.uv = temp.data.uv_layers.active.data[cursor].uv
            cursor += 1
    scene = bpy.context.scene
    scene.cycles.samples = 16
    scene.render.bake.margin = 8
    scene.render.bake.use_clear = True
    scene.render.bake.use_selected_to_active = False
    scene.render.bake.normal_space = 'TANGENT'
    tree = surf.tree
    output = next(n for n in tree.nodes if n.type == 'OUTPUT_MATERIAL')
    emitter = surf.node('ShaderNodeEmission', Strength=1)
    target = surf.node('ShaderNodeTexImage')
    images = {}
    def bake(name, kind, source=None, non_color=False):
        img = bpy.data.images.new(f'T_{ASSET_ID}_{part}_{name}', width=size, height=size, alpha=False)
        img.colorspace_settings.name = 'Non-Color' if non_color else 'sRGB'
        target.image = img
        tree.nodes.active = target
        if kind == 'EMIT':
            surf.set(emitter.inputs['Color'], source)
            surf.set(output.inputs['Surface'], emitter.outputs[0])
        else:
            surf.set(output.inputs['Surface'], surf.bsdf.outputs[0])
        active(temp)
        print(f'BAKE {part} {name}: {size}px, {kind}, CPU, 8px margin', flush=True)
        bpy.ops.object.bake(type=kind)
        images[name] = img
        return img
    bake('base_color', 'EMIT', surf.color)
    rm = surf.node('ShaderNodeCombineColor', Red=1, Green=surf.roughness, Blue=surf.metallic)
    orm = bake('orm', 'EMIT', rm.outputs[0], True)
    bake('normal', 'NORMAL', non_color=True)
    ao = bake('ao_work', 'AO', non_color=True)
    packed = array('f', [0]) * (size * size * 4)
    occlusion = array('f', [0]) * len(packed)
    orm.pixels.foreach_get(packed)
    ao.pixels.foreach_get(occlusion)
    for i in range(0, len(packed), 4):
        packed[i] = .5 + .5 * occlusion[i]
        packed[i + 3] = 1
    orm.pixels.foreach_set(packed)
    bpy.data.images.remove(ao)
    del images['ao_work']
    for image in images.values():
        image.file_format = 'PNG'
        image.filepath_raw = str(cache / f'{image.name}.png')
        image.save()
        image.pack()
    for node in list(tree.nodes):
        if node not in (surf.bsdf, output):
            tree.nodes.remove(node)
    surf.set(output.inputs['Surface'], surf.bsdf.outputs[0])
    base_texture(surf.mat, images['base_color'])
    orm_texture(surf.mat, images['orm'])
    normal_texture(surf.mat, images['normal'])
    if surf.emission:
        tex = next(n for n in tree.nodes if n.type == 'TEX_IMAGE' and n.image == images['base_color'])
        surf.set(surf.bsdf.inputs['Emission Color'], tex.outputs['Color'])
    bpy.data.objects.remove(temp, do_unlink=True)
    return [{'name': image.name, 'size': list(image.size), 'map': name,
             'material': surf.mat.name, 'embedded': True} for name, image in sorted(images.items())]


def build(out_dir):
    reset_scene(SEED)
    cache = ROOT / 'assets/cache' / ASSET_ID
    cache.mkdir(parents=True, exist_ok=True)
    mats = {name: Surface(name, rough, metallic, emission)
            for name, rough, metallic, emission in [('plastic', .40, 0, 0), ('paint', .48, 0, 0),
             ('metal', .22, 1, 0), ('lamp', .24, 0, .08), ('led', .23, 0, .55)]}
    groups, anchors, smoke_pos = geometry(mats)
    components = [o for pieces in groups.values() for o in pieces]
    triangle_count = sum(len(o.data.polygons) for o in components)
    print(f'GEOMETRY: {triangle_count} triangles before baking', flush=True)
    if triangle_count > 20000:
        raise RuntimeError('Geometry exceeds 20k triangle budget')
    # Separate unrelated kit parts while baking: overlap is intentional only
    # in the delivered GLB, and must never cast false AO into another part.
    for name, pieces in groups.items():
        for obj in pieces:
            obj.location += bl(LAYOUT[name])
            obj.hide_render = True
    bpy.context.view_layer.update()
    textures = []
    for part, surf in mats.items():
        selected = [obj for obj in components if obj.data.materials[0] == surf.mat]
        textures.extend(bake_surface(part, surf, selected, cache))
    for name, pieces in groups.items():
        for obj in pieces:
            obj.location -= bl(LAYOUT[name])
            obj.hide_render = False
    bpy.context.view_layer.update()
    objects = []
    part_bounds = {}
    for name, pieces in groups.items():
        obj = join_static(pieces, name, origin=bl(smoke_pos) if name == 'smoke_led' else (0, 0, 0))
        # Tint was baked, so do not multiply vertex colours a second time.
        for attribute in list(obj.data.color_attributes):
            obj.data.color_attributes.remove(attribute)
        triangulate(obj)
        objects.append(obj)
        bpy.context.view_layer.update()
        points = [obj.matrix_world @ Vector(c) for c in obj.bound_box]
        gp = [(p.x, p.z, -p.y) for p in points]
        part_bounds[name] = {'min': [round(min(v[i] for v in gp), 8) for i in range(3)],
                             'max': [round(max(v[i] for v in gp), 8) for i in range(3)]}
    bpy.context.view_layer.update()
    glb_path = Path(out_dir).resolve() / f'{ASSET_ID}.glb'
    gltf = export_glb(glb_path, objects)
    nodes = {n['name']: n for n in gltf['nodes'] if 'mesh' in n}
    if set(nodes) != set(groups) or gltf.get('animations') or gltf.get('cameras'):
        raise RuntimeError('Unexpected parts, animations or cameras')
    for name, node in nodes.items():
        if node.get('scale', [1, 1, 1]) != [1, 1, 1] or node.get('rotation', [0, 0, 0, 1]) != [0, 0, 0, 1]:
            raise RuntimeError(f'Unapplied transform: {name}')
        expected = smoke_pos if name == 'smoke_led' else (0, 0, 0)
        if any(abs(a - b) > 1e-7 for a, b in zip(node.get('translation', [0, 0, 0]), expected)):
            raise RuntimeError(f'Incorrect mounting origin: {name}')
    for name, bounds in part_bounds.items():
        if name != 'smoke_led' and abs(bounds['max'][2]) > .000001:
            # Most faceplates have a bevelled inset rear foot; their foot is
            # explicitly modelled at z=0. Vent back reaches the wall at z=0.
            raise RuntimeError(f'Mount face not z=0: {name}: {bounds}')
    meta = write_metadata(ASSET_ID, ROOT / 'assets/meta' / f'{ASSET_ID}.json', glb_path,
        objects, Path(__file__), textures, origin='mount_plane_center', extra={
        'forward': 'Blender +Y -> Godot -Z', 'anchors_godot_m': anchors,
        'part_bounds_godot_m': part_bounds, 'collision': None,
        'part_origins_godot_m': {n: list(smoke_pos) if n == 'smoke_led' else [0, 0, 0] for n in groups},
        'baking': {'engine': 'CYCLES', 'device': 'CPU', 'samples': 16, 'margin_px': 8,
                   'maps': 'procedural colour/roughness, tangent normals, AO packed into ORM'},
        'render': {'engine': 'CYCLES', 'device': 'CPU', 'samples': 32, 'threads': 4, 'denoise': True},
        'lamp_angles_degrees': {'down': 30, 'outward': 30},
        'glb_path': str(glb_path.relative_to(ROOT)) if glb_path.is_relative_to(ROOT) else str(glb_path)})
    if meta['triangles'] > 20000 or len(meta['materials']) > 5:
        raise RuntimeError('Asset exceeds request budget')
    print('PASS geometry: seven exact parts; mounting origins; applied transforms; no collisions/animations', flush=True)
    # Preview-only exploded presentation. Nothing is exported after this.
    original_locations = {obj.name: obj.location.copy() for obj in objects}
    for obj in objects:
        obj.location += bl(LAYOUT[obj.name])
    bpy.context.view_layer.update()
    views = {'front': {'position': (-.07, 3, .07), 'target': (-.07, 0, .07), 'scale': 1.35},
             'iso': {'position': (1.45, 3, 1.32), 'target': (0, .02, .06), 'scale': 1.42},
             'detail': {'position': (.44, 2, .45), 'target': (0, .015, -.01), 'scale': .70}}
    class DetailViews(dict):
        def __getitem__(self, key):
            if key == 'detail':
                cluster = {'emergency_light': (0, .12, 0), 'outlet_double': (-.13, -.10, 0),
                           'light_switch': (.115, -.10, 0), 'smoke_detector': (0, -.25, 0),
                           'smoke_led': (0, -.25, 0)}
                for obj in objects:
                    obj.hide_render = obj.name not in cluster
                    if obj.name in cluster:
                        obj.location = original_locations[obj.name] + bl(cluster[obj.name])
                bpy.context.view_layer.update()
            return super().__getitem__(key)
    try:
        render_previews(ASSET_ID, ROOT / 'assets/previews', objects, DetailViews(views), seed=SEED)
    finally:
        for obj in objects:
            obj.location = original_locations[obj.name]
        bpy.context.view_layer.update()
    print(f'ASSET BUILT: {glb_path}; {meta["triangles"]} triangles; {len(meta["materials"])} materials')
    return glb_path


if __name__ == '__main__':
    run_cli(build, __doc__)
