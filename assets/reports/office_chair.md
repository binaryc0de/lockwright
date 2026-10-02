# office_chair — M1 office look test

Built on the RTX 3080 Ti development machine on 2026-10-02 with Blender
**5.2.2 LTS**. Ready for Claude's in-room visual review; the request remains
open and its in-engine screenshot acceptance item remains pending.

## Delivered

- `tools/blender/props/office_chair.py`: deterministic `build(out_dir)` and
  the shared headless CLI entry point, using the accepted keypad structure.
- `game/assets/core/props/office_chair.glb`: **16,256 triangles**, exactly
  **two named meshes** (`base`, `seat`), **three materials**, nine embedded
  PNG maps. No collision geometry, animation, camera or light in the GLB.
- `assets/previews/office_chair_{front,iso,detail}.png`: **1024 × 1024**,
  neutral-grey studio, shared three-point lighting, **Cycles CPU, 32
  samples, denoise, four threads**. All three were personally inspected.
- `assets/meta/office_chair.json`: exported counts, dimensions, materials,
  embedded texture sizes, hashes, build/version information, and
  `anchors_godot_m` for the floor origin and swivel axis.

## Construction and materials

Original 2010s contract task chair with charcoal fabric upholstery, a
compressed sitting bowl and rolled waterfall edge, a reclined padded
back with lumbar bow, real perimeter welts, a moulded rear shell, closed
loop arms with rounded pads, underside ribs, tilt plate, tension knob,
height lever, telescoping gas lift, tapered five-star nylon base and ten
rounded wheels on five swivel castors. Geometry has applied transforms
and modifiers, outward normals and explicit triangles.

The request's fabric-back option was used. All surface detail is baked
from original metre-based procedural shaders into non-overlapping UV
atlases with **8 px margins**, using **Cycles CPU, 16 samples**. No
procedural node network is required in Godot.

| Material | Surface detail | Embedded maps |
|---|---|---|
| `M_office_chair_fabric` | Coarse interlaced weave in colour and tangent normal; fibre variation, front-edge pilling and localized rubbed wear | Base colour, normal, ORM; each 2048 × 2048 |
| `M_office_chair_plastic` | Nylon mould grain, lighter grey castor wheels, upward-facing base dust, smoother rubbed arm-pad areas | Base colour, normal, ORM; each 2048 × 2048 |
| `M_office_chair_metal` | Dark mechanism steel and exposed brighter gas piston, with fine surface variation | Base colour, normal, ORM; each 2048 × 2048 |

ORM uses roughness in G and metallic in B; R is white (no baked contact
occlusion). Occlusion and metallic/roughness share the same embedded
texture in glTF. Lighting and room SSAO should supply contact shading.
No third-party models, images, fonts or downloads were used; no
attribution entry is needed.

## Dimensions and integration

Measured AABB: **0.628000 W × 0.643928 D × 1.001228 H m**. The nominal
0.66 m radial five-star footprint projects to a narrower rectangular
AABB because of the five spoke/castor orientations. Fabric welts extend
the top by about 1.2 mm. The compressed seat's highest padded surface is
**0.466216 m**, about 3.8 mm below the nominal 0.47 m seat height.
Arm-pad tops are 0.66 m. These are the small dimensional differences
from the request; material, mesh, texture and triangle budgets are met.

Godot bounds: `[-0.314000, 0, -0.321964]` to
`[0.314000, 1.001228, 0.321964]`. The floor-plane origin is exactly at
the centre of the overall footprint. Forward is Blender +Y → Godot -Z.

`base` has zero translation. `seat` has only a location, with its origin
on the gas-column axis at Godot **[0, 0.383, -0.002267316] m**. The
2.27 mm horizontal offset preserves the physical swivel axis while the
overall root is centred on the AABB. Rotate `seat` around its local Y
axis if later needed; it includes the back and both arms. Leave collision
to the room, as requested.

Keep the imported normal and ORM maps for the room look test. Review
exposure and warm desk lighting in the room before changing the albedo
or roughness. This handoff verifies import and studio appearance;
in-room screenshots and gameplay integration remain Claude's review.

## Verification actually run

`tools/blender/build_assets.sh office_chair` completed **twice with exit
0** on the final script. Its relevant real output was:

```text
Building office_chair with Blender 5.2.2 (CPU only, 4 threads)
ASSET BUILT: ~/Work/escapebox/game/assets/core/props/office_chair.glb; 16256 triangles; 3 materials
```

The full bake/export/render output is retained under ignored
`assets/cache/office_chair/`. Blender also reports its sampler warning
(`More than one shader node tex image used for a texture`); all texture
nodes use identical Linear/Extend sampler settings, and the shared ORM
bindings were checked in the exported JSON and Godot.

The two final GLBs are **byte-identical**, including the baked textures;
size **19,663,564 bytes**. Metadata differs only in `built_at`:
`2026-10-02T05:47:15+00:00` and `2026-10-02T05:58:26+00:00`.

```text
PASS two final builds: byte-identical GLB; 19663564 bytes
SHA256 93cc2ba2cfd4892501793ef420149b9d9c2ac1d2bc5ba374cc8e8e6bbfe75b49
Metadata differences: built_at
```

An optional **PNG byte-hash comparison did not match** for the three
previews. Blender PNGs embed `Date`, `RenderTime` and Cycles performance
text chunks; only GLB byte identity is asserted here, not preview pixel
identity. The delivered previews were visually inspected again.

`go run ./tools/assetcheck office_chair` completed with **exit 0**:

```text
PASS office_chair (16256 tris, 2 parts)
assetcheck: 1 asset(s) checked, 1 passed, 0 failed, 0 warning(s)
```

Godot **4.7.2** loaded the GLB through `GLTFDocument` in an isolated,
headless scratch project under `assets/cache/office_chair/godot-check/`.
The command completed with **exit 0** and printed:

```text
PASS Godot headless: office_chair loads; base/seat; 3 PBR materials with colour/normal/ORM; applied transforms; swivel pivot matches metadata; centred floor origin; height 1.00 m
```

An independent scan of exported accessor/index data found **0 degenerate
triangles**, finite positions/UVs, unit normals, and **0 overlapping UV
pixel samples** in a 512 px raster check for each material atlas. This is
a sampled overlap check; atlas packing also uses Blender's shared
multi-object island packing. Nine embedded images and absence of
animations/cameras were checked directly in the GLB JSON. Python syntax
also passed.

No shared helpers, another asset's files,
runtime code, room YAML, requests, or documents outside the asset lane
were edited. No commit was made.
