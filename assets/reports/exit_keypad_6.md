# exit_keypad_6 — M1 look-test asset

Built on the Alienware development checkout with Blender 5.2.2 LTS.
All procedural baking and previews use **Cycles CPU**, four threads, through
`tools/blender/build_assets.sh` and its shared `flock`. No external assets,
fonts, downloads, new dependencies, shared helper changes or commits.

## Deliverables and appearance

- `tools/blender/props/exit_keypad_6.py`: deterministic seeded `build(out_dir)`
  with the shared headless CLI. The accepted keypad_4 supplies the structure
  and original stroke alphabet; desk_3drawer supplies the procedural PBR bake
  pattern. Those routines are copied/extended locally, so rebuilding this
  asset does not depend on another concurrently edited asset script.
- `game/assets/core/props/exit_keypad_6.glb`: **16,050 triangles** including
  the 12-triangle collision helper; **16,038 visible triangles**, **17 named
  mesh nodes**, **six materials**, **12 embedded PNGs**, no animation.
- `assets/previews/exit_keypad_6_{front,iso,detail}.png`: 1024 × 1024,
  neutral-grey shared three-point studio, 32 samples, denoising. Detail
  frames the engraved clue plate. All three were visually inspected:
  legends are upright, row order is correct, and both clue lines read clearly.
- `assets/meta/exit_keypad_6.json`: actual counts, texture sizes, bounds,
  names, applied-transform/key-anchor information, source/pipeline/GLB hashes,
  Blender version, build timestamp and the requested `anchors_godot_m` block.

The cast dark-grey housing has a rear mounting step, rounded 2.5 mm edges,
real display and key recesses, fine surface stipple and localized perimeter
scuffs. Twelve individually movable rubber caps sit above recessed gaskets.
Caps 1, 4, 7, 0 and ENT have smoother, lightly polished thumb-contact areas;
the neutral legends remain clear. Four recessed Torx fasteners secure the
housing. The smoked display is blank for six runtime characters, and the
white emissive status dome has its own tintable material.

The separate stainless clue plate has a 0.45 mm edge bevel, horizontal
brushing, subtle tonal variation and sparse hairline scratches. Four real
through-holes with tapered countersinks receive recessed Torx heads.
`MAGLOCK OVERRIDE:` / `SITE + RACK` use the extended original sans stroke
alphabet at a nominal 22 mm cap height. Black-filled strokes also alter the
roughness/metallic maps and depressed groove borders in the tangent normals.
The engraving is texture-based; no external font or floating text geometry.

Four surface materials have baked base colour, tangent normal and packed
ORM maps. Body, key/legend atlas and screws are 1024 px; plate maps are
2048 px. UV islands are unique within each material, with 8 px packing/bake
margins. Base colour and roughness/metallic are procedural emission bakes;
AO is ray traced and gently packed into ORM R. Roughness is G, metallic B.
The exported graphs contain Principled materials and image textures.

## Dimensions, anchors and integration

Housing: **0.120 W × 0.180 H × 0.028 D m**, back mounting face at Godot Z = 0,
centred on the asset origin. Keys are **0.022 W × 0.017 H m**, with
**0.028 × 0.022 m** pitch and 4 mm protrusion. Key objects keep only location,
with their base origins at Z = −0.028 m. Press each by **(0, 0, +0.0025) m**
into the housing. The full asset depth, including raised caps, is **0.032 m**;
this is additional to the explicitly specified 28 mm housing depth.

Plate: **0.360 W × 0.130 H × 0.004 D m**, centre at
**(0, +0.320, −0.002) m**, with its back at Z = 0. The combined asset bounds
are approximately **(−0.180, −0.090, −0.032)** to
**(+0.180, +0.385, 0) m**, or **0.360 W × 0.032 D × 0.475 H m**.
The origin stays at the keypad's mounting centre, as explicitly requested.

```json
"anchors_godot_m": {
  "screen_centre": [0, 0.057, -0.027],
  "screen_size": [0.085, 0.020],
  "plate_centre": [0, 0.320, -0.002]
}
```

