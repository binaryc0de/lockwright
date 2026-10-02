"""Original, worn 14-inch business laptop; deterministic Blender 5.2 build.

blender -b --factory-startup --threads 4 -noaudio --python-exit-code 1
  --python tools/blender/props/laptop_open.py -- --out game/assets/core/props
Only bpy, mathutils, stdlib and shared pipeline helpers; no downloads.
"""
from array import array
import hashlib
import math
from pathlib import Path
import random
import sys

import bpy
from mathutils import Vector, Matrix

sys.dont_write_bytecode = True
TOOLS = Path(__file__).resolve().parents[1]
ROOT = TOOLS.parents[1]
sys.path.insert(0, str(TOOLS))
from common.cli import run_cli
from common.export import export_glb, write_metadata
from common.geometry import active, box, join_static, mesh_object, triangulate
from common.materials import material, image_from_pixels, base_texture, normal_texture, orm_texture
from common.preview import render_previews, point_at
from common.scene import reset_scene

ASSET_ID = 'laptop_open'
SEED = 332105
ANGLE = math.radians(15)
# An original compact 5x7 pixel alphabet. Raster artwork is part of this script,
# independent of system fonts and licensing or installation of external files.
FONT = {
'A': ['01110','10001','10001','11111','10001','10001','10001'],
'B': ['11110','10001','10001','11110','10001','10001','11110'],
'C': ['01111','10000','10000','10000','10000','10000','01111'],
'D': ['11110','10001','10001','10001','10001','10001','11110'],
'E': ['11111','10000','10000','11110','10000','10000','11111'],
'F': ['11111','10000','10000','11110','10000','10000','10000'],
'G': ['01111','10000','10000','10111','10001','10001','01111'],
'H': ['10001','10001','10001','11111','10001','10001','10001'],
'I': ['11111','00100','00100','00100','00100','00100','11111'],
'J': ['00111','00010','00010','00010','10010','10010','01100'],
'K': ['10001','10010','10100','11000','10100','10010','10001'],
'L': ['10000','10000','10000','10000','10000','10000','11111'],
'M': ['10001','11011','10101','10101','10001','10001','10001'],
'N': ['10001','11001','11001','10101','10011','10011','10001'],
'O': ['01110','10001','10001','10001','10001','10001','01110'],
'P': ['11110','10001','10001','11110','10000','10000','10000'],
'Q': ['01110','10001','10001','10001','10101','10010','01101'],
'R': ['11110','10001','10001','11110','10100','10010','10001'],
'S': ['01111','10000','10000','01110','00001','00001','11110'],
'T': ['11111','00100','00100','00100','00100','00100','00100'],
'U': ['10001','10001','10001','10001','10001','10001','01110'],
'V': ['10001','10001','10001','10001','10001','01010','00100'],
'W': ['10001','10001','10001','10101','10101','10101','01010'],
'X': ['10001','10001','01010','00100','01010','10001','10001'],
'Y': ['10001','10001','01010','00100','00100','00100','00100'],
'Z': ['11111','00001','00010','00100','01000','10000','11111'],
'0': ['01110','10001','10011','10101','11001','10001','01110'],
'1': ['00100','01100','00100','00100','00100','00100','01110'],
'2': ['01110','10001','00001','00010','00100','01000','11111'],
'3': ['11110','00001','00001','01110','00001','00001','11110'],
'4': ['00010','00110','01010','10010','11111','00010','00010'],
'5': ['11111','10000','10000','11110','00001','00001','11110'],
'6': ['01110','10000','10000','11110','10001','10001','01110'],
'7': ['11111','00001','00010','00100','01000','01000','01000'],
'8': ['01110','10001','10001','01110','10001','10001','01110'],
'9': ['01110','10001','10001','01111','00001','00001','01110'],
'-': ['00000','00000','00000','11111','00000','00000','00000'],
'=': ['00000','00000','11111','00000','11111','00000','00000'],
'/': ['00001','00001','00010','00100','01000','10000','10000'],
'[': ['01110','01000','01000','01000','01000','01000','01110'],
']': ['01110','00010','00010','00010','00010','00010','01110'],
';': ['00000','00100','00100','00000','00100','00100','01000'],
"'": ['00100','00100','00000','00000','00000','00000','00000'],
',': ['00000','00000','00000','00000','00100','00100','01000'],
'.': ['00000','00000','00000','00000','00000','00100','00100'],
'`': ['01000','00100','00000','00000','00000','00000','00000'],
'\\': ['10000','10000','01000','00100','00010','00001','00001'],
' ': ['00000'] * 7,
}


