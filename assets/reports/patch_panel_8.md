# patch_panel_8

Built from `assets/requests/patch_panel_8.md` with Blender 5.2.2 LTS. The
accepted `exit_door_maglock` and `exit_keypad_6` scripts supplied the local
structure for Godot-axis geometry, original stroke lettering, procedural
surface baking, named-part checks, metadata and previews. Their routines
were copied and adapted inside this asset's script; this build does not
import another asset script. No shared helper changes, external assets,
fonts, downloads, dependencies or commits.

## Delivered asset

- **53,156 triangles**, five named meshes, five materials and **15 embedded
  PNG textures**. No collision helpers, animation, cameras or lights in GLB.
- A 483 mm wide, 89 mm high 2U panel with a 100 mm deep folded sheet-metal
  chassis. The rear face is at Godot Z = 0; the 2 mm mounting ears have their
  back at Z = -0.100; the central front land is at Z = -0.103.
- Eight keystone sockets on 60 mm pitch, centred at Y = +0.008. Each has a
  real aperture, latch keyway, recessed walls and eight gold contact fingers.
  Ports read 1–8 from left to right when viewed from the front. Original
  white stroke legends have the requested 12 mm cap height; the upper-left
  `P1 -> UPS BYPASS` strip uses 9 mm capitals.
- A 1U cable manager directly below the panel, with a folded shelf, front
  lip, four round guide loops, slotted ears and recessed cross-head screws.
- Four independent hanging Cat6 leads. A is red with one white band, B blue
  with two, C yellow with three, and D green with none. Bands wrap only the
  neck approaching the plug. Each cable includes its boot, strain-relief
  ribs, latch, contact pads, tie and 28 × 29 mm paper tag. Tags use original
  slanted marker strokes at the specified 15 mm cap height. Lead lengths,
  including the connector allowance, are A 0.671274 m, B 0.685900 m,
  C 0.671627 m and D 0.686581 m; plug centres are approximately Y = -0.32
  to -0.365 m, with tags and plugs separated in front view.

Surface detail includes powder-coat grain, slight edge chipping, rubbed
manager edges, fine service scratches, dust on upward-facing steel, moulded
plastic grain, PVC jacket texture, paper fibers and brushed contact/fastener
metal. All five materials have baked base colour, tangent normal and packed
ORM maps. Panel/legend and cable maps are 2048 px; socket, tag and metal maps
are 1024 px. UV islands are unique per material, with 8 px packing and bake
margins. Base colour and roughness/metallic use procedural emission bakes;
AO is ray traced and packed into ORM R, with roughness in G and metallic in B.
The cable micro-normal map is rounded to two-code intervals in its 8-bit
encoding, retaining neutral code 128 and the fine PVC grain. This addresses
a variation found in an initial unchanged-build comparison: one red-channel
sample of the 2048 px cable normal map encoded as 130 in one build and 131
in the next. Geometry and the other fourteen texture payloads were identical.
The delivered source applies this rounding before saving and embedding.

The three 1024 × 1024 previews use the shared neutral-grey three-point studio,
Cycles CPU, 32 samples, denoising and four threads. All were visually reviewed.
The detail view clearly shows A/B/C/D and the one/two/three/zero band counts.
Initial visual review prompted narrower edge wear on the manager and removal
of duplicated stripe groups on the return side of each cable bend.

## Integration

Exactly `panel`, `cable_a`, `cable_b`, `cable_c`, `cable_d` are exported. Each
has identity rotation/scale and an origin at the requested rear-face centre;
moving a cable moves its plug, tag and stripes with it. Everything is at
Godot Z ≤ 0 and faces -Z. Combined bounds are approximately 0.483 W × 0.222 D
× 0.474 H m, including the hanging leads.

Metadata includes the requested anchors:

```json
"anchors_godot_m": {
  "rail_plane_z": -0.100,
  "front_face_z": -0.103
}
```