`screen_centre` is the **front window surface centre**, useful for placing
runtime characters. The screen mesh's geometric centre is Z = −0.0267 m;
its front is Z = −0.027 m, exactly 1 mm behind the housing face. Place runtime
characters a little toward −Z from the front window. `plate_centre` is the
plate mesh's geometric/object centre.

`body-colonly` is a closed box over the housing alone. Godot imports it as
an invisible static collision helper; its default mesh importer produces a
`ConcavePolygonShape3D` with the box's 12 triangles. It excludes the keys and
plate. All object rotations/scales are applied; faces point toward Godot −Z.

Claude owns in-room wiring and visual approval. Keep the screen dark and
LED emission disabled while unpowered; enable runtime characters/screen
emission and tint the LED's base/emission together for feedback. Re-extract
embedded textures if Godot cached an earlier version. No runtime code,
room scene, room.yaml, request status or another asset's files were edited.
No in-room screenshot or gameplay approval is claimed.

## Verification actually run

The first attempt was stopped before baking/export (exit 143) while correcting
an inward-wound countersink cutter. The corrected final build completed
with **exit 0**. Actual build output excerpt:

```text
Building exit_keypad_6 with Blender 5.2.2 (CPU only, 4 threads)
PASS geometry: 17 named parts; mount z=0; independent key bases z=-0.028; applied transforms
ASSET BUILT: ~/Work/escapebox/game/assets/core/props/exit_keypad_6.glb; 16050 triangles; 6 materials
```

The exporter emitted its existing warning for shared ORM image nodes:

```text
WARNING: More than one shader node tex image used for a texture. The resulting glTF sampler will behave like the first shader node tex image.
```

The generated sampler settings agree. Direct exported-data checks confirmed
that occlusion and metallic/roughness share the packed texture index for
all four mapped materials. They also verified source/GLB hashes, unit scales,
identity rotations, exact key bases/depth, screen surface and plate anchors,
12 embedded images and three 1024 px previews.

Actually ran `go run ./tools/assetcheck exit_keypad_6`. Real output:

```text
WARN exit_keypad_6: bounds centre y = 0.1475 m; a mount-plane-centre origin would put it near 0
PASS exit_keypad_6 (16050 tris, 17 parts)
assetcheck: 1 asset(s) checked, 1 passed, 0 failed, 1 warning(s)
```

This warning is expected from the requested plate at Y = +0.32 m: the
combined bounds centre differs from the explicitly required keypad origin.
No origin or request change was made to suppress the warning.

Godot **4.7.2 headless** imported a copy in the isolated asset-only project
under `assets/cache/exit_keypad_6/godot-check/`, then checked the imported
scene, with **exit 0**:

```text
PASS Godot headless: GLB imports; 16 visible meshes; 12 independent keys facing -Z; six PBR materials; screen/plate anchors; one housing-only collision box
```

The check confirms no visible collision helper, a single closed-box collision
mesh of the specified size, applied transforms, baked material textures and
correct anchors. Python source syntax and allowed-import checks also passed.

Both final `tools/blender/build_assets.sh exit_keypad_6` builds exited **0**.
The final two GLBs, including all embedded texture bytes, are **byte-identical**.
Metadata is identical except `built_at` (`2026-10-02T14:11:35+00:00` and `2026-10-02T14:33:07+00:00`).
The final assetcheck rerun also exited **0**, with the same output above.

```text
PASS reproducibility: byte-identical GLB including all embedded textures; metadata identical except built_at
GLB 10530464 bytes; SHA256 95e1993874010ae92abc109fbadd9ec75eb7d0cef86d2e273fb989f8f0549eb7
```

An additional whole-PNG byte comparison did not pass. Blender writes Date,
RenderTime and Cycles timing metadata into its PNGs, so these preview files
have different byte hashes. The first render's pixel buffers were not retained;
no pixel-identity claim is made. The final three PNGs were visually inspected.
No source/model revision was required after the successful first final build.

Full output is in this asset's ignored cache directory:
`build.log`, `repro-build.log`, `final-assetcheck.log`, `repro-check.log`,
`godot-import.log`, and `godot-check.log`. The isolated Godot check used the
first final GLB, which is byte-identical to the delivered second final GLB.
