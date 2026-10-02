# desk_3drawer — M1 office look test

Built on the RTX 3080 Ti development machine (ADR-0011), using Blender
5.2.2 LTS. All baking and previews use Cycles **CPU**, four threads, through
the shared serialized build wrapper. No external assets, fonts or textures,
network calls, shared helper changes, runtime changes or commits.

## Deliverables and appearance

- `tools/blender/props/desk_3drawer.py`: deterministic seeded `build(out_dir)`
  and shared headless CLI, following the accepted keypad structure.
- `game/assets/core/props/desk_3drawer.glb`: four named mesh objects, four
  Principled metallic/roughness materials, embedded textures, no collision,
  cameras, lights or animation.
- `assets/previews/desk_3drawer_{front,iso,detail}.png`: 1024 × 1024, neutral
  grey, shared three-point studio, 32 samples and denoising. Front and iso
  show the closed desk; detail shows the tray extended exactly 0.40 m,
  viewed from above at 45 degrees with a slight side angle.
- `assets/meta/desk_3drawer.json`: actual geometry/texture counts, hashes,
  exported anchor, desktop height, overall bounds, footprint and tray bounds.

Light grey oak-effect laminate with lengthwise fibres, fine pores and mild
tonal variation; dark ABS edge banding around a 2 mm rounded desktop edge;
warm grey melamine carcass with subtle stipple; round brushed aluminium
bar pulls with separate mounting posts and roses. Two faint broken mug
rings, a softly polished wrist edge and localised plinth scuffs provide
light office wear. The desktop is clear.

Base colour, tangent normals and packed ORM are baked from original
procedural materials. Occlusion is ray traced and gently blended into the
ORM R channel; roughness is G and metallic is B. Top and carcass maps are
2048 × 2048; metal and interior maps are 1024 × 1024. UV islands are unique
per material across the whole asset; packing and baking reserve 8 px.
The exported material graphs contain Principled BSDF and image textures.

## Geometry and integration

The desktop is 1.60 × 0.75 m, with its top at Godot Y = 0.76 m and underside
at 0.72 m. End panels, rear modesty panel, pedestal, recessed 40 mm plinth,
shelves and outer slide channels belong to `body`, with its origin at the
specified footprint centre on the floor. The pedestal is on the seated
user's right, Godot −X. Panel edges have applied small bevels and normals;
all exported polygons are triangles.

`drawer_top` contains the front, handle, floor, both sides, back and inner
slide channels. Its closed object origin is Godot **(−0.42, 0.62, −0.395) m**,
with identity rotation and scale. The SDK should translate it by
**(0, 0, −0.40) m** to open it. The other two drawer fronts and their handles
remain separate static objects. There is no exported animation.

The top drawer interior is **0.56 W × 0.46 D × 0.11 H m**, with floor at
Y = 0.56 and back inner face at Z = +0.08. A 5 mm rebate on the back of the
front panel preserves its 20 mm overall thickness while fitting those
specified interior planes. This is a joinery detail, not a dimension
change. Interior walls and floor are finished light grey melamine. Fixed
shelves lie below the tray; the upper carcass rail is above it. The builder
checks every static triangle against the tray's interior and full 400 mm
swept clearance volume.

The full closed geometry extends farther forward than the desktop: drawer
fronts reach Z = −0.395 and handles reach Z = −0.426 m. The resulting full
depth is **0.801 m**, although the specified desktop footprint is 0.75 m.
The origin intentionally remains at the requested footprint centre.

Claude owns room integration and the final in-room screenshot. No in-room
visual approval or gameplay wiring is claimed here. Re-extract this GLB's
embedded textures during integration if Godot cached an earlier draft.

## Verification actually run

Ran `tools/blender/build_assets.sh desk_3drawer` for the first version and
twice for the final geometry/material revision. All three returned **exit 0**.
Final build output (the preceding bake lines record CPU and 8 px margins):

```text
Building desk_3drawer with Blender 5.2.2 (CPU only, 4 threads)
PASS geometry: exact drawer origin; empty tray and 400 mm swept clearance; applied transforms
ASSET BUILT: ~/Work/escapebox/game/assets/core/props/desk_3drawer.glb; 17884 triangles; 4 materials
```

**17,884 triangles**, four meshes, four materials, twelve embedded PNGs.
The final two GLBs are **byte-identical**, 15,222,012 bytes, and their
metadata is identical except `built_at` (`2026-10-02T05:53:37+00:00` and
`2026-10-02T06:04:45+00:00`). The comparison also verified that metadata's
GLB/source hashes match the delivered files:

```text
PASS reproducibility: byte-identical GLB; metadata identical except built_at
SHA256 364acd849ae548f8cc176c393b78dcc147f04a3ad3fba2ded2df940490becd1f
```

The exported ORM texture index is shared by occlusion and
metallic/roughness in every material. The exporter emits its existing
"More than one shader node tex image used for a texture" warning for these
shared maps; their sampler settings agree (Linear/EXTEND), and the output
was checked directly and loaded by Godot.

Ran Godot 4.7.2 headless with `GLTFDocument.append_from_file` and
`generate_scene` in an isolated project under
`assets/cache/desk_3drawer/godot-check/`, **exit 0**:

