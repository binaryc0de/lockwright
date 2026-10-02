# whiteboard_wall — M1 office look test

Built on the RTX 3080 Ti development machine (ADR-0011), 2026-10-02,
with Blender 5.2.2 LTS. Ready for Claude's room integration and review.
No runtime files, requests, shared Blender helpers, or other assets changed;
no git commit made.

## Deliverables and construction

- `tools/blender/props/whiteboard_wall.py`: deterministic `build(out_dir)`
  and headless `--out` CLI using the accepted keypad's shared scene,
  geometry, export, metadata, preview and process-exit helpers. Seed 62047;
  no network, external dependencies, fonts or downloads.
- `game/assets/core/props/whiteboard_wall.glb`: **12,154 triangles**, exactly
  `frame`, `surface`, `tray`, four requested Principled PBR materials;
  no animation, collision, lights or cameras.
- `assets/previews/whiteboard_wall_{front,iso,detail}.png`: **1024 × 1024**,
  neutral grey, shared three-point studio, Cycles **CPU**, 32 samples,
  denoising and four threads. Detail shows tray, both capped markers and eraser.
- `assets/meta/whiteboard_wall.json`: measured export counts and bounds,
  embedded maps, hashes, version, timestamp, writing-plane anchors and
  protected-region/ghosting information.

Board envelope: **1.600 W × 1.000 H × 0.025 D m**. Including its projecting
tray, the full GLB is **1.600 W × 0.082 D × 1.000 H m**. All three mesh
origins are at the board's back-face centre; Godot back face Z = 0,
front face normal -Z, applied rotation and unit scale.

`surface` is a single flat rectangle, triangulated to two triangles, with
one full **0..1 UV island** and only `M_whiteboard_wall_surface`.
The required metadata is:

```json
"anchors_godot_m": {
  "surface_front_z": -0.022,
  "surface_size": [1.564, 0.964]
}
```

Frame front lip is Z = -0.025 m, so the writing plane sits **3 mm behind**
it. Rails have a physical stepped extrusion profile, softened machining
edges and lengthwise brushing. Rounded grey polymer corner caps have inset
moulding seams; the backing closes the board at the wall plane. The open
aluminium tray has a sloping cradle, a **12 mm front return**, and grey end
caps. Its leading edge is **60 mm ahead of the writing plane**, Z = -0.082 m.
Markers are approximately 143 mm long and 15 mm diameter, ivory barrels
with separate black/blue moulded caps, ribbed collars, clips and rear plugs,
all joined into `tray`. The eraser has a rounded ribbed grip over porous felt.

## Materials and surface detail

Nine original seeded raster textures are embedded: base colour, tangent
normal and packed ORM for each of surface, aluminium and accessories.
Surface maps are **2048 × 1024**; aluminium/accessory maps **1024 × 1024**.
Plastic and markers share the accessory atlas. All maps stay within budget;
ORM channels are occlusion R, roughness G, metallic B.

The satin white melamine has very fine microtexture, slight sheen variation,
faded diagram boxes and arrows near the upper/right margins, a hand-wipe
band below the text area, and faint dust near the corners. Erased traces
are bounded below **4.8% darkening**, under the request's 6% limit. The
protected Godot rectangle X[-0.65,+0.65], Y[-0.35,+0.30] has **zero ghosting
or wipe marks**. There are no words, digits, clues, logos or UV codes in
these textures; Claude supplies the real writing in-engine.

Aluminium maps include fine directional brushing and sparse scratches;
accessories have moulded plastic grain, minor scuffs and a coarse felt
normal. This is direct analytic rasterisation into exportable maps, as in
keypad_4, without high-to-low baking. Each writing-plane, extrusion and
primitive unwrap has separate islands. Reusable accessory swatches and
some repeated small components deliberately share atlas regions; these
are tiled material textures rather than unique baked lighting.

All geometry is explicitly triangulated, normals recalculated and
modifiers applied. No third-party assets were used, so no attribution
entry is needed.

## Verification actually run

`tools/blender/build_assets.sh whiteboard_wall` completed **twice**, both
with **exit 0**. `cmp` confirmed byte-identical GLBs: **12,116,932 bytes**,
SHA-256 `5b2ebf406b39faae9adcea2eeedb15947c5a4da4e59ed2756bfeb0dd8b03a6a8`.
The second build is logged in `assets/cache/whiteboard_wall/rebuild.log`.
Full output is retained in ignored `assets/cache/whiteboard_wall/build.log`.
Its final lines were:

```text
00:45.151  render           | Saved: '~/Work/escapebox/assets/previews/whiteboard_wall_detail.png'

ASSET BUILT: ~/Work/escapebox/game/assets/core/props/whiteboard_wall.glb; 12154 triangles; 4 materials
```

The exporter prints a sampler warning because the shared ORM helper uses
separate image nodes for roughness/metallic and occlusion. All relevant
samplers have identical settings; the GLB retains the packed ORM maps.

`go run ./tools/assetcheck whiteboard_wall` returned **exit 0**:

```text
PASS whiteboard_wall (12154 tris, 3 parts)
assetcheck: 1 asset(s) checked, 1 passed, 0 failed, 0 warning(s)
```

Godot **4.7.2**, headless, isolated project under
`assets/cache/whiteboard_wall/godot-check/`, loaded the GLB directly with
`GLTFDocument` and generated the scene. Verified exactly three mesh nodes,
applied transforms, surface material, writing depth, facing normal,
UV extents, and absence of collision/animation nodes. Output:

```text
PASS Godot headless: GLB loads; 3 mesh nodes; applied transforms; surface faces -Z at -0.022 m; UV 0..1; no collision or animations
```

The script also checks part names, triangle/material budgets, mounting
transforms, plane normal, and protected-region ghosting during each build.
Direct GLB inspection confirmed nine embedded images, base/normal maps on
all four materials, and identical texture indices for occlusion and
metallic/roughness (packed ORM). Python source compilation passed.
All three final previews were personally
inspected.

## Integration notes

No functional deviations from the request. The tray projection is measured
from the writing plane; the quoted 25 mm depth describes the board/frame,
not the entire tray-equipped asset.

Place marker/UV overlays just forward of Z = -0.022 m and use the recorded
1.564 × 0.964 m writing area. Keep the subtle roughness/normal maps when
setting room exposure: these supply the surface sheen under the spotlight.
Refresh only this GLB's extracted textures when reimporting, per the pipeline.
Room screenshot, SDK writing overlays and final in-engine acceptance belong
to Claude's integration review and have not been performed here.
