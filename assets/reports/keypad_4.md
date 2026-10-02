# keypad_4 — M0 asset pipeline smoke test

Built and verified on the local Linux / Intel UHD 620 host on 2026-10-01,
using Blender **5.2.2 LTS**. Ready for Claude's SDK integration and visual
review in the room; the request remains open in Claude's lane.

## Deliverables

- `tools/blender/build_assets.sh`: selected/all prop builds, 5.2.x version
  gate, request preflight, serialized Blender processes and four threads.
- `tools/blender/common/`: scene/seeding, geometry/UVs, named PBR materials,
  GLB export, metadata, CPU studio previews and CLI helpers. Usage and the
  coordinate convention are documented in `tools/blender/README.md`.
- `tools/blender/props/keypad_4.py`: deterministic `build(out_dir)` and
  standalone headless `--out` entry point, with no external dependencies.
- `game/assets/core/props/keypad_4.glb`.
- `assets/previews/keypad_4_front.png`, `keypad_4_iso.png`,
  `keypad_4_detail.png`: **1024 × 1024**, neutral grey, three area lights,
  **Cycles CPU, 32 samples, denoise, four threads**.
- `assets/meta/keypad_4.json`: actual exported triangle count, dimensions,
  required parts, materials, embedded textures, empty animations,
  per-key origins, script/shared-tool hashes, version and UTC build time.

## Result

**5,674 triangles**, including the 12-triangle collision box; **5,662**
visible triangles. **Five materials**, **16 named mesh nodes**, no animation.
Bounds are **0.075 W × 0.022 D × 0.115 H m**, within float precision.
Godot-space bounds are `[-0.0375, -0.0575, -0.022]` to
`[0.0375, 0.0575, 0]`. The back mounting face is centred at the origin.

Dark zinc-alloy housing, lightly polished edges and faint key grime,
four recessed six-lobed Torx heads joined into `body`, individually named
rounded rubber keys, a recessed smoked screen and a white tintable
emissive status dome. Key origins sit at the plate face, Godot Z = -0.016 m;
caps extend to -0.022 m. Rotation and scale are applied. Keys are ordered
`1 2 3 / 4 5 6 / 7 8 9 / CLR 0 ENT` when viewed from the front.

Embedded textures: housing base colour, tangent-space normal and packed
ORM at **1024 × 1024** each, plus one **1024 × 1024** legend atlas shared
by all keys. Housing UV islands are separated, including bevels and the
display recess; keys deliberately share an atlas's blank region on their
sides. All geometry is explicitly triangulated and modifiers applied.
Legends use an original bold rounded stroke alphabet, rasterised by the
script: no font file, download, third-party asset or attribution needed.

## Verification actually run

Ran `tools/blender/build_assets.sh keypad_4` twice on the final scripts;
both returned **exit 0**. The GLBs are **byte-identical**, including their
JSON chunks, with no timestamp normalization necessary. Size: 2,755,492 bytes.

```text
SHA256 cf2aa3f98878c7557333974547f08d19234f1b8b09116bc0a70fb7b4a26b7cc5
```

Metadata is identical except `built_at`: `2026-10-02T00:47:36+00:00`
and `2026-10-02T00:49:42+00:00` (2026-10-01 in America/Chicago).
Local comparison evidence and build logs are in ignored `assets/cache/`.

Ran `go run ./tools/assetcheck keypad_4` with Go's build/temp caches
redirected into `assets/cache/` and network module fetching disabled:

```text
PASS keypad_4 (5674 tris, 16 parts)
assetcheck: 1 asset(s) checked, 1 passed, 0 failed, 0 warning(s)
```

Ran Godot **4.7.2** only with `--headless`, using an isolated scratch
project in `assets/cache/godot-check/` and `GLTFDocument.append_from_file`
plus `generate_scene`. It loaded the GLB and inspected the generated meshes:

```text
PASS Godot headless: GLB loads; 15 visible meshes; 12 keys at Z=-0.016, caps face -Z; applied transforms; back mount at Z=0
```

Also checked the exported accessor bounds, all key translations, absence
of cameras/lights/animations, four embedded images, and sharing of the
same packed ORM texture for occlusion and metallic/roughness. Python source
compiles and `bash -n tools/blender/build_assets.sh` passes. A fake version
executable confirmed loud rejection of Blender 5.1.0; invalid asset ids
and absent scripts also fail before invoking a build.