```text
PASS Godot headless: GLB loads; 4 named meshes; 17884 triangles; 4 baked PBR materials; exact drawer anchor and -0.40 m slide; floor Y=0; desktop Y=0.76
```

This check also verified image textures on every material, identity
rotation/scale, and closed/open drawer positions. Python source syntax
passed. Personally inspected all three final PNGs: grain and banding are
visible, the pedestal side gaps from the first draft are closed, and the
extended tray has finished walls, a floor and visible side-slide hardware.

Ran `go run ./tools/assetcheck desk_3drawer` on the final deliverables and
again after the reproducibility rebuild, both
**exit 1**, with the real output:

```text
FAIL desk_3drawer: origin not at base centre: bounds centre x = 0.0000, z = -0.0255 m (want 0 +/- 5 mm); bounds min (-0.8000, 0.0000, -0.4260) max (0.8000, 0.7600, 0.3750)
assetcheck: 1 asset(s) checked, 0 passed, 1 failed, 0 warning(s)
exit status 1
```

**Pipeline acceptance remains blocked by this validator/request mismatch.**
`tools/assetcheck/check.go:checkOrigin` centres all visible geometry,
including projecting handles, rather than the request's desk footprint.
The static `body` mesh itself has Godot bounds
`[-0.80, 0, -0.375]` to `[+0.80, 0.76, +0.375]`, centred exactly on X/Z = 0.
The specified fronts already extend 20 mm beyond the desktop, so even
removing the pulls would fail the 5 mm tolerance. Moving the asset origin
would violate the explicit request; altering the validator is outside
this task's lane. The owner/runtime agent needs to resolve this check.
There are no other reported assetcheck failures or warnings.

Local full bake/build logs and verification scratch files are in ignored
`assets/cache/desk_3drawer/`. No request status or acceptance box was changed.


## Revision — 2026-10-02: overall bounding-box origin

Applied Claude's dated origin correction in `assets/requests/desk_3drawer.md`.
This revision resolves the validator/request mismatch described in the initial
report above; its old origin, anchors and failed acceptance are historical.
The closed desk's origin is now at floor level at the centre of the complete
bounding-box footprint, including all drawer fronts and pulls. Every position
moves **+0.0255 m on Godot Z** relative to the original build. The script
computes the shift from the actual geometry after texture baking, retaining
the original procedural texture coordinates. Preview cameras move with the
desk to preserve the framing.

Recomputed `anchors_godot_m` from exported GLB node translations and the
position accessors of the desktop material:

```json
{
  "desktop_front_edge_z": -0.3495,
  "desktop_surface_y": 0.75999999,
  "drawer_top": [
    -0.419999987,
    0.620000005,
    -0.369500011
  ]
}
```

The exported bounds are approximately **(-0.8000, 0, -0.4005)** to
**(+0.8000, 0.7600, +0.4005) m**. Footprint and tray-volume metadata use the
same shift. The drawer's travel remains `(0, 0, -0.40)` m.

Rebuilt the GLB and all three 1024 px previews with Cycles CPU, four threads.
Personally inspected front, iso and detail; detail still shows the finished
open tray extended 0.40 m. An independent comparison against the previous
GLB checked every indexed vertex: the geometry differs only by the uniform
translation, with zero measured vertex translation error. Index topology,
UVs, part names and material definitions are unchanged; all twelve embedded
PNG textures are byte-identical. Body normal/tangent components differ by
at most 0.00030 after the coordinate rebase and export; drawer normals and
tangents are identical. The exported centre, floor, anchors and metadata
source/GLB hashes also passed the independent check. Triangle count remains
**17,884**, with four parts and four materials.

Actually ran `tools/blender/build_assets.sh desk_3drawer`: **exit 0**.
Real output excerpt:

```text
Building desk_3drawer with Blender 5.2.2 (CPU only, 4 threads)
PASS geometry: exact drawer origin; empty tray and 400 mm swept clearance; applied transforms
ASSET BUILT: ~/Work/escapebox/game/assets/core/props/desk_3drawer.glb; 17884 triangles; 4 materials
```

The exporter also emitted its existing shared-ORM warning:

```text
WARNING: More than one shader node tex image used for a texture. The resulting glTF sampler will behave like the first shader node tex image.
```

Actually ran `go run ./tools/assetcheck desk_3drawer`: **exit 0**.
Complete real output:

```text
PASS desk_3drawer (17884 tris, 4 parts)
assetcheck: 1 asset(s) checked, 1 passed, 0 failed, 0 warning(s)
```

Full build output, assetcheck output and independent comparison output are
in ignored desk-only scratch logs:
`assets/cache/desk_3drawer/origin_revision_build.log`,
`assets/cache/desk_3drawer/origin_revision_assetcheck.log`, and
`assets/cache/desk_3drawer/origin_revision_verify.log`.

Final GLB SHA-256: `4aa5cc6404a6d349572ff081bc96a5347bd417b9dae24d0737c7b8a5357185e1`.
Only desk_3drawer deliverables and their scratch files were edited. No
request, runtime, room, shared helper or other asset was changed, and no
commit was made. No new Godot import or in-engine screenshot was run in
this revision; Claude retains that review step.
