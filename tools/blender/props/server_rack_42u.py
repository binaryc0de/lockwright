"""Populated open-front 42U rack; original geometry and CPU-baked worn PBR.

Deterministic Blender 5.2 source, no downloads. Structural baking/export pattern
from the accepted exit_door_maglock and exit_keypad_6 scripts. All design
coordinates below are Godot metres; Blender +Y exports toward Godot -Z.
"""
from array import array
import json
import math
from pathlib import Path
import random
import struct
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

ASSET_ID = 'server_rack_42u'
SEED = 420062
U = .04445
PATCH = (1.25 - U, 1.25 + U)
STENCIL = (1.72 - 1.5 * U, 1.72 + 1.5 * U)
ANCHORS = {'patch_slot_centre': [0, 1.25, -.47],
           'stencil_plate_centre': [0, 1.72, -.474], 'rail_front_z': -.47}


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



def bake_surface(part, surf, components, cache):
    """Unwrap one material globally, bake four passes, transfer exact UV loops.

    The temporary mesh uses world coordinates, so grain/wear are continuous.
    Islands never overlap; packing and baking both reserve an 8 pixel margin.
    Only the AO pass uses rays. Base colour / packed RM are emission bakes;
    normals are Cycles tangent NORMAL bakes of the procedural microstructure.
    """
    size = 2048 if part in ('cabinet', 'equipment', 'metal') else 1024
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



def surfaces():
    cabinet = Surface('cabinet', (.007, .009, .011), .70)
    grain = cabinet.noise((1050, 1050, 1050))
    broad = cabinet.noise((17, 14, 11), detail=3)
    color = cabinet.mix(broad, (.0045, .006, .008, 1), (.008, .010, .013, 1))
    x = cabinet.math('ABSOLUTE', cabinet.axes.outputs['X'])
    z = cabinet.axes.outputs['Z']
    depth = cabinet.math('ABSOLUTE', cabinet.axes.outputs['Y'])
    side_edge = cabinet.math('MULTIPLY', cabinet.math('GREATER_THAN', x, .288),
                             cabinet.math('GREATER_THAN', depth, .440))
    foot_edge = cabinet.math('MULTIPLY', cabinet.math('LESS_THAN', z, .105),
                             cabinet.math('GREATER_THAN', depth, .478))
    edges = cabinet.math('MAXIMUM', side_edge, foot_edge)
    chip = cabinet.math('MULTIPLY', edges,
                        cabinet.math('GREATER_THAN', cabinet.noise((250, 320, 270)), .66))
    color = cabinet.mix(chip, color, (.22, .24, .25, 1))
    # Dust is deposited on upward surfaces and in the upper cabinet corners.
    normal = cabinet.node('ShaderNodeSeparateXYZ', Vector=cabinet.node('ShaderNodeNewGeometry').outputs['Normal'])
    top = cabinet.math('MULTIPLY', cabinet.math('GREATER_THAN', z, 1.98),
                       cabinet.math('GREATER_THAN', normal.outputs['Z'], .5))
    dust = cabinet.math('MULTIPLY', top, cabinet.noise((45, 45, 45)))
    color = cabinet.mix(cabinet.math('MULTIPLY', dust, .18), color, (.09, .083, .075, 1))
    cabinet.metallic = cabinet.math('MULTIPLY', chip, .85)
    cabinet.set(cabinet.bsdf.inputs['Metallic'], cabinet.metallic)
    rough = cabinet.math('ADD', .62, cabinet.math('MULTIPLY', grain, .16))
    rough = cabinet.math('ADD', rough, cabinet.math('MULTIPLY', dust, .17))
    height = cabinet.math('SUBTRACT', grain, cabinet.math('MULTIPLY', chip, .7))
    cabinet.finish(color, rough, height, .27, .00010)

    equipment = Surface('equipment', (.015, .020, .025), .55, .15)
    grain = equipment.noise((1350, 1350, 1350))
    broad = equipment.noise((37, 12, 28))
    color = equipment.mix(broad, (.008, .012, .017, 1), (.016, .022, .028, 1))
    rub = equipment.math('GREATER_THAN', equipment.noise((8, 35, 450)), .70)
    front = equipment.math('GREATER_THAN', equipment.axes.outputs['Y'], .464)
    rub = equipment.math('MULTIPLY', rub, front)
    color = equipment.mix(equipment.math('MULTIPLY', rub, .32), color, (.045, .055, .065, 1))
    rough = equipment.math('SUBTRACT', equipment.math('ADD', .48, equipment.math('MULTIPLY', grain, .15)),
                           equipment.math('MULTIPLY', rub, .15))
    equipment.finish(color, rough, grain, .19, .000065)

    metal = Surface('metal', (.37, .39, .41), .35, 1)
    brush = metal.noise((14, 3000, 2400))
    color = metal.mix(brush, (.28, .30, .33, 1), (.46, .48, .50, 1))
    mark = metal.math('GREATER_THAN', metal.noise((9, 150, 1900)), .72)
    color = metal.mix(metal.math('MULTIPLY', mark, .28), color, (.17, .19, .21, 1))
    metal.finish(color, metal.math('ADD', .27, metal.math('MULTIPLY', brush, .21)), brush, .24, .00003)

    cables = Surface('cables', (.009, .014, .017), .69)
    grain = cables.noise((2500, 2500, 2500))
    variation = cables.noise((11, 14, 16))
    cables.finish(cables.mix(variation, (.006, .011, .014, 1), (.014, .021, .025, 1)),
                  cables.math('ADD', .60, cables.math('MULTIPLY', grain, .18)), grain, .16, .000045)
    return {'cabinet': cabinet, 'equipment': equipment, 'metal': metal, 'cables': cables}


