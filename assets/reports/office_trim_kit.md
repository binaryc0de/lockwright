# office_trim_kit

Original, deterministic office dressing for the M1 look test. The deliverable
script is `tools/blender/props/office_trim_kit.py`; no external assets, textures,
fonts or network calls are used. No attribution entry is required.

## Construction and materials

- `skirting_1m`: 1 m MDF extrusion, 100 mm height, 15 mm maximum projection,
  curved pencil/ogee profile, satin paint, a faint rubbed lower band. Surface
  detail is independent of X so scaling long runs does not stretch features.
- `outlet_double`: 146 x 86 mm faceplate with two recessed socket inserts,
  actual pin/earth apertures, dark aperture floors, twin small switches and
  recessed slotted fixings. It is a fictional, UK/EU-neutral fitting.
- `light_switch`: 86 mm square plate, recessed rocker, slight rocker tilt,
  dark clearance gap, slotted screws and a separate rear mounting foot.
- `vent_600`: 595 mm grille with rolled frame, 23 inclined louvres, open dark
  gaps, a central stiffener and four screws. No painted-on imitation slots.
- `smoke_detector`: 110 mm circular fitting, twist-base seam, 32 open radial
  vent slots, rounded crown and a central test button.
- `smoke_led`: separate white-base emissive dot on the detector. Its origin is
  its detector attachment point, rather than the kit mounting plane.
- `emergency_light`: 300 x 120 x 80 mm battery enclosure, moulded lid/seam,
  fixings, green charge and dim red indicator dots, twin articulated heads,
  chrome reflector bowls and concentrically ribbed frosted lenses.

Exactly five requested materials are used: plastic, paint, metal, lamp and LED.
The plastic is slightly yellowed, with moulded microtexture and subtle baked
short-distance seam dirt; paint has fine
surface stipple and modest wear; metal is polished with fine roughness detail.
Procedural colour/roughness and tangent normals are baked on Cycles CPU, with
8 px UV gutters. Subtle ray-traced AO is packed into ORM. The three primary
finishes use 1024 px maps; lamp/LED maps are 512 px. Textures are embedded.

## Integration

Every exported main part is intentionally at `(0,0,0)` with its rear mounting
face on Godot `z=0`, facing `-Z`. The skirting origin is the bottom of its rear
face; other mounting origins are centred. All rotations/scales are applied.
The main parts overlap in the GLB because the room author instances them
individually. `smoke_led` must follow `smoke_detector` when the latter is moved.
There are no colliders, animations, cameras or lights in the GLB.

`assets/meta/office_trim_kit.json` provides per-part bounds/origins and the
requested `anchors_godot_m` block. Lamp anchors are front lens centres; beam
vectors are unit Godot vectors, 30 degrees down and 30 degrees outward.
Rotate both positions and vectors with the emergency fixture transform when
placing spotlights. For ceiling mounting, rotate the detector/grille together
with their local `-Z` forward direction.

Front/iso previews spread the complete kit for review; the detail preview
clusters the four small fittings for a closer view. The GLB is exported
before this presentation layout is applied. Baking also separates unrelated
parts to avoid false AO from the intentionally overlapping kit layout.

The lamp material has low emission (0.08) and the LED material 0.55, suitable
for inspecting lens detail. Set lamp emission to the desired emergency-power
level in Godot and use real spotlights at the metadata anchors for room light.
The plastic and paint use restrained surface detail intended to survive dim
PBR room lighting without conspicuous dirt. No scene or runtime changes made.

## Verification

Executed on 2026-10-02 on `dev-laptop`, Blender 5.2.2 LTS, CPU only,
four threads. The corrected `tools/blender/build_assets.sh office_trim_kit`
completed with exit 0. Its actual summary output:

```text
Building office_trim_kit with Blender 5.2.2 (CPU only, 4 threads)
GEOMETRY: 19680 triangles before baking
PASS geometry: seven exact parts; mounting origins; applied transforms; no collisions/animations
ASSET BUILT: ~/Work/escapebox/game/assets/core/props/office_trim_kit.glb; 19680 triangles; 5 materials
```

`go run ./tools/assetcheck office_trim_kit` completed with exit 0:

```text
PASS office_trim_kit (19680 tris, 7 parts)
assetcheck: 1 asset(s) checked, 1 passed, 0 failed, 0 warning(s)
```

All three 1024 x 1024 previews were opened and visually inspected. The initial
render's cropped vent edge and coincident detector button/crown were corrected;
the final front view contains the full kit, the iso shows depth and vent slots,
and the detail shows rocker clearances, recessed apertures, charge LEDs and
concentric lens diffusion ridges. The detector's test button is a raised white
face with a subtle rim. Fifteen embedded maps, five materials, seven parts,
19,680 triangles; no combined bounds-centre warning was emitted.

The six main part origins are exactly zero in the exported glTF; `smoke_led`
is translated to `[0.023, -0.019, -0.0425]`. Mesh rotations/scales are applied.
The unit-length beam vectors audit to 30 degrees down and outward. Per-part
bounds match the request's nominal dimensions (including the 110 mm detector
and 595 mm vent).

The additional exported topology audit initially found 96 collapsed corner
triangles in thin bevelled layers. The asset-local slab helper now limits the
bevel below half the layer thickness; shared helpers are unchanged. The script
also rejects loose vertices and zero-area faces before baking. The corrected
GLB audit completed with exit 0:

```text
GLB topology audit: 19680 triangles; 0 unused exported vertices; 0 degenerate triangles; finite attributes=True
```

Two complete builds of the final source both exited 0 and produced a
byte-identical GLB. SHA-256: `68f980072a7ea6bc101d1182f302656cbc2c800ecfac5f24849c0eaabb4531c6`.

The GLB checksum comparison returned `office_trim_kit.glb: OK`. The preview
PNG file checksums differ between renders; their embedded `Date`, `RenderTime`
and Cycles timing text chunks are variable. The final PNGs were reopened and
visually checked; each is 1024 x 1024. Preview file-byte identity is not claimed.

Assetcheck was rerun after the repeat and returned the same PASS/zero-warning
output above. Final metadata source/GLB hashes were independently checked,
as were all 15 embedded images, five materials, seven nodes, the absence of
animations/cameras, and unit beam-vector lengths.
The topology-clean build log is `assets/cache/office_trim_kit.rebuild.log`;
the repeat log is `assets/cache/office_trim_kit.determinism.log`. Other outputs:
`assets/cache/office_trim_kit.assetcheck.log`,
`assets/cache/office_trim_kit.topology.log`,
`assets/cache/office_trim_kit.determinism_check.log`.

Blender emits a shared-image sampler warning for the packed texture workflow:

```text
WARNING: More than one shader node tex image used for a texture. The resulting glTF sampler will behave like the first shader node tex image.
```

The exported GLB has one consistent sampler (linear magnification, mipmapped
linear minification, clamp-to-edge S/T) for its 15 embedded images. This warning
is distinct from assetcheck warnings; the final assetcheck reported none.

## Deviations and remaining review

No requested features omitted. An in-engine screenshot and final acceptance
remain Claude's integration/review step. The combined kit bounds are not an
individual fixture's footprint; use the per-part metadata for placement.
