"""Deterministic office whiteboard: build(out_dir), no downloads or dependencies.

Blender +Y is the writing-face normal, exported as Godot -Z. All three
mesh origins are the back mounting-face centre. Original analytic PBR maps
are rasterised directly; the only full 0..1 UV plane is `surface`.
"""
from array import array
import hashlib
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
from common.materials import base_texture, material, normal_texture, orm_texture
from common.preview import render_previews
from common.scene import reset_scene

ASSET_ID = 'whiteboard_wall'
SEED = 62047
SURFACE_W, SURFACE_H, SURFACE_Y = 1.564, .964, .022


def image_map(name, width, height, pixels, cache, data=False):
    """Rectangular counterpart to keypad_4's shared square-image helper."""
    if len(pixels) != width * height * 4:
        raise ValueError(name)
    image = bpy.data.images.new(f'T_{ASSET_ID}_{name}', width=width, height=height, alpha=True)
    image.colorspace_settings.name = 'Non-Color' if data else 'sRGB'
    image.pixels.foreach_set(pixels)
    image.file_format = 'PNG'
    image.filepath_raw = str(cache / f'{image.name}.png')
    image.save()
    image.pack()
    return image


def stroke_mask(mask, width, height, path, radius, strength):
    """Antialiased faded marker strokes in board-centred metres."""
    for (ax, ay), (bx, by) in zip(path, path[1:]):
        # Front-view texture coordinates: +X is screen-left from Blender +Y.
        ax, bx = (.5 - ax / SURFACE_W) * width, (.5 - bx / SURFACE_W) * width
        ay, by = (.5 + ay / SURFACE_H) * height, (.5 + by / SURFACE_H) * height
        r = radius * width / SURFACE_W
        dx, dy = bx - ax, by - ay
        for y in range(max(0, int(min(ay, by) - r - 2)), min(height, int(max(ay, by) + r + 3))):
            for x in range(max(0, int(min(ax, bx) - r - 2)), min(width, int(max(ax, bx) + r + 3))):
                t = max(0, min(1, ((x - ax) * dx + (y - ay) * dy) / max(dx * dx + dy * dy, 1e-10)))
                dist = math.hypot(x - ax - t * dx, y - ay - t * dy)
                a = max(0, min(1, r + .65 - dist)) * strength
                index = y * width + x
                mask[index] = max(mask[index], a)