Personally inspected all three PNGs. Front facing, row ordering, digit
legends, `CLR` and `ENT` are correct and legible. The initial overly light
housing/keys and low-resolution decorative label were revised before the
two final reproducibility builds. No Eevee, GPU compute or windowed Godot
was used. A room screenshot and gameplay wiring remain Claude's review.

## Clarifications, deviations and integration notes

- The stated 22 mm overall depth includes a **4 mm rear mounting plinth**,
  the requested **12 mm plate**, and **6 mm protruding key caps**.
- **Press-direction conflict in the request:** with the required applied
  rotations and front facing Godot -Z, moving a key into the plate means
  **+0.0025 m along local Z**. The request's local -Z travel points outward.
  Geometry follows its explicit mount-plane/facing requirements; Claude
  should use +Z for the press tween. No animation is exported as requested.
- Blender's native shutdown stalled in this sandbox after completed
  exports/renders, even with audio disabled. `common/cli.py` flushes output
  and exits directly after all synchronous writes finish; exceptions print
  tracebacks and exit 1. Imported `build(out_dir)` returns normally.
- The glTF exporter in this Blender patch throws `KeyError: loglevel` when
  an explicit log level is passed. The shared exporter uses its working
  default log level; all binding export settings are retained.
- Tint `M_keypad_4_led` base/emission together for status feedback. Screen
  digits belong to the in-engine Label3D, placed slightly toward -Z from
  the window face at Z = -0.015 m. Increase LED emission only as needed
  when Claude reviews room exposure/glow. `body-col` covers the full box;
  keys have no additional collision meshes.
- The game's import pipeline created extracted PNGs and `.import` sidecars
  concurrently during the first draft (19:42 local). Those existing files
  were left untouched. **Reimport the final GLB and refresh its extracted
  images** during integration: the final embedded housing maps are 1024 px
  and the earlier extracted draft maps were 512 px.

No runtime code, room YAML, request file, or other agent's tooling was
edited. No commit was made.

## Revision — 2026-10-02: collision-only helper

Applied Claude's dated M1 look-test follow-up: renamed the separate collision
box from `body-col` to `body-colonly` in `tools/blender/props/keypad_4.py`,
including its metadata declaration and expected-part check. Rebuilt the GLB
and refreshed `assets/meta/keypad_4.json`. Status remains accepted; the
request file was not edited.

Compared against a snapshot of the original accepted output. The GLB JSON
changes only `nodes[1].name` and `meshes[1].name`; its complete binary chunk
is byte-identical, preserving all geometry and embedded textures. Bounds,
key transforms, materials, triangle count (5,674), parts count (16), and
animations are unchanged. Metadata changes only the collision/part name,
script hash, GLB hash, and build timestamp. New GLB SHA-256:

```text
5b15b794fd4840c8e3113cfa107ecef17a15a207d65247430a8a32f3ffb80536
```

The build regenerated all three previews with Cycles CPU, four threads.
Those renders had tiny pixel differences from the accepted PNGs (maximum
3/255 per channel), so the original front/iso/detail PNGs were restored
byte-for-byte to fulfill the requested output identity. Regenerated images
and comparison evidence remain in ignored
`assets/cache/keypad_4-collision-revision-20261002/`.

Verification actually run on the Alienware Linux host, Blender 5.2.2 LTS
and Godot 4.7.2:

- `tools/blender/build_assets.sh keypad_4`: exit 0; actual final line:
  `ASSET BUILT: ~/Work/escapebox/game/assets/core/props/keypad_4.glb; 5674 triangles; 5 materials`.
- `go run ./tools/assetcheck keypad_4`: exit 0; actual output below.
- Godot headless import in an isolated project under the revision cache:
  exit 0. Ran an unchanged copy of
  `game/tests/assets/test_keypad_4.gd` with gdUnit4: **4/4 passed**, zero
  errors/failures; `test_has_collision` still finds a `StaticBody3D`.
  The shared game's import files and extracted textures were not touched.

```text
PASS keypad_4 (5674 tris, 16 parts)
assetcheck: 1 asset(s) checked, 1 passed, 0 failed, 0 warning(s)
```

No visual redesign, shared helper changes, other asset edits, runtime or
room edits, or commit. In-room visual review remains Claude's lane.
