# cage_partition_kit

Owner-made welded security-cage kit built from `assets/requests/cage_partition_kit.md`. The script follows the accepted `exit_door_maglock` and `exit_keypad_6` surface-builder, CPU-bake, export and preview structure. No third-party resources, downloads, fonts or attribution changes.

## Deliverables and construction

- `tools/blender/props/cage_partition_kit.py`: deterministic headless `build(out_dir)`, fixed seed 420026, stdlib/Blender/common helpers only.
- `game/assets/core/props/cage_partition_kit.glb`: three independent meshes, `panel_1200`, `panel_400`, `header_1000`. Every exported object is at (0, 0, 0), has identity rotation/unit scale, and has its own bottom-centre origin. The intentional overlapping kit is separated only for baking and previews.
- `assets/previews/cage_partition_kit_{front,iso,detail}.png`: 1024 × 1024 neutral-grey studio renders using `common/preview.py`, Cycles CPU, four threads, 32 samples and denoising.
- `assets/meta/cage_partition_kit.json`: exported triangle/material totals, script/pipeline/GLB hashes, maps, bounds, individual origins and bounds, and the wire texture's physical dimensions.

Each panel has 40 × 40 mm square-tube frames with 1.5 mm rounded edges, closed corner joints, small raised coated welds, and real recessed fixing sockets on both sides. Tall panels have small inward-offset anchor plates, washers, hex heads and two cable ties. Main frame widths and heights match the request; anchor plates remain within the panel width.

The mesh is an actual transparent cutout, with no solid backing: a 200 mm tile contains four 50 mm pitches and 4 mm wire. Base-colour alpha carries the holes; exported glTF uses `alphaMode: MASK`, cutoff 0.5 and `doubleSided: true`. Tangent normals model round wire profiles and flattened welded intersections. Nominal clear area is 84.64%. The repeating tile retains wire resolution over the full 2.8 m panel without exceeding the texture budget.

Powder coat uses spatial colour drift, orange-peel normal detail, roughness variation, sparse hand-height scratches and exposed corner flecks. Frame and hardware maps are CPU-baked into non-overlapping atlases with an 8 px margin; ray-traced AO is packed into ORM. Hardware has machined surface grain. All three materials are Principled PBR. Frame maps are 2048 px; hardware and wire maps are 1024 px; all nine PNG maps are embedded in the GLB.

## Request interpretation and integration

The frame itself is 40 mm deep; fixing heads add about 1 mm per side and the floor plates are 90 mm deep. This small base footprint is the only dimension beyond the approximate 50 mm panel thickness. The elevated header has no floor anchors. Butt adjacent panels at their nominal widths; the matching full-height coated tubes form a flush paired post with a fine central joint.

No collision meshes, animations, lights, cameras or text ship in the GLB. The room owns collision. No `anchors_godot_m` block was requested; individual origins and bounds are recorded instead. Lift `header_1000` to Godot y = 2.10 when using it over the door opening. Keep the cutout material double-sided and its texture sampler repeating; a solid material override would hide the rack through the partition.

Godot integration, in-room screenshots and viewing-distance/mipmap behaviour remain for Claude's review. Inspect from both sides under room lighting; if distant wire flickers, review alpha-to-coverage and anisotropic filtering in Godot. No runtime, room scene, request, shared-helper, other-asset or `room.yaml` files were edited. No commit was made.

## Verification

Run on this checkout with Blender 5.2.2 LTS, CPU only, four threads:

`tools/blender/build_assets.sh cage_partition_kit` completed with exit 0. Relevant real output:

```text
Building cage_partition_kit with Blender 5.2.2 (CPU only, 4 threads)
PASS structure: 3 independent meshes at origin; cutout MASK; double-sided; no collisions
ASSET BUILT: ~/Work/escapebox/game/assets/core/props/cage_partition_kit.glb; 17270 triangles; 3 materials
```

The build also saved all three required previews and emitted four glTF sampler-sharing warnings (`More than one shader node tex image used for a texture`). The exported wire sampler was inspected and repeats in both directions; baked frame/hardware samplers clamp in both directions. Full output is in `assets/cache/cage_partition_kit.build.log`.

`go run ./tools/assetcheck cage_partition_kit` completed with exit 0. Real output:

```text
PASS cage_partition_kit (17270 tris, 3 parts)
assetcheck: 1 asset(s) checked, 1 passed, 0 failed, 0 warning(s)
```

Inspected the exported node transforms, bounds, mesh/material names, MASK/double-sided settings, embedded-image count, absent animations/cameras/collision helpers and base-map alpha. The wire image has alpha extrema 0/255 and approximately 84.985% transparent pixels at the exported cutoff. Individually measured triangle counts: panel_1200 6,938; panel_400 6,938; header_1000 3,394. Visually reviewed the final front, iso and detail renders; the detail shows rounded wire shading, sockets, coating scuffs and a cable tie.

Two consecutive full builds of the final script completed with exit 0 and produced byte-identical GLBs. The second build again rendered all three previews. `sha256sum -c assets/cache/cage_partition_kit.repro.sha256` printed:

```text
game/assets/core/props/cage_partition_kit.glb: OK
```

Final GLB SHA-256: `73cce2055e8ebfd9b2eaeae3a6abfac6a1df5e532e6218ea635d96091a11d8e3`.

The second build log is `assets/cache/cage_partition_kit.rebuild.log`. Assetcheck was rerun against that build and produced the same PASS / zero-warning output above. All Blender runs used the pipeline's shared `flock` lock; time waiting for other asset builds did not involve another simultaneous Blender process.
