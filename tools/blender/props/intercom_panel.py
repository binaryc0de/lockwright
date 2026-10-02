"""Commercial security intercom: original geometry and baked brushed-metal PBR.

Blender 5.2 headless, deterministic, no network or external fonts/assets.
Run tools/blender/build_assets.sh intercom_panel (flock, CPU, four threads).
"""
import math
from pathlib import Path
import sys

import bpy

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

ASSET_ID = 'intercom_panel'
SEED = 102026
SCREEN_CENTRE = (0, .067, -.038)
SCREEN_SIZE = (.18, .10)


def blender(p):
    """Godot X,Y,Z -> Blender X,-Z,Y; +Y in Blender faces Godot -Z."""
    return (p[0], -p[2], p[1])


class Surface:
    """Explicit procedural shader, subsequently baked to portable PBR maps."""
    def __init__(self, part, color, roughness, metallic):
        self.mat = material(ASSET_ID, part, color, roughness=roughness, metallic=metallic)
        self.tree = self.mat.node_tree
        self.bsdf = self.tree.nodes.get('Principled BSDF')
        self.pos = self.node('ShaderNodeNewGeometry').outputs['Position']
        self.axes = self.node('ShaderNodeSeparateXYZ', Vector=self.pos)
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

    def math(self, kind, a, b):
        node = self.node('ShaderNodeMath')
        node.operation = kind
        self.set(node.inputs[0], a)
        self.set(node.inputs[1], b)
        return node.outputs[0]

    def noise(self, scale, detail=2):
        vec = self.node('ShaderNodeVectorMath')
        vec.operation = 'MULTIPLY'
        self.set(vec.inputs[0], self.pos)
        self.set(vec.inputs[1], scale)
        return self.node('ShaderNodeTexNoise', Vector=vec.outputs[0], Scale=1., Detail=detail,
                         Roughness=.66).outputs['Fac']

    def mix(self, fac, a, b):
        return self.node('ShaderNodeMixRGB', Fac=fac, Color1=a, Color2=b).outputs[0]

    def ellipse(self, x, z, rx, rz):
        dx = self.math('DIVIDE', self.math('SUBTRACT', self.axes.outputs['X'], x), rx)
        dz = self.math('DIVIDE', self.math('SUBTRACT', self.axes.outputs['Z'], z), rz)
        d = self.math('ADD', self.math('MULTIPLY', dx, dx), self.math('MULTIPLY', dz, dz))
        return self.math('MAXIMUM', 0., self.math('SUBTRACT', 1., d))

    def finish(self, color, roughness, height, distance):
        self.color, self.roughness = color, roughness
        self.set(self.bsdf.inputs['Base Color'], color)
        self.set(self.bsdf.inputs['Roughness'], roughness)
        bump = self.node('ShaderNodeBump', Height=height, Strength=.30, Distance=distance)
        self.tree.links.new(bump.outputs['Normal'], self.bsdf.inputs['Normal'])