There are no request deviations. In-room attachment, lighting review,
focused UI wiring and the acceptance screenshot remain Claude's integration
work. No in-room screenshot or gameplay approval is claimed. No runtime
code, room scene, room.yaml, request status or another asset's files were
edited. No Godot material overrides are required for the initial review;
refresh extracted GLB textures if a previous version was imported.

## Verification actually run

`tools/blender/build_assets.sh patch_panel_8` completed with **exit 0** through
the shared `flock`, CPU only, four threads. Selected real output from the
final-source build:

```text
Building patch_panel_8 with Blender 5.2.2 (CPU only, 4 threads)
PASS geometry: 5 named parts; rear z=0; rail z=-0.100; face z=-0.103; 60mm port pitch; applied transforms
PASS cable lengths: A=0.671m/1 stripes, B=0.686m/2 stripes, C=0.672m/3 stripes, D=0.687m/0 stripes
ASSET BUILT: ~/Work/escapebox/game/assets/core/props/patch_panel_8.glb; 53156 triangles; 5 materials
```

`go run ./tools/assetcheck patch_panel_8` completed with **exit 0**. Real output:

```text
WARN patch_panel_8: bounds centre y = -0.1925 m; a mount-plane-centre origin would put it near 0
PASS patch_panel_8 (53156 tris, 5 parts)
assetcheck: 1 asset(s) checked, 1 passed, 0 failed, 1 warning(s)
```

The warning is expected: the request places the origin at the panel body's
rear-face centre, while the hanging cables extend the overall bounds below
it. The requested origin was retained. The build separately checks the
rear-most geometry at Z = 0, X centring and all five exported transforms.

Read-only artifact checks passed for texture budgets, fifteen embedded maps,
shared ORM/occlusion texture indices on every material, three 1024 px PNGs,
the requested anchors, and current source/pipeline/GLB hashes. An independent
standard-library calculation also verified the four sampled cable lengths.
Godot 4.7.2 imported a copy of the final-source GLB in an isolated project
under this asset's ignored cache directory. Import and the headless scene
check both exited **0**:

```text
PASS Godot headless: 5 named meshes; five textured PBR materials; no collision/animation; rear mount z=0; front toward -Z; applied transforms
```

The exporter emits its existing shared-ORM warning:

```text
WARNING: More than one shader node tex image used for a texture. The resulting glTF sampler will behave like the first shader node tex image.
```

Texture-node settings agree; exported-data checks confirm that all five
materials retain their packed ORM and use the same texture for occlusion
and metallic/roughness.

The two unchanged builds of the final source (including normal rounding)
both exited **0**, regenerating the GLB and all previews. The second GLB is
**byte-identical** to the first, including all embedded texture bytes;
metadata is identical except `built_at`. Real comparison output:

```text
PASS reproducibility: byte-identical GLB including embedded textures; metadata identical except built_at
GLB SHA256 41efb74e5c9d9ebdef3e0bb2d2734bc18b9a079ec23afca1e306a19efd145ba3
```

The delivered GLB is **17,768,540 bytes**. The final assetcheck rerun after
the unchanged rebuild exited **0** with the exact output quoted above.
The isolated Godot check used the first final-source GLB, which is identical
to the delivered second GLB. No preview PNG byte-identity claim is made;
Blender includes rendering timestamps and timing metadata in preview PNGs.
The final three previews were visually inspected.

Final build logs: `assets/cache/patch_panel_8/build-canonical-final.log` and
`assets/cache/patch_panel_8/build-canonical-repro.log`. Final assetcheck output:
`assets/cache/patch_panel_8/assetcheck-final.log`. Isolated Godot logs:
`assets/cache/patch_panel_8/godot-import-final.log` and
`assets/cache/patch_panel_8/godot-check-final.log`.

## Deliverables

- `tools/blender/props/patch_panel_8.py`
- `game/assets/core/props/patch_panel_8.glb`
- `assets/previews/patch_panel_8_front.png`
- `assets/previews/patch_panel_8_iso.png`
- `assets/previews/patch_panel_8_detail.png`
- `assets/meta/patch_panel_8.json`
- `assets/reports/patch_panel_8.md`

Full build/import logs are retained under `assets/cache/patch_panel_8/`.
