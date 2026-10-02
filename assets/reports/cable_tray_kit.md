# cable_tray_kit

Built from `assets/requests/cable_tray_kit.md`, using the accepted
`exit_door_maglock.py` and `exit_keypad_6.py` as structural references for
geometry, procedural surface baking, export validation and CPU previews.

The kit contains exactly three independently placeable meshes: `tray_1m`,
`tray_2m`, and `drop_1m`. Both trays use inward-facing 2 mm folded galvanised
C channels, open-bottom pressed rungs at 200 mm spacing, end splice plates
with rivets, a trapeze bearer, two M8 hanger rods reaching 350 mm above the
underside, hollow washers and hex nuts. Twelve individual blue, grey, yellow
Cat6 / black power jackets follow slightly slack paths; reusable fabric ties
hold them in place. The separate drop turns through a rounded waterfall and
hangs one metre, with three velcro bands and overlap tabs.

Three Principled materials have original, baked base-colour, tangent-normal
and packed ORM maps, all 1024 × 1024. Zinc spangle, oxide bloom, directional
scratches, fine jacket grain and polished scuffs, helical rod threads and
fabric weave are represented in the exported textures. Geometry supplies
folds, lip thickness, seams, fasteners, washers, cable curvature and strap
thickness. All materials use metallic/roughness PBR; no external resources,
fonts or downloads were used, so no attribution entry is needed.

Every exported object has identity transforms at the origin. Each tray's
underside is y=0; the drop spans y=0 to y=1. Straight lengths run along Godot X.
Parts are temporarily spaced during baking to avoid overlapping-kit AO and
in the previews for review. Preview offsets are recorded in metadata and do
not occur in the GLB. No collisions, cameras, lights or animations ship.

Use `tray_2m` for two-metre runs to preserve rung spacing. Instancing one
kit GLB displays overlapping alternatives; keep the chosen part visible
and hide the others during integration. The request does not call for an
`anchors_godot_m` block; per-part bounds and origins are recorded instead.

## Verified output

| Part | Triangles | Overall W × D × H, metres |
|---|---:|---|
| `drop_1m` | 6,036 | 0.152 × 0.050 × 1.000 |
| `tray_1m` | 5,232 | 1.000 × 0.300 × 0.350 |
| `tray_2m` | 7,852 | 2.000 × 0.300 × 0.350 |

Total: **19,120 triangles**, three materials, nine embedded
1024 × 1024 maps. Tray overall height includes the 0.35 m hanger rods;
the channel itself is 0.10 m tall. All three previews are 1024 × 1024 PNGs
on neutral grey with the common three-point studio lights. Front, iso and
detail were visually inspected. Both trays are separated in the review
layout; the detail shows the lower tray, cabling and hanger hardware.

Final commands actually run on this checkout, Blender 5.2.2 LTS, Cycles CPU,
four threads, on 2026-10-02:

`tools/blender/build_assets.sh cable_tray_kit` — exit **0**. Actual output
excerpt (full log: `assets/cache/cable_tray_kit.build.log`):

```text
Building cable_tray_kit with Blender 5.2.2 (CPU only, 4 threads)
GEOMETRY 19120 triangles; 3 parts; folded sheet, 12 cable runs each, M8 hangers
PASS kit: all three mesh transforms at zero; tray bases y=0; no collision or animation
ASSET BUILT: ~/Work/escapebox/game/assets/core/props/cable_tray_kit.glb; 19120 triangles; 3 materials
```

`go run ./tools/assetcheck cable_tray_kit` — exit **0**. Actual complete output:

```text
PASS cable_tray_kit (19120 tris, 3 parts)
assetcheck: 1 asset(s) checked, 1 passed, 0 failed, 0 warning(s)
```

The initial preflight failed with 21,040 triangles and exit 1. Reducing
sampling along the gentle cable paths brought it to 19,120 without removing
hardware or folded sheet detail. Subsequent builds passed. The final two
mesh/material builds were byte-identical; the intervening edit changed
only preview offsets/camera framing. GLB SHA-256:

`765e39b6734d2b3dec207ff181cc3827af9bb65c2a4d637b9cf4936ba1126ebf`

Additional inspection confirmed exactly the three named nodes at identity
transforms, nine embedded PNGs within the size budget, base/normal/ORM and
AO links on all three materials, and metadata hashes matching the final
script and GLB. Blender emits shared-texture sampler warnings for ORM;
the exported AO and metallic/roughness references use the same texture
index and one consistent linear, mipmapped clamp sampler. No conflicting
sampler settings were found.

## Handoff and limitations

No request deviations remain. No shared helper, other asset, runtime file,
room scene, request or room manifest was edited. No commit was made.
The in-engine integration screenshot remains Claude's acceptance step.
Suggested material treatment: retain the embedded maps and normal strength
1.0; judge metal roughness under the room's reflection environment before
adding overrides. In-engine appearance and placement have not been tested
by this task.
