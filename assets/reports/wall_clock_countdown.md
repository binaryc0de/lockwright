# wall_clock_countdown

Built from `assets/requests/wall_clock_countdown.md` for the M1 look test.
The structure follows the accepted `keypad_4` and `desk_3drawer` scripts:
shared CLI/reset/export/preview helpers, applied geometry, computed GLB
metadata, portable baked PBR textures and CPU-only rendering.

## Asset

- 460 × 160 × 50 mm black powder-coated housing, with a chamfered perimeter,
  separate rear plate seam, four modelled Torx screw sockets and ten recessed
  side ventilation slots.
- Real window pocket and black gasket surround; 400 × 95 mm smoked dark-red
  acrylic surface sits 3 mm behind the housing face.
- `body` contains all static geometry, including the original white stroke
  lettering `UPS RUNTIME` and `h:mm:ss`. The paths are analytically rasterised
  into one 1024 px color/alpha print atlas, mapped to two single decal faces
  within `body`, avoiding overlapping coplanar strokes. Caption cap height is
  approximately 14 mm. No system fonts, downloads or third-party inputs were used.
- `screen` is a separate front-facing planar surface. Its origin is its
  visible centre and its unmirrored UVs cover exactly 0..1. It is deliberately
  blank; the live countdown is rendered by the room/SDK in Godot.
- Three Principled materials: `M_wall_clock_countdown_body`,
  `M_wall_clock_countdown_screen`, `M_wall_clock_countdown_print`.
- Procedural powder-coat micrograin, subtle finish variation, sparse edge
  chips, dusty upward-facing edge, brushed screw heads and mild acrylic
  cleaning smears. Color, tangent normal and packed ORM maps are baked at
  1024 × 1024 with an 8 px margin. AO is ray traced and packed into ORM R.
- No collision, animations, cameras or lights in the GLB. Body origin is the
  back mounting-face centre; Blender +Y becomes Godot -Z.

## Integration anchors

`assets/meta/wall_clock_countdown.json` records:

```json
"anchors_godot_m": {
  "screen_centre": [0, 0.012, -0.047],
  "screen_size": [0.4, 0.095]
}
```

Place the countdown text slightly forward of the surface, e.g. Godot
z = -0.0473, centred on the above anchor. Red emissive digits can start around
strength 2 and be tuned in the room's actual lighting and glow. Leave the
smoked acrylic material dark, with its baked roughness/normal maps intact.

## Deviations and review limits

The optional underside cable gland was omitted, preserving the requested
housing silhouette and unobstructed bottom caption. The four screw heads
stand 0.8 mm proud of the 50 mm housing. The screen is an opaque PBR surface,
which gives stable glTF/Godot rendering for a smoked display window without
requiring transmission or transparency sorting. No countdown time is baked
into the asset.

The three requested previews use `common/preview.py`, Cycles CPU, 32 samples,
denoising and four threads. In-engine appearance and SDK integration remain
Claude Code's review step; no room scenes or runtime code were edited.

## Verification

Executed on 2026-10-02 in `~/Work/escapebox`, Blender 5.2.2 LTS.

`tools/blender/build_assets.sh wall_clock_countdown` exited 0. Final output:

```text
Building wall_clock_countdown with Blender 5.2.2 (CPU only, 4 threads)
PASS geometry: mount-plane origin; 400x95mm window recessed 3mm; screen-centre anchor; UV 0..1; applied transforms
ASSET BUILT: ~/Work/escapebox/game/assets/core/props/wall_clock_countdown.glb; 4126 triangles; 3 materials
```

`go run ./tools/assetcheck wall_clock_countdown` exited 0:

```text
PASS wall_clock_countdown (4126 tris, 2 parts)
assetcheck: 1 asset(s) checked, 1 passed, 0 failed, 0 warning(s)
```

The exporter also printed the following sampler warning three
times; all image nodes use the same Linear/EXTEND sampler settings:

```text
WARNING: More than one shader node tex image used for a texture. The resulting glTF sampler will behave like the first shader node tex image.
```

The final script's first build log is `assets/cache/wall_clock_countdown.build.log`;
the repeat build log is `assets/cache/wall_clock_countdown.rebuild.log`.

Both final-script builds exited 0 and produced a **byte-identical GLB**:

```text
SHA-256: 7fa60f2e6c155b095e0c92e064ce5739731cde129449398f4f653ad28b226d97
game/assets/core/props/wall_clock_countdown.glb: OK
```

The checksum comparison found different PNG file hashes for all three
previews. Blender embeds `Date`, `RenderTime` and Cycles timing text chunks
in these PNGs; those values change between runs. Pixel-level equality was
not separately checked. The GLB reproducibility check passed, and assetcheck
was run again after the repeat build with the same passing output above.

Inspected all three 1024 × 1024 CPU previews after correcting the first
iteration's coplanar lettering artifacts and light housing finish. The final
labels are clear and unmirrored; the detail view shows the gasket recess,
vent pockets, screw sockets, edge wear and surface variation. An independent
read of the exported GLB confirmed the screen's exact dimensions, translation,
dedicated material, seven embedded images and absence of animations/cameras.

Only this asset's script, GLB, previews, metadata, report and ignored cache
outputs were written. No shared helpers, runtime files, scenes, room manifest,
request files, documentation outside the asset lane or other assets were edited.
No commit was made.

## Deliverables

- [Build script](../../tools/blender/props/wall_clock_countdown.py)
- [GLB](../../game/assets/core/props/wall_clock_countdown.glb)
- [Front preview](../previews/wall_clock_countdown_front.png),
  [iso preview](../previews/wall_clock_countdown_iso.png),
  [detail preview](../previews/wall_clock_countdown_detail.png)
- [Metadata, including anchors](../meta/wall_clock_countdown.json)
