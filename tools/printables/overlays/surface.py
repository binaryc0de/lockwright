"""Original seeded surface overlays, generated locally on the CPU.

Paper fibre, print banding, adhesive and curl shading, laminate sheen/scratches,
and LCD scanline variation. Colour relief only: runtime roughness is integration.
"""
import numpy as np


def apply(canvas, kind, seed):
    rng = np.random.default_rng(seed)
    h, w = canvas.shape[:2]
    yy = np.arange(h, dtype=np.float32)[:, None] / h
    xx = np.arange(w, dtype=np.float32)[None, :] / w
    if kind == 'marker':
        # Only vary existing ink. Never create alpha on the blank board.
        pressure = .92 + .06 * np.sin(xx * 131 + yy * 67)
        pressure -= .29 * (np.sin(xx * 447 + yy * 83) > .997)
        canvas *= pressure[:, :, None]
        return
    noise = rng.normal(0, .0028 if kind != 'screen' else .0007, (h, w)).astype(np.float32)
    variation = noise + .0015 * np.sin(yy * h * 1.1)
    if kind in ('paper', 'note', 'laminate'):
        edge = np.minimum(np.minimum(xx, 1 - xx), np.minimum(yy, 1 - yy))
        variation -= .035 * np.exp(-edge * 110)
    if kind == 'paper':
        # Light handling wear, confined to the lower-right corner and margins.
        variation -= .026 * np.exp(-((xx - .90) / .09) ** 2 - ((yy - .94) / .045) ** 2)
        variation += .006 * np.sin(xx * 31 + yy * 7)
    elif kind == 'note':
        variation -= .043 * np.exp(-((yy - .075) / .055) ** 8)
        curl = np.exp(-((yy - .985 + .014 * np.cos(xx * 3.14)) / .014) ** 2)
        variation -= .11 * curl
        variation += .025 * np.exp(-((yy - .965) / .011) ** 2)
    elif kind == 'laminate':
        variation += .032 * np.exp(-((xx + yy * .70 - .16) / .055) ** 2)
        variation += .015 * np.exp(-((xx + yy * .70 - 1.36) / .08) ** 2)
    elif kind == 'screen':
        variation += .0015 * np.sin(yy * h * 3.14159)
    canvas[:, :, :3] = np.clip(canvas[:, :, :3] + variation[:, :, None], 0, 1)