def aperture_cells(name, cells, plane_z, thickness, mat):
    """Real open rectangular perforations, with folded inward aperture walls.

    Cells are (x,y,width,height,hole_width,hole_height) in Godot axes.
    Outer edges meet exactly; each hole gets four flat lands and four inner
    walls. No opaque texture impostor and no intersecting grid bar faces.
    """
    verts, faces = [], []
    for cell in cells:
        x, y, w, h, hw, hh = cell[:6]
        hole_y = cell[6] if len(cell) == 7 else y
        outer = [(x-w/2, y-h/2), (x+w/2, y-h/2),
                 (x+w/2, y+h/2), (x-w/2, y+h/2)]
        inner = [(x-hw/2, hole_y-hh/2), (x+hw/2, hole_y-hh/2),
                 (x+hw/2, hole_y+hh/2), (x-hw/2, hole_y+hh/2)]
        base = len(verts)
        verts += [godot((xx, yy, plane_z)) for xx, yy in outer+inner]
        verts += [godot((xx, yy, plane_z+thickness)) for xx, yy in inner]
        for i in range(4):
            j = (i+1) % 4
            faces += [(base+i, base+j, base+4+j, base+4+i),
                      (base+4+i, base+4+j, base+8+j, base+8+i)]
    return mesh_object(name, verts, faces, mat)


def tube(name, points, radius, mat, sides=8):
    """Continuous smooth cable swept along a deterministic polyline."""
    points = [Vector(godot(p)) for p in points]
    verts, faces = [], []
    for k, p in enumerate(points):
        tangent = points[min(k+1, len(points)-1)] - points[max(0, k-1)]
        tangent.normalize()
        u = tangent.cross(Vector((0, 0, 1)))
        if u.length < .01:
            u = tangent.cross(Vector((0, 1, 0)))
        u.normalize()
        v = tangent.cross(u).normalized()
        verts += [tuple(p + radius*(u*math.cos(i*math.tau/sides) + v*math.sin(i*math.tau/sides))) for i in range(sides)]
        if k:
            for i in range(sides):
                j = (i+1) % sides
                faces.append(((k-1)*sides+i, (k-1)*sides+j, k*sides+j, k*sides+i))
    faces += [tuple(reversed(range(sides))), tuple(range((len(points)-1)*sides, len(points)*sides))]
    obj = mesh_object(name, verts, faces, mat)
    for poly in obj.data.polygons:
        poly.use_smooth = len(poly.vertices) == 4
    return obj


def screw(name, x, y, plane_z, mat):
    """Chamfered screw head with an actual recessed hex driver socket."""
    rings = [(.0034, plane_z+.0008), (.0040, plane_z),
             (.0036, plane_z-.0008), (.0015, plane_z-.0008),
             (.0015, plane_z+.0004)]
    count = 8
    verts = [godot((x+r*math.cos(i*math.tau/count), y+r*math.sin(i*math.tau/count), z))
             for r, z in rings for i in range(count)]
    faces = []
    for k in range(len(rings)-1):
        for i in range(count):
            j = (i+1) % count
            faces.append((k*count+i, k*count+j, (k+1)*count+j, (k+1)*count+i))
    faces.append(tuple(range((len(rings)-1)*count, len(rings)*count)))
    return mesh_object(name, verts, faces, mat)