def surfaces():
    steel = Surface('body', (.43, .46, .49), .36, 1.)
    brush = steel.noise((19, 3500, 5800), 2)
    broad = steel.noise((32, 32, 32), 2)
    fine = steel.noise((2100, 2100, 2100), 2)
    color = steel.mix(brush, (.37, .40, .43, 1), (.48, .51, .54, 1))
    # Hand oil around the call button, with faint irregular fingerprint ridges.
    oil = steel.math('MAXIMUM', steel.ellipse(.017, -.103, .026, .028),
                     steel.ellipse(-.020, -.117, .023, .026))
    oil = steel.math('MULTIPLY', oil, steel.math('ADD', .45,
                         steel.math('MULTIPLY', broad, .55)))
    color = steel.mix(steel.math('MULTIPLY', oil, .09), color, (.26, .28, .29, 1))
    rough = steel.math('ADD', .29, steel.math('MULTIPLY', brush, .19))
    rough = steel.math('SUBTRACT', rough, steel.math('MULTIPLY', oil, .11))
    # Accumulated edge grime is thin and uneven; stainless never gets rusty.
    edge_x = steel.math('GREATER_THAN', steel.math('ABSOLUTE', steel.axes.outputs['X'], 0), .105)
    edge_z = steel.math('GREATER_THAN', steel.math('ABSOLUTE', steel.axes.outputs['Z'], 0), .155)
    edge = steel.math('MULTIPLY', steel.math('MAXIMUM', edge_x, edge_z), broad)
    color = steel.mix(steel.math('MULTIPLY', edge, .16), color, (.13, .135, .14, 1))
    rough = steel.math('ADD', rough, steel.math('MULTIPLY', edge, .09))
    steel.finish(color, rough, steel.math('ADD', brush, steel.math('MULTIPLY', fine, .12)), .000065)

    button = Surface('button', (.034, .039, .042), .39, .82)
    grain = button.noise((40, 3700, 3700), 2)
    mottling = button.noise((150, 150, 150), 2)
    polish = button.ellipse(0, -.107, .018, .018)
    color = button.mix(grain, (.027, .033, .037, 1), (.048, .055, .060, 1))
    rough = button.math('ADD', .31, button.math('MULTIPLY', grain, .17))
    rough = button.math('SUBTRACT', rough, button.math('MULTIPLY', polish, .045))
    # Broken concentric oil ridges: restrained roughness detail rather than dirt decals.
    wave = button.node('ShaderNodeTexWave', Vector=button.pos, Scale=1600.,
                       Distortion=5., Detail=3., **{'Detail Scale': 3.})
    wave.wave_type = 'RINGS'
    wave.rings_direction = 'Y'
    oil = button.math('MULTIPLY', wave.outputs['Fac'],
                      button.math('MULTIPLY', mottling, polish))
    rough = button.math('SUBTRACT', rough, button.math('MULTIPLY', oil, .055))
    # CALL is light laser marking in the button material, distinguished by
    # its physical front depth. Bake the lettering together with the cap.
    ink = button.math('GREATER_THAN', button.axes.outputs['Y'], .04253)
    color = button.mix(ink, color, (.72, .74, .74, 1))
    rough = button.math('ADD', button.math('MULTIPLY', rough, button.math('SUBTRACT', 1., ink)),
                         button.math('MULTIPLY', ink, .53))
    button.metallic = button.math('MULTIPLY', .82, button.math('SUBTRACT', 1., ink))
    button.set(button.bsdf.inputs['Metallic'], button.metallic)
    button.finish(color, rough, button.math('MULTIPLY', grain, button.math('SUBTRACT', 1., ink)), .000045)
    grille = material(ASSET_ID, 'grille', (.008, .011, .013), metallic=.20, roughness=.76)
    screen = material(ASSET_ID, 'screen', (.005, .015, .018), metallic=0., roughness=.29,
                      emission=((.003, .008, .010), .12))
    led = material(ASSET_ID, 'led', (1., 1., 1.), roughness=.23,
                   emission=((1., 1., 1.), 1.2))
    return steel, button, grille, screen, led


def slab(name, dims, pos, mat, radius=.0005, segments=3):
    return box(name, (dims[0], dims[2], dims[1]), mat, blender(pos), bevel=radius, segments=segments)


def profile_mesh(name, x, y, profile, mat, count=48, caps=True):
    """Axis along Blender +Y, closed machined circular profiles in Godot depths."""
    verts = [(x + r * math.cos(i * math.tau / count), -z,
              y + r * math.sin(i * math.tau / count))
             for z, r in profile for i in range(count)]
    faces = []
    for ring in range(len(profile) - 1):
        for i in range(count):
            j = (i + 1) % count
            faces.append((ring * count + i, ring * count + j,
                          (ring + 1) * count + j, (ring + 1) * count + i))
    if caps:
        for start in (0, (len(profile) - 1) * count):
            for i in range(1, count - 1):
                faces.append((start, start + i, start + i + 1))
    obj = mesh_object(name, verts, faces, mat)
    for face in obj.data.polygons:
        face.use_smooth = len(face.vertices) == 4 and abs(face.normal.y) < .999
    return obj


def subtract(obj, cutter):
    active(obj)
    mod = obj.modifiers.new('machined_aperture', 'BOOLEAN')
    mod.operation = 'DIFFERENCE'
    mod.solver = 'EXACT'
    mod.object = cutter
    bpy.ops.object.modifier_apply(modifier=mod.name)
    bpy.data.objects.remove(cutter, do_unlink=True)


