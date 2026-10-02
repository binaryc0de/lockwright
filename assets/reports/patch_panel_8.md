# patch_panel_8 — revision 2: plugged leads

Implemented the dated revision in `assets/requests/patch_panel_8.md` using
Blender 5.2.2 LTS. The final GLB contains **57,900 triangles, nine meshes,
five materials and fifteen embedded PNG textures**. The original panel,
hanging leads, materials, rear-face origin and mounting anchors are retained.
No shared helpers, other assets, runtime code, room scenes, room.yaml or
request files were edited by this task. No third-party assets, fonts,
downloads, dependencies or commits were added.

## Added leads

`plug_a`, `plug_b`, `plug_c`, `plug_d` are independently movable meshes.
All four are parked at Godot **[-0.21, 0.008, -0.103] m**, with their origins
at that port mouth and identity rotation/scale. They deliberately overlap
in the GLB. Each contains an inserted RJ45 nose with eight contact pads,
release latch, ribbed boot, curved Cat6 jacket, paper tag and tie. The
jacket stays at constant X and descends into the continuous manager shelf;
there is no sideways run across neighbouring sockets. Each complete lead
is narrower than the 60 mm port pitch. A/B/C/D use the accepted red/blue/
yellow/green finishes and one/two/three/zero white bands, respectively.

The added triangle counts are A 1,168, B 1,204, C 1,240 and D 1,132:
**4,744 new triangles**, leaving 2,100 below the hero budget. The seated
parts use compact applied bevels and a smooth ten-sided jacket. All four
have the same geometry apart from stripe count and the tag's existing ink.
No collision helpers, animation, cameras or lights are exported.

The accepted five materials are baked before any new geometry is created.
New triangles reuse interiors of the existing atlas islands; paper tags
copy their accepted geometry and UVs. The white sleeves sample existing
white jacket texels, checked during the build, and follow the cable bend.
This adds no textures or materials. The source pins one cable-normal
boundary texel to its accepted value (PNG R at x=654, y=1264: code 132),
resolving an observed unchanged CPU bake variation between codes 130/132.
The delivered fifteen embedded PNGs match the accepted GLB byte for byte.

Metadata retains the existing anchors and adds:

```json
"port_pitch_m": 0.06,
"port1_godot_m": [-0.21, 0.008, -0.103]
```

The three existing previews were regenerated with the plugs hidden.
`patch_panel_8_plugged.png` hides the hanging leads and translates A/B/C/D
by the requested `(port - 1) * 0.06` offsets for ports 3/7/1/5. All four
previews are 1024 × 1024, neutral-grey, shared three-point studio, Cycles
CPU, 32 samples, denoised, four threads. Tags and stripe counts were
visually reviewed after correcting an initial atlas-seam sampling artifact.
Baking also uses Cycles CPU, 16 samples and 8 px margins. The script runs
headless with seeded randomness and no network. Its inspection `.blend`
cache is regenerated on every build and is never a build input.

## Request consistency issue

The accepted panel's printed port 1 is at **X=+0.21**, with numbers
increasing toward negative X. Revision 2 explicitly specifies port 1 at
**X=-0.21** and positive X steps. Those conventions are reversed. This
revision preserves the accepted panel and follows the new parking anchor
and translation formula exactly. Consequently, the specified A/B/C/D
preview translations lie beneath printed labels **6/2/8/4**, respectively.
The supplied logical port numbers are **3/7/1/5**. The owner/Claude needs
to reconcile this numbering conflict before the world visuals can match
the diagram's printed numbers. Neither labels nor SDK code were changed.

## Verification actually run

`tools/blender/build_assets.sh patch_panel_8` completed with **exit 0**,
through the shared `flock`, CPU only, four threads. Selected real output
from the final corrected-source build (`revision2-build-verified.log`):

