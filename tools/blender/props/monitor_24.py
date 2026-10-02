"""24-inch corporate display: moulded ABS, recessed glass and cast-metal stand.

Deterministic, offline, original geometry and CPU-baked textures. Run through
build_assets.sh (serialized Blender 5.2.x, four threads, Cycles CPU previews).
"""
from array import array
import math
from pathlib import Path
import random
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
from common.materials import base_texture, image_from_pixels, material, normal_texture, orm_texture
from common.preview import render_previews
from common.scene import reset_scene

ASSET_ID = 'monitor_24'
SEED = 242026
SIZE = 1024
SCREEN_CENTRE = (0, .0297, .292)


def rounded_rect(w, h, radius, centre_z, steps=6):
    points = []
    for cx, cz, start in ((w / 2 - radius, h / 2 - radius, 0),
                           (-w / 2 + radius, h / 2 - radius, 90),
                           (-w / 2 + radius, -h / 2 + radius, 180),
                           (w / 2 - radius, -h / 2 + radius, 270)):
        for i in range(steps + 1):
            a = math.radians(start + i * 90 / steps)
            points.append((cx + radius * math.cos(a), centre_z + cz + radius * math.sin(a)))
    return points


def loft(name, profiles, mat, cap_start=False, cap_end=False):
    """Moulded profiles with rounded corners; matched rings, no booleans."""
    vertices = []
    for w, h, radius, z, y in profiles:
        vertices.extend((x, y, zz) for x, zz in rounded_rect(w, h, radius, z))
    count = len(vertices) // len(profiles)
    faces = []
    for ring in range(len(profiles) - 1):
        for i in range(count):
            j = (i + 1) % count
            faces.append((ring * count + i, ring * count + j,
                          (ring + 1) * count + j, (ring + 1) * count + i))
    if cap_start:
        faces.append(tuple(reversed(range(count))))
    if cap_end:
        faces.append(tuple(range((len(profiles) - 1) * count, len(profiles) * count)))
    obj = mesh_object(name, vertices, faces, mat)
    for p in obj.data.polygons:
        p.use_smooth = len(p.vertices) == 4 and max(abs(v) for v in p.normal) < .999
    return obj


def cylinder(name, radius, depth, mat, position, axis='Y', count=24):
    verts = []
    for side in (-1, 1):
        for i in range(count):
            a = i * math.tau / count
            p = (radius * math.cos(a), side * depth / 2, radius * math.sin(a))
            if axis == 'Z':
                p = (p[0], p[2], p[1])
            verts.append(p)
    faces = [(i, (i + 1) % count, count + (i + 1) % count, count + i) for i in range(count)]
    faces.extend((tuple(reversed(range(count))), tuple(range(count, count * 2))))
    obj = mesh_object(name, verts, faces, mat, position)
    for p in obj.data.polygons:
        p.use_smooth = len(p.vertices) == 4
    return obj


def cut(obj, cutter):
    active(obj)
    mod = obj.modifiers.new('moulded_opening', 'BOOLEAN')
    mod.operation = 'DIFFERENCE'
    mod.solver = 'EXACT'
    mod.object = cutter
    bpy.ops.object.modifier_apply(modifier=mod.name)
    bpy.data.objects.remove(cutter, do_unlink=True)


