# filing_cabinet_keypad — M1 look test

Built on the Alienware RTX 3080 Ti development box, 2026-10-02, with
Blender **5.2.2 LTS**. Baking and previews use **Cycles CPU, four threads**.
Ready for Claude's in-engine assembly and visual review; the request status
has not been changed.

## Deliverables and result

- `tools/blender/props/filing_cabinet_keypad.py`: deterministic, standalone
  `build(out_dir)` and common CLI entry point, fixed seed, no network or
  third-party dependencies. Uses the accepted keypad's shared geometry,
  material, export, metadata, scene, preview and CLI structure.
- `game/assets/core/props/filing_cabinet_keypad.glb`: **13,720 triangles**,
  **four named mesh objects**, **four Principled PBR materials**,
  **10 embedded PNG images**, no collision helpers or animations.
- `assets/previews/filing_cabinet_keypad_{front,iso,detail}.png`:
  **1024 x 1024**, neutral grey, common three-point studio lighting,
  **Cycles CPU, 32 samples, denoise, four threads**. Detail shows only the
  top drawer moved **0.40 m toward Godot -Z**, viewed from above.
- `assets/meta/filing_cabinet_keypad.json`: exported budgets and bounds,
  script/shared-tool/GLB hashes, version/time, and `anchors_godot_m`.

The light office-grey powder-coated carcass is **0.50 W x 0.60 D x 1.20 H m**.
Closed overall bounds, including the projecting pulls, are
**0.50 W x 0.672 D x 1.20 H m**. The carcass is hollow behind the top drawer;
its sides, rear, cap, plinth, folded front stiles, drawer separators and
outside slide rails are real geometry. Panel edges have 1–4 mm bevels,
with a 3 mm rolled top edge and rounded 4 mm pull edges.

`drawer_top` contains the 0.46 x 0.22 x 0.02 m front, brushed steel pull,
recessed off-white blank card, folded steel holder, recessed fasteners,
and finished open tray. Clear interior dimensions are **0.42 W x 0.50 D m**;
floor surface is at Y=0.755 m, sheet sides extend to Y=0.915 m, and the
rolled lips extend another 2 mm. The lower drawers contain static fronts,
pulls and blank label holders. All details are joined into their owning
named object, so the top drawer slides as one part.

All appearance is original procedural work, baked with an **8 px margin**:
paint orange peel, restrained corner and pull-area chips, fine top-front
scuffs, fingertip oil in roughness, faint plinth rust, brushed metal grain,
and galvanised tray spangle. Paint and interior base colour/normal/ORM maps
are **2048 px**; metal maps **1024 px**; the blank card base colour **512 px**.
ORM uses R=1 (neutral occlusion), G=roughness, B=metallic; cavities and gaps
come from geometry. No high-to-low baking or downloaded assets were used,
so no attribution entry is required.

## Integration anchors and motion

The complete closed footprint is centred at the root origin on the floor.
To achieve this while retaining the requested proportions, the entire
carcass/design is translated **+0.036 m in Godot Z**. These are the exported
Godot-space anchor values, also stored in metadata:

| Anchor | Value in metres |
|---|---|
| Carcass back plane | Z = +0.336 |
| Carcass front plane | Z = -0.264 |
| `drawer_top` origin, centre of front outer face | (0, 0.85, -0.284) |
| `keypad_mount`, keypad back-face centre | (0, 1.12, -0.264) |
| `label_card_top`, blank card outer face centre | (0, 0.907, -0.2858) |

Mount the existing `keypad_4` at `keypad_mount`; no keypad geometry is
included. The fixed header spans Y=0.97–1.19 m. The keypad mounting plane is
flat and unobstructed. Label text should sit slightly toward -Z from the
reported card surface; visible card area is 0.09 x 0.03 m.

Slide only `drawer_top` by **-0.40 m along Godot Z**. Its open origin becomes
(0, 0.85, -0.684). Rotation and scale are applied, and drawer objects retain
only their location. The script checks each fixed carcass component against
the top tray's full swept envelope before joining/exporting; rails sit
outside the tray walls and separators below its floor. The GLB and metadata
always contain the closed state, and preview-only movement is restored.

## Verification actually run

Ran `tools/blender/build_assets.sh filing_cabinet_keypad` **twice** on the
unchanged final script: **both exit 0**. Relevant real output:

```text
Building filing_cabinet_keypad with Blender 5.2.2 (CPU only, 4 threads)
ASSET BUILT: ~/Work/escapebox/game/assets/core/props/filing_cabinet_keypad.glb; 13720 triangles; 4 materials
```

The exporter also prints repeated texture-sampler warnings when gathering
the shared ORM channels. The image sampler settings match, the GLB retains
all ten embedded images, and Godot loads the intended PBR maps.

Ran `go run ./tools/assetcheck filing_cabinet_keypad`: **exit 0**.

```text
PASS filing_cabinet_keypad (13720 tris, 4 parts)
assetcheck: 1 asset(s) checked, 1 passed, 0 failed, 0 warning(s)
```

Ran Godot **4.7.2** with `--headless` in an isolated scratch project under
`assets/cache/filing_cabinet_keypad/godot/`, using `GLTFDocument` to load the
GLB directly: **exit 0**.

```text
PASS Godot headless: GLB loads; 4 meshes; embedded PBR maps; applied transforms; centred 0.50 x 0.672 x 1.20 m bounds; drawer pivot and -0.40 m travel correct
```

Also checked script syntax, exact exported nodes/material count, ten
embedded images, shared image sources for occlusion and metallic/roughness,
and absence of cameras and animations. Personally inspected all three
final previews, including the completed tray floor, walls and rolled lips.
Logs and scratch verification files are retained in the ignored
`assets/cache/filing_cabinet_keypad/` directory.

## Reproducibility verified

The two final builds produced a **byte-identical GLB**, **14,724,420 bytes**:

```text
SHA256 a0a0ca2e58658cbab30f5e2512ba26bdf2ff59b7c047a627fe73f88363400a98
```

Metadata is identical except `built_at`: `2026-10-02T05:44:38+00:00` and
`2026-10-02T05:55:50+00:00`. All three previews have **identical decoded RGB pixels**;
the PNG files' render-date and timing metadata changes between runs.
Comparison evidence is in `assets/cache/filing_cabinet_keypad/`.
Assetcheck was rerun after the second completed build and again passed with
zero warnings. The unchanged GLB is the same one verified in headless Godot.

## Deviations, limitations and review notes

No functional deviations from the request. The optional cable grommet is
omitted, keeping the mounting band clean. The +0.036 m origin adjustment is
required by the request's overall-footprint centring rule and is reported
above. Neutral baked occlusion avoids baking preview lighting into the
prop; room lighting/SSAO can shade its actual cavities in-engine.

Keep the embedded PBR textures for the room look test; flat replacement
materials lose the authored paint, brushing and wear. Judge fine surface
detail under a raking workspace light and room exposure. Fingerprint effects
are subtle roughness changes, rather than prominent printed marks. No
emissive material is needed on this cabinet; emissions belong to the
separately mounted keypad.

Claude's room screenshot, keypad wiring, dynamic document/USB placement
and gameplay test remain the integration review. If Godot extracted older
textures during an earlier draft, refresh this asset's extracted images
and import sidecars per the pipeline before that review.

No runtime code, room YAML, request files, docs outside the asset lane,
other assets, or shared Blender tooling were edited. No commit was made.
