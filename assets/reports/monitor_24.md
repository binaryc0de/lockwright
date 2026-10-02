# monitor_24 — M1 office look test

Original 24-inch corporate desktop monitor, built offline by
`tools/blender/props/monitor_24.py` using the accepted keypad's `build(out_dir)`,
shared export/metadata/preview helpers and reliable headless CLI structure.
No third-party geometry, textures, fonts or downloads; no attribution needed.

## Appearance and construction

Matte black injection-moulded housing with rounded perimeter corners, a thin
parting seam, recessed display aperture, glossy bottom strip, tiny white
power lens and underside OSD buttons. The rear shell tapers from 15 mm edges
to an approximately 45 mm central bulge, with actual rounded ventilation
openings, a shadow baffle, clamp/release plate, recessed cross-head screws and
a down-facing connector bay. The satin alloy rectangular foot and flat neck
include rubber pads, a rounded cable-management opening and rear plastic trim.
All these details remain inside the four requested named mesh objects.

Seeded surface grain, fine brushed alloy, settled top-edge/foot dust and faint
fingerprint whorls on the lower-right chin are baked into embedded base-colour,
tangent normal and packed ORM maps. Both textured materials share one
non-overlapping atlas, raster-baked on CPU from actual triangle coordinates,
with eight pixels of island dilation. The screen is a clean, two-triangle
rectangle with four unique vertices and UV corners spanning 0..1; it has no
baked content or surface contamination. It retains its own centre origin and
`M_monitor_24_screen`, with dark base colour, roughness 0.20 and faint emission.
`M_monitor_24_led` has white base/emission for tinting in Godot.

## Dimensions and integration

Overall footprint **0.560 W × 0.170 D × 0.460 H m**. The foot underside is at
Godot Y=0; the footprint is centred on X=Z=0. The main bezel shell spans
Y=0.120..0.460 m. Its display is exactly **0.531 × 0.299 m**.

`anchors_godot_m` supplies:

- `screen_centre`: `[0, 0.292, -0.0297]`.
- `bezel_front_z`: `-0.031275` (front of the glossy chin strip).
- `bezel_bottom_right`: `[-0.270, 0.1315, -0.031275]` (on the lower-right bezel).

Visual right, when looking at the front from Godot -Z, is **-X**, matching the
accepted keypad convention. Put the external sticky note slightly farther
along -Z from its anchor. No note, logos, puzzle text, animations or collision
are embedded. Screen content belongs to Claude's integration; set the screen's
base/emission texture in-engine. Refresh only this GLB's extracted textures
and their import sidecars when integrating a rebuilt version.

The exact 560 mm shell and 531 mm display widths imply **14.5 mm side bezels**,
which conflicts with the request's approximate “6–8 mm” prose. The exact
specified dimensions were preserved. Display Y=0.292 gives approximately
18.5 mm top and 22.5 mm bottom margins. The chin stands 0.275 mm proud of the
31 mm bezel face; this makes the shell's local maximum depth about 45.3 mm.
Stand mounting hardware extends behind the shell as expected.

## Verification

Built on the RTX 3080 Ti development machine with **Blender 5.2.2 LTS**.
Previews use the pipeline's **Cycles CPU**, 32 samples, denoise and four threads;
all three are **1024 × 1024** on neutral grey with the shared three-point lights.
Personally inspected the front, iso and detail renders during material iteration.
Final output: **9,314 triangles**, **four named meshes**, **four materials**,
**three embedded 1024 × 1024 PNG maps**, no collision or animations.

`tools/blender/build_assets.sh monitor_24` returned **exit 0**:

```text
Building monitor_24 with Blender 5.2.2 (CPU only, 4 threads)
ASSET BUILT: ~/Work/escapebox/game/assets/core/props/monitor_24.glb; 9314 triangles; 4 materials
```

The exporter printed two shared-image sampler notices:

```text
WARNING: More than one shader node tex image used for a texture. The resulting glTF sampler will behave like the first shader node tex image.
```

These arise from the same atlas attached to both plastic and metal. The helper
assigns identical Linear/EXTEND settings to every texture node; there is no
sampler conflict. The GLB contains only three distinct embedded images.

`go run ./tools/assetcheck monitor_24` returned **exit 0**:

```text
PASS monitor_24 (9314 tris, 4 parts)
assetcheck: 1 asset(s) checked, 1 passed, 0 failed, 0 warning(s)
```

Godot **4.7.2** headless, in an isolated scratch project under
`assets/cache/monitor_24/godot_check`, loaded the GLB directly through
`GLTFDocument` and verified applied transforms, PBR texture imports, mesh names,
screen origin, full UV corners and face direction. It returned **exit 0**:

```text
PASS Godot headless: GLB loads; four named meshes; applied transforms; PBR maps imported; screen has four UV corners 0..1, centre (0,0.292,-0.0297), and -Z normals
```

An additional exported-file inspection confirmed PNG dimensions, no helper
nodes/cameras/lights/animations/collision, the zero-height base plane, and current
script/GLB hashes and sticky-note anchors. The GLB is **2,246,052 bytes**.

```text
SHA256 940d5e0363c21c5345d707e5d24c33c4e14a0841b094b85c353c14437a1637e1
```

Ran the unchanged final script through `tools/blender/build_assets.sh monitor_24`
**twice**, both returning **exit 0**. The two GLBs are **byte-identical** with the
SHA256 above. Metadata differs only in `built_at`:
`2026-10-02T05:49:03+00:00` and `2026-10-02T05:59:07+00:00`. Ran assetcheck again
after the second build: same successful output, zero warnings. The final three
previews were inspected. Detailed logs and comparison files are confined to
ignored `assets/cache/monitor_24/`.

```text
PASS reproducibility: unchanged final script produces byte-identical GLB; metadata differs only in built_at
```

Room screenshot, exposure/glow tuning and final acceptance remain Claude's
in-engine review. Screen emission is intentionally faint; assign its content
and tune emission against the actual room exposure. No runtime code, request
file, other asset files or common helpers were edited. No commit was made.