def make_geometry(plastic, metal, screen_mat, led_mat):
    # Front frame: outside 560 x 340 mm, inner bevel and recessed glass.
    # Display is 531 x 299 mm: exact dimensions take priority over bezel prose.
    frame = loft('front_frame', [
        (.556, .336, .002, .29, .016),
        (.560, .340, .004, .29, .018),
        (.560, .340, .004, .29, .0288),
        (.558, .338, .003, .29, .031),
        (.533, .301, .00045, .292, .031),
        (.5314, .2994, .0001, .292, .0296),
        (.5314, .2994, .0001, .292, .0255),
    ], plastic)
    # The rear is thin at the edge and swells to 45 mm total thickness centrally.
    rear = loft('rear_shell', [
        (.556, .336, .003, .29, .0157),
        (.548, .328, .006, .29, .015),
        (.485, .268, .023, .29, .004),
        (.408, .202, .025, .281, -.013),
        (.402, .196, .025, .281, -.014),
    ], plastic, cap_start=True, cap_end=True)
    # A crisp mould parting seam on the flank, not an oversized dark stripe.
    seam = loft('shell_parting_seam', [
        (.5568, .3368, .0033, .29, .0160),
        (.5568, .3368, .0033, .29, .01645),
    ], plastic)
    # Thin glossy bottom chin: flush almost everywhere, with a genuine fine seam.
    chin = box('chin_strip', (.550, .00065, .010), plastic,
               (0, .03095, .1285), bevel=.0003, segments=3)
    # Rear convection slots, actual small recessed openings into the back shell.
    # This region lies on the flat rear cap; slot ends have a moulding radius.
    vent_cutters = []
    for i in range(27):
        vent_cutters.append(box(f'vent_cutter_{i}', (.0025, .009, .013), None,
                               ((i - 13) * .0095, -.014, .347), bevel=.0008, segments=3))
    vent_cut = join_static(vent_cutters, 'vent_cut-noimp')
    cut(rear, vent_cut)
    vent_back = box('vent_shadow_baffle', (.268, .001, .017), plastic,
                    (0, -.0085, .347), bevel=.0003)
    mount = box('stand_mount', (.090, .024, .079), plastic,
                (0, -.025, .247), bevel=.004, segments=4)
    release = box('mount_release', (.026, .002, .009), plastic,
                  (0, -.038, .219), bevel=.001)
    panel_parts = [frame, rear, seam, chin, vent_back, mount, release]
    # Inset screw heads on the VESA/mount plate: head and real cross recess.
    for x in (-.036, .036):
        for z in (.220, .274):
            head = cylinder('mount_screw', .00225, .001, metal, (x, -.0373, z))
            for dimensions in ((.0024, .001, .0005), (.0005, .001, .0024)):
                cut(head, box('cross_cut-noimp', dimensions, None, (x, -.0378, z)))
            panel_parts.append(head)
    # Down-facing modest connector bay (no logos or labels).
    bay = box('connector_bay', (.096, .018, .009), plastic,
              (.126, -.001, .181), bevel=.0015)
    for x, w in ((.102, .016), (.131, .013), (.154, .007)):
        cut(bay, box('port_cut-noimp', (w, .011, .010), None,
                     (x, -.002, .177), bevel=.00045))
    panel_parts.append(bay)
    # Four little underside OSD controls, visually present but never separate SDK nodes.
    for i in range(4):
        panel_parts.append(box('osd_button', (.009, .006, .0014), plastic,
                               (-.186 - i * .018, .024, .1193), bevel=.0006))
    panel = join_static(panel_parts, 'panel')
    # Rectangular satin alloy foot. Rubber pads are tucked inside its 15 mm height.
    foot = box('alloy_foot', (.220, .170, .013), metal,
               (0, 0, .0085), bevel=.0025, segments=5)
    stand_parts = [foot]
    for x in (-.083, .083):
        for y in (-.061, .061):
            stand_parts.append(box('rubber_foot', (.026, .026, .003), plastic,
                                   (x, y, .0015), bevel=.0012))
    heel = box('neck_socket', (.081, .045, .007), plastic,
               (0, -.036, .017), bevel=.0022, segments=4)
    stand_parts.append(heel)
    neck = box('flat_neck', (.068, .016, .246), metal,
               (0, -.034, .138), bevel=.0026, segments=4)
    # Actual cable-management opening, rounded and inset in the flat neck.
    cut(neck, box('cable_slot_cut-noimp', (.027, .035, .040), None,
                  (0, -.034, .083), bevel=.006, segments=5))
    stand_parts.append(neck)
    trim = box('neck_rear_trim', (.060, .002, .176), plastic,
               (0, -.043, .170), bevel=.001)
    stand_parts.append(trim)
    stand = join_static(stand_parts, 'stand')
    # Original quad coordinates exactly span 0..1, +Y normal -> Godot -Z.
    sw, sh = .531 / 2, .299 / 2
    screen = mesh_object('screen', [(-sw, 0, -sh), (-sw, 0, sh),
                                     (sw, 0, sh), (sw, 0, -sh)],
                         [(0, 1, 2, 3)], screen_mat, SCREEN_CENTRE)
    uv = screen.data.uv_layers.new(name='UVMap')
    # As viewed from +Y, screen-right is -X, consistent with accepted keypad.
    for loop, coord in zip(uv.data, ((1, 0), (1, 1), (0, 1), (0, 0))):
        loop.uv = coord
    # Tiny white lens; emission can be tinted with its base colour in Godot.
    led = box('led_power', (.0032, .0006, .0008), led_mat,
              (-.259, .0317, .1285), bevel=.00025, segments=4)
    return [panel, stand, screen, led]