def rect(pixels, size, bounds, color):
    x0,y0,x1,y1 = bounds
    for y in range(max(0,int(y0)), min(size,int(y1))):
        for x in range(max(0,int(x0)), min(size,int(x1))):
            k = 4 * (y * size + x)
            pixels[k:k+4] = array('f', (*color, 1))


def text(pixels, size, string, centre, height, color):
    unit = height / 7
    left = centre[0] - (6 * len(string) - 1) * unit / 2
    bottom = centre[1] - height / 2
    for i,char in enumerate(string):
        for row, bits in enumerate(FONT[char]):
            for col, bit in enumerate(bits):
                if bit == '1':
                    rect(pixels, size, (left+(i*6+col)*unit, bottom+(6-row)*unit,
                                       left+(i*6+col+1)*unit, bottom+(7-row)*unit), color)


def make_textures(cache, layout):
    """Rasterise original procedural surfaces: color, micro-normal, packed ORM.

    No procedural shader nodes remain in the GLB: every generated surface is
    baked into PNGs in linear working space before export (8px atlas gutters).
    """
    rng = random.Random(SEED)
    size = 1024
    color, normal, orm = array('f'), array('f'), array('f')
    for y in range(size):
        for x in range(size):
            grain = rng.uniform(-1,1)
            cloud = .5*math.sin(x*.023+math.sin(y*.017)) + .5*math.sin(y*.031)
            # Top deck lower-left island, underside lower-right, lid back
            # upper-left, bezel upper-right. Palms on the +Y/user side.
            u,v = (x/size-.02)/.46, (y/size-.02)/.46
            palms = 0
            if x < size*.49 and y < size*.49:
                for cx,cy in ((.20,.84),(.79,.84)):
                    palms += math.exp(-(((u-cx)/.13)**2+((v-cy)/.11)**2)*2)
            edge = max(0,1-min(u,1-u,v,1-v)/.02) if 0<u<1 and 0<v<1 else 0
            base = .008 + grain*.0007 + cloud*.0003 + palms*.0008 + edge*.0005
            rough = .64 + grain*.020 + cloud*.008 - palms*.10 - edge*.025
            metal = 0.025
            if x/size > .51 and y/size < .49:
                base *= .68
                rough = .56 + grain*.02
            # Reserved spine through atlas centre: hardware palette.
            if .490 < x/size < .510:
                if y/size < .33:
                    base,rough,metal = .0015+grain*.0002,.73+grain*.02,0
                elif y/size < .66:
                    base,rough,metal = .12+grain*.008,.32+grain*.025,.8
                else:
                    base,rough,metal = .004+grain*.0003,.56+grain*.02,.02
            color.extend((base*.94,base*.99,base*1.04,1))
            orm.extend((1,max(.2,min(.85,rough)),metal,1))
            normal.extend((.5+grain*.012,.5+rng.uniform(-.012,.012),.999,1))
    # Very fine scratches in paint, mostly near front edge and case corners.
    for _ in range(32):
        x=rng.randint(28,480); y=rng.choice((rng.randint(24,37),rng.randint(461,486)))
        length=rng.randint(2,18)
        for dx in range(length):
            k=(y*size+min(size-1,x+dx))*4
            color[k:k+3]=array('f',(.016,.017,.018))
            orm[k+1]=.40
    images={
        'shell_base_color':image_from_pixels(ASSET_ID,'shell_base_color',size,color,cache),
        'shell_normal':image_from_pixels(ASSET_ID,'shell_normal',size,normal,cache,True),
        'shell_orm':image_from_pixels(ASSET_ID,'shell_orm',size,orm,cache,True),
    }
    size=2048
    keys=array('f',(.002,.0022,.0025,1))*(size*size)
    keyorm=array('f',(1,.69,0,1))*(size*size)
    keynormal=array('f',(.5,.5,1,1))*(size*size)
    rectangles=[]
    for index,(legend,width,row) in enumerate(layout):
        column,slotrow=index%8,index//8
        x0,y0=column*256+16,slotrow*192+16
        w,h=224,160
        # A shallow polished dish varies for frequently used caps.
        used=legend in ('A','S','D','E','R','T','N','O','I','SPACE','ENTER')
        for yy in range(h):
            for xx in range(w):
                k=((y0+yy)*size+x0+xx)*4
                g=rng.uniform(-1,1)
                shine=math.exp(-(((xx/w-.50)/.30)**2+((yy/h-.50)/.35)**2)*2)
                b=.0025 + g*.0002 + (shine*.0006 if used else 0)
                keys[k:k+3]=array('f',(b*.9,b*.96,b))
                keyorm[k+1]=.68 + g*.025 - shine*(.14 if used else .055)
                keynormal[k:k+3]=array('f',(.5+g*.013,.5+rng.uniform(-.012,.012),1))
        # Single letters sit at the key's upper-left, standard business layout.
        height=35 if len(legend)==1 else 19
        if legend=='SPACE':
            pass
        else:
            # Anamorphic atlas compensates for wide modifier keys.
            htxt=height
            cx=x0+w*.5 if len(legend)>1 else x0+w*.34
            cy=y0+h*.58 if len(legend)>1 else y0+h*.66
            text(keys,size,legend,(cx,cy),htxt,(.68,.70,.69))
        rectangles.append((x0/size,y0/size,(x0+w)/size,(y0+h)/size))
    # Seeded specks remain sparse, not a dirt-covered abandoned machine.
    for _ in range(115):
        x=rng.randint(18,size-18); y=rng.randint(18,1880)
        rect(keys,size,(x,y,x+2,y+2),(.09,.087,.08))
    images.update({
        'keys_base_color':image_from_pixels(ASSET_ID,'keys_base_color',size,keys,cache),
        'keys_orm':image_from_pixels(ASSET_ID,'keys_orm',size,keyorm,cache,True),
        'keys_normal':image_from_pixels(ASSET_ID,'keys_normal',size,keynormal,cache,True),
    })
    size=1024
    tag=array('f',(.68,.675,.61,1))*(size*size)
    tagorm=array('f',(1,.63,0,1))*(size*size)
    for y in range(size):
        for x in range(size):
            k=(y*size+x)*4
            speck=rng.uniform(-.025,.025)
            edge=min(x,size-1-x,y,size-1-y)
            yellow=max(0,1-edge/40)*.07
            for c in range(3):
                tag[k+c]+=speck-yellow
    ink=(.009,.012,.014)
    text(tag,size,'KL-LT-0332',(512,730),113,ink)
    text(tag,size,'PROPERTY OF KESTREL',(512,940),39,ink)
    text(tag,size,'IT ASSET / 2023',(512,160),42,ink)
    # Original Code 39 barcode; start/stop + exact asset identifier (no flag).
    patterns={'*':'nwnnwnwnn','K':'wnnnnwnnw','L':'nnwnnwnnw',
              '-':'nwnnnnwnw','T':'nnnnwwnnw','0':'nnnwwnwnn',
              '3':'wnwwnnnnn','2':'nnwwnnnnw'}
    sequence='*KL-LT-0332*'
    units=sum(sum(3 if c=='w' else 1 for c in patterns[ch])+1 for ch in sequence)-1
    step=844/units; x=90
    for ch in sequence:
        for i,mode in enumerate(patterns[ch]):
            span=step*(3 if mode=='w' else 1)
            if i%2==0:
                rect(tag,size,(x,280,x+span,574),ink)
            x+=span
        x+=step
    images['sticker_base_color']=image_from_pixels(ASSET_ID,'sticker_base_color',size,tag,cache)
    images['sticker_orm']=image_from_pixels(ASSET_ID,'sticker_orm',size,tagorm,cache,True)
    return images,rectangles


