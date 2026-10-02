# intercom_panel — M1 look test

Built on 2026-10-02 with Blender **5.2.2 LTS**. All baking and previews use
**Cycles CPU, four threads**. Ready for Claude's room integration and visual
review; the request status is unchanged.

## Deliverables

- `tools/blender/props/intercom_panel.py`: deterministic `build(out_dir)` and
  common CLI entry point; fixed seed 102026; no network, fonts or downloads.
  Follows the accepted keypad's geometry/export/preview structure and the
  desk's procedural shader, global unwrap and PBR bake structure.
- `game/assets/core/props/intercom_panel.glb`: **18,988 triangles**, four named
  objects (`body`, `screen`, `btn_call`, `led_status`), five requested materials,
  **six embedded 1024 x 1024 PNG maps**, no collision or animations.
- `assets/previews/intercom_panel_{front,iso,detail}.png`: **1024 x 1024**, neutral
  grey, common three-point lighting, Cycles CPU, 32 samples and denoising.
  All three were personally inspected after the final visual refinements.
- `assets/meta/intercom_panel.json`: actual exported counts, dimensions, named
  parts, script/pipeline/GLB hashes, Blender version, build time and LCD anchors.

## Construction and materials

A brushed stainless faceplate sits over a rounded wall housing, with a fine
black gasket seam, four recessed six-lobed tamper screws with centre pins,
a dark recessed LCD and a separately inset speaker sheet. The grille has
**120 actual 2.9 mm through-holes**, at 8 mm pitch, in a **1.2 mm** sheet;
a dark cavity behind it remains clear of the bores. A 38 mm dark anodised
call cap has a machined steel bezel, a light CALL marking and restrained
oil/wear. A lined microphone bore and a separate white emissive LED flank it.
SECURITY and CALL use original stroke geometry, without external typography.

Brushed grain, fine surface texture, irregular edge grime and local hand oil
are procedural PBR detail baked into base colour, tangent normal and packed
ORM maps. UVs are globally unwrapped without overlap per mapped material,
with **8 px bake margins**. ORM is R=1 (neutral occlusion), G=roughness,
B=metallic; the light button lettering is nonmetallic in the same button map.
No high-to-low bake or third-party input was used; no attribution entry is
needed. Materials are exactly `M_intercom_panel_body`, `_button`, `_grille`,
`_screen`, and `_led`.

## Dimensions and integration

Housing: **0.22 W x 0.32 H x 0.04 D m**, back face on Godot Z=0, front at
Z=-0.04. The origin is the centre of that back mounting face. The proud call
button/marking brings overall depth to **0.04256 m**. Blender +Y exports to
Godot -Z; scale and rotation are applied, and moving/decor parts retain only
their location.

The following required block is generated in metadata:

```json
"anchors_godot_m": {
  "screen_centre": [0, 0.067, -0.038],
  "screen_size": [0.18, 0.10]
}
```

`screen` is an exact **180 x 100 mm** front-facing plane with its origin on
its visible surface, **2 mm recessed** from the faceplate. UVs cover 0..1
without mirroring. Put dynamic hint text just forward of this surface
(toward Godot -Z), or use its UVs for the runtime display. The LCD is dark
with low idle emission and has its own material; hints are not baked in.
The LED has a white base and white emission, ready for runtime tinting.

## Verification actually run

Ran `tools/blender/build_assets.sh intercom_panel` **twice on the unchanged
final script: both exit 0**. Relevant real output from both runs:

```text
Building intercom_panel with Blender 5.2.2 (CPU only, 4 threads)
PASS geometry: mount origin, LCD anchor/UV, applied transforms, 120 through-holes, no collision/animations
ASSET BUILT: ~/Work/escapebox/game/assets/core/props/intercom_panel.glb; 18988 triangles; 5 materials
```

Ran `go run ./tools/assetcheck intercom_panel`: **exit 0**.

```text
PASS intercom_panel (18988 tris, 4 parts)
assetcheck: 1 asset(s) checked, 1 passed, 0 failed, 0 warning(s)
```

Ran Godot **4.7.2** with `--headless` in the isolated project
`assets/cache/intercom_panel/godot/`: **exit 0**. Direct GLTFDocument loading
verifies the actual imported nodes and materials without changing the game.

```text
PASS Godot headless: 4 meshes; 5 PBR materials; embedded maps; mount z=0; LCD origin (0,0.067,-0.038), size 0.18x0.10, UV 0..1, normal -Z; white emissive LED; no collision/animations
```

The glTF exporter emits its shared ORM sampler warning once per mapped
material: “More than one shader node tex image used for a texture.” Sampler
settings are identical; the exported AO and metallic/roughness channels use
the same packed image. Assetcheck has zero warnings, and Godot retains the
embedded PBR maps. Full logs are under `assets/cache/intercom_panel/`: `build.log`, `rebuild.log`,
`assetcheck.log`, `godot_verify.log` and `reproducibility.log`. Assetcheck and
the headless Godot check were rerun after the second build and passed again.

## Reproducibility verified

The two final builds produced a **byte-identical GLB**, **4,314,940 bytes**:

```text
SHA256 3494cbfac711715fdac2c0662bbac52c13552520c75a731d4b86cc6ca5736adf
```

Metadata is identical except `built_at`: `2026-10-02T14:13:08+00:00` and
`2026-10-02T14:34:16+00:00`. All six embedded images and the packed ORM image sources
were also checked directly in the GLB JSON.

An exact preview pixel comparison was not identical: repeated CPU/denoised
renders differ on **19 front pixels, 5 iso pixels and 18 detail pixels** out
of **1,048,576 pixels per image**, with a maximum difference of **one 8-bit
RGB level (1/255)**. The final three previews were inspected again and show
the same appearance. PNG render-date/timing metadata also changes between
runs. This does not affect GLB determinism. Detailed measurements and the
first final build are retained under `assets/cache/intercom_panel/`.

## Deviations and review notes

No functional deviations. The 40 mm depth describes the housing, with
controls standing slightly proud as documented above. Fine brushing and
finger oil should be judged under a raking workspace light. Retain the
embedded PBR maps for the look test; flat replacement materials lose this
detail. Suggested room tweaks are exposure and LED emission/glow as needed.

The in-room screenshot and SDK hint text/chime integration remain Claude's
review. No runtime code, room scenes/YAML, request files, other assets,
shared Blender tooling, or documentation outside this report were edited.
No commit was made.