def unwrap(objects):
    """One shared, non-overlapping atlas for every baked plastic/metal surface."""
    bpy.ops.object.select_all(action='DESELECT')
    for obj in objects:
        obj.select_set(True)
    bpy.context.view_layer.objects.active = objects[0]
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.uv.smart_project(angle_limit=math.radians(66), island_margin=.016,
                             area_weight=0.0, correct_aspect=True, scale_to_bounds=True)
    bpy.ops.uv.pack_islands(rotate=True, margin=.009)
    bpy.ops.object.mode_set(mode='OBJECT')


def surface(x, y, z, nx, ny, nz, is_metal, grain):
    """Analytic surface shader, sampled at UV texel centres on the actual mesh.

    Grain, smudges, top-edge settled dust and brushed alloy survive GLB export;
    no runtime procedural node is needed. Base colours are sRGB texel values
    (the shared generated-image writer preserves them); ORM is linear data.
    """
    upward = max(0, nz) ** 5
    if is_metal:
        brush = .5 + .5 * math.sin(x * 7200 + math.sin(y * 155) * .5)
        dust = upward * (.016 + .016 * (1 + math.sin(x * 45 + y * 30)) / 2)
        if grain > .998 and upward > .5:
            dust += .045
        base = .580 + .002 * grain + .004 * brush + dust
        rough = .44 + .008 * grain + .10 * dust
        return (base, base * 1.025, base * 1.045), rough, .88, 1
    base = .075 + .0012 * grain
    rough = .73 + .015 * grain
    # Dust is localized on horizontal top edge and at the foot socket/pads.
    dust = upward * (.0045 + .0035 * (1 + math.sin(x * 66 + y * 170)) / 2)
    if z > .455:
        dust += .008 * max(0, (z - .455) / .005) * (.65 + .35 * math.sin(x * 71) ** 2)
    if grain > .998 and upward > .5:
        dust += .035
    front = max(0, ny) ** 8
    if .123 < z < .1345 and y > .030:
        rough = .31 + .006 * grain
    # Fingerprint whorls across the polished lower-right chin, about 20 x 10 mm.
    if front > .1 and y > .028 and x < -.215 and z < .153:
        smudge = 0.0
        for cx, cz, angle in ((-.244, .1300, -.18), (-.261, .1370, .31)):
            dx, dz = x - cx, z - cz
            ax = dx * math.cos(angle) - dz * math.sin(angle)
            az = dx * math.sin(angle) + dz * math.cos(angle)
            r = math.sqrt((ax / .012) ** 2 + (az / .0055) ** 2)
            if r < 1:
                envelope = (1 - r * r) ** 2
                ridges = .5 + .5 * math.sin(r * 62 + ax * 250)
                smudge += envelope * (.35 + .65 * ridges)
        rough -= .18 * smudge
        base += .006 * smudge
        # Two small handling scuffs; no false metal exposure on black ABS.
        for ax, az, bx, bz in ((-.236, .129, -.224, .131), (-.254, .132, -.249, .1326)):
            dx, dz = bx - ax, bz - az
            t = max(0, min(1, ((x - ax) * dx + (z - az) * dz) / (dx * dx + dz * dz)))
            distance = math.hypot(x - ax - t * dx, z - az - t * dz)
            scuff = math.exp(-(distance / .00035) ** 2) * math.sin(t * math.pi) ** 2
            base += .009 * scuff
            rough += .08 * scuff
    # Subtle rubbed edge tone and contact dirt, never bare-metal chips in ABS.
    occlusion = .97
    if z < .023 and abs(x) < .047 and abs(y + .036) < .027:
        base *= .77
        occlusion = .82
    color = (base + dust * .95, base * 1.05 + dust * .85, base * 1.14 + dust * .70)
    return color, rough + dust * 5, 0, occlusion


