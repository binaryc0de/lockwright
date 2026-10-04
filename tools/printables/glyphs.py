"""Original prop-matching glyph geometry, transcribed from R5 prop sources.

Coordinates are upright, +Y up. Heraldic u is Godot X (viewer-left); MASON u
is viewer-right as specified in the gate source. No bpy import or runtime
prop dependency.
"""
import math

MASON = {
 'arrow': [[(0,-.5),(0,.5)],[(-.4,.1),(0,.5),(.4,.1)]],
 'hourglass': [[(-.4,.5),(.4,.5),(0,0),(-.4,.5)],
               [(-.4,-.5),(.4,-.5),(0,0),(-.4,-.5)]],
 'trident': [[(0,-.5),(0,.5)],[(-.4,.5),(-.4,-.05),(.4,-.05),(.4,.5)]],
}


def heraldic(kind):
    def rect(x0,y0,x1,y1): return [(x0,y0),(x1,y0),(x1,y1),(x0,y1)]
    def disk(x,y,r,n=12):
        return [(x+r*math.cos(i*math.tau/n),y+r*math.sin(i*math.tau/n)) for i in range(n)]
    if kind=='cross':
        return [[(-.20,-.9),(.20,-.9),(.20,-.2),(.75,-.2),(.75,.2),(.20,.2),(.20,.9),(-.20,.9),(-.20,.2),(-.75,.2),(-.75,-.2),(-.20,-.2)]]
    if kind=='key':
        return [rect(-.12,-.85,.12,.25),rect(.05,-.8,.6,-.61),rect(.05,-.48,.48,-.30)]
    if kind=='lamb':
        return [disk(-.12,.05,.48),disk(.36,.08,.36),disk(.64,.37,.25),
                rect(-.48,-.75,-.30,-.17),rect(.12,-.75,.30,-.17),
                [(.50,.56),(.34,.85),(.73,.62)],[(-.55,.12),(-.88,.50),(-.74,.56),(-.40,.33)]]
    if kind=='tower':
        return [[(-.65,-.9),(.65,-.9),(.55,.48),(.67,.48),(.67,.85),(.32,.85),(.32,.56),(.15,.56),(.15,.85),(-.15,.85),(-.15,.56),(-.32,.56),(-.32,.85),(-.67,.85),(-.67,.48),(-.55,.48)]]
    if kind=='star':
        return [[((.86 if i%2==0 else .40)*math.sin(i*math.pi/6),
                  (.86 if i%2==0 else .40)*math.cos(i*math.pi/6)) for i in range(12)]]
    return [disk(.47*math.sin(i*math.tau/5),.47*math.cos(i*math.tau/5),.37) for i in range(5)]+[disk(0,0,.29)]