def perforated_grille(mat):
    """120 real through-holes in one 1.2 mm sheet; no painted-on dots.

    Every cell is a planar square annulus, with circular bore walls and a
    back surface. Shared borders are welded; only the sheet perimeter is capped.
    """
    cols, rows, pitch, radius, count = 20, 6, .008, .00145, 16
    cy = -.036
    verts, faces, lookup = [], [], {}
    def vertex(point):
        key = tuple(round(v, 9) for v in point)
        if key not in lookup:
            lookup[key] = len(verts)
            verts.append(point)
        return lookup[key]
    def ring(cx, cz, depth, outer):
        result = []
        for i in range(count):
            a = i * math.tau / count
            r = pitch / 2 / max(abs(math.cos(a)), abs(math.sin(a))) if outer else radius
            result.append(vertex((cx + r * math.cos(a), depth, cz + r * math.sin(a))))
        return result
    for row in range(rows):
        for col in range(cols):
            cx, cz = (col - (cols - 1) / 2) * pitch, cy + (row - (rows - 1) / 2) * pitch
            front_outer, front_inner = ring(cx, cz, .0392, True), ring(cx, cz, .0392, False)
            back_outer, back_inner = ring(cx, cz, .0380, True), ring(cx, cz, .0380, False)
            for i in range(count):
                j = (i + 1) % count
                faces.extend([(front_outer[i], front_outer[j], front_inner[j], front_inner[i]),
                              (back_outer[i], back_inner[i], back_inner[j], back_outer[j]),
                              (front_inner[i], front_inner[j], back_inner[j], back_inner[i])])
                a, b = verts[front_outer[i]], verts[front_outer[j]]
                if ((abs(a[0] - b[0]) < 1e-8 and abs(abs(a[0]) - cols * pitch / 2) < 1e-8) or
                    (abs(a[2] - b[2]) < 1e-8 and abs(abs(a[2] - cy) - rows * pitch / 2) < 1e-8)):
                    faces.append((front_outer[i], back_outer[i], back_outer[j], front_outer[j]))
    return mesh_object('punched_speaker_sheet', verts, faces, mat)


GLYPHS = {
    'S': [[(.6, 1), (0, 1), (0, .5), (.6, .5), (.6, 0), (0, 0)]],
    'E': [[(.6, 1), (0, 1), (0, 0), (.6, 0)], [(0, .5), (.48, .5)]],
    'C': [[(.6, 1), (0, 1), (0, 0), (.6, 0)]],
    'U': [[(0, 1), (0, 0), (.6, 0), (.6, 1)]],
    'R': [[(0, 0), (0, 1), (.6, 1), (.6, .5), (0, .5)], [(.24, .5), (.6, 0)]],
    'I': [[(.3, 0), (.3, 1)]],
    'T': [[(0, 1), (.6, 1)], [(.3, 1), (.3, 0)]],
    'Y': [[(0, 1), (.3, .5), (.6, 1)], [(.3, .5), (.3, 0)]],
    'A': [[(0, 0), (.3, 1), (.6, 0)], [(.15, .5), (.45, .5)]],
    'L': [[(0, 1), (0, 0), (.6, 0)]],
}


def lettering(text, centre, height, stroke, mat):
    """Original stroke geometry; no host fonts, font downloads or hidden decals."""
    advance = .85 * height
    width = advance * (len(text) - 1) + .6 * height
    pieces = []
    for index, char in enumerate(text):
        for path in GLYPHS[char]:
            for a, b in zip(path, path[1:]):
                # Front-view text advances toward Blender -X, per the accepted keypad.
                ax = centre[0] + width / 2 - index * advance - a[0] * height
                bx = centre[0] + width / 2 - index * advance - b[0] * height
                az, bz = centre[1] + (a[1] - .5) * height, centre[1] + (b[1] - .5) * height
                dx, dz = bx - ax, bz - az
                length = math.hypot(dx, dz)
                nx, nz = -dz / length * stroke / 2, dx / length * stroke / 2
                verts = [(ax - nx, -centre[2], az - nz), (bx - nx, -centre[2], bz - nz),
                         (bx + nx, -centre[2], bz + nz), (ax + nx, -centre[2], az + nz)]
                pieces.append(mesh_object('printed_stroke', verts, [(3, 2, 1, 0)], mat))
    return pieces


def tamper_screw(x, y, mat):
    n = 48
    verts = []
    for ring in range(5):
        for i in range(n):
            angle = i * math.tau / n
            if ring < 2:
                radius, z = ((.0039, -.0396), (.0034, -.0406))[ring]
            else:
                radius = .00135 * (1 + .18 * math.cos(6 * angle))
                z = (-.0406, -.0397, -.03965)[ring - 2]
            verts.append((x + radius * math.cos(angle), -z, y + radius * math.sin(angle)))
    faces = []
    for ring in range(4):
        for i in range(n):
            j = (i + 1) % n
            faces.append((ring * n + i, ring * n + j, (ring + 1) * n + j, (ring + 1) * n + i))
    for start in (0, 4 * n):
        for i in range(1, n - 1):
            faces.append((start, start + i, start + i + 1))
    obj = mesh_object('tamper_screw', verts, faces, mat)
    for p in obj.data.polygons:
        p.use_smooth = len(p.vertices) == 4 and abs(p.normal.y) < .999
    # Security pin prevents using an ordinary Torx bit.
    pin = profile_mesh('security_pin', x, y, [(-.03965, .00034), (-.0402, .00034)], mat, 16)
    return [obj, pin]