def bake_atlas(objects, cache):
    """CPU procedural-to-texture raster bake with eight-pixel island dilation.

    Interpolate world coordinates across exported triangles, evaluating the
    original surface shader. No external libraries, GPU, fonts or downloads.
    """
    color = array('f', [.011, .012, .013, 1]) * (SIZE * SIZE)
    orm = array('f', [1, .65, 0, 1]) * (SIZE * SIZE)
    normal = array('f', [.5, .5, 1, 1]) * (SIZE * SIZE)
    covered = bytearray(SIZE * SIZE)
    rng = random.Random(SEED)
    grain = array('f', (rng.uniform(-1, 1) for _ in range(SIZE * SIZE)))
    for obj in objects:
        uv = obj.data.uv_layers.active.data
        for face in obj.data.polygons:
            if len(face.vertices) != 3:
                raise RuntimeError('Bake expects explicitly triangulated geometry')
            uvs = [uv[i].uv * SIZE for i in face.loop_indices]
            a, b, c = uvs
            determinant = (b.y - c.y) * (a.x - c.x) + (c.x - b.x) * (a.y - c.y)
            if abs(determinant) < 1e-10:
                continue
            xyz = [obj.matrix_world @ obj.data.vertices[i].co for i in face.vertices]
            n = face.normal
            metal = obj.data.materials[face.material_index].name.endswith('_metal')
            lo_x = max(0, math.floor(min(p.x for p in uvs)))
            hi_x = min(SIZE - 1, math.ceil(max(p.x for p in uvs)))
            lo_y = max(0, math.floor(min(p.y for p in uvs)))
            hi_y = min(SIZE - 1, math.ceil(max(p.y for p in uvs)))
            for py in range(lo_y, hi_y + 1):
                for px in range(lo_x, hi_x + 1):
                    wa = ((b.y - c.y) * (px + .5 - c.x) + (c.x - b.x) * (py + .5 - c.y)) / determinant
                    wb = ((c.y - a.y) * (px + .5 - c.x) + (a.x - c.x) * (py + .5 - c.y)) / determinant
                    wc = 1 - wa - wb
                    if min(wa, wb, wc) < -1e-7:
                        continue
                    slot = py * SIZE + px
                    p = xyz[0] * wa + xyz[1] * wb + xyz[2] * wc
                    col, rough, metallic, ao = surface(*p, *n, metal, grain[slot])
                    index = slot * 4
                    color[index:index + 4] = array('f', (*col, 1))
                    orm[index:index + 4] = array('f', (ao, min(.95, max(.18, rough)), metallic, 1))
                    # Normal perturbation: injection-mould grain or fine alloy brush.
                    g = grain[slot]
                    gx = grain[py * SIZE + max(0, px - 1)] - g
                    gy = grain[max(0, py - 1) * SIZE + px] - g
                    strength = .006 if metal else .012
                    vx, vy = gx * strength, gy * strength
                    vz = math.sqrt(max(0, 1 - vx * vx - vy * vy))
                    normal[index:index + 4] = array('f', (.5 + vx / 2, .5 + vy / 2, .5 + vz / 2, 1))
                    covered[slot] = 1
    # Eight synchronous rings: true margin without overwriting another island.
    frontier = [i for i, mark in enumerate(covered) if mark]
    for _ in range(8):
        next_ring = []
        for slot in frontier:
            px, py = slot % SIZE, slot // SIZE
            for neighbor in ((slot - 1 if px else -1), (slot + 1 if px < SIZE - 1 else -1),
                             (slot - SIZE if py else -1), (slot + SIZE if py < SIZE - 1 else -1)):
                if neighbor >= 0 and not covered[neighbor]:
                    covered[neighbor] = 2
                    next_ring.append((neighbor, slot))
        frontier = []
        for neighbor, source in next_ring:
            for buf in (color, orm, normal):
                buf[neighbor * 4:neighbor * 4 + 4] = buf[source * 4:source * 4 + 4]
            covered[neighbor] = 1
            frontier.append(neighbor)
    return {
        'surface_base_color': image_from_pixels(ASSET_ID, 'surface_base_color', SIZE, color, cache),
        'surface_orm': image_from_pixels(ASSET_ID, 'surface_orm', SIZE, orm, cache, non_color=True),
        'surface_normal': image_from_pixels(ASSET_ID, 'surface_normal', SIZE, normal, cache, non_color=True),
    }


