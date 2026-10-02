# usb_stick — Night Shift inspectable prop

Original, deterministic Blender 5.2.2 LTS asset built from
`assets/requests/usb_stick.md`. All geometry, procedural finishes and handwriting
are made in the asset script. No external assets, fonts, downloads or new
packages; no attribution entry is required. No shared helpers, requests,
runtime files, room scenes, room.yaml or other assets were edited. No commit.

## Deliverables

- `tools/blender/props/usb_stick.py`: self-contained `build(out_dir)` with the
  shared headless CLI, seeded randomness and no network access.
- `game/assets/core/props/usb_stick.glb`: one object/mesh named `body`, **5,408
  triangles**, the three requested Principled PBR materials, **nine embedded
  1024 × 1024 PNGs**. No collision helpers, animation, cameras or lights.
- `assets/previews/usb_stick_{front,iso,detail}.png`: three 1024 × 1024 renders
  on neutral grey, using `common/preview.py`'s three-point lighting, Cycles
  **CPU**, 32 samples, denoising and four threads. Preview exposure is −1.25 EV
  to preserve the orange colour and brushed-steel highlights.
- `assets/meta/usb_stick.json`: exported counts, textures, bounds, names,
  source/pipeline/GLB hashes, Blender version and real build timestamp.

## Construction and finish

Two rounded moulded orange shells have a narrow dark parting seam, fine stipple,
long scuff marks, perimeter wear, and a physical chip on the exposed connector
shoulder. A real keyring bore passes through the rear plastic and metal plates.
The windowed stainless swivel cover is folded rearward to expose the connector
and leave the label visible. Side cheeks, pivot bores and rivets are modelled;
its back-left corner is bent upward by approximately 0.20 mm.

The USB-A connector has four thin shell walls, an open mouth, two actual
retention holes, a dark insulating tongue, and four gold contact bars. Steel
and contacts share `M_usb_stick_metal` through the baked texture atlas.

Thin white tape with irregular cut corners carries exactly **`MR - backups`**.
The strokes are original hand-drawn paths rasterised into the tape's UV island,
with slight slant, baseline variation and dry-marker density. Text is baked,
not a font or floating text mesh. All three previews were visually inspected;
the full label reads clearly, and the iso view shows the hollow connector.

Base colour, tangent normal and packed ORM are baked for each material from
original procedural surfaces. ORM uses occlusion R, roughness G and metallic B.
UVs are unwrapped and packed globally within each material, with an 8 px
margin. AO is ray traced and kept gentle. All modifiers are applied and all
exported faces are triangles.

## Dimensions and integration

The requested **plastic body** is **58 L × 19 W × 9 H mm**. The exposed connector
adds 12.1 mm to the length; the cover/rivets and bend add width and height.
Complete exported bounds are **70.1 L × 21.0 W × 9.706 H mm**. This interprets
the request's dimensions as the plastic body dimensions, rather than shrinking
that body to fit the exposed connector into 58 mm.

Origin is the complete footprint's centre at the lowest underside, Godot Y = 0.
Godot bounds are approximately `(-0.0105, 0, -0.03505)` to
`(+0.0105, +0.00970647, +0.03505)` metres. The connector points toward **−Z**.
The joined `body` has identity rotation/scale and zero translation.

The cover is static, as requested; there is no exported swivel animation.
Keep the baked colour/normal/ORM maps and no emission. If Godot cached an earlier
build, re-extract this asset's embedded textures during integration per the
pipeline. Final in-room screenshot and inspect-distance approval remain
Claude's review; no in-room visual approval is claimed here.

## Verification actually run

All successful asset builds used `tools/blender/build_assets.sh usb_stick`,
which serialises Blender with the shared `flock` and enforces four threads.
Final reviewed build: **exit 0**. Real output excerpt:

```text
Building usb_stick with Blender 5.2.2 (CPU only, 4 threads)
ASSET BUILT: ~/Work/escapebox/game/assets/core/props/usb_stick.glb; 5408 triangles; 3 materials
```

The exporter emits three existing shared-ORM warnings, one per material:

```text
WARNING: More than one shader node tex image used for a texture. The resulting glTF sampler will behave like the first shader node tex image.
```

The binary audit confirms each material's occlusion and metallic/roughness
references share the same exported texture. Assetcheck reports zero warnings.

Actually ran `go run ./tools/assetcheck usb_stick`: **exit 0**. Complete output:

```text
PASS usb_stick (5408 tris, 1 parts)
assetcheck: 1 asset(s) checked, 1 passed, 0 failed, 0 warning(s)
```

Actually ran an isolated Godot 4.7.2 **headless** GLTFDocument load check and a
stdlib binary audit under `assets/cache/usb_stick/`, both **exit 0**:

```text
PASS Godot headless: GLB loads; one body; 5408 triangles; three baked PBR materials; 1024px maps; identity transforms; centred floor origin; no collision or animation
PASS binary audit: 5408 triangles; no loose vertices or degenerate triangles; unit normals; nine embedded 1024px PNGs; shared ORM/AO; three 1024px previews; source and GLB hashes match
```

Full build logs, audit, Godot check and assetcheck output are retained in the
ignored, asset-local `assets/cache/usb_stick/` directory. Early previews prompted
an orange colour adjustment, a more visible edge chip and lower studio exposure.

Final source was rebuilt **twice without changes**, both required build commands
returning **exit 0**. GLBs are **byte-identical**, and metadata is identical
except `built_at`. Actual comparison output:

```text
PASS reproducibility: two full builds of unchanged source produce byte-identical GLBs; metadata identical except built_at
GLB SHA256 e4b6f033d75e1d3406004bb0260fbc9f2be6b0da44c6cc72e2596bd25196cb2e
```

After the repeat build, assetcheck, binary audit and the headless Godot load
check were run again, all **exit 0**, with the same passing output shown above.
Logs: `build_reviewed.log`, `build_repro.log`, `assetcheck.log`, `audit.log`,
`godot.log` and `repro.log`, all under `assets/cache/usb_stick/`.