def geometry(mats):
    parts, lenses, solid_boxes = [], [], []
    def slab(name, dims, pos, finish='equipment', radius=.0006, segments=1):
        obj = box(name, (dims[0], dims[2], dims[1]), mats[finish].mat,
                  godot(pos), bevel=radius, segments=segments)
        parts.append(obj)
        solid_boxes.append((name, [pos[i]-dims[i]/2 for i in range(3)],
                            [pos[i]+dims[i]/2 for i in range(3)]))
        return obj
    def bolt(x, y, z=-.472):
        parts.append(screw('recessed_mount_screw', x, y, z, mats['metal'].mat))
    def grille(x, y, w, h, cols, rows, z=-.470, finish='equipment'):
        cells = [(x-w/2+(i+.5)*w/cols, y-h/2+(j+.5)*h/rows,
                  w/cols, h/rows, w/cols*.64, h/rows*.51)
                 for j in range(rows) for i in range(cols)]
        parts.append(aperture_cells('punched_vent', cells, z, .0012, mats[finish].mat))
    led_mat = material(ASSET_ID, 'led', (1, 1, 1), roughness=.27,
                       emission=((1, 1, 1), .7))
    # glTF COLOR_0 does not tint emission. An original two-colour lens palette
    # is therefore linked directly to both albedo and emission; all LEDs still
    # share one material and can have their emission strength blinked together.
    pixels = array('f')
    for yy in range(64):
        for xx in range(64):
            pixels.extend((.012, .62, .065, 1) if xx < 32 else (1, .30, .008, 1))
    palette = image_from_pixels(ASSET_ID, 'led_palette', 64, pixels,
                                ROOT / 'assets/cache' / ASSET_ID)
    base_texture(led_mat, palette)
    tree = led_mat.node_tree
    texture = next(n for n in tree.nodes if n.type == 'TEX_IMAGE')
    tree.links.new(texture.outputs['Color'], tree.nodes.get('Principled BSDF').inputs['Emission Color'])
    def led(x, y, amber=False, radius=.0016):
        obj = box('indicator_lens', (radius*2, .0011, radius*1.4), led_mat,
                  godot((x, y, -.477)), bevel=.0004, segments=1)
        uv = obj.data.uv_layers.new(name='UVMap')
        for polygon in obj.data.polygons:
            major = max(range(3), key=lambda i: abs(polygon.normal[i]))
            axes = [i for i in range(3) if i != major]
            for index in polygon.loop_indices:
                point = obj.data.vertices[obj.data.loops[index].vertex_index].co
                uv.data[index].uv = ((.75 if amber else .25) + .10*point[axes[0]]/radius,
                                     .50 + .10*point[axes[1]]/radius)
        lenses.append(obj)

    # Welded plinth and four load-bearing folded uprights. Full outer bounds.
    slab('plinth', (.60, .085, 1), (0, .0425, 0), 'cabinet', .002, 3)
    slab('top_cap', (.60, .026, 1), (0, 1.987, 0), 'cabinet', .0012, 3)
    for x in (-.28, .28):
        for z in (-.480, .480):
            slab('upright', (.040, 1.89, .040), (x, 1.030, z), 'cabinet', .0013, 3)
    for x in (-.295, .295):
        slab('removable_side_panel', (.008, 1.828, .903), (x, 1.022, 0), 'cabinet', .0006)
        # Long returned edges and recessed latch backs give the removable sheet
        # its seams without a coplanar black painted line.
        for z in (-.444, .444):
            slab('side_panel_return', (.012, 1.82, .007), (x*.97, 1.022, z), 'cabinet')
        for y in (.32, 1.70):
            slab('side_latch_recess', (.001, .055, .025), (x + math.copysign(.0045, x), y, -.34), 'cables', .0004)
            slab('side_latch_tongue', (.001, .024, .009), (x + math.copysign(.0045, x), y, -.34), 'metal', .0003)
    # Closed rear door with real open perforations; equipment backs remain dark.
    for x in (-.258, .258):
        slab('rear_door_stile', (.040, 1.83, .013), (x, 1.022, .487), 'cabinet')
    for y in (.124, 1.92):
        slab('rear_door_crossmember', (.480, .038, .013), (0, y, .487), 'cabinet')
    grille(0, 1.022, .476, 1.756, 14, 40, z=.4935, finish='cabinet')
    for y in (.35, 1.04, 1.73):
        slab('rear_hinge', (.016, .064, .016), (-.263, y, .486), 'metal', .002)
    slab('rear_lock_recess', (.025, .116, .001), (.260, 1.05, .496), 'cables')
    slab('rear_lock_handle', (.009, .076, .004), (.260, 1.05, .497), 'metal', .001)

    # Front rails at exactly z=-.47. EIA spacing: 15.875, 15.875, 12.7 mm.
    for x in (-.2325, .2325):
        cells = []
        for unit in range(42):
            base = .1 + unit*U
            for offset, lower, upper in ((.00635, 0, .0142875),
                                         (.022225, .0142875, .0301625),
                                         (.0381, .0301625, U)):
                cells.append((x, base+(lower+upper)/2, .021, upper-lower, .0088, .0088, base+offset))
        # Hole centres differ slightly from the cell centres at unit ends;
        # use each aperture at the required EIA hole coordinate explicitly.
        obj = aperture_cells('eia_42u_front_rail', cells, -.47, .002, mats['metal'].mat)
        parts.append(obj)
        slab('rail_return', (.003, 1.8669, .032), (x+math.copysign(.009, x), 1.03345, -.453), 'metal', .00025, 1)
        # Rear rails need no animated API and are visible through side gaps.
        slab('rear_rail', (.021, 1.8669, .005), (x, 1.03345, .36), 'metal', .0004)
        for yy in (.10 + 25*U + .022225, .10 + 26*U + .022225):
            # Empty slot cage nuts live on the OUTER edge; aperture remains free.
            slab('patch_slot_cage_nut', (.013, .013, .006), (x, yy, -.463), 'metal', .0004, 1)
    # Dark side ledges and front plinth remain below all working equipment.
    for x in (-.266, .266):
        slab('lower_chassis_ledge', (.030, .012, .88), (x, .096, 0), 'cabinet')
    for y in (.14445, .23335, .32225):
        slab('bottom_2u_blanking_plate', (.4826, .0859, .005), (0, y, -.4665), 'cabinet', .00035, 1)
        for x in (-.2325, .2325):
            bolt(x, y)

    def chassis(y, height, depth=.65):
        slab('server_chassis', (.432, height-.006, depth), (0, y, -.456+depth/2), 'equipment', .0007, 1)
        for x in (-.229, .229):
            slab('rack_ear', (.024, height-.003, .003), (x, y, -.4685), 'equipment', .0004, 1)
            bolt(x, y)
    def server(y, units=2, count=4):
        height = units*U-.0024
        chassis(y, height)
        row_count = 2 if units == 2 else 1
        for row in range(row_count):
            yy = y+(row-(row_count-1)/2)*.033
            for drive in range(count):
                xx = -.174 + drive*.074
                # Four metal tray edges surround a genuinely recessed drive face.
                slab('drive_well', (.054, .029, .001), (xx, yy, -.4605), 'cables', 0)
                for yoff in (-.0137, .0137):
                    slab('drive_carrier_edge', (.054, .0021, .010), (xx, yy+yoff, -.466), 'equipment', 0)
                slab('drive_release', (.005, .023, .004), (xx-.024, yy, -.472), 'equipment', 0)
                slab('brushed_drive_handle', (.034, .004, .004), (xx+.001, yy+.008, -.473), 'metal', .00065, 1)
                # Punched ventilation slits on the inset caddy lower face.
                grille(xx+.002, yy-.004, .031, .009, 3, 1, z=-.468)
                led(xx-.024, yy-.008, amber=(drive == 4 and row == 0))
        grille(.152, y, .092, height-.020, 7, 4 if units == 2 else 2)
        led(.211, y+.008)
        led(.211, y-.008, amber=True)
    for i in range(6):
        server(.41115+i*2*U, 2)

    def switch(y, ports=16):
        chassis(y, U-.003, .30)
        # Twin rows of 8 shielded ports, front rim surrounds hollow recess.
        for row in range(2):
            for col in range(ports//2):
                x = -.178+col*.039
                yy = y+(row-.5)*.018
                parts.append(aperture_cells('rj45_shield', [(x, yy, .026, .016, .018, .011)], -.473, .006, mats['metal'].mat))
                slab('port_socket_back', (.018, .011, .001), (x, yy, -.463), 'cables', 0)
                for dx in (-.004, 0, .004):
                    slab('port_contact', (.001, .003, .001), (x+dx, yy+.003, -.466), 'metal', 0)
                led(x+.014, yy, amber=(col == 6 and row == 1), radius=.0011)
        grille(.172, y, .049, .028, 5, 2)
        led(.211, y)
    switch(.922325)
    switch(.966775)
    slab('thin_blank', (.4826, .0405, .005), (0, 1.011225, -.4665), 'cabinet', .0004, 1)
    for x in (-.2325, .2325):
        bolt(x, 1.011225)
    # Closed KVM drawer with thumb recess, slide seam and folded pull lip.
    chassis(1.072, .075, .57)
    slab('kvm_inset_front', (.414, .052, .003), (0, 1.072, -.467), 'equipment', .0005)
    slab('kvm_thumb_recess', (.122, .021, .001), (0, 1.074, -.469), 'cables', .001, 2)
    slab('kvm_pull_lip', (.137, .005, .007), (0, 1.080, -.473), 'metal', .001, 2)
    led(.19, 1.065)
    slab('kvm_upper_blank', (.4826, .043, .005), (0, 1.134, -.4665), 'cabinet', .00035, 1)
    for x in (-.2325, .2325):
        bolt(x, 1.134)
    # Dedicated 1U cable manager ends just below the specified patch slot.
    manager_y = PATCH[0]-U/2-.002
    chassis(manager_y, U-.003, .11)
    slab('manager_back', (.432, .033, .002), (0, manager_y, -.431), 'cables', .0004)
    for i in range(12):
        x = -.198+i*.036
        slab('manager_finger', (.007, .025, .033), (x, manager_y, -.454), 'cables', .001, 1)
        slab('manager_tip', (.014, .006, .006), (x, manager_y+.009, -.473), 'cables', .001, 1)
    # NOTHING across the 2U patch opening, including front cable dressing.
    # Equipment above it is offset to the request's exact plate/slot heights.
    server(1.344, 2)
    server(1.433, 2)
    switch(1.501)
    server(1.548, 1)
    server(1.607, 1)
    slab('stencil_lower_spacer', (.4826, .023, .005), (0, 1.640, -.4665), 'cabinet', .00035, 1)
    # The stencil substrate has a broad clean matte flat face, without text.
    slab('stencil_3u_plate', (.4826, 3*U-.002, .006), (0, 1.72, -.471), 'cabinet', .0004, 1)
    for x in (-.2325, .2325):
        for yy in (1.72-U, 1.72+U):
            bolt(x, yy, -.474)
    switch(1.814)
    server(1.862, 1)
    server(1.912, 1)
    slab('upper_blank', (.4826, .026, .005), (0, 1.951, -.466), 'cabinet', .00035, 1)

    # Rear vertical PDU with recessed outlet rows, socket switches and strain relief.
    slab('vertical_pdu', (.035, 1.62, .054), (.263, 1.025, .378), 'equipment', .002)
    for i in range(18):
        yy = .28+i*.083
        slab('pdu_socket', (.020, .035, .002), (.263, yy, .349), 'cables', .001, 1)
        for xx in (.258, .268):
            slab('pdu_socket_aperture', (.003, .007, .001), (xx, yy, .3475), 'equipment', 0)
    # Rear and side cable dress stays behind the reserved front aperture.
    rng = random.Random(SEED)
    for side in (-1, 1):
        for i in range(8):
            x = side*(.250+(i%4)*.0034)
            start = .45+i*.17
            points = []
            for k in range(18):
                t = k/17
                yy = start+(1.86-start)*t
                xx = x+side*.004*math.sin(t*math.pi*3+i)
                zz = -.37+.68*t+.016*math.sin(t*math.tau+i)
                points.append((xx, yy, zz))
            parts.append(tube('side_network_bundle', points, .0020+rng.random()*.0004, mats['cables'].mat))
        for y in (.58, 1.02, 1.48, 1.83):
            slab('bundle_velcro_tie', (.025, .007, .018), (side*.256, y, -.10), 'cables', .0007, 1)
    for i in range(6):
        start_y = .41115+i*2*U
        points = [(0.21+.003*i, start_y, .18), (.247, start_y+.04, .25),
                  (.258, start_y+.09, .31), (.263, start_y+.10, .345)]
        parts.append(tube('rear_power_lead', points, .003, mats['cables'].mat, 10))
    return parts, lenses, solid_boxes


def validate(objects, gltf, solid_boxes):
    nodes = {n['name']: n for n in gltf['nodes'] if 'mesh' in n}
    if set(nodes) != {'cabinet', 'leds'} or gltf.get('animations') or gltf.get('cameras'):
        raise RuntimeError('Unexpected exported nodes or animations')
    for name, node in nodes.items():
        for field, default in [('translation', [0, 0, 0]), ('scale', [1, 1, 1]), ('rotation', [0, 0, 0, 1])]:
            if node.get(field, default) != default:
                raise RuntimeError(f'Nonidentity {name} {field}')
    # Box components may occur at the outer rails, but nothing can occupy the
    # required 19-inch front opening, for 200 mm behind the mounting plane.
    for name, lo, hi in solid_boxes:
        if hi[0] <= -.220 or lo[0] >= .220 or hi[2] <= -.48 or lo[2] >= -.27:
            continue
        if hi[1] > PATCH[0]+1e-6 and lo[1] < PATCH[1]-1e-6:
            raise RuntimeError(f'{name} obstructs 2U patch slot')
    points = [obj.matrix_world @ Vector(corner) for obj in objects for corner in obj.bound_box]
    for axis, low, high in ((0, -.30, .30), (1, -.50, .50), (2, 0, 2.00)):
        if abs(min(p[axis] for p in points)-low) > 1e-6 or abs(max(p[axis] for p in points)-high) > 1e-6:
            raise RuntimeError(f'Cabinet bounds drifted on Blender axis {axis}')
    for obj in objects:
        for vertex in obj.data.vertices:
            p = obj.matrix_world @ vertex.co
            if -.220+1e-6 < p.x < .220-1e-6 and PATCH[0]+1e-6 < p.z < PATCH[1]-1e-6 and .27 < p.y < .48:
                raise RuntimeError(f'{obj.name} vertex in patch opening')
    if 'materials' in gltf:
        expected = {f'M_{ASSET_ID}_{part}' for part in ('cabinet', 'equipment', 'metal', 'led', 'cables')}
        if {m['name'] for m in gltf['materials']} != expected:
            raise RuntimeError('Incorrect exported material set')
        led = next(m for m in gltf['materials'] if m['name'] == f'M_{ASSET_ID}_led')
        if 'emissiveTexture' not in led or 'baseColorTexture' not in led['pbrMetallicRoughness']:
            raise RuntimeError('LED palette did not export to albedo and emission')
    if any(obj.modifiers for obj in objects):
        raise RuntimeError('Unapplied modifiers')
    print('PASS geometry: base centre; 0.60 x 1.00 x 2.00 m; identity transforms; clear 2U slot at y=1.25; two meshes', flush=True)


def stabilize_tangents(path):
    """Remove MikkTSpace's tiny thread-order jitter from the GLB tangent data.

    Blender 5.2's cable tangent export varied by 0.0001 in one component
    between otherwise byte-identical builds. Quantize XYZ to 0.001, normalize
    again, and retain the original handedness. Maximum directional change is
    below 0.05 degrees; the packed normal maps and all other data are intact.
    This asset-local canonicalization leaves shared exporters unchanged.
    """
    raw = bytearray(Path(path).read_bytes())
    json_length = struct.unpack_from('<I', raw, 12)[0]
    gltf = json.loads(raw[20:20+json_length])
    binary_start = 28 + json_length
    accessors = {primitive['attributes']['TANGENT']
                 for mesh in gltf['meshes'] for primitive in mesh['primitives']
                 if 'TANGENT' in primitive['attributes']}
    for index in sorted(accessors):
        accessor = gltf['accessors'][index]
        if accessor['componentType'] != 5126 or accessor['type'] != 'VEC4':
            raise RuntimeError('Unexpected tangent accessor format')
        view = gltf['bufferViews'][accessor['bufferView']]
        offset = binary_start + view.get('byteOffset', 0) + accessor.get('byteOffset', 0)
        stride = view.get('byteStride', 16)
        for i in range(accessor['count']):
            where = offset + i*stride
            x, y, z, handedness = struct.unpack_from('<4f', raw, where)
            v = [round(c, 3) for c in (x, y, z)]
            length = math.sqrt(sum(c*c for c in v))
            if length < .5:
                raise RuntimeError('Invalid tangent vector')
            struct.pack_into('<4f', raw, where, *(c/length for c in v), handedness)
    Path(path).write_bytes(raw)
    print(f'PASS deterministic export: {len(accessors)} tangent accessors canonicalized and normalized', flush=True)
    return gltf


def build(out_dir):
    reset_scene(SEED)
    cache = ROOT / 'assets/cache' / ASSET_ID
    cache.mkdir(parents=True, exist_ok=True)
    mats = surfaces()
    print('BUILD original rack geometry: frame, rails, equipment, rear door and cable dressing', flush=True)
    parts, lenses, solid_boxes = geometry(mats)
    bpy.context.view_layer.update()
    validate(parts+lenses, {'nodes': [{'name': 'cabinet', 'mesh': 0}, {'name': 'leds', 'mesh': 1}]}, solid_boxes)
    triangle_estimate = 0
    for obj in parts+lenses:
        obj.data.calc_loop_triangles()
        triangle_estimate += len(obj.data.loop_triangles)
    print(f'PREFLIGHT {triangle_estimate} triangles, {len(lenses)} LEDs', flush=True)
    for finish in list(mats) + ['led']:
        count = sum(len(obj.data.loop_triangles) for obj in parts+lenses
                    if obj.data.materials[0].name == f'M_{ASSET_ID}_{finish}')
        print(f'TOPOLOGY {finish}: {count} triangles', flush=True)
    if triangle_estimate > 60000:
        raise RuntimeError(f'Geometry exceeds budget before baking: {triangle_estimate}')
    textures = [{'name': 'T_server_rack_42u_led_palette', 'size': [64, 64],
                 'map': 'base_color/emissive', 'material': 'M_server_rack_42u_led', 'embedded': True}]
    for part, surf in mats.items():
        selected = [obj for obj in parts if obj.data.materials[0] == surf.mat]
        textures.extend(bake_surface(part, surf, selected, cache))
    objects = [join_static(parts, 'cabinet'), join_static(lenses, 'leds')]
    for obj in objects:
        triangulate(obj)
    bpy.context.view_layer.update()
    path = Path(out_dir).resolve() / f'{ASSET_ID}.glb'
    export_glb(path, objects)
    gltf = stabilize_tangents(path)
    validate(objects, gltf, solid_boxes)
    meta = write_metadata(ASSET_ID, ROOT / 'assets/meta' / f'{ASSET_ID}.json',
                          path, objects, Path(__file__), textures, 'base_center', extra={
        'anchors_godot_m': ANCHORS,
        'patch_slot_clear_godot_m': {'min': [-.220, PATCH[0], -.48], 'max': [.220, PATCH[1], -.27]},
        'stencil_flat_area_m': [.432, .11335],
        'rack_units': {'count': 42, 'height_m': U, 'u1_start_y_m': .10},
        'tangent_export': 'XYZ quantized to 0.001 then normalized; removes MikkTSpace thread-order jitter',
        'forward': 'Blender +Y -> Godot -Z', 'collision': None, 'third_party': [],
        'front_led_count': len(lenses),
        'led_color': 'green/amber palette shared by albedo and emission, single emissive material, strength 0.7',
        'baking': {'engine': 'CYCLES', 'device': 'CPU', 'samples': 16, 'margin_px': 8,
                   'maps': 'procedural color/RM emission, tangent normals, ray AO packed in ORM'},
        'render': {'engine': 'CYCLES', 'device': 'CPU', 'samples': 32, 'denoise': True, 'threads': 4},
        'glb_path': str(path.relative_to(ROOT)) if path.is_relative_to(ROOT) else str(path),
    })
    if meta['triangles'] > 60000 or len(meta['materials']) > 5:
        raise RuntimeError(f'Request budget exceeded: {meta["triangles"]} triangles')
    render_previews(ASSET_ID, ROOT / 'assets/previews', objects, views={
        'front': {'position': (0, 4, 1), 'target': (0, .1, 1), 'scale': 2.22},
        'iso': {'position': (-2.7, 4.3, 2.65), 'target': (0, 0, 1), 'scale': 2.55},
        'detail': {'position': (-.45, 2.2, 1.48), 'target': (0, .43, 1.34), 'scale': .87},
    }, seed=SEED)
    print(f'ASSET BUILT: {path}; {meta["triangles"]} triangles; {len(meta["materials"])} materials', flush=True)
    return path


if __name__ == '__main__':
    run_cli(build, __doc__)