def geometry(steel, button, grille, screen_mat, led_mat):
    fixed = []
    shell = slab('folded_rear_case', (.216, .316, .038), (0, 0, -.019), steel.mat, .003, 5)
    plate = slab('stainless_faceplate', (.22, .32, .002), (0, 0, -.039), steel.mat, .00065, 4)
    # True display pocket and grille cavity; no hidden solid face blocks the holes.
    for obj in (shell, plate):
        subtract(obj, slab('screen_cutter-noimp', (.186, .106, .019), (0, .067, -.0375), None, .002, 4))
        subtract(obj, slab('grille_cutter-noimp', (.161, .049, .020), (0, -.036, -.036), None, .0012, 3))
        subtract(obj, profile_mesh('mic_cutter-noimp', .053, -.107,
                                  [(-.024, .0018), (-.045, .0018)], None, 24))
    fixed.extend([shell, plate])
    # Black elastomer faceplate gasket visible as a fine seam at the side.
    gasket = slab('faceplate_gasket', (.217, .317, .0005), (0, 0, -.03775), grille, .0002)
    for dims, pos in [((.186, .106, .005), (0, .067, -.039)),
                      ((.161, .049, .005), (0, -.036, -.039))]:
        subtract(gasket, slab('gasket_aperture-noimp', dims, pos, None, .001, 3))
    subtract(gasket, profile_mesh('mic_gasket_cutter-noimp', .053, -.107,
                                  [(-.034, .0018), (-.045, .0018)], None, 24))
    fixed.append(gasket)
    # LCD socket lips outside the exact 180 x 100 mm dynamic content window.
    for x in (-.0915, .0915):
        fixed.append(slab('lcd_side_gasket', (.003, .104, .0024), (x, .067, -.0372), grille, .0004))
    for y in (.0155, .1185):
        fixed.append(slab('lcd_end_gasket', (.180, .003, .0024), (0, y, -.0372), grille, .0004))
    fixed.append(slab('speaker_dark_cavity', (.164, .052, .001), (0, -.036, -.0265), grille, .0004))
    fixed.append(perforated_grille(steel.mat))
    for x in (-.095, .095):
        for y in (-.144, .144):
            fixed.extend(tamper_screw(x, y, steel.mat))
    fixed.extend(lettering('SECURITY', (0, .137, -.04006), .006, .00055, grille))
    fixed.append(profile_mesh('button_seal', 0, -.107,
                              [(-.0398, .022), (-.0405, .022)], grille, 64))
    fixed.append(profile_mesh('button_bezel', 0, -.107,
                              [(-.0402, .0215), (-.0415, .021), (-.042, .020),
                               (-.042, .0188), (-.0407, .0188)], steel.mat, 64, False))
    # LED is beside the button, and the microphone bore is on the other side.
    fixed.append(profile_mesh('led_socket', -.053, -.107,
                              [(-.0398, .0036), (-.0407, .0033), (-.0407, .0025)], grille, 32, False))
    fixed.append(profile_mesh('microphone_lining', .053, -.107,
                              [(-.038, .0018), (-.040, .0018), (-.040, .0014),
                               (-.030, .0014)], grille, 24, False))
    fixed.append(profile_mesh('microphone_back', .053, -.107,
                              [(-.026, .0016), (-.0262, .0016)], grille, 24))
    cap = profile_mesh('call_cap', 0, -.107,
                       [(-.0405, .0184), (-.0412, .0184), (-.0420, .0182),
                        (-.0425, .0175)], button.mat, 64)
    call = [cap, *lettering('CALL', (0, -.107, -.04256), .0045, .00048, button.mat)]
    # Full-range, unmirrored display UVs. Its origin lies on the front surface.
    w, h = SCREEN_SIZE
    display = mesh_object('screen', [(-w/2, 0, -h/2), (-w/2, 0, h/2),
                                     (w/2, 0, h/2), (w/2, 0, -h/2)],
                          [(0, 1, 2, 3)], screen_mat, blender(SCREEN_CENTRE))
    uv = display.data.uv_layers.new(name='UVMap')
    for loop, point in zip(uv.data, [(1, 0), (1, 1), (0, 1), (0, 0)]):
        loop.uv = point
    led = profile_mesh('led_status', -.053, -.107,
                       [(-.0400, .0025), (-.0407, .0025), (-.0414, .0021),
                        (-.0419, .0013), (-.0421, .0001)], led_mat, 32)
    led_origin = blender((-.053, -.107, -.040))
    for vertex in led.data.vertices:
        for axis in range(3):
            vertex.co[axis] -= led_origin[axis]
    led.location = led_origin
    for obj in [*fixed, *call, display, led]:
        triangulate(obj)
    return fixed, call, display, led