def build(out_dir):
    reset_scene(SEED)
    plastic = material(ASSET_ID, 'plastic', (.012, .013, .015), roughness=.64)
    plastic.node_tree.nodes['Principled BSDF'].inputs['Specular IOR Level'].default_value = .32
    metal = material(ASSET_ID, 'metal', (.20, .21, .22), metallic=.88, roughness=.38)
    screen_mat = material(ASSET_ID, 'screen', (.0025, .0035, .0045), roughness=.20,
                          emission=((.0018, .0030, .0040), .35))
    led_mat = material(ASSET_ID, 'led', (1, 1, 1), roughness=.24,
                       emission=((1, 1, 1), .8))
    objects = make_geometry(plastic, metal, screen_mat, led_mat)
    unwrap(objects[:2])
    for obj in objects:
        triangulate(obj)
    bpy.context.view_layer.update()
    images = bake_atlas(objects[:2], ROOT / 'assets/cache' / ASSET_ID)
    for mat in (plastic, metal):
        base_texture(mat, images['surface_base_color'])
        orm_texture(mat, images['surface_orm'])
        normal_texture(mat, images['surface_normal'], strength=1)
    glb_path = Path(out_dir).resolve() / f'{ASSET_ID}.glb'
    gltf = export_glb(glb_path, objects)
    for node in gltf['nodes']:
        if node.get('scale', [1, 1, 1]) != [1, 1, 1] or node.get('rotation', [0, 0, 0, 1]) != [0, 0, 0, 1]:
            raise RuntimeError(f'Unapplied transform on {node["name"]}')
        if node['name'] == 'screen':
            expected = [SCREEN_CENTRE[0], SCREEN_CENTRE[2], -SCREEN_CENTRE[1]]
            if any(abs(a - b) > 1e-7 for a, b in zip(node.get('translation', [0, 0, 0]), expected)):
                raise RuntimeError('Screen origin is not at display centre')
    textures = [{'name': image.name, 'size': list(image.size), 'map': name, 'embedded': True}
                for name, image in sorted(images.items())]
    meta = write_metadata(ASSET_ID, ROOT / 'assets/meta' / f'{ASSET_ID}.json', glb_path,
                          objects, Path(__file__), textures, origin='base_center', extra={
        'forward': 'Blender +Y -> Godot -Z',
        'anchors_godot_m': {'screen_centre': [0, .292, -.0297],
                           'bezel_front_z': -.031275,
                           'bezel_bottom_right': [-.270, .1315, -.031275]},
        'anchor_notes': 'Visual right viewed from Godot -Z is -X. Anchor is on lower-right bezel for an external sticky note.',
        'screen_size_m': [.531, .299],
        'panel_size_m': [.560, .045, .340],
        'screen_uv': {'min': [0, 0], 'max': [1, 1], 'visual_right': 'u=1'},
        'collision': None,
        'texture_bake': {'method': 'CPU analytic surface raster bake', 'margin_px': 8,
                         'atlas': 'non-overlapping plastic and metal islands', 'seed': SEED},
        'render': {'engine': 'CYCLES', 'device': 'CPU', 'samples': 32, 'denoise': True, 'threads': 4},
        'glb_path': str(glb_path.relative_to(ROOT)) if glb_path.is_relative_to(ROOT) else str(glb_path),
    })
    if meta['triangles'] > 20000 or len(meta['materials']) > 4:
        raise RuntimeError('Request budget exceeded')
    if set(meta['parts']) != {'panel', 'stand', 'screen', 'led_power'}:
        raise RuntimeError(f'Wrong mesh names: {meta["parts"]}')
    if abs(meta['bounds_godot_m']['min'][1]) > 1e-7:
        raise RuntimeError('Foot underside must be y=0')
    render_previews(ASSET_ID, ROOT / 'assets/previews', objects, views={
        'front': {'position': (0, 1.6, .240), 'target': (0, 0, .240), 'scale': .67},
        'iso': {'position': (.90, 1.45, .86), 'target': (0, 0, .230), 'scale': .71},
        'detail': {'position': (-.45, .78, .38), 'target': (-.211, .029, .145), 'scale': .170},
    }, seed=SEED)
    print(f'ASSET BUILT: {glb_path}; {meta["triangles"]} triangles; {len(meta["materials"])} materials')
    return glb_path


if __name__ == '__main__':
    run_cli(build, __doc__)