def rounded_outline(width,depth,radius,steps=8):
    pts=[]
    for cx,cy,start in ((width/2-radius,depth/2-radius,0),
                        (-width/2+radius,depth/2-radius,90),
                        (-width/2+radius,-depth/2+radius,180),
                        (width/2-radius,-depth/2+radius,270)):
        for i in range(steps+1):
            a=math.radians(start+90*i/steps)
            pts.append((cx+math.cos(a)*radius,cy+math.sin(a)*radius))
    return pts


def rounded_slab(name,width,depth,zprofiles,mat,radius=.005,steps=8):
    """Closed, bevel-profile shell with true rounded plan corners and quad bands."""
    verts=[]
    for z,inset in zprofiles:
        verts.extend((x,y,z) for x,y in rounded_outline(width-2*inset,depth-2*inset,
                                                     max(radius-inset,.0001),steps))
    n=len(verts)//len(zprofiles)
    faces=[tuple(reversed(range(n)))]
    for row in range(len(zprofiles)-1):
        a,b=row*n,(row+1)*n
        for i in range(n):
            j=(i+1)%n
            faces.append((a+i,a+j,b+j,b+i))
    faces.append(tuple(range((len(zprofiles)-1)*n,len(zprofiles)*n)))
    obj=mesh_object(name,verts,faces,mat)
    for f in obj.data.polygons:
        f.use_smooth=len(f.vertices)==4
    active(obj)
    mod=obj.modifiers.new('area_normals','WEIGHTED_NORMAL'); mod.keep_sharp=True
    bpy.ops.object.modifier_apply(modifier=mod.name)
    return obj