def bake_surface(surf, components, cache):
    """Accepted desk structure: global nonoverlap unwrap, emission color/RM,
    Cycles tangent normal bake, eight-pixel margin, embedded 1024 px PNGs.
    Only the temporary bake mesh contains the procedural graph at export time.
    """
    size = 1024
    vertices, faces, smooth = [], [], []
    for obj in components:
        offset = len(vertices)
        vertices.extend(tuple(obj.matrix_world @ v.co) for v in obj.data.vertices)
        faces.extend(tuple(offset + i for i in p.vertices) for p in obj.data.polygons)
        smooth.extend(p.use_smooth for p in obj.data.polygons)
    temp = mesh_object('bake_surface-noimp', vertices, faces, surf.mat)
    for p, flag in zip(temp.data.polygons, smooth):
        p.use_smooth = flag
    active(temp)
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.uv.smart_project(angle_limit=math.radians(66), island_margin=8/size,
                             margin_method='FRACTION', scale_to_bounds=True)
    bpy.ops.uv.average_islands_scale()
    bpy.ops.uv.pack_islands(rotate=True, margin_method='FRACTION', margin=8/size)
    bpy.ops.object.mode_set(mode='OBJECT')
    source = temp.data.uv_layers.active.data
    cursor = 0
    for obj in components:
        uv = obj.data.uv_layers.new(name='UVMap')
        for loop in uv.data:
            loop.uv = source[cursor].uv
            cursor += 1
    if cursor != len(source):
        raise RuntimeError('UV loop transfer mismatch')
    scene = bpy.context.scene
    scene.cycles.samples = 16
    scene.render.bake.margin = 8
    scene.render.bake.use_clear = True
    scene.render.bake.use_selected_to_active = False
    scene.render.bake.normal_space = 'TANGENT'
    tree = surf.tree
    output = next(n for n in tree.nodes if n.type == 'OUTPUT_MATERIAL')
    emitter = surf.node('ShaderNodeEmission', Strength=1.)
    target = surf.node('ShaderNodeTexImage')
    rm = surf.node('ShaderNodeCombineColor', Red=1., Green=surf.roughness, Blue=surf.metallic)
    images = {}
    for name, kind, color in [('base_color', 'EMIT', surf.color),
                               ('orm', 'EMIT', rm.outputs[0]), ('normal', 'NORMAL', None)]:
        image = bpy.data.images.new(f'T_{ASSET_ID}_{surf.mat.name.split(ASSET_ID + "_")[1]}_{name}',
                                   width=size, height=size, alpha=False)
        image.colorspace_settings.name = 'sRGB' if name == 'base_color' else 'Non-Color'
        target.image = image
        tree.nodes.active = target
        if kind == 'EMIT':
            surf.set(emitter.inputs['Color'], color)
            tree.links.new(emitter.outputs[0], output.inputs['Surface'])
        else:
            tree.links.new(surf.bsdf.outputs[0], output.inputs['Surface'])
        active(temp)
        print(f'BAKE {surf.mat.name} {name}: {size}px, {kind}, CPU, 8px margin', flush=True)
        bpy.ops.object.bake(type=kind)
        image.file_format = 'PNG'
        image.filepath_raw = str(cache / f'{image.name}.png')
        image.save()
        image.pack()
        images[name] = image
    for node in list(tree.nodes):
        if node not in (surf.bsdf, output):
            tree.nodes.remove(node)
    tree.links.new(surf.bsdf.outputs[0], output.inputs['Surface'])
    base_texture(surf.mat, images['base_color'])
    orm_texture(surf.mat, images['orm'])
    normal_texture(surf.mat, images['normal'])
    bpy.data.objects.remove(temp, do_unlink=True)
    return [{'name': image.name, 'size': list(image.size), 'map': name,
             'material': surf.mat.name, 'embedded': True} for name, image in sorted(images.items())]


