"""Original industrial stencil contours and seeded spray enamel surface.

Normalized polygon geometry, no font or downloaded art. Counter cutouts and
bridges remove RGBA rather than painting black. Raster work is CPU-only.
"""
import numpy as np

# Each glyph is an outer contour followed by counter cutouts. Chamfered bowls
# suggest cut sheet-metal templates; the six has a large OPEN upper-right gap.
GLYPHS = {
    'R': [
        [(0, 0), (.78, 0), (1, .14), (1, .41), (.77, .55), (1, 1),
         (.68, 1), (.43, .59), (.27, .59), (.27, 1), (0, 1)],
        [(.27, .17), (.66, .17), (.74, .23), (.74, .36), (.66, .42), (.27, .42)],
        [(.70, .275), (1.01, .275), (1.01, .305), (.70, .305)],
    ],
    'A': [
        [(.35, 0), (.65, 0), (1, 1), (.71, 1), (.62, .73), (.38, .73), (.29, 1), (0, 1)],
        [(.50, .24), (.33, .57), (.67, .57)],
        [(.47, .53), (.53, .53), (.53, .75), (.47, .75)],
    ],
    'C': [
        [(1, .04), (.80, 0), (.21, 0), (0, .15), (0, .85), (.21, 1),
         (.80, 1), (1, .96), (1, .79), (.75, .83), (.36, .83), (.27, .76),
         (.27, .24), (.36, .17), (.75, .17), (1, .21)],
    ],
    'K': [
        [(0, 0), (.27, 0), (.27, .40), (.68, 0), (1, 0), (.52, .47),
         (1, 1), (.67, 1), (.27, .57), (.27, 1), (0, 1)],
    ],
    '0': [
        [(.21, 0), (.79, 0), (1, .15), (1, .85), (.79, 1), (.21, 1), (0, .85), (0, .15)],
        [(.36, .17), (.64, .17), (.73, .24), (.73, .76), (.64, .83), (.36, .83), (.27, .76), (.27, .24)],
        [(-.01, .485), (1.01, .485), (1.01, .515), (-.01, .515)],
    ],
    '6': [
        [(.85, 0), (.40, 0), (.10, .20), (0, .43), (0, .82), (.21, 1),
         (.79, 1), (1, .82), (1, .51), (.80, .35), (.28, .35), (.33, .28),
         (.51, .17), (.85, .17)],
        [(.36, .52), (.64, .52), (.73, .59), (.73, .76), (.64, .83), (.36, .83), (.27, .76), (.27, .59)],
        [(-.01, .675), (1.01, .675), (1.01, .705), (-.01, .705)],
    ],
    '2': [
        [(0, .13), (.21, 0), (.79, 0), (1, .14), (1, .34), (.29, .83),
         (1, .83), (1, 1), (0, 1), (0, .79), (.73, .30), (.73, .23),
         (.64, .17), (.36, .17), (.27, .23), (.27, .28), (0, .28)],
    ],
}


def draw(canvas, text, center, baseline, cap, maximum, color):
    if text != 'RACK 062':
        raise ValueError('rack_stencil requires the exact request string RACK 062')
    glyph_width, gap, word_gap = cap * .46, cap * .10, cap * .23
    width = 7 * glyph_width + 5 * gap + word_gap
    if width > maximum:
        raise ValueError('Stencil would exceed its text width budget')
    x, top = center - width / 2, baseline - cap
    for char in text:
        if char == ' ':
            x += word_gap - gap
            continue
        # A temporary alpha mask makes holes/bridges truly transparent, including
        # nonzero background paint should this helper ever be reused.
        view = canvas.data
        x0, x1 = int((x - 3) * 2), int((x + glyph_width + 3) * 2) + 2
        y0, y1 = int(top * 2), int(baseline * 2) + 2
        before = view[y0:y1, x0:x1].copy()
        for index, contour in enumerate(GLYPHS[char]):
            points = [(x + px * glyph_width, top + py * cap) for px, py in contour]
            if index == 0:
                canvas.polygon(points, color)
            else:
                # Rasterize the cutout into a small scratch canvas region by
                # reusing polygon coverage; restore the pre-glyph framebuffer.
                saved = view[y0:y1, x0:x1].copy()
                view[y0:y1, x0:x1] = 0
                canvas.polygon(points, np.array([1, 1, 1, 1], dtype=np.float32))
                cut = view[y0:y1, x0:x1, 3] > 0
                view[y0:y1, x0:x1] = saved
                view[y0:y1, x0:x1][cut] = before[cut]
        x += glyph_width + gap
    # Two small gravity drips on letters; none in the digits or their gaps.
    left = center - width / 2
    for dx, length in ((glyph_width * .14, 24), (3 * (glyph_width + gap) + glyph_width * .89, 33)):
        tip_x = left + dx
        canvas.polygon([(tip_x-2.3, baseline-6), (tip_x+2.3, baseline-6),
                        (tip_x+1.4, baseline+length), (tip_x-1.4, baseline+length)], color)
        canvas.ellipse(tip_x, baseline+length, 2.3, 3.4, color, np.zeros(4), 0)
    return width


def box_blur(values, radius, axis):
    padding = [(0, 0)] * values.ndim
    padding[axis] = (radius, radius)
    padded = np.pad(values, padding)
    cumulative = np.cumsum(padded, axis=axis, dtype=np.float32)
    zeros = list(cumulative.shape)
    zeros[axis] = 1
    cumulative = np.concatenate([np.zeros(zeros, dtype=np.float32), cumulative], axis=axis)
    start, end = [slice(None)] * values.ndim, [slice(None)] * values.ndim
    start[axis], end[axis] = slice(None, -(2*radius+1)), slice(2*radius+1, None)
    return (cumulative[tuple(end)] - cumulative[tuple(start)]) / (2*radius+1)


def apply_wear(canvas, seed):
    rng = np.random.default_rng(seed)
    frame = canvas.data
    alpha = frame[:, :, 3].copy()
    halo = alpha.copy()
    for _ in range(3):
        halo = box_blur(box_blur(halo, 4, 1), 4, 0)
    halo = np.clip(halo, 0, 1)
    h, w = alpha.shape
    yy = np.arange(h, dtype=np.float32)[:, None] / 2
    xx = np.arange(w, dtype=np.float32)[None, :] / 2
    # Spray density/paint tooth: subtle clustered variation plus tiny pinholes.
    density = .945 + .024*np.sin(xx*.042 + yy*.018) + .018*np.sin(yy*.081)
    density = np.clip(density + rng.normal(0, .013, alpha.shape), .86, .995)
    density[rng.random(alpha.shape) < .0025] *= .30
    # Restrained short scuffs, mostly at edges, never whole missing strokes.
    for _ in range(24):
        sx, sy = rng.integers(150, 1900), rng.integers(130, 555)
        length = rng.integers(4, 17)
        x0, y0 = int(sx*2), int(sy*2)
        density[y0:y0+2, x0:x0+length*2] *= .46
    ink = alpha * density
    spray = halo * .11 * np.clip(rng.normal(1, .30, alpha.shape), .2, 1.6)
    out_alpha = ink + spray * (1-ink)
    # Slight warm enamel tone and real granular opacity, no baked lighting.
    shade = np.clip(.985 + .008*np.sin(xx*.035 + yy*.048), .96, 1)
    tone = np.array([245, 244, 237], dtype=np.float32) / 255
    frame[:, :, 3] = out_alpha
    frame[:, :, :3] = out_alpha[:, :, None] * shade[:, :, None] * tone