def make_textures(cache):
    cache.mkdir(parents=True, exist_ok=True)
    rng = random.Random(SEED)
    width, height = 2048, 1024
    ghost = array('f', [0]) * (width * height)
    # No actual words, digits, or puzzle data. All old diagram traces are outside
    # the protected rectangle x[-.65,.65], y[-.35,.30].
    paths = [([(-.59, .352), (-.59, .421), (-.34, .421), (-.34, .352), (-.59, .352)], .003, .024),
             ([(-.27, .383), (.07, .383), (.047, .397)], .002, .030),
             ([(.047, .368), (.07, .383)], .002, .030),
             ([(.14, .353), (.14, .419), (.38, .419), (.38, .353), (.14, .353)], .0025, .021),
             ([(.703, .18), (.703, .05), (.686, .075)], .002, .025),
             ([(.719, .075), (.703, .05)], .002, .025),
             ([(.68, -.06), (.739, -.06), (.739, -.19), (.68, -.19), (.68, -.06)], .002, .018)]
    for path, radius, strength in paths:
        stroke_mask(ghost, width, height, path, radius, strength)
    base, orm, normal = array('f'), array('f'), array('f')
    max_dark, protected_dark = 0, 0
    for y in range(height):
        z = (y / (height - 1) - .5) * SURFACE_H
        for x in range(width):
            xx = (.5 - x / (width - 1)) * SURFACE_W
            protected = -.65 <= xx <= .65 and -.35 <= z <= .30
            fine = rng.uniform(-.0014, .0014)
            # Barely visible hand-wipe band under the writing region.
            wipe = .017 * math.exp(-((z + .411) / .027) ** 2) * (.70 + .30 * math.sin(xx * 17 + .8) ** 2)
            edge_dist = min(SURFACE_W / 2 - abs(xx), SURFACE_H / 2 - abs(z))
            corner = .014 * math.exp(-max(0, edge_dist) / .004) * (abs(xx) / .782) ** 12
            fade = 0 if protected else min(.048, ghost[y * width + x] + wipe + corner)
            max_dark = max(max_dark, fade)
            protected_dark = max(protected_dark, fade if protected else 0)
            color = .82 * (1 - fade) + fine
            base.extend((color, color * 1.006, color * .995, 1))
            rough = .255 + fade * 1.6 + fine * 3 + .008 * math.sin(x * .009 + y * .004)
            orm.extend((1, rough, 0, 1))
            normal.extend((.5 + rng.uniform(-.009, .009), .5 + rng.uniform(-.009, .009), 1, 1))
    assert max_dark < .06 and protected_dark == 0
    images = {}
    for name, pixels, data in [('surface_base_color', base, False), ('surface_orm', orm, True), ('surface_normal', normal, True)]:
        images[name] = image_map(name, width, height, pixels, cache, data)
    # Original aluminium maps: submillimetre lengthwise brushing, very sparse
    # fine scratches, and a slightly dirtier side of each extrusion strip.
    size = 1024
    base, orm, normal = array('f'), array('f'), array('f')
    streaks = [rng.uniform(-.028, .028) for _ in range(size)]
    for y in range(size):
        brush = streaks[y]
        for x in range(size):
            grain = rng.uniform(-.007, .007)
            scratch = .037 if (y % 193 == 43 and .17 < x / size < .59) else 0
            c = .48 + brush + grain + scratch
            base.extend((c * .985, c, c * 1.02, 1))
            orm.extend((1, .34 + brush * 1.1 - scratch, .86, 1))
            normal.extend((.5 + grain * .12, .5 + brush * .5, 1, 1))
    for name, pixels, data in [('frame_base_color', base, False), ('frame_orm', orm, True), ('frame_normal', normal, True)]:
        images[name] = image_map(name, size, size, pixels, cache, data)
    # Five vertical swatch regions: corner polymer, felt, black cap, blue cap,
    # warm ivory marker barrel. Untextured writing is intentionally absent.
    swatches = [(.20, .215, .225), (.028, .032, .036), (.015, .018, .024), (.018, .055, .25), (.72, .73, .71)]
    base, orm, normal = array('f'), array('f'), array('f')
    for y in range(size):
        for x in range(size):
            tile = min(4, x * 5 // size)
            grain = rng.uniform(-1, 1)
            fiber = tile == 1
            amount = .004 if not fiber else .007
            scuff = .009 * math.sin(y * .22) ** 12 * math.sin(x * .037) ** 10 if tile in (2, 3, 4) else 0
            base.extend((*[max(.001, c + grain * amount + scuff) for c in swatches[tile]], 1))
            rough = [.60, .95, .39, .40, .46][tile] + grain * (.075 if fiber else .018)
            orm.extend((1, rough, 0, 1))
            amplitude = .10 if fiber else .02
            normal.extend((.5 + grain * amplitude, .5 + rng.uniform(-amplitude, amplitude), 1, 1))
    for name, pixels, data in [('accessories_base_color', base, False), ('accessories_orm', orm, True), ('accessories_normal', normal, True)]:
        images[name] = image_map(name, size, size, pixels, cache, data)
    return images


def mapped_material(part, maps, images, normal_strength):
    mat = material(ASSET_ID, part, (.8, .8, .8))
    base_texture(mat, images[f'{maps}_base_color'])
    orm_texture(mat, images[f'{maps}_orm'])
    normal_texture(mat, images[f'{maps}_normal'], normal_strength)
    return mat


def box_uv(obj, rect):
    """Six distinct projection islands, plus reserved bevel-face islands."""
    uv = obj.data.uv_layers.new(name='UVMap')
    count = len(obj.data.polygons)
    cols = math.ceil(math.sqrt(count))
    rows = math.ceil(count / cols)
    for i, face in enumerate(obj.data.polygons):
        dominant = max(range(3), key=lambda axis: abs(face.normal[axis]))
        axes = [axis for axis in range(3) if axis != dominant]
        coords = [obj.data.vertices[index].co for index in face.vertices]
        bounds = [(min(v[a] for v in coords), max(v[a] for v in coords)) for a in axes]
        lo_u = rect[0] + (i % cols + .08) / cols * (rect[2] - rect[0])
        lo_v = rect[1] + (i // cols + .08) / rows * (rect[3] - rect[1])
        for loop in face.loop_indices:
            vertex = obj.data.vertices[obj.data.loops[loop].vertex_index].co
            u, v = [(vertex[a] - lo) / max(hi - lo, 1e-9) for a, (lo, hi) in zip(axes, bounds)]
            uv.data[loop].uv = (lo_u + u * .84 / cols * (rect[2] - rect[0]), lo_v + v * .84 / rows * (rect[3] - rect[1]))


def rounded(name, dims, mat, loc, rect, radius=.001, segments=3):
    obj = box(name, dims, mat, loc, bevel=radius, segments=segments)
    box_uv(obj, rect)
    return obj


def extrusion(name, length, profile, mat, rect, loc, vertical=False):
    """Closed physical aluminium extrusion, individually unwrapped profile faces."""
    verts = []
    for along in (-length / 2, length / 2):
        for q, depth in profile:
            verts.append((q, depth, along) if vertical else (along, depth, q))
    n = len(profile)
    faces = [tuple(reversed(range(n))), tuple(range(n, 2 * n))]
    faces += [(i, (i + 1) % n, (i + 1) % n + n, i + n) for i in range(n)]
    obj = mesh_object(name, verts, faces, mat, loc)
    uv = obj.data.uv_layers.new(name='UVMap')
    # Profile faces each occupy a separate padded band; end caps reserved at top.
    for index, face in enumerate(obj.data.polygons):
        if index < 2:
            qmin, qmax = min(p[0] for p in profile), max(p[0] for p in profile)
            dmin, dmax = min(p[1] for p in profile), max(p[1] for p in profile)
            for loop in face.loop_indices:
                v = obj.data.vertices[obj.data.loops[loop].vertex_index].co
                q = v.x if vertical else v.z
                uv.data[loop].uv = (rect[0] + (.03 + (q - qmin) / (qmax - qmin) * .42 + index * .5) * (rect[2] - rect[0]), rect[1] + (.92 + (v.y - dmin) / max(dmax - dmin, 1e-9) * .065) * (rect[3] - rect[1]))
        else:
            band = (index - 2) / n * .88
            for j, loop in enumerate(face.loop_indices):
                along = 0 if j < 2 else 1
                across = 0 if j in (0, 3) else 1
                uv.data[loop].uv = (rect[0] + (.015 + along * .97) * (rect[2] - rect[0]), rect[1] + (band + (.08 + across * .84) / n * .88) * (rect[3] - rect[1]))
    active(obj)
    bevel = obj.modifiers.new('machined_edge_radius', 'BEVEL')
    bevel.width = .00025
    bevel.segments = 3
    bpy.ops.object.modifier_apply(modifier=bevel.name)
    for face in obj.data.polygons:
        face.use_smooth = max(abs(v) for v in face.normal) < .999
    normal = obj.modifiers.new('weighted_normals', 'WEIGHTED_NORMAL')
    normal.keep_sharp = True
    bpy.ops.object.modifier_apply(modifier=normal.name)
    return obj


def lathe(name, profile, mat, rect, location, axis, sides=40):
    """Closed capped rotational moulding with real cap ribs and stepped ends."""
    verts = []
    for distance, radius in profile:
        for i in range(sides):
            angle = i * math.tau / sides
            verts.append((distance, radius * math.cos(angle), radius * math.sin(angle)))
    faces = [tuple(reversed(range(sides))), tuple(range((len(profile) - 1) * sides, len(profile) * sides))]
    for r in range(len(profile) - 1):
        for i in range(sides):
            j = (i + 1) % sides
            faces.append((r * sides + i, r * sides + j, (r + 1) * sides + j, (r + 1) * sides + i))
    obj = mesh_object(name, verts, faces, mat, location)
    uv = obj.data.uv_layers.new(name='UVMap')
    length = profile[-1][0] - profile[0][0]
    for index, face in enumerate(obj.data.polygons):
        face.use_smooth = index >= 2
        for loop in face.loop_indices:
            vi = obj.data.loops[loop].vertex_index
            ring, around = divmod(vi, sides)
            if index < 2:
                co = obj.data.vertices[vi].co
                radius = max(p[1] for p in profile)
                u, v = .025 + index * .49 + (.5 + co.y / (2 * radius)) * .44, .89 + (.5 + co.z / (2 * radius)) * .09
            else:
                face_i = (index - 2) % sides
                # Correct duplicated UV seam while retaining shared geometric vertices.
                u = (profile[ring][0] - profile[0][0]) / length * .96 + .02
                v = (around if around else sides if face_i == sides - 1 else 0) / sides * .84 + .02
            uv.data[loop].uv = (rect[0] + u * (rect[2] - rect[0]), rect[1] + v * (rect[3] - rect[1]))
    rotation = Vector((1, 0, 0)).rotation_difference(Vector(axis).normalized())
    for vertex in obj.data.vertices:
        vertex.co = rotation @ vertex.co
    return obj


def build(out_dir):
    reset_scene(SEED)
    cache = ROOT / 'assets/cache' / ASSET_ID
    images = make_textures(cache)
    surface_mat = mapped_material('surface', 'surface', images, .20)
    frame_mat = mapped_material('frame', 'frame', images, .45)
    plastic_mat = mapped_material('plastic', 'accessories', images, .40)
    marker_mat = mapped_material('markers', 'accessories', images, .45)
    # Rectangle is a single coplanar UV island, no bevel or frame pixels.
    surface = mesh_object('surface', [(-.782, SURFACE_Y, -.482), (-.782, SURFACE_Y, .482), (.782, SURFACE_Y, .482), (.782, SURFACE_Y, -.482)], [(0, 1, 2, 3)], surface_mat)
    uv = surface.data.uv_layers.new(name='UVMap')
    for loop, coordinate in zip(uv.data, [(1, 0), (1, 1), (0, 1), (0, 0)]):
        loop.uv = coordinate
    parts = []
    # Rigid backing ends at mounting plane y=0; frame lies in y[0,.025].
    parts.append(rounded('backing', (1.575, .020, .975), plastic_mat, (0, .010, 0), (.02, .02, .18, .29), .001))
    rail_profile = [(-.009, 0), (.009, 0), (.009, .021), (.0078, .024), (.0068, .025), (-.0068, .025), (-.009, .023), (-.009, .020), (-.0065, .019), (-.0065, .006), (-.009, .006)]
    for i, (z, reverse) in enumerate([(.491, False), (-.491, True)]):
        profile = [(-q if reverse else q, d) for q, d in rail_profile]
        parts.append(extrusion(f'rail_h_{i}', 1.532, profile, frame_mat, (.01, .01 + i * .19, .99, .18 + i * .19), (0, 0, z)))
    for i, x in enumerate([-.791, .791]):
        parts.append(extrusion(f'rail_v_{i}', .932, rail_profile, frame_mat, (.01, .39 + i * .19, .99, .56 + i * .19), (x, 0, 0), True))
    # Injection-moulded corner caps with a fine inset tooling line.
    for i, (x, z) in enumerate([(-.783, -.483), (.783, -.483), (-.783, .483), (.783, .483)]):
        parts.append(rounded(f'corner_{i}', (.034, .025, .034), plastic_mat, (x, .0125, z), (.015, .32 + i * .155, .185, .45 + i * .155), .004, 5))
        parts.append(rounded(f'corner_insert_{i}', (.024, .0012, .024), plastic_mat, (x, .0244, z), (.02, .951, .18, .99), .003, 4))
    frame = join_static(parts, 'frame')
    # Open channel: sloped cradle, curled front return 12 mm above floor.
    # Top front of channel is exactly 60 mm forward of writing plane.
    tray_profile = [(.014, -.500), (.014, -.485), (.019, -.485), (.022, -.491), (.024, -.495), (.076, -.495), (.079, -.492), (.079, -.483), (.082, -.483), (.082, -.495), (.079, -.498), (.024, -.498)]
    # extrusion expects (height,depth) rather than (depth,height).
    tray_parts = [extrusion('tray_channel', 1.568, [(z, y) for y, z in tray_profile], frame_mat, (.01, .79, .99, .985), (0, 0, 0))]
    # Grey protective end caps keep small items from rolling off.
    for i, x in enumerate([-.792, .792]):
        tray_parts.append(rounded(f'tray_end_{i}', (.016, .068, .018), plastic_mat, (x, .048, -.491), (.02, .04, .18, .26), .003, 4))
    # Two capped dry-wipe markers, 143 mm long, ~15 mm in diameter.
    for i, (x, y, angle, tile) in enumerate([(-.24, .038, -.09, 2), (-.045, .057, .065, 3)]):
        axis = (math.cos(angle), math.sin(angle), 0)
        origin = Vector((x, y, -.487))
        barrel_rect = (.805, .03 + i * .46, .992, .43 + i * .46)
        tray_parts.append(lathe(f'marker_barrel_{i}', [(0, .0062), (.002, .007), (.093, .007), (.098, .0063)], marker_mat, barrel_rect, origin, axis))
        cap_origin = origin + Vector(axis) * .096
        cap_profile = [(0, .0074), (.002, .0078), (.005, .0078)]
        for j in range(5):
            t = .007 + j * .0015
            cap_profile.extend([(t, .0078), (t + .00045, .00805), (t + .0009, .0078)])
        cap_profile += [(.041, .0077), (.044, .0072), (.046, .0058)]
        rect = (tile / 5 + .008, .03 + i * .47, (tile + 1) / 5 - .008, .45 + i * .47)
        tray_parts.append(lathe(f'marker_cap_{i}', cap_profile, marker_mat, rect, cap_origin, axis))
        tray_parts.append(lathe(f'marker_plug_{i}', [(0, .005), (.0012, .0062), (.003, .0062)], marker_mat, rect, origin - Vector(axis) * .002, axis, 32))
        clip = rounded(f'marker_clip_{i}', (.033, .003, .0035), marker_mat, cap_origin + Vector(axis) * .023 + Vector((0, 0, .0084)), rect, .0012, 3)
        rotation = Vector((1, 0, 0)).rotation_difference(Vector(axis))
        for vertex in clip.data.vertices:
            vertex.co = rotation @ vertex.co
        tray_parts.append(clip)
    # Eraser: visible porous felt below a rounded charcoal moulded hand grip.
    tray_parts.append(rounded('eraser_felt', (.118, .039, .007), plastic_mat, (.27, .053, -.491), (.21, .03, .389, .44), .0015, 3))
    tray_parts.append(rounded('eraser_grip', (.122, .042, .018), plastic_mat, (.27, .053, -.479), (.408, .50, .589, .89), .004, 5))
    for i in range(4):
        tray_parts.append(rounded(f'eraser_grip_rib_{i}', (.090, .002, .0013), plastic_mat, (.27, .043 + i * .006, -.4696), (.409, .91, .589, .99), .0006, 3))
    tray = join_static(tray_parts, 'tray')
    objects = [frame, surface, tray]
    for obj in objects:
        triangulate(obj)
        assert obj.location.length < 1e-8 and all(abs(s - 1) < 1e-8 for s in obj.scale)
    bpy.context.view_layer.update()
    # Surface normals are explicit and must still face the player after triangulation.
    assert all(p.normal.y > .999 for p in surface.data.polygons)
    glb_path = Path(out_dir).resolve() / f'{ASSET_ID}.glb'
    gltf = export_glb(glb_path, objects)
    for node in gltf['nodes']:
        assert node.get('translation', [0, 0, 0]) == [0, 0, 0]
        assert node.get('scale', [1, 1, 1]) == [1, 1, 1]
        assert node.get('rotation', [0, 0, 0, 1]) == [0, 0, 0, 1]
    textures = [{'name': image.name, 'size': list(image.size), 'map': name, 'embedded': True} for name, image in sorted(images.items())]
    meta = write_metadata(ASSET_ID, ROOT / 'assets/meta' / f'{ASSET_ID}.json', glb_path, objects, Path(__file__), textures, 'mount_plane_center', extra={
        'forward': 'Blender +Y -> Godot -Z',
        'anchors_godot_m': {'surface_front_z': -SURFACE_Y, 'surface_size': [SURFACE_W, SURFACE_H]},
        'board_outer_m': [1.60, .025, 1.00],
        'collision': None,
        'ghosting': {'max_darkening_fraction': .048, 'protected_rect_godot_xy_m': [-.65, -.35, .65, .30], 'protected_rect_ghosting': 0},
        'render': {'engine': 'CYCLES', 'device': 'CPU', 'samples': 32, 'denoise': True, 'threads': 4},
        'glb_path': str(glb_path.relative_to(ROOT)) if glb_path.is_relative_to(ROOT) else str(glb_path),
        'texture_method': 'original_seeded_analytic_raster_maps; no external sources',
    })
    assert meta['triangles'] <= 20000 and len(meta['materials']) == 4
    assert set(meta['parts']) == {'frame', 'surface', 'tray'} and not meta['animations']
    render_previews(ASSET_ID, ROOT / 'assets/previews', objects, views={
        'front': {'position': (0, 3, 0), 'target': (0, .02, 0), 'scale': 1.88},
        'iso': {'position': (2.10, 3.30, 1.40), 'target': (0, .025, 0), 'scale': 1.93},
        'detail': {'position': (.82, 1.30, .28), 'target': (.04, .047, -.468), 'scale': .88},
    }, seed=SEED)
    print(f'ASSET BUILT: {glb_path}; {meta["triangles"]} triangles; {len(meta["materials"])} materials')
    return glb_path


if __name__ == '__main__':
    run_cli(build, __doc__)