def build(out_dir):
    reset_scene(SEED)
    cache = ROOT / 'assets/cache' / ASSET_ID
    cache.mkdir(parents=True, exist_ok=True)
    steel, button, grille, screen_mat, led_mat = surfaces()
    fixed, call, display, led = geometry(steel, button, grille, screen_mat, led_mat)
    bpy.context.view_layer.update()
    components = [*fixed, *call]
    textures = []
    for surf in (steel, button):
        selected = [obj for obj in components if obj.data.materials[0] == surf.mat]
        textures.extend(bake_surface(surf, selected, cache))
    body = join_static(fixed, 'body')
    call = join_static(call, 'btn_call', blender((0, -.107, -.0405)))
    objects = [body, call, display, led]
    for obj in objects:
        triangulate(obj)
    bpy.context.view_layer.update()
    glb_path = Path(out_dir).resolve() / f'{ASSET_ID}.glb'
    gltf = export_glb(glb_path, objects)
    nodes = {n['name']: n for n in gltf['nodes'] if 'mesh' in n}
    if set(nodes) != {'body', 'screen', 'btn_call', 'led_status'} or gltf.get('animations') or gltf.get('cameras'):
        raise RuntimeError('Unexpected exported parts, animations or cameras')
    for name, node in nodes.items():
        if node.get('scale', [1, 1, 1]) != [1, 1, 1] or node.get('rotation', [0, 0, 0, 1]) != [0, 0, 0, 1]:
            raise RuntimeError(f'Unapplied transform: {name}')
    anchor = nodes['screen'].get('translation', [0, 0, 0])
    if any(abs(a-b) > 1e-7 for a, b in zip(anchor, SCREEN_CENTRE)):
        raise RuntimeError(f'Incorrect screen anchor: {anchor}')
    if any(abs(v) > 1e-8 for v in nodes['body'].get('translation', [0, 0, 0])):
        raise RuntimeError('Body origin must be mount-plane centre')
    meta = write_metadata(ASSET_ID, ROOT / 'assets/meta' / f'{ASSET_ID}.json', glb_path,
                          objects, Path(__file__), textures, 'mount_plane_center', extra={
        'anchors_godot_m': {'screen_centre': list(SCREEN_CENTRE), 'screen_size': list(SCREEN_SIZE)},
        'forward': 'Blender +Y -> Godot -Z',
        'housing_dimensions_godot_m': [.22, .32, .04],
        'screen_recess_m': .002,
        'screen_uv': '0..1, unmirrored front view; origin at front surface centre',
        'collision': None,
        'lettering': 'original geometry stroke alphabet: SECURITY and CALL',
        'speaker_grille': {'through_holes': 120, 'bore_diameter_m': .0029, 'sheet_thickness_m': .0012},
        'baking': {'engine': 'CYCLES', 'device': 'CPU', 'samples': 16, 'margin_px': 8,
                   'maps': 'procedural base color, tangent normal, ORM (R=1, G=roughness, B=metallic)'},
        'render': {'engine': 'CYCLES', 'device': 'CPU', 'samples': 32, 'denoise': True, 'threads': 4},
        'glb_path': str(glb_path.relative_to(ROOT)) if glb_path.is_relative_to(ROOT) else str(glb_path),
    })
    if meta['triangles'] > 20000 or len(meta['materials']) > 5:
        raise RuntimeError('Request budget exceeded')
    if abs(meta['bounds_godot_m']['max'][2]) > 1e-7:
        raise RuntimeError('Back mount face is not on z=0')
    print('PASS geometry: mount origin, LCD anchor/UV, applied transforms, 120 through-holes, no collision/animations', flush=True)
    render_previews(ASSET_ID, ROOT / 'assets/previews', objects, views={
        'front': {'position': (0, .8, 0), 'target': (0, .025, 0), 'scale': .385},
        'iso': {'position': (-.50, .78, .35), 'target': (0, .020, 0), 'scale': .405},
        'detail': {'position': (-.20, .68, -.007), 'target': (0, .038, -.079), 'scale': .220},
    }, seed=SEED)
    print(f'ASSET BUILT: {glb_path}; {meta["triangles"]} triangles; {len(meta["materials"])} materials', flush=True)
    return glb_path


if __name__ == '__main__':
    run_cli(build, __doc__)