```text
Building patch_panel_8 with Blender 5.2.2 (CPU only, 4 threads)
PASS geometry: 9 named parts; plug origins=(-0.210,0.008,-0.103); parked at port 1; rear z=0; rail z=-0.100; face z=-0.103; 60mm port pitch; applied transforms
PASS cable lengths: A=0.671m/1 stripes, B=0.686m/2 stripes, C=0.672m/3 stripes, D=0.687m/0 stripes
PASS plugged preview: A/B/C/D at ports 3/7/1/5; hanging leads hidden
ASSET BUILT: ~/Work/escapebox/game/assets/core/props/patch_panel_8.glb; 57900 triangles; 5 materials
```

`go run ./tools/assetcheck patch_panel_8` completed with **exit 0**.
Real output:

```text
WARN patch_panel_8: bounds centre y = -0.1925 m; a mount-plane-centre origin would put it near 0
PASS patch_panel_8 (57900 tris, 5 parts)
assetcheck: 1 asset(s) checked, 1 passed, 0 failed, 1 warning(s)
```

The existing warning reflects the hanging cables extending the bounds
below the panel's rear-face origin. The requested origin was preserved.
The checker's `5 parts` counts the main request table's five required
parts; it does not parse the added table in Revision notes. The independent
artifact audit and Godot check verify all **nine** exported meshes and
all four new port-mouth origins.

The preservation audit passed against a copy of the accepted GLB saved
before editing: every original position, normal, tangent, UV, index,
transform and material graph is unchanged; all fifteen embedded PNG
payloads are byte-identical. It also checked the four new origins, unit
rotations/scales, port-lane widths, texture budgets and four 1024 px PNGs.
The accepted front/iso preview pixels differ only by one display code at
a few dozen pixels (CPU render/denoising precision); the detail image
pixels match exactly. No preview PNG byte-identity claim is made.

Godot 4.7.2 imported a copy in an isolated project under this asset's cache.
Extracted textures were removed before reimporting. Import and the
headless scene check both completed with **exit 0**. Real check output:

```text
PASS Godot headless: 9 named meshes; four exact plug anchors; five textured PBR materials; no collision/animation; rear mount z=0; front toward -Z; applied transforms
```

The exporter retains its shared-ORM warning about multiple texture nodes;
the unchanged exported materials use the same sampler and ORM image for
occlusion and metallic/roughness. No in-room screenshot, gameplay test
or integration acceptance is claimed; those remain Claude's work.

Two complete builds of the final unchanged source completed with **exit 0**
(`revision2-build-verified.log` and `revision2-build-repro.log`). Their GLBs
are byte-identical, including all embedded textures; metadata matches
except `built_at`. The delivered GLB is **18,375,972 bytes**. Real comparison
output:

```text
PASS reproducibility: two unchanged full builds produce byte-identical GLB; metadata identical except built_at
GLB SHA256 d4046d9d4d1a6fe2d068a25b85dc0f855d30c46d0e9634d2d61193f4ac57ab85
GLB bytes 18375972
```

Assetcheck and the preservation audit were rerun after the reproducibility
build; both exited **0**. All four delivered previews were visually
inspected. The final front/iso comparisons against the accepted previews
found 44/46 pixels different by one display code, respectively; the detail
pixels match exactly. The Godot-tested GLB is byte-identical to the final
delivered GLB. `git diff --check` passed for this task's text deliverables.

Logs and audit scripts are in ignored `assets/cache/patch_panel_8/`:
`revision2-build-verified.log`, `revision2-build-repro.log`,
`revision2-repro-audit.log`, `revision2-assetcheck.log`,
`revision2-audit.log`, `revision2-godot-import.log` and
`revision2-godot-check.log`.

## Deliverables

- `tools/blender/props/patch_panel_8.py`
- `game/assets/core/props/patch_panel_8.glb`
- `assets/previews/patch_panel_8_front.png`
- `assets/previews/patch_panel_8_iso.png`
- `assets/previews/patch_panel_8_detail.png`
- `assets/previews/patch_panel_8_plugged.png`
- `assets/meta/patch_panel_8.json`
- `assets/reports/patch_panel_8.md`