def uv_xy(obj,top_rect=(.02,.02,.48,.48),bottom_rect=(.52,.02,.98,.48),width=None,depth=None,flip_v=False):
    uv=obj.data.uv_layers.new(name='UVMap')
    width=width or obj.dimensions.x; depth=depth or obj.dimensions.y
    for face in obj.data.polygons:
        r=top_rect if face.normal.z>.999 else bottom_rect if face.normal.z<-.999 else (.493,.72,.507,.96)
        for loop in face.loop_indices:
            p=obj.data.vertices[obj.data.loops[loop].vertex_index].co
            uv.data[loop].uv=(r[0]+(.5-p.x/width)*(r[2]-r[0]),r[1]+(.5+(-p.y if flip_v else p.y)/depth)*(r[3]-r[1]))


def clear_uv(obj):
    for layer in list(obj.data.uv_layers):
        obj.data.uv_layers.remove(layer)


def palette(obj,kind='dark'):
    uv=obj.data.uv_layers.new(name='UVMap')
    v={'dark':.16,'metal':.49,'soft':.82}[kind]
    for face in obj.data.polygons:
        # Palette rectangles intentionally shared by repeated hardware,
        # not high-to-low surface baking or unique artwork.
        axes=sorted(range(3),key=lambda a:abs(face.normal[a]))[:2]
        pts=[obj.data.vertices[i].co for i in face.vertices]
        lo=[min(p[a] for p in pts) for a in axes]; hi=[max(p[a] for p in pts) for a in axes]
        for loop in face.loop_indices:
            p=obj.data.vertices[obj.data.loops[loop].vertex_index].co
            uvs=[(p[a]-l)/max(h-l,1e-9) for a,l,h in zip(axes,lo,hi)]
            uv.data[loop].uv=(.494+uvs[0]*.012,v-.065+uvs[1]*.13)


def cylinder(name,radius,length,mat,loc,axis='Z',count=32):
    verts=[]
    for z in (-length/2,length/2):
        for i in range(count):
            a=i*math.tau/count
            p=Vector((radius*math.cos(a),radius*math.sin(a),z))
            if axis=='X': p=Vector((p.z,p.x,p.y))
            if axis=='Y': p=Vector((p.x,p.z,p.y))
            verts.append(tuple(p))
    faces=[tuple(reversed(range(count))),tuple(range(count,2*count))]
    for i in range(count):
        j=(i+1)%count; faces.append((i,j,count+j,count+i))
    obj=mesh_object(name,verts,faces,mat,loc)
    for f in obj.data.polygons: f.use_smooth=len(f.vertices)==4
    palette(obj)
    return obj


def cut_box(obj,name,dims,loc,bevel=.0005):
    cutter=box(name+'-noimp',dims,None,loc,bevel=bevel,segments=3)
    active(obj); mod=obj.modifiers.new(name,'BOOLEAN')
    mod.operation='DIFFERENCE'; mod.solver='EXACT'; mod.object=cutter
    bpy.ops.object.modifier_apply(modifier=mod.name)
    bpy.data.objects.remove(cutter,do_unlink=True)


