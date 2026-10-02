"""Worn RAL-7035 filing cabinet; standalone, deterministic, CPU-only build.

blender -b --threads 4 -noaudio --python tools/blender/props/filing_cabinet_keypad.py
    -- --out game/assets/core/props
The keypad is mounted by Claude; only its unobstructed mounting band is built.
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
from common.materials import material, base_texture, normal_texture, orm_texture, image_from_pixels
from common.preview import render_previews
from common.scene import reset_scene

ASSET_ID = 'filing_cabinet_keypad'
SEED = 70351990
# Unshifted design uses the request's carcass +/-0.30 Z planes. Handles end
# at Z=-.372, so translate +.036 Z to centre the complete closed footprint.
SHIFT_Z = .036


def godot(x, y, z):
    return (x, -z - SHIFT_Z, y)


def panel(name, w, h, d, x, y, z, mat, bevel=.001, segments=3):
    return box(name, (w, d, h), mat, godot(x, y, z), bevel=bevel, segments=segments)


def tube(name, points, radius, mat, sides=12):
    """Applied closed tube along a polyline, for rolled tray lips."""
    vertices, faces = [], []
    for i, point in enumerate(points):
        p = Vector(godot(*point))
        tangent = Vector(godot(*points[min(i + 1, len(points) - 1)])) - Vector(godot(*points[max(i - 1, 0)]))
        tangent.normalize()
        a = tangent.cross(Vector((0, 0, 1)))
        if a.length < .01:
            a = tangent.cross(Vector((1, 0, 0)))
        a.normalize()
        b = tangent.cross(a).normalized()
        for j in range(sides):
            angle = math.tau * j / sides
            vertices.append(p + radius * (math.cos(angle) * a + math.sin(angle) * b))
    for i in range(len(points) - 1):
        for j in range(sides):
            a, b = i * sides + j, i * sides + (j + 1) % sides
            faces.append((a, b, b + sides, a + sides))
    faces += [tuple(reversed(range(sides))), tuple(range((len(points)-1)*sides, len(points)*sides))]
    obj = mesh_object(name, vertices, faces, mat)
    for face in obj.data.polygons:
        face.use_smooth = len(face.vertices) == 4
    return obj


def screw(name, x, y, z, mat):
    """Small domed machine screw; actual recessed socket geometry."""
    n = 24
    vertices = []
    for radius, dz in ((.0028, 0), (.0025, -.001), (.0011, -.0012), (.0011, -.0005)):
        for i in range(n):
            a = math.tau*i/n
            vertices.append(godot(x+radius*math.cos(a), y+radius*math.sin(a), z+dz))
    faces = []
    for ring in range(3):
        for i in range(n):
            j = (i+1)%n
            faces.append((ring*n+i, ring*n+j, (ring+1)*n+j, (ring+1)*n+i))
    faces.extend((tuple(reversed(range(n))), tuple(range(3*n, 4*n))))
    obj = mesh_object(name, vertices, faces, mat)
    for face in obj.data.polygons:
        face.use_smooth = len(face.vertices) == 4
    return obj


class Shader:
    """Tiny local node builder; procedural sources are baked, never exported."""
    def __init__(self, mat):
        self.tree = mat.node_tree
        self.bsdf = self.tree.nodes.get('Principled BSDF')
        pos = self.tree.nodes.new('ShaderNodeNewGeometry').outputs['Position']
        split = self.tree.nodes.new('ShaderNodeSeparateXYZ')
        self.tree.links.new(pos, split.inputs[0])
        self.x, self.depth, self.height = split.outputs
        self.pos = pos

    def node(self, kind):
        return self.tree.nodes.new(kind)

    def set(self, socket, value):
        if isinstance(value, (int, float)) or isinstance(value, tuple):
            socket.default_value = value
        else:
            self.tree.links.new(value, socket)

    def op(self, kind, a, b=0):
        n = self.node('ShaderNodeMath')
        n.operation = kind
        self.set(n.inputs[0], a)
        self.set(n.inputs[1], b)
        return n.outputs[0]

    def noise(self, scale, detail=2, vector=None):
        n = self.node('ShaderNodeTexNoise')
        self.set(n.inputs['Vector'], vector or self.pos)
        n.inputs['Scale'].default_value = scale
        n.inputs['Detail'].default_value = detail
        return n.outputs['Fac']

    def mix(self, fac, a, b):
        n = self.node('ShaderNodeMixRGB')
        n.blend_type = 'MIX'
        self.set(n.inputs[0], fac)
        self.set(n.inputs[1], (*a, 1) if isinstance(a, tuple) and len(a)==3 else a)
        self.set(n.inputs[2], (*b, 1) if isinstance(b, tuple) and len(b)==3 else b)
        return n.outputs[0]

    def distance_mask(self, x, y, z, radius):
        n = self.node('ShaderNodeVectorMath')
        n.operation = 'DISTANCE'
        self.set(n.inputs[0], self.pos)
        self.set(n.inputs[1], godot(x, y, z))
        return self.op('MAXIMUM', 0, self.op('SUBTRACT', 1, self.op('DIVIDE', n.outputs['Value'], radius)))


def procedural_materials():
    paint = material(ASSET_ID, 'paint', (.62, .65, .63), roughness=.57)
    s = Shader(paint)
    coarse = s.noise(65, 3)
    fine = s.noise(1100, 2)
    # Wear is positioned in physical space: top-front corners, pull stems,
    # and the bottom few centimetres. No indiscriminate all-over grunge.
    edge = 0
    for x in (-.247, .247):
        edge = s.op('MAXIMUM', edge, s.distance_mask(x, 1.194, -.296, .027))
    for y in (.815, .515, .165):
        for x in (-.059, .059):
            edge = s.op('MAXIMUM', edge, s.op('MULTIPLY', .83, s.distance_mask(x, y, -.320, .013)))
    chip_noise = s.op('ADD', s.op('MULTIPLY', coarse, .30), s.op('MULTIPLY', s.noise(420, 3), .36))
    chips = s.op('GREATER_THAN', s.op('ADD', edge, chip_noise), .96)
    rust_zone = s.op('MAXIMUM', 0, s.op('SUBTRACT', 1, s.op('DIVIDE', s.height, .049)))
    rust = s.op('MULTIPLY', rust_zone, s.op('MULTIPLY', .40, s.op('GREATER_THAN', s.noise(170, 3), .53)))
    col = s.mix(s.op('MULTIPLY', s.noise(8, 3), .22), (.48,.515,.495), (.435,.47,.45))
    # Stretched noise gives gentle dull wipe marks on drawer fronts.
    stretch = s.node('ShaderNodeVectorMath'); stretch.operation = 'MULTIPLY'
    s.set(stretch.inputs[0], s.pos); s.set(stretch.inputs[1], (8, 2, 95))
    scuff = s.op('MULTIPLY', .12, s.op('GREATER_THAN', s.noise(8, 2, stretch.outputs[0]), .64))
    col = s.mix(scuff, col, (.32,.35,.335))
    # Discrete fine horizontal scuffs beside the top pull, not random damage
    # across every face. All distances are metres in the closed design.
    front = s.op('LESS_THAN', s.op('ABSOLUTE', s.op('SUBTRACT', s.depth, .284)), .003)
    scratches = 0
    for x, y, length, width in ((-.138,.836,.041,.00040),(-.124,.832,.025,.00032),
                                (.108,.801,.029,.00045),(.102,.804,.021,.00027)):
        xx = s.op('DIVIDE', s.op('ABSOLUTE', s.op('SUBTRACT', s.x, x)), length)
        yy = s.op('DIVIDE', s.op('ABSOLUTE', s.op('SUBTRACT', s.height, y)), width)
        line = s.op('LESS_THAN', s.op('ADD', xx, yy), 1)
        scratches = s.op('MAXIMUM', scratches, s.op('MULTIPLY', line, front))
    col = s.mix(s.op('MULTIPLY', scratches, .52), col, (.18,.20,.19))
    col = s.mix(rust, col, (.18,.073,.025))
    col = s.mix(chips, col, (.075,.082,.085))
    rough = s.op('ADD', .49, s.op('MULTIPLY', coarse, .12))
    # Fingerprint smears around the frequently handled top pull.
    smear = s.distance_mask(.032, .813, -.320, .07)
    rough = s.op('SUBTRACT', rough, s.op('MULTIPLY', smear, .16))
    # Small elliptical whorls model oil transferred by fingertips. The effect
    # lives mainly in roughness and appears when the lighting catches it.
    for x, y in ((.031,.848),(.069,.823)):
        dx = s.op('MULTIPLY', s.op('SUBTRACT', s.x, x), 1.30)
        dy = s.op('SUBTRACT', s.height, y)
        distance = s.op('SQRT', s.op('ADD', s.op('MULTIPLY', dx, dx), s.op('MULTIPLY', dy, dy)))
        mask = s.op('MULTIPLY', front, s.op('MAXIMUM', 0, s.op('SUBTRACT', 1, s.op('DIVIDE', distance, .014))))
        rings = s.op('MULTIPLY', .5, s.op('ADD', 1, s.op('SINE', s.op('MULTIPLY', distance, 10500))))
        fingerprint = s.op('MULTIPLY', mask, rings)
        rough = s.op('SUBTRACT', rough, s.op('MULTIPLY', fingerprint, .13))
        col = s.mix(s.op('MULTIPLY', fingerprint, .025), col, (.23,.245,.235))
    rough = s.op('ADD', rough, s.op('MULTIPLY', rust, .35))
    rough = s.mix(chips, rough, (.34,.34,.34))
    bump = s.node('ShaderNodeBump')
    s.set(bump.inputs['Height'], s.op('ADD', fine, s.op('MULTIPLY', chips, -.8)))
    bump.inputs['Distance'].default_value = .00010
    bump.inputs['Strength'].default_value = .32
    s.tree.links.new(bump.outputs['Normal'], s.bsdf.inputs['Normal'])
    metallic = s.op('MULTIPLY', chips, .85)
    sources = {paint: (col, rough, metallic, 2048)}

    metal = material(ASSET_ID, 'metal', (.48,.50,.51), metallic=1, roughness=.28)
    s = Shader(metal)
    stretch = s.node('ShaderNodeVectorMath'); stretch.operation = 'MULTIPLY'
    s.set(stretch.inputs[0], s.pos); s.set(stretch.inputs[1], (3, 850, 850))
    grain = s.noise(3, 2, stretch.outputs[0])
    col = s.mix(grain, (.40,.42,.435), (.52,.54,.55))
    rough = s.op('ADD', .24, s.op('MULTIPLY', grain, .13))
    bump = s.node('ShaderNodeBump'); s.set(bump.inputs['Height'], grain)
    bump.inputs['Distance'].default_value = .000018
    bump.inputs['Strength'].default_value = .22
    s.tree.links.new(bump.outputs['Normal'], s.bsdf.inputs['Normal'])
    sources[metal] = (col, rough, .98, 1024)

    interior = material(ASSET_ID, 'interior', (.42,.46,.48), metallic=.86, roughness=.52)
    s = Shader(interior)
    vor = s.node('ShaderNodeTexVoronoi'); s.set(vor.inputs['Vector'], s.pos)
    vor.inputs['Scale'].default_value = 410
    spangle = vor.outputs['Distance']
    col = s.mix(spangle, (.36,.395,.415), (.47,.50,.515))
    rough = s.op('ADD', .38, s.op('MULTIPLY', s.noise(210, 2), .23))
    bump = s.node('ShaderNodeBump'); s.set(bump.inputs['Height'], spangle)
    bump.inputs['Distance'].default_value = .000032
    bump.inputs['Strength'].default_value = .23
    s.tree.links.new(bump.outputs['Normal'], s.bsdf.inputs['Normal'])
    sources[interior] = (col, rough, .85, 2048)
    card = material(ASSET_ID, 'card', (.78,.75,.64), roughness=.86)
    s = Shader(card)
    col = s.mix(s.noise(450), (.78,.75,.665), (.81,.785,.70))
    sources[card] = (col, .85, 0, 512)
    for mat, (color, rough, metallic, _) in sources.items():
        s = Shader(mat)
        s.set(s.bsdf.inputs['Base Color'], color)
        s.set(s.bsdf.inputs['Roughness'], rough)
        s.set(s.bsdf.inputs['Metallic'], metallic)
    return paint, metal, interior, card, sources


def drawer(name, cy, height, mats, with_tray=False):
    paint, metal, interior, card = mats
    parts = [panel(name+'_front', .46, height, .02, 0, cy, -.31, paint, .003, 4)]
    handle_y = cy - .035
    # Two mounting feet, two stand-offs, and a generous rolled bar: the open
    # space behind it is genuinely modelled, rather than painted black.
    for x in (-.059, .059):
        parts += [panel('pull_foot', .022,.033,.003, x,handle_y,-.3215,metal,.002),
                  panel('pull_stem', .016,.022,.034, x,handle_y,-.340,metal,.003),
                  screw('pull_fixing',x,handle_y+.012,-.323,metal)]
    parts += [panel('pull_bar', .14,.022,.022, 0,handle_y,-.361,metal,.004,5)]
    label_y = cy + (.057 if with_tray else .095)
    # Slim folded label holder; separate rails surround a recessed blank card.
    parts += [panel('blank_card', .09,.030,.0008, 0,label_y,-.3214,card,.0003)]
    for x in (-.048, .048):
        parts += [panel('label_side', .006,.039,.0035,x,label_y,-.3226,metal,.0008)]
    for y in (label_y-.0175,label_y+.0175):
        parts += [panel('label_rail', .101,.004,.0035,0,y,-.3226,metal,.0006)]
    for x in (-.054, .054):
        parts += [screw('label_rivet',x,label_y,-.3205,metal)]
    if with_tray:
        parts += [panel('tray_floor', .428,.002,.508,0,.754,-.04,interior,.0007),
                  panel('tray_back', .428,.16,.004,0,.835,.212,interior,.001)]
        for x in (-.212,.212):
            parts += [panel('tray_side', .004,.16,.504,x,.835,-.04,interior,.001),
                      tube('rolled_tray_lip',[(x,.915,-.292),(x,.915,.212)],.002,interior)]
        parts += [tube('rolled_back_lip',[(-.212,.915,.212),(.212,.915,.212)],.002,interior),
                  panel('tray_front_inner',.42,.16,.003,0,.835,-.2915,interior,.0008)]
    return join_static(parts,name,godot(0,cy,-.32))


def geometry(mats):
    paint, metal, interior, card = mats
    pieces = [panel('cap',.5,.012,.60,0,1.194,0,paint,.003,5),
              panel('back',.494,1.178,.004,0,.601,.298,paint,.001),
              panel('base_plinth',.5,.025,.60,0,.0125,0,paint,.002,4),
              panel('header_band',.464,.22,.010,0,1.08,-.295,paint,.0025,4),
              panel('lower_sill',.464,.012,.025,0,.027,-.2875,paint,.001),
              panel('drawer_separator',.464,.008,.025,0,.73,-.2875,paint,.001),
              panel('drawer_separator',.464,.006,.025,0,.375,-.2875,paint,.001)]
    for x in (-.246,.246):
        pieces += [panel('side',.008,1.18,.60,x,.602,0,paint,.0025,4),
                   panel('folded_front_stile',.014,1.155,.018,math.copysign(.233,x),.6025,-.290,paint,.0015),
                   panel('tray_slide',.012,.017,.52,math.copysign(.225,x),.771,-.027,interior,.001)]
    # Top tray opening: no shelf, lock bar or cross-brace in its travel volume.
    # Check the full 0.40 m swept envelope, including floor thickness and
    # rolled lips. Fixed pieces must not intersect this axis-aligned volume.
    swept_min = Vector((-.214, -.214-SHIFT_Z, .752))
    swept_max = Vector(( .214,  .694-SHIFT_Z, .917))
    bpy.context.view_layer.update()
    for piece in pieces:
        corners = [piece.matrix_world @ Vector(c) for c in piece.bound_box]
        lo = Vector([min(c[i] for c in corners) for i in range(3)])
        hi = Vector([max(c[i] for c in corners) for i in range(3)])
        if all(hi[i] > swept_min[i] and lo[i] < swept_max[i] for i in range(3)):
            raise RuntimeError('Fixed geometry intrudes into tray travel: '+piece.name)
    body = join_static(pieces,'body')
    objects = [body,drawer('drawer_top',.85,.22,mats,True),
               drawer('drawer_mid',.55,.34,mats),drawer('drawer_low',.20,.34,mats)]
    return objects


def unwrap(objects, materials):
    """Pack disjoint islands per material across all four named mesh objects."""
    for obj in objects:
        if not obj.data.uv_layers:
            obj.data.uv_layers.new(name='UVMap')
    bpy.context.scene.tool_settings.mesh_select_mode = (False, False, True)
    for mat in materials:
        bpy.ops.object.select_all(action='DESELECT')
        for obj in objects:
            obj.select_set(True)
            for poly in obj.data.polygons:
                poly.select = obj.data.materials[poly.material_index] == mat
        bpy.context.view_layer.objects.active = objects[0]
        bpy.ops.object.mode_set(mode='EDIT')
        bpy.ops.uv.smart_project(angle_limit=math.radians(66), island_margin=.012, area_weight=.6, correct_aspect=True, scale_to_bounds=True)
        bpy.ops.object.mode_set(mode='OBJECT')


def bake_materials(objects, sources, cache):
    """Actual procedural-to-texture Cycles baking, with 8-pixel gutters.

    Emission bakes isolate color/roughness/metallic from preview lighting.
    Tangent normals include the orange peel, galvanised spangle and brushing.
    """
    scene = bpy.context.scene
    scene.cycles.samples = 1
    scene.render.bake.margin = 8
    scene.render.bake.use_clear = False
    scene.render.bake.use_selected_to_active = False
    images = {}
    targets = {}
    # Every material must have an active bake image, even when a mesh contains
    # several of them. Other materials point at their own harmless scratch.
    for mat, (_,_,_,size) in sources.items():
        image = bpy.data.images.new('scratch_'+mat.name, width=size,height=size,alpha=False)
        image.colorspace_settings.name = 'Non-Color'
        node = mat.node_tree.nodes.new('ShaderNodeTexImage'); node.image = image
        mat.node_tree.nodes.active = node
        targets[mat] = node
    for mat,(color,rough,metallic,size) in sources.items():
        tree = mat.node_tree
        output = tree.nodes.get('Material Output')
        bsdf = tree.nodes.get('Principled BSDF')
        emission = tree.nodes.new('ShaderNodeEmission')
        scalar_images = {}
        part = mat.name.rsplit('_',1)[-1]
        for kind, value in [('base_color',color),('roughness',rough),('metallic',metallic),('normal',None)]:
            if part == 'card' and kind != 'base_color':
                continue
            name = f'T_{ASSET_ID}_{part}_{kind}'
            image = bpy.data.images.new(name,width=size,height=size,alpha=False)
            image.colorspace_settings.name = 'sRGB' if kind=='base_color' else 'Non-Color'
            targets[mat].image = image; tree.nodes.active = targets[mat]
            if kind == 'normal':
                tree.links.new(bsdf.outputs['BSDF'],output.inputs['Surface'])
            else:
                if emission.inputs['Color'].is_linked:
                    tree.links.remove(emission.inputs['Color'].links[0])
                if isinstance(value,(int,float)):
                    emission.inputs['Color'].default_value = (value,value,value,1)
                else:
                    tree.links.new(value,emission.inputs['Color'])
                tree.links.new(emission.outputs[0],output.inputs['Surface'])
            bpy.ops.object.select_all(action='DESELECT')
            for obj in objects:
                if mat in list(obj.data.materials):
                    active(obj)
                    bpy.ops.object.bake(type='NORMAL' if kind=='normal' else 'EMIT')
            image.file_format='PNG'
            image.filepath_raw=str(cache/(name+'.png')); image.save(); image.pack()
            scalar_images[kind]=image
            if kind in ('base_color','normal'):
                images[f'{part}_{kind}']=image
        # Pack AO=1, roughness=G, metallic=B. Gaps/crevices are actual geometry.
        if part != 'card':
            r=array('f',[0])* (size*size*4); m=array('f',[0])*len(r)
            scalar_images['roughness'].pixels.foreach_get(r)
            scalar_images['metallic'].pixels.foreach_get(m)
            pixels=array('f',[1])*len(r)
            for i in range(0,len(r),4):
                pixels[i+1]=r[i]; pixels[i+2]=m[i]
            images[f'{part}_orm']=image_from_pixels(ASSET_ID,f'{part}_orm',size,pixels,cache,non_color=True)
        tree.nodes.clear()
        output=tree.nodes.new('ShaderNodeOutputMaterial')
        bsdf=tree.nodes.new('ShaderNodeBsdfPrincipled')
        tree.links.new(bsdf.outputs[0],output.inputs['Surface'])
        base_texture(mat,images[f'{part}_base_color'])
        if part == 'card':
            bsdf.inputs['Roughness'].default_value=.85
        else:
            orm_texture(mat,images[f'{part}_orm'])
            normal_texture(mat,images[f'{part}_normal'])
        # Restore an active scratch target for bakes of subsequent materials.
        scratch=tree.nodes.new('ShaderNodeTexImage'); scratch.image=bpy.data.images.get('scratch_'+mat.name)
        tree.nodes.active=scratch
    # Strip unused scratch image nodes from final Principled-only materials.
    for mat in sources:
        for node in list(mat.node_tree.nodes):
            if node.type=='TEX_IMAGE' and not node.outputs['Color'].is_linked:
                mat.node_tree.nodes.remove(node)
    return images


def build(out_dir):
    reset_scene(SEED)
    cache=ROOT/'assets/cache'/ASSET_ID; cache.mkdir(parents=True,exist_ok=True)
    paint,metal,interior,card,sources=procedural_materials()
    objects=geometry((paint,metal,interior,card))
    unwrap(objects,sources)
    bake_materials_result=bake_materials(objects,sources,cache)
    for obj in objects:
        triangulate(obj)
    bpy.context.view_layer.update()
    glb_path=Path(out_dir).resolve()/f'{ASSET_ID}.glb'
    gltf=export_glb(glb_path,objects)
    anchors={'carcass_back_z':.30+SHIFT_Z,'carcass_front_z':-.30+SHIFT_Z,
             'drawer_top':[0,.85,-.32+SHIFT_Z], 'keypad_mount':[0,1.12,-.30+SHIFT_Z],
             'label_card_top':[0,.907,-.3218+SHIFT_Z]}
    for node in gltf['nodes']:
        if node.get('scale',[1,1,1]) != [1,1,1] or node.get('rotation',[0,0,0,1]) != [0,0,0,1]:
            raise RuntimeError('Unapplied transform '+node['name'])
        if node['name']=='drawer_top' and any(abs(a-b)>1e-6 for a,b in zip(node['translation'],anchors['drawer_top'])):
            raise RuntimeError('Wrong top drawer origin')
    anchors = {key: [round(v, 9) for v in value] if isinstance(value, list) else round(value, 9)
               for key, value in anchors.items()}
    textures=[{'name':im.name,'size':list(im.size),'map':key,'embedded':True}
              for key,im in sorted(bake_materials_result.items())]
    meta=write_metadata(ASSET_ID,ROOT/'assets/meta'/f'{ASSET_ID}.json',glb_path,objects,Path(__file__),textures,'base_center',extra={
        'anchors_godot_m':anchors,'carcass_translation_godot_m':[0,0,SHIFT_Z],
        'forward':'Blender +Y -> Godot -Z', 'collision':None,
        'render':{'engine':'CYCLES','device':'CPU','samples':32,'denoise':True,'threads':4},
        'baking':{'method':'procedural_to_texture','margin_px':8,'orm':'R=1 (AO neutral), G=roughness, B=metallic'},
        'glb_path':str(glb_path.relative_to(ROOT)) if glb_path.is_relative_to(ROOT) else str(glb_path)})
    if meta['triangles']>60000 or len(meta['materials'])>4 or set(meta['parts'])!={'body','drawer_top','drawer_mid','drawer_low'}:
        raise RuntimeError('Request budget/parts violated')
    # A dict hook moves only the named drawer just before common/preview.py
    # renders the third view. Export and metadata always describe closed state.
    drawer_top=next(o for o in objects if o.name=='drawer_top')
    closed=drawer_top.location.copy()
    class Views(dict):
        def __getitem__(self,key):
            if key=='detail':
                drawer_top.location.y=closed.y+.40
                bpy.context.view_layer.update()
            return super().__getitem__(key)
    try:
        render_previews(ASSET_ID,ROOT/'assets/previews',objects,Views({
            'front':{'position':(0,3,.60),'target':(0,0,.60),'scale':1.40},
            'iso':{'position':(1.8,2.7,1.85),'target':(0,0,.61),'scale':1.55},
            'detail':{'position':(.82,1.8,2.25),'target':(0,.34,.88),'scale':.87}}),seed=SEED)
    finally:
        drawer_top.location=closed
        bpy.context.view_layer.update()
    print(f'ASSET BUILT: {glb_path}; {meta["triangles"]} triangles; {len(meta["materials"])} materials')
    return glb_path


if __name__=='__main__':
    run_cli(build,__doc__)
