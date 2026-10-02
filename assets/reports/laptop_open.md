# laptop_open — M1 office look test

Original 14-inch business laptop for the Night Shift terminal. The deterministic
source is `tools/blender/props/laptop_open.py`, with `build(out_dir)` and the
standard headless `--out` entry point. No external assets, fonts, downloads or
Python dependencies are used. No attribution entry is required.

## Construction and materials

The 330 × 230 × 18 mm base has rounded plan corners, a bevelled upper deck,
a continuous case seam, recessed keyboard tray, separately shaped chiclet
keycaps (78, including split up/down arrows), a recessed touchpad, speaker
perforations, power button, status lens,
USB/HDMI-type port cavities, side exhaust slots, hinge barrels, underside
service screws, ventilation marks and rubber feet. All static details are
joined into `base`.

The 330 × 220 × 6 mm lid leans 15 degrees backwards (105 degrees from the
closed/base plane). `lid` has its origin on the hinge axis. A webcam, mic
pinhole and raised vinyl asset tag are joined into that mesh. The back tag
reads `KL-LT-0332`, with an original Code 39 barcode and small property text.

`screen` is exactly 300 × 188 mm, with one material, a display-centre origin,
local Godot -Z normal, and UVs spanning 0..1 over its visible area. The quad
sits 0.5 mm forward of the bezel plane. The screen centre, outward normal
and size are recorded in `anchors_godot_m` for in-engine content placement.

Four Principled PBR materials: `M_laptop_open_shell`, `M_laptop_open_keys`,
`M_laptop_open_screen` and `M_laptop_open_sticker`. Original procedural
raster textures encode charcoal plastic grain, small paint scratches,
palm-rest shine, lightly polished frequently used keys, sparse dust,
white QWERTY legends and worn off-white sticker stock. Color, normal and
packed ORM maps are embedded in the GLB. The screen has a restrained dark
blue-black base, low roughness and a small uniform emission; it contains
no baked interface or puzzle content.

## Previews

Three 1024 × 1024 PNGs on the shared neutral-grey three-point studio:
`laptop_open_front.png`, `laptop_open_iso.png`, `laptop_open_detail.png`.
Cycles CPU, 32 samples, denoise, four threads. The detail is a two-render
contact sheet: keyboard above, reverse-side asset tag below, because both
surfaces cannot face a single camera at once.

## Integration and clarifications

- The overall footprint, including the backward-leaning lid, is centred at
  the asset origin and the static base origin. The base geometry is offset
  inside that footprint; the underside of the feet lies at Godot Y=0.
  Hinge and screen origins are recorded in metadata.
- Display size follows the exact 300 × 188 mm requirement (aspect 1.596:1,
  the specified approximate 16:10). No collision helpers or animations.
- Apply screen UI at `screen_centre`, oriented along `screen_normal`, with
  a tiny additional outward offset to avoid coplanar rendering. Keep UV
  artwork aligned to the screen quad, whose U direction is screen-right.
- Refresh this GLB's extracted textures during integration. Final room
  exposure, terminal UI placement and in-engine screenshot remain Claude's
  review lane.
- Primary housing surfaces have distinct atlas regions. Repeated hardware
  deliberately shares material-palette texels, and keys share blank side
  texels. Textures are generated directly from original deterministic
  procedural raster artwork; no high-to-low bake is required by the request.

## Verification actually run

Built on the RTX 3080 Ti development machine on 2026-10-02, with Blender
**5.2.2 LTS**. Rendering remained Cycles CPU/four threads as specified by
`docs/ASSET_PIPELINE.md`.

Actual result: **28,130 triangles**, **four materials**, **three named
mesh nodes**, **eight embedded PNG textures**, no animations or collisions.
Overall open bounds: **0.330000 W × 0.287026 D ×
0.231845 H m**. Both footprint axes are centred at the origin;
underside Y=0. This is above the request's 8–20k triangle estimate but within
its binding 60k hero budget; the shaped keys, bevels, ports, vents and
underside details are retained for this look test.

Ran `tools/blender/build_assets.sh laptop_open` twice on the final source:
**exit 0 both times**. Real output:

```text
Building laptop_open with Blender 5.2.2 (CPU only, 4 threads)
ASSET BUILT: ~/Work/escapebox/game/assets/core/props/laptop_open.glb; 28130 triangles; 4 materials
```

The exporter also printed its “More than one shader node tex image used for
a texture” sampler warning for shared packed ORM channels. Those nodes
have identical Linear/EXTEND sampler settings; all eight images are
embedded and the same ORM texture supplies occlusion and metallic/roughness.
There were no export errors.

Ran `go run ./tools/assetcheck laptop_open`: **exit 0**. Real output:

```text
PASS laptop_open (28130 tris, 3 parts)
assetcheck: 1 asset(s) checked, 1 passed, 0 failed, 0 warning(s)
```

Ran isolated Godot **4.7.2** headless verification using
`GLTFDocument.append_from_file` and `generate_scene` (scratch project and
script under ignored `assets/cache/laptop_open/godot-check/`). It did not
import or modify the shared game project. Real output:

```text
PASS Godot headless: GLB loads; base/lid/screen; 300x188mm display; local -Z normal; 0..1 UVs; 105deg lid; centre/normal anchors match; no collisions or animations
```

Also verified preview PNG dimensions, all embedded images, current source
and GLB hashes, no exported lights/cameras, and Python source compilation.
Personally inspected all three final preview compositions: QWERTY legends
and the asset identifier are correctly oriented and readable; the complete
laptop fits the isometric frame. The detail contact sheet exposes both
sides. Earlier drafts were revised to correct upside-down legends, soften
wear, darken the plastic and remove stretched touchpad normals. An initial
API error (`uv_layers.clear()` is unavailable) was corrected before these
successful builds.

Compared both complete final builds: the GLBs are **byte-identical**,
**13,126,804 bytes**, with metadata identical except `built_at`.

```text
PASS reproducibility: byte-identical GLB; metadata identical except built_at
SHA256 b26ae90e1f581e39f178dcb83ec3fd613896a5de54abdad86c613796455df105
```

Logs, the isolated import verifier and intermediate comparison artifacts
are in ignored `assets/cache/laptop_open/`. Re-ran assetcheck and the
Godot verifier against the final delivered rebuild: both exit 0.

Only laptop_open files were authored. Shared helpers, requests, runtime
code, other assets and documentation outside the asset lane were untouched.
No git commit was made.