def board_layout():
    rows=[
        [('ESC',1),*[(f'F{i}',.9) for i in range(1,13)],('DEL',1.2)],
        [('`',1),*[(str(i),1) for i in range(1,10)],('0',1),('-',1),('=',1),('BKSP',2)],
        [('TAB',1.5),*[(c,1) for c in 'QWERTYUIOP'],('[',1),(']',1),('\\',1.5)],
        [('CAPS',1.8),*[(c,1) for c in 'ASDFGHJKL'],(';',1),("'",1),('ENTER',2.2)],
        [('SHIFT',2.3),*[(c,1) for c in 'ZXCVBNM'],(',',1),('.',1),('/',1),('SHIFT',2.7)],
        [('CTRL',1.25),('FN',1),('SYS',1.25),('ALT',1.25),('SPACE',5.5),('ALT',1.25),('CTRL',1.25),('LEFT',1),('UP',1),('RIGHT',1)],
    ]
    return rows,[(label,width,row) for row,keys in enumerate(rows) for label,width in keys]+[('DOWN',1,5)]


def make_detail(cache,objects):
    """Two render panels: keyboard close-up and reverse-side asset tag.

    Both use the same neutral studio and three-point light specification as
    common/preview.py; the final 1024px contact sheet is a preview artifact.
    """
    scene=bpy.context.scene
    keyboard=bpy.data.images.load(str(ROOT/'assets/previews/laptop_open_detail.png'))
    keyboard_pixels=array('f',[0])*len(keyboard.pixels); keyboard.pixels.foreach_get(keyboard_pixels)
    scene.render.resolution_y=384
    data=bpy.data.cameras.new('tag_camera-noimp'); data.type='ORTHO'; data.ortho_scale=.092
    data.clip_start=.001; data.clip_end=10
    cam=bpy.data.objects.new('tag_camera-noimp',data); scene.collection.objects.link(cam); scene.camera=cam
    tagcentre=objects[1].matrix_world @ Vector((-.090,-.00325,.158))
    normal=Vector((0,-math.cos(ANGLE),-math.sin(ANGLE)))
    cam.location=tagcentre+normal*.40; point_at(cam,tagcentre)
    helpers=[cam]
    centre=Vector((0,0,.12)); factor=.33/.115
    for name,position,power,size in (('key',(.13,.18,.18),3,.15),('fill',(-.14,.12,.025),1.2,.12),('rim',(-.035,-.10,.16),2,.10)):
        ld=bpy.data.lights.new('tag_'+name+'-noimp','AREA'); ld.energy=power*factor*factor; ld.shape='DISK'; ld.size=size*factor
        light=bpy.data.objects.new('tag_'+name+'-noimp',ld); scene.collection.objects.link(light)
        light.location=centre+Vector((position[0],position[1]-.01,position[2]))*factor
        point_at(light,tagcentre); helpers.append(light)
    scene.render.filepath=str(cache/'tag_detail.png')
    bpy.ops.render.render(write_still=True)
    tag=bpy.data.images.load(str(cache/'tag_detail.png'))
    tag_pixels=array('f',[0])*len(tag.pixels); tag.pixels.foreach_get(tag_pixels)
    output=array('f',[0])*(1024*1024*4)
    # Bottom 384px: reverse tag. Upper 640px: central crop of keyboard.
    output[:1024*384*4]=tag_pixels
    output[1024*384*4:]=keyboard_pixels[1024*192*4:1024*832*4]
    # Neutral separation rule.
    for yy in range(382,388):
        for xx in range(1024):
            k=(yy*1024+xx)*4; output[k:k+4]=array('f',(.09,.09,.09,1))
    img=image_from_pixels(ASSET_ID,'detail_contact_sheet',1024,output,cache)
    img.filepath_raw=str(ROOT/'assets/previews/laptop_open_detail.png'); img.save()
    for helper in helpers: bpy.data.objects.remove(helper,do_unlink=True)
    scene.render.resolution_y=1024


