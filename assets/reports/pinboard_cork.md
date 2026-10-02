# pinboard_cork — M1 office look test

## Deliverables

- `tools/blender/props/pinboard_cork.py`: deterministic `build(out_dir)` and the
  shared headless CLI. Uses the accepted keypad_4 and desk_3drawer structure,
  with all asset-specific surface, lettering and geometry code kept local.
- `game/assets/core/props/pinboard_cork.glb`: `board`, `header_card`, and `pins`;
  four Principled PBR materials with embedded PNG textures. No collisions,
  animation, cameras or lights.
- `assets/previews/pinboard_cork_{front,iso,detail}.png`: 1024 × 1024 neutral
  grey studio renders, shared three-point lighting, Cycles CPU, 32 samples,
  denoising, four threads.
- `assets/meta/pinboard_cork.json`: actual exported counts, bounds and hashes;
  `anchors_godot_m.cork_front_z` derived from the exported cork primitive.

## Appearance and construction

The 1200 × 800 mm board has a 20 mm deep, 20 mm wide natural oak frame,
mitred corners and 0.8 mm roundovers. The cork face is recessed 3.5 mm
behind the frame. Original procedural cork includes individual compressed
chips, fine fibres, darker interstices, varied roughness and tangent normal
relief. Covered margins are darker; two subtle old-notice silhouettes and
20 old punctures provide restrained office wear. The specified WiFi area,
Godot X +0.10 to +0.40 / Y -0.10 to +0.10 m, has no pins, puncture marks or
old-notice silhouettes.

Seven pushpins have modelled spool heads and steel needles: six unused
pins on the cork and one pin holding the header. Muted red, blue, ochre and
olive plastics share one baked material; needles use metallic response
within that same material. The original 300 × 70 mm header card is centred
at Godot Y +0.33 m, with 450-micron thickness, a restrained 0.8 mm curl and
fine paper fibres. `IT NOTICES` is the only text: original antialiased bold
sans stroke lettering, 30 mm cap height, black on warm white. No other
papers or readable marks are included. The Guest WiFi Document remains a
separate integration asset.

Base colour, tangent normals and ORM are baked from original procedural
materials (lettering starts as a locally generated stroke raster). Cork
maps are 2048 × 2048; frame, pin and card maps are 1024 × 1024. Unique UV
islands are packed per material across all its components, with 8 px
packing and bake margins. ORM stores gently blended ray-traced AO in R,
roughness in G and metallic in B. All bake passes use Cycles CPU at 16
samples; exported shaders use Principled and image textures.

## Integration and deviations

Origin is the centre of the back mounting face at Godot Z=0. Blender +Y
exports toward Godot -Z. The cork front is Godot Z=-0.0165 m; position the
separate WiFi card just in front of this anchor. All three meshes have
identity location, rotation and scale; the header and its pin are grouped
under `header_card` as requested. Pins stand proud of the 20 mm board, so
the complete asset depth is 29.35 mm including their projection. This is expected
physical detail, not a change to the board dimensions.

No external textures, fonts or assets were used; no attribution entry is
needed. No shared helper, request, runtime, scene, room manifest or other
asset file was edited. No commit was made.

In-engine placement and the acceptance screenshot remain Claude's review
step. Start with the exported PBR values; keep the normal map enabled and
ORM channel mapping intact. If Godot cached an earlier build, refresh
only this asset's extracted textures and their import sidecars as the
pipeline describes.

## Verification actually run

Ran `tools/blender/build_assets.sh pinboard_cork` for the initial pass and
again for the final material/framing revision: both **exit 0** on this
Alienware checkout, Blender 5.2.2 LTS. All previews and baking used CPU,
four threads, through the shared serialized wrapper. Real final-version
build output excerpt:

```text
Building pinboard_cork with Blender 5.2.2 (CPU only, 4 threads)
PASS geometry: 1200 x 800 x 20 mm frame; back Z=0; cork front Z=-0.0165; WiFi region clear; 3 applied meshes
ASSET BUILT: ~/Work/escapebox/game/assets/core/props/pinboard_cork.glb; 7068 triangles; 4 materials
```

Ran `go run ./tools/assetcheck pinboard_cork` after the final-version
previews finished: **exit 0**, complete real output:

```text
PASS pinboard_cork (7068 tris, 3 parts)
assetcheck: 1 asset(s) checked, 1 passed, 0 failed, 0 warning(s)
```

An earlier validator run during preview rendering passed with one warning
that the detail PNG was not yet written. The final check above includes
all three finished previews.

The glTF exporter emitted its existing shared-ORM warning:

```text
WARNING: More than one shader node tex image used for a texture. The resulting glTF sampler will behave like the first shader node tex image.
```

An independent GLB inspection verified twelve embedded PNGs, each within
2048 px; all four materials reference the same texture index for ORM
occlusion and metallic/roughness, with the shared Linear/EXTEND settings.
The three preview PNGs are exactly 1024 × 1024. Source/GLB hashes and the
exported cork anchor match metadata. Geometry is 7,068 triangles, three
parts, four materials; the GLB is 20,063,868 bytes.

Personally inspected all three revised previews: brown cork, oak edge
roundovers and mitres, coloured pushpins, legible bold header, full header
card in the detail view, sparse wear, and unobstructed WiFi area. The first
render was too pale and its detail crop clipped the card; both were
corrected in the final script before the revision build.

Both the initial and final GLBs passed an isolated Godot 4.7.2 headless import under
`assets/cache/pinboard_cork/godot-check/`, using `GLTFDocument` without
editing or importing the main game project:

```text
PASS Godot headless: GLB loads; 3 named meshes; 7068 triangles; textured PBR; back Z=0; cork Z=-0.0165; 1.20 x 0.80 m; no collisions
```

Full build logs and private verification files are in ignored
`assets/cache/pinboard_cork/`. No windowed Godot run, room integration,
acceptance screenshot, or full runtime test suite was performed.


## Final rebuild and reproducibility

Ran `tools/blender/build_assets.sh pinboard_cork` a third time, with no
source changes after the material/framing revision: **exit 0**. Builds 2
and 3 produced a **byte-identical GLB**; all metadata fields are identical
except `built_at`. Actual comparison output:

```text
PASS reproducibility: byte-identical GLB; metadata identical except built_at
GLB SHA256 a3166b2792d56383953f9d5147f7fc47f4e6cad0d0fb07a899c94e210d700755
```

An attempted comparison of complete preview-PNG hashes found differences.
The PNGs include `Date`, `RenderTime`, and Cycles timing metadata, which
changes between renders. Byte-identical preview PNGs are not claimed;
the final images were inspected, and the GLB and asset metadata meet the
pipeline's reproducibility requirement.

After the third build, ran `go run ./tools/assetcheck pinboard_cork` again:
**exit 0**, complete final output:

```text
PASS pinboard_cork (7068 tris, 3 parts)
assetcheck: 1 asset(s) checked, 1 passed, 0 failed, 0 warning(s)
```

Also reran the isolated Godot import check on the final GLB: **exit 0**,
with the same successful import/bounds/PBR/collision output shown above.
Final metadata contains:

```json
"anchors_godot_m": {
  "cork_front_z": -0.0165
}
```

Final logs: `assets/cache/pinboard_cork/build_3.log`,
`assetcheck_final.log`, `godot-check-final.log`, and `reproducibility.log`
inside that same asset-only cache directory.
