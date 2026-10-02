"""Pocket 365 nm UV torch: original machined geometry and CPU-baked PBR.

Self-contained deterministic Blender 5.2 build. No downloads or fonts.
Surface baking follows the accepted hero props; only this asset is written.
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
from common.geometry import active, join_static, mesh_object, triangulate
from common.materials import base_texture, image_from_pixels, material, normal_texture, orm_texture
from common.preview import render_previews
from common.scene import reset_scene

ASSET_ID = 'uv_torch'
SEED = 3650118
CENTRE = .013

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
    size = 1024
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
    body = Surface('body', (.016, .022, .029), .44, .86)
    grain = body.noise((4500, 200, 4500))
    variation = body.noise((45, 32, 45))
    color = body.mix(variation, (.008, .012, .017, 1), (.022, .029, .037, 1))
    x, y, z = (body.axes.outputs[k] for k in ('X', 'Y', 'Z'))
    dz = body.math('SUBTRACT', z, CENTRE)
    radius = body.math('SQRT', body.math('ADD', body.math('MULTIPLY', x, x),
                                       body.math('MULTIPLY', dz, dz)))
    knurl = body.math('MULTIPLY', body.math('GREATER_THAN', radius, .01101),
                     body.math('MULTIPLY', body.math('GREATER_THAN', y, -.047),
                               body.math('LESS_THAN', y, -.029)))
    worn = body.math('MULTIPLY', knurl, body.math('GREATER_THAN', body.noise((2700, 900, 2700)), .52))
    # Bare-metal witness lines on the chamfered bezel and tail seam.
    rim = body.math('MULTIPLY', body.math('GREATER_THAN', y, .0509),
                    body.math('GREATER_THAN', radius, .01265))
    ring = body.math('MULTIPLY', body.math('LESS_THAN', y, -.0478),
                     body.math('GREATER_THAN', radius, .0109))
    rim = body.math('MAXIMUM', rim, ring)
    worn = body.math('MAXIMUM', worn, body.math('MULTIPLY', rim, .55))
    color = body.mix(worn, color, (.25, .28, .31, 1))
    # A handling scuff confined to the side of the centre barrel.
    scuff = body.math('MULTIPLY', body.math('GREATER_THAN', x, .008),
                      body.math('MULTIPLY', body.math('LESS_THAN', y, .004),
                                body.math('GREATER_THAN', y, -.005)))
    scratch = body.math('GREATER_THAN', body.noise((2500, 180, 1200)), .66)
    scuff = body.math('MULTIPLY', scuff, scratch)
    color = body.mix(body.math('MULTIPLY', scuff, .38), color, (.15, .17, .19, 1))
    # Reflector bowl, retaining the same body material/atlas as the housing.
    reflector = body.math('MULTIPLY', body.math('GREATER_THAN', y, .041),
                          body.math('LESS_THAN', radius, .0096))
    loop = body.math('LESS_THAN', y, -.053)
    bare = body.math('MAXIMUM', reflector, loop)
    color = body.mix(bare, color, (.48, .51, .54, 1))
    rough = body.math('ADD', .35, body.math('MULTIPLY', grain, .19))
    rough = body.mix(bare, rough, (.23, .23, .23, 1))
    body.finish(color, rough, grain, .15, .000015)
    rubber = Surface('rubber', (.006, .007, .009), .76)
    grain = rubber.noise((6000, 6000, 6000))
    rubber.finish(rubber.mix(grain, (.004, .005, .006, 1), (.012, .014, .016, 1)),
                  rubber.math('ADD', .69, rubber.math('MULTIPLY', grain, .17)), grain, .17, .00002)
    return {'body': body, 'rubber': rubber}


def lathe(name, profile, mat, sides=64):
    """Closed or open revolved profile along Blender +Y (Godot -Z)."""
    vertices, rings, faces = [], [], []
    for y, r in profile:
        ring = []
        for i in range(sides if r else 1):
            a = 2*math.pi*i/sides
            ring.append(len(vertices))
            vertices.append((r*math.sin(a), y, CENTRE+r*math.cos(a)))
        rings.append(ring)
    # This angle convention is clockwise from +Y; winding is outward.
    for low, high in zip(rings, rings[1:]):
        for i in range(sides):
            j = (i+1) % sides
            if len(low) == 1:
                faces.append((low[0], high[j], high[i]))
            elif len(high) == 1:
                faces.append((low[i], low[j], high[0]))
            else:
                faces.append((low[i], low[j], high[j], high[i]))
    obj = mesh_object(name, vertices, faces, mat)
    for face in obj.data.polygons:
        face.use_smooth = True
    return obj


def knurl(mat):
    vertices, faces = [], []
    sides, rows = 64, 18
    for j in range(rows+1):
        y = -.0468 + .0176*j/rows
        for i in range(sides):
            a = 2*math.pi*i/sides
            r = .01068 + (.00036 if (i+j) % 2 == 0 and j not in (0, rows) else 0)
            vertices.append((r*math.sin(a), y, CENTRE+r*math.cos(a)))
    for j in range(rows):
        for i in range(sides):
            a, b = j*sides+i, j*sides+(i+1)%sides
            c, d = a+sides, b+sides
            # Alternate diagonals: true faceted diamond peaks, never smooth.
            faces.extend([(a, b, c), (b, d, c)] if (i+j)%2 else [(a, b, d), (a, d, c)])
    return mesh_object('tail_diamond_knurl', vertices, faces, mat)


def tube(name, points, radius, mat, sides=8):
    vertices, faces = [], []
    for i, point in enumerate(points):
        p = Vector(point)
        direction = Vector(points[min(i+1, len(points)-1)]) - Vector(points[max(0, i-1)])
        direction.normalize()
        u = direction.cross(Vector((0, 0, 1)))
        if u.length < .01:
            u = direction.cross(Vector((1, 0, 0)))
        u.normalize()
        v = direction.cross(u).normalized()
        for j in range(sides):
            angle = 2*math.pi*j/sides
            vertices.append(tuple(p+radius*(math.cos(angle)*u+math.sin(angle)*v)))
    for i in range(len(points)-1):
        for j in range(sides):
            a, b = i*sides+j, i*sides+(j+1)%sides
            faces.append((a, b, b+sides, a+sides))
    # Triangle fans avoid n-gons at the end caps.
    for index, reverse in ((0, True), (len(points)-1, False)):
        centre = len(vertices)
        vertices.append(tuple(points[index]))
        for j in range(sides):
            tri = (centre, index*sides+j, index*sides+(j+1)%sides)
            faces.append(tuple(reversed(tri)) if reverse else tri)
    obj = mesh_object(name, vertices, faces, mat)
    for poly in obj.data.polygons:
        poly.use_smooth = True
    # Recalculate before baking, as tube local frames may change winding.
    triangulate(obj)
    return obj


GLYPHS = {
    'U': [[(0,1),(0,.18),(.15,0),(.45,0),(.6,.18),(.6,1)]],
    'V': [[(0,1),(.3,0),(.6,1)]],
    '3': [[(0,.9),(.15,1),(.45,1),(.6,.85),(.6,.65),(.42,.5),(.25,.5)],[(.42,.5),(.6,.35),(.6,.15),(.45,0),(.15,0),(0,.1)]],
    '6': [[(.55,.9),(.4,1),(.18,1),(0,.8),(0,.15),(.15,0),(.45,0),(.6,.15),(.6,.4),(.45,.55),(.15,.55),(0,.4)]],
    '5': [[(.6,1),(0,1),(0,.55),(.42,.55),(.6,.4),(.6,.15),(.45,0),(.15,0),(0,.1)]],
    'n': [[(0,0),(0,.7)],[(0,.5),(.16,.7),(.44,.7),(.6,.52),(.6,0)]],
    'm': [[(0,0),(0,.7)],[(0,.5),(.15,.7),(.3,.5),(.3,0)],[(.3,.5),(.45,.7),(.6,.5),(.6,0)]],
    'K': [[(0,0),(0,1)],[(.6,1),(0,.43),(.6,0)]],
    'L': [[(0,1),(0,0),(.6,0)]],
    'I': [[(0,1),(.6,1)],[(.3,1),(.3,0)],[(0,0),(.6,0)]],
    'T': [[(0,1),(.6,1)],[(.3,1),(.3,0)]],
    '0': [[(.15,0),(.45,0),(.6,.18),(.6,.82),(.45,1),(.15,1),(0,.82),(0,.18),(.15,0)]],
    '1': [[(.08,.8),(.3,1),(.3,0)],[(.05,0),(.55,0)]],
    '8': [[(.15,.5),(0,.67),(0,.85),(.15,1),(.45,1),(.6,.85),(.6,.67),(.45,.5),(.15,.5),(0,.33),(0,.15),(.15,0),(.45,0),(.6,.15),(.6,.33),(.45,.5)]],
    '-': [[(.05,.5),(.55,.5)]],
}


def labels(cache):
    """Original stroke artwork rasterized without fonts or external libraries."""
    size = 1024
    pixels = array('f', [.15, .16, .18, 1]) * (size*size)
    def line(p, q, width, color):
        ax, ay = p; bx, by = q
        dx, dy = bx-ax, by-ay
        length = dx*dx+dy*dy
        for y in range(max(0, int(min(ay,by)-width-1)), min(size, int(max(ay,by)+width+2))):
            for x in range(max(0, int(min(ax,bx)-width-1)), min(size, int(max(ax,bx)+width+2))):
                t = max(0, min(1, ((x+.5-ax)*dx+(y+.5-ay)*dy)/length)) if length else 0
                d = math.hypot(x+.5-ax-t*dx, y+.5-ay-t*dy)
                alpha = max(0, min(1, width+.5-d))
                k = (y*size+x)*4
                for c in range(3):
                    pixels[k+c] = pixels[k+c]*(1-alpha)+color[c]*alpha
    def text(string, start, h, stroke, color):
        x, y = start
        for ch in string:
            if ch != ' ':
                for path in GLYPHS[ch]:
                    points = [(x+a*h, y+b*h) for a,b in path]
                    for p,q in zip(points, points[1:]):
                        line(p,q,stroke,color)
            x += .83*h
    # UV left half: charcoal violet main identification band. Right: ivory sticker.
    for y in range(32, 460):
        for x in range(32, 992):
            k=(y*size+x)*4
            edge=min(x-32,991-x,y-32,459-y)
            shade=.010 if edge>6 else .095
            pixels[k:k+4]=array('f',[shade*.82,shade*.94,shade*1.2,1])
    text('UV 365nm', (95,185), 125, 6, (.85,.86,.91))
    for y in range(544, 992):
        for x in range(32, 992):
            k=(y*size+x)*4
            f=.82+random.Random(SEED+y*size+x).random()*.025
            pixels[k:k+4]=array('f',[f,f*.96,f*.84,1])
    text('KL-IT-0118',(70,725),105,5,(.012,.016,.02))
    # Restrained abrasion at sticker corners, away from the printed strings.
    rng=random.Random(SEED)
    for i in range(35):
        x=rng.uniform(38,980); y=rng.choice([rng.uniform(550,580),rng.uniform(961,988)])
        line((x,y),(x+rng.uniform(1,10),y+2),rng.uniform(.3,1),(.20,.22,.23))
    image = image_from_pixels(ASSET_ID,'label_base_color',size,pixels,cache)
    mat=material(ASSET_ID,'label',(.8,.8,.8),roughness=.57)
    base_texture(mat,image)
    return mat, [{'name':image.name,'size':[size,size],'map':'base_color','material':mat.name,'embedded':True}]


def band(name, y0, y1, half_angle, mat, uvrect, angle_centre=0):
    vertices, faces = [], []
    steps=20
    for y in (y0,y1):
        for i in range(steps+1):
            a=angle_centre-half_angle+2*half_angle*i/steps
            vertices.append((.011045*math.sin(a),y,CENTRE+.011045*math.cos(a)))
    for i in range(steps):
        faces.append((i,i+1,i+1+steps+1,i+steps+1))
    obj=mesh_object(name,vertices,faces,mat)
    # Read along +Y from the tail to the head; top-facing curved label.
    uv=obj.data.uv_layers.new(name='UVMap')
    u0,v0,u1,v1=uvrect
    for poly in obj.data.polygons:
        poly.use_smooth=True
        for loop in poly.loop_indices:
            vertex=obj.data.loops[loop].vertex_index
            row,i=divmod(vertex,steps+1)
            uv.data[loop].uv=(u0+(u1-u0)*row,v1-(v1-v0)*i/steps)
    return obj


def geometry(mats,label):
    aluminium=mats['body'].mat; rubber=mats['rubber'].mat
    # Tube + chamfered tail collar + graduated head. Radial grooves are modeled.
    profile=[(-.0525,0),(-.0525,.0080),(-.0522,.0096),(-.0515,.0105),
             (-.0498,.0110),(-.0483,.0110),(-.0479,.01055),(-.0475,.01055),
             (-.0471,.0107),(-.0290,.0107),(-.0287,.0110),(-.0270,.0110),
             (-.0266,.01065),(-.0262,.01065),(-.0258,.011),
             (.0250,.011),(.0270,.0113),(.0290,.0120)]
    for y in (.030,.034,.038):
        profile.extend([(y,.0120),(y+.0003,.01135),(y+.001,.01135),(y+.0013,.0120)])
    profile.extend([(.0405,.0120),(.0420,.0128),(.0430,.0130),
                    (.0505,.0130),(.0515,.0128),(.0525,.0122),(.0525,.0096),
                    (.0517,.00915),(.0480,.00915),(.0450,.0060),(.0430,.0045),
                    (.0415,.0045),(.0415,0)])
    parts=[lathe('machined_shell',profile,aluminium),knurl(aluminium)]
    # Matte domed tail switch, proud of the recessed collar but within length.
    parts.append(lathe('tail_switch',[(-.05248,0),(-.05248,.0038),(-.0522,.0055),
                (-.0518,.0069),(-.0509,.0074),(-.0500,.0074),(-.0500,0)],rubber,48))
    # Rubber moulded concentric traction ribs.
    for r in (.0026,.0041,.0055):
        parts.append(lathe('switch_rib', [(-.05255,r-.00012),(-.05268,r),
                     (-.05255,r+.00012),(-.05240,r+.00012),(-.05240,r-.00012),
                     (-.05255,r-.00012)],rubber,48))
    eyelet=[(0,-.0514+.0021*math.sin(a),.022+.0021*math.cos(a))
            for a in [2*math.pi*i/32 for i in range(33)]]
    parts.append(tube('lanyard_eyelet',eyelet,.0007,aluminium))
    # Two nearly complete helical turns make a real split ring, including gaps.
    points=[]
    for i in range(80):
        a=-.15+i/79*(4*math.pi-.25)
        points.append((.0037*math.sin(a),-.0566+.0037*math.cos(a),.0222+.00065*i/79))
    parts.append(tube('split_ring',points,.00043,aluminium))
    parts.append(band('uv_identification_band',-.022,.018,.51,label,(32/1024,32/1024,992/1024,460/1024)))
    parts.append(band('asset_sticker',.004,.0250,.34,label,(32/1024,544/1024,992/1024,992/1024),angle_centre=.90))
    lensmat=material(ASSET_ID,'lens',(.72,.67,.84),roughness=.19,
                     metallic=.05,emission=((.28,.008,1.0),.75))
    # A small die behind the frosted 18 mm lens; the glass/filter and LED
    # share the SDK-controlled optical material and remain a single part.
    led=lathe('uv_led_die',[(.0475,0),(.0475,.0016),(.0480,.0016),(.0480,0)],lensmat,16)
    optics=[lathe('lens',[(.0498,0),(.0498,.0087),(.0500,.0090),(.0506,.0090),
                         (.0508,.0087),(.0508,0)],lensmat,64)]
    optics.append(led)
    return parts,optics


def build(out_dir):
    reset_scene(SEED)
    cache=ROOT/'assets/cache'/ASSET_ID
    cache.mkdir(parents=True,exist_ok=True)
    mats=surfaces()
    label,textures=labels(cache)
    parts,optics=geometry(mats,label)
    bpy.context.view_layer.update()
    for part in ('body','rubber'):
        selected=[obj for obj in parts if obj.data.materials[0]==mats[part].mat]
        textures.extend(bake_surface(part,mats[part],selected,cache))
    objects=[join_static(parts,'body'),join_static(optics,'lens')]
    # All meshes use identity transforms; floor base and combined bounds centre.
    points=[vertex.co for obj in objects for vertex in obj.data.vertices]
    shift=Vector((-(min(p.x for p in points)+max(p.x for p in points))/2,
                  -(min(p.y for p in points)+max(p.y for p in points))/2,
                  -min(p.z for p in points)))
    for obj in objects:
        for vertex in obj.data.vertices:
            vertex.co+=shift
        triangulate(obj)
    bpy.context.view_layer.update()
    assert all(abs(v-1)<1e-9 for obj in objects for v in obj.scale)
    assert all(abs(v)<1e-9 for obj in objects for v in obj.rotation_euler)
    assert min(v.co.z for obj in objects for v in obj.data.vertices)==0
    print('PASS geometry: two identity-transform meshes; floor min y=0; lens faces Godot -Z; no collision',flush=True)
    path=Path(out_dir).resolve()/f'{ASSET_ID}.glb'
    export_glb(path,objects)
    metadata=write_metadata(ASSET_ID,ROOT/'assets/meta'/f'{ASSET_ID}.json',path,objects,
                           Path(__file__),textures,'base_center',extra={
        'forward':'Blender +Y -> Godot -Z','collision':None,'third_party':[],
        'dimensions_nominal_m':{'body_length':.105,'body_diameter':.022,'head_diameter':.026,'lens_diameter':.018},
        'label_strings':['UV 365nm','KL-IT-0118'],
        'lens_emission':{'linear_rgb':[.28,.008,1.0],'strength':.75},
        'anchors_godot_m':{'lens_surface_centre':[shift.x,CENTRE+shift.z,-(.0508+shift.y)]},
    })
    if metadata['triangles']>60000 or metadata['parts']!=['body','lens'] or len(metadata['materials'])!=4:
        raise RuntimeError('Export contract failed')
    # Preview-only quarter turn presents both printed strings left-to-right.
    # Applied export transforms above remain identity.
    for obj in objects:
        obj.rotation_euler.z=-math.pi/2
    bpy.context.view_layer.update()
    centre=Vector((shift.y,0,CENTRE+shift.z))
    views={
        'front':{'position':tuple(centre+Vector((0,-.015,.24))),'target':tuple(centre),'scale':.132},
        'iso':{'position':tuple(centre+Vector((.16,-.13,.17))),'target':tuple(centre),'scale':.127},
        'detail':{'position':tuple(centre+Vector((.13,-.08,.13))),'target':tuple(centre+Vector((.025,0,0))),'scale':.088},
    }
    render_previews(ASSET_ID,ROOT/'assets/previews',objects,views,seed=SEED)
    print(f'ASSET BUILT: {path}; {metadata["triangles"]} triangles; {len(metadata["materials"])} materials',flush=True)


if __name__=='__main__':
    run_cli(build,'Build the pocket UV torch')