def build(out_dir):
    reset_scene(SEED)
    cache=ROOT/'assets/cache'/ASSET_ID; cache.mkdir(parents=True,exist_ok=True)
    rows,layout=board_layout()
    images,keyrects=make_textures(cache,layout)
    shell=material(ASSET_ID,'shell',(.026,.028,.030),roughness=.61)
    base_texture(shell,images['shell_base_color']); orm_texture(shell,images['shell_orm']); normal_texture(shell,images['shell_normal'],.22)
    keys=material(ASSET_ID,'keys',(.008,.009,.01),roughness=.68)
    base_texture(keys,images['keys_base_color']); orm_texture(keys,images['keys_orm']); normal_texture(keys,images['keys_normal'],.24)
    screenmat=material(ASSET_ID,'screen',(.0015,.003,.006),roughness=.18,emission=((.024,.047,.073),.15))
    sticker=material(ASSET_ID,'sticker',(.68,.67,.61),roughness=.63)
    base_texture(sticker,images['sticker_base_color']); orm_texture(sticker,images['sticker_orm'])
    baseparts=[]
    bottom=rounded_slab('lower_case',.33,.23,[(.002,.001),(.003,0),(.0144,0),(.0148,.0003)],shell)
    uv_xy(bottom); baseparts.append(bottom)
    # Actual USB-A, USB-C, HDMI and ventilation cavities, not painted bars.
    for side,yy,ww,hh in ((-1,-.065,.014,.005),(-1,-.040,.009,.003),(-1,-.011,.015,.004),
                          (1,-.050,.014,.005),(1,-.022,.014,.005)):
        cut_box(bottom,f'port_{side}_{yy}',(.008,ww,hh),(side*.163,yy,.0084),.00055)
        inner=box('port_lining',(.001,ww*.90,hh*.80),shell,(side*.160,yy,.0084),bevel=.0003)
        palette(inner,'metal'); baseparts.append(inner)
        if ww==.014:
            tongue=box('usb_tongue',(.003,ww*.72,.001),shell,(side*.162,yy,.0084),bevel=.00015)
            palette(tongue); baseparts.append(tongue)
    for i in range(12):
        yy=.008+i*.0057
        cut_box(bottom,'exhaust',(.008,.0028,.0048),(-.163,yy,.008),.0004)
    # Recompute UVs on generated port walls. UV layers cleared to avoid stale
    # boolean-generated loops carrying unrelated main face coordinates.
    clear_uv(bottom); uv_xy(bottom)
    seam=rounded_slab('case_seam',.3298,.2298,[(.0148,0),(.01535,0)],shell,radius=.0049)
    palette(seam); baseparts.append(seam)
    deck=rounded_slab('upper_deck',.33,.23,[(.01535,.0005),(.0163,0),(.0175,0),(.018,.0007)],shell)
    # Keyboard is a recessed well, not loose keys floating on a flat slab.
    cut_box(deck,'keyboard_well',(.296,.122,.006),(0,-.035,.020),.0020)
    cut_box(deck,'touchpad_well',(.107,.054,.005),(0,.068,.0195),.0021)
    uv_xy(deck); baseparts.append(deck)
    well=box('keyboard_tray',(.294,.120,.002),shell,(0,-.035,.0161),bevel=.0022,segments=4)
    palette(well); baseparts.append(well)
    def add_cap(atlas_index, width, depth, x, y):
        cap=rounded_slab('keycap',width,depth,[(.0171,.0004),(.0176,0),(.0193,.0003),(.0197,.0009)],keys,radius=.00145,steps=4)
        uv_xy(cap,keyrects[atlas_index],(.02,.945,.05,.97),width,depth,flip_v=True)
        uv=cap.data.uv_layers.active
        for face in cap.data.polygons:
            if face.normal.z<.999:
                for loop in face.loop_indices: uv.data[loop].uv=(.01,.98)
        cap.location=(x,y,0)
        baseparts.append(cap)
    index=0
    for row,keyrow in enumerate(rows):
        total=sum(w for _,w in keyrow); pitch=.285/total
        xx=.1425
        yy=-.083+row*.0195
        for legend,unit in keyrow:
            width=pitch*unit-.0018
            xx-=pitch*unit/2
            if legend=='UP':
                add_cap(index,width,.0073,xx,yy-.0045)
                add_cap(len(layout)-1,width,.0073,xx,yy+.0045)
            else:
                add_cap(index,width,.0120 if row==0 else .0165,xx,yy)
            index+=1; xx-=pitch*unit/2
    touch=rounded_slab('touchpad',.104,.051,[(.0168,.0002),(.01765,0)],shell,radius=.002)
    uv_xy(touch,top_rect=(.52,.02,.98,.48),width=.104,depth=.051); touch.location=(0,.068,0); baseparts.append(touch)
    # Touchpad click separation is engraved, with a narrow reveal at front.
    line=box('touchpad_clickline',(.100,.00032,.00015),shell,(0,.085,.01774))
    palette(line); baseparts.append(line)
    # Speaker perforations; sparse geometry, continuous darkness in the holes.
    for side in (-1,1):
        for row in range(3):
            for col in range(20):
                dot=cylinder('speaker_hole',.00048,.00012,shell,(side*(.026+col*.0044),-.104+row*.0018,.0181),count=8)
                baseparts.append(dot)
    power=cylinder('power_button',.0027,.00065,shell,(-.145,-.103,.01825),count=32)
    baseparts.append(power)
    led=box('status_lens',(.002,.0007,.0003),screenmat,(-.135,-.103,.01835),bevel=.0002)
    baseparts.append(led)
    # Rubber feet establish the underside y=0. Service screws + lower grille.
    for xx in (-.125,.125):
        for yy in (-.088,.088):
            foot=rounded_slab('rubber_foot',.028,.010,[(0,.0008),(.0015,0),(.0025,.0005)],shell,radius=.004,steps=5)
            palette(foot); foot.location=(xx,yy,0); baseparts.append(foot)
    for xx,yy in ((-.147,-.095),(.147,-.095),(-.147,.095),(.147,.095),(0,.092),(0,-.092)):
        screw=cylinder('service_screw',.00175,.00012,shell,(xx,yy,.00195),count=24)
        clear_uv(screw); palette(screw,'metal'); baseparts.append(screw)
        slit=box('screw_slot',(.0025,.0004,.00012),shell,(xx,yy,.00187))
        palette(slit); baseparts.append(slit)
    for i in range(24):
        slot=box('underside_vent',(.0015,.039,.00015),shell,(-.059+i*.0051,-.049,.00185),bevel=.0005)
        palette(slot); baseparts.append(slot)
    # Hinge barrels share shell's satin-metal palette and retain proper scale.
    for xx in (-.111,.111):
        barrel=cylinder('hinge_barrel',.0039,.036,shell,(xx,-.112,.0185),axis='X',count=40)
        clear_uv(barrel); palette(barrel,'metal'); baseparts.append(barrel)
        for dx in (-.017,.017):
            band=cylinder('hinge_end',.004,.001,shell,(xx+dx,-.112,.0185),axis='X',count=32)
            baseparts.append(band)
    base=join_static(baseparts,'base')
    # Lid is authored locally, 0..220mm up from its hinge. Its shell back is
    # local -Y; front bezel is local +Y, screen 0.5mm forward of that plane.
    lidparts=[]
    lid_shell=rounded_slab('lid_shell',.33,.22,[(-.003,.0007),(-.0024,0),(.0024,0),(.003,.0007)],shell,radius=.005)
    # Slab originally lies XY with thickness Z; orient to XZ, front +Y.
    for v in lid_shell.data.vertices:
        p=v.co.copy(); v.co=(p.x,-p.z,p.y+.11)
    lid_shell.data.update()
    # True bezel opening makes a 0.300x0.188m rectangular display recess.
    cut_box(lid_shell,'display_opening',(.300,.005,.188),(0,.0035,.11),.0001)
    clear_uv(lid_shell)
    uv=lid_shell.data.uv_layers.new(name='UVMap')
    for face in lid_shell.data.polygons:
        front=face.normal.y>0
        r=(.52,.52,.98,.98) if front else (.02,.52,.48,.98)
        for loop in face.loop_indices:
            p=lid_shell.data.vertices[lid_shell.data.loops[loop].vertex_index].co
            u=.5-p.x/.33 if front else .5+p.x/.33
            uv.data[loop].uv=(r[0]+u*(r[2]-r[0]),r[1]+p.z/.22*(r[3]-r[1]))
    lidparts.append(lid_shell)
    # Recessed 2mm webcam + pinhole mic, plain bezel without brand lettering.
    for xx,radius in ((0,.0011),(.008,.00035)):
        lens=cylinder('webcam',radius,.00018,shell,(xx,.00316,.211),axis='Y',count=24)
        lidparts.append(lens)
    # Sticker adheres to lid back, with a slight raised vinyl edge.
    tag=box('asset_tag',(.066,.00015,.025),sticker,(-.090,-.00312,.158),bevel=.00035,segments=3)
    uv=tag.data.uv_layers.new(name='UVMap')
    for f in tag.data.polygons:
        for loop in f.loop_indices:
            p=tag.data.vertices[tag.data.loops[loop].vertex_index].co
            # From behind, +X is to the viewer's right.
            uv.data[loop].uv=(.5+p.x/.066,.5+p.z/.025)
    lidparts.append(tag)
    lid=join_static(lidparts,'lid')
    lid.rotation_euler.x=ANGLE
    hinge=Vector((0,-.112,.0185)); lid.location=hinge
    # Local plane and UV axes match Godot screen normal local -Z.
    display=mesh_object('screen',[(-.15,0,-.094),(.15,0,-.094),(.15,0,.094),(-.15,0,.094)],[(0,3,2,1)],screenmat)
    uv=display.data.uv_layers.new(name='UVMap')
    for loop,coord in zip(display.data.polygons[0].loop_indices,((1,0),(1,1),(0,1),(0,0))):
        uv.data[loop].uv=coord
    display.rotation_euler.x=ANGLE
    display.location=hinge+Matrix.Rotation(ANGLE,3,'X')@Vector((0,.0035,.11))
    objects=[base,lid,display]
    bpy.context.view_layer.update()
    # Overall bbox footprint, not lower-case footprint, is centred at origin.
    # Match the transformed accessor bounds used by metadata/assetcheck.
    ys=[(obj.matrix_world@Vector(corner)).y for obj in objects for corner in obj.bound_box]
    shift=(min(ys)+max(ys))/2
    for obj in objects: obj.location.y-=shift
    # Static base origin is the overall footprint centre at the floor plane;
    # only hinge/display parts retain their specifically requested origins.
    for vertex in base.data.vertices:
        vertex.co+=base.location
    base.location=(0,0,0)
    for obj in objects: triangulate(obj)
    bpy.context.view_layer.update()
    glbpath=Path(out_dir).resolve()/f'{ASSET_ID}.glb'
    gltf=export_glb(glbpath,objects)
    centre=display.location
    normal=display.rotation_euler.to_matrix()@Vector((0,1,0))
    godot=lambda p:[round(p.x,9),round(p.z,9),round(-p.y,9)]
    meta=write_metadata(ASSET_ID,ROOT/'assets/meta/laptop_open.json',glbpath,objects,Path(__file__),
        [{'name':img.name,'size':list(img.size),'map':name,'embedded':True} for name,img in sorted(images.items())],
        origin='base_center',extra={
            'forward':'Blender +Y -> Godot -Z',
            'anchors_godot_m':{'screen_centre':godot(centre),'screen_normal':godot(normal),'screen_size':[.300,.188]},
            'part_origins_godot_m':{obj.name:godot(obj.location) for obj in objects},
            'lid_angle_from_base_degrees':105,
            'screen_offset_from_bezel_m':.0005,
            'collision':None,
            'render':{'engine':'CYCLES','device':'CPU','samples':32,'denoise':True,'threads':4},
            'texture_generation':'seeded original procedural raster bake; no high-to-low bake',
            'legend_font':'original_5x7_sans',
            'glb_path':str(glbpath.relative_to(ROOT)) if glbpath.is_relative_to(ROOT) else str(glbpath),
        })
    if meta['triangles']>60000 or len(meta['materials'])>4: raise RuntimeError('Request budget exceeded')
    if set(meta['parts'])!={'base','lid','screen'}: raise RuntimeError('Incorrect named mesh set')
    for node in gltf['nodes']:
        if node.get('scale',[1,1,1])!=[1,1,1]: raise RuntimeError('Unapplied scale')
    if len(gltf.get('animations',[])): raise RuntimeError('Unexpected animation')
    render_previews(ASSET_ID,ROOT/'assets/previews',objects,views={
        'front':{'position':(0,.78,.39),'target':(0,-.025,.115),'scale':.405},
        'iso':{'position':(-.54,.67,.46),'target':(0,-.018,.113),'scale':.49},
        'detail':{'position':(0,.37,.88),'target':(0,.010,.018),'scale':.345},
    },seed=SEED)
    make_detail(cache,objects)
    print(f'ASSET BUILT: {glbpath}; {meta["triangles"]} triangles; {len(meta["materials"])} materials')
    return glbpath


if __name__=='__main__':
    run_cli(build,__doc__)
