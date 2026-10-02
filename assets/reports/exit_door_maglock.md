# exit_door_maglock

Built from `assets/requests/exit_door_maglock.md` for the Night Shift M1 look test. The deterministic Blender 5.2 script follows the accepted `desk_3drawer` structure for procedural baking and the `keypad_4` structure for named parts, white tintable status lighting, export checks, metadata and CPU previews. No external assets, downloads, fonts or dependencies were used.

## Asset

- Painted satin grey-blue steel leaf, 0.98 × 2.08 × 0.05 m, at the exact requested Godot slab coordinates. Millimetre bevels, layered paint with edge chips, push-height hand rubs, fragmented contact scrapes and kick-zone scuffs. Baked tangent normals retain fine orange-peel surface detail; worn chips expose metal in the packed metallic channel.
- Pressed darker steel frame with a head return and jamb returns, separate hinge knuckles and recessed cruciform fasteners. The panic hardware has cast dark end caps, aluminium trims, a backing spine and a rounded metal touch bar. A brushed steel kick plate and maglock armature are attached to the leaf.
- Surface-mounted brushed aluminium maglock, end caps, fine extrusion grooves, mounting rail, fasteners, conduit and couplers. Separate white emissive LED, ready for Godot red/green tinting.
- Glossy green sticker with original running-person, doorway and arrow artwork; no text. A clear 0.40 × 0.15 m label area is reserved above the panic bar.
- Exactly four exported mesh nodes: `leaf`, `frame`, `maglock`, `maglock_led`. All leaf hardware follows `leaf`. No collision meshes, cameras, lights or animations are exported. `leaf` has an identity transform at the floor hinge axis `(0,0,0)`.
- Procedural-to-texture Cycles CPU bakes: base colour, tangent normal and packed ORM, with ray-traced AO, non-overlapping material UV atlases and 8 px margins. Twelve embedded PNG maps in total. Three 2048 px atlas sets (leaf, frame, metal), one 512 px sticker atlas set; five materials including the untextured LED.

## Integration and deviation

The requested 50 mm thick leaf is offset behind a pivot fixed at wall-face `(0,0,0)`. A straight hinge return at x=0 intersects it during the requested 100° corridor swing. The hinge-side return therefore has a 78 mm relief pocket behind the room-side architrave; the visible architrave remains 50 mm wide. This is the only dimensional adjustment, and is recorded as `hinge_jamb_relief_m` in metadata. The surrounding wall must leave this small hinge pocket clear when integrated. A sampled solid sweep of the leaf slab, panic hardware, kick plate and armature checks the fixed frame/maglock boxes at every whole degree from 0° to 100°. This geometric check does not replace Claude's in-engine collision and visual review.

`anchors_godot_m` contains:

```json
{
  "leaf_room_face_z": 0.005,
  "leaf_label_centre": [0.5, 1.27, 0.0045],
  "maglock_led": [0.948, 2.068, -0.0708]
}
```

The label anchor sits 0.5 mm toward the room from the flat face to avoid coplanar rendering. The LED anchor is its separate node origin at the lens base. Opening uses Godot Y rotation of -100° to swing into +Z. Tint both the LED material's albedo and emission in Godot; the initial white emission strength is 0.65. No other material override is needed before reviewing under the room lighting.

## Verification

Verified in this checkout on 2026-10-02 using Blender 5.2.2 LTS, Cycles CPU, four threads. The final source built successfully and all three 1024 × 1024 previews were visually inspected. The detail camera looks slightly upward so the armature and its gap beneath the housing are visible. The delivered GLB has **25,870 triangles, five materials, four mesh parts and twelve embedded PNGs** (19,292,672 bytes), within the requested budgets.

`tools/blender/build_assets.sh exit_door_maglock` — **exit 0**. Selected real output:

```text
Building exit_door_maglock with Blender 5.2.2 (CPU only, 4 threads)
PASS geometry: hinge origin (0,0,0), applied transforms; 1162914 solid sweep samples, 0–100 degrees into Godot +Z
ASSET BUILT: ~/Work/escapebox/game/assets/core/props/exit_door_maglock.glb; 25870 triangles; 5 materials
```

`go run ./tools/assetcheck exit_door_maglock` — **exit 0**. Real output:

```text
WARN exit_door_maglock: hinge origin not checked automatically; verify in-engine (bounds min (-0.0800, 0.0000, -0.0722) max (1.0500, 2.3450, 0.1000))
PASS exit_door_maglock (25870 tris, 4 parts)
assetcheck: 1 asset(s) checked, 1 passed, 0 failed, 1 warning(s)
```

The warning is the request's expected hinge-origin warning. The script separately verifies the exported hinge transform and samples the solid swing against fixed frame and magnet boxes. Additional read-only artifact checks passed: exact exported paint-slab bounds, LED node translation matching the requested metadata anchor, source/pipeline/GLB SHA-256 freshness, all four textured materials exporting base colour + tangent normal + shared ORM/AO, white LED emission, twelve embedded image buffer views, and three 1024 px PNGs.

Blender's exporter also emits `More than one shader node tex image used for a texture. The resulting glTF sampler will behave like the first shader node tex image.` Its shared ORM links produce these messages; all texture nodes use matching settings, and the exported GLB contains one shared Linear/Clamp sampler. No map is missing.

Reproducibility comparison passed: **two unchanged final-source builds produced a byte-identical GLB**, both exiting 0 and regenerating all three previews. SHA-256:

```text
84f8948125bf4d852682f4bb23c91d92d8e73ff950ed3f416e8a0d8c62899491
```

The final `assetcheck` run after the unchanged rebuild also exited 0 with the same output above.

Logs are retained under `assets/cache/exit_door_maglock.build_final.log` and `assets/cache/exit_door_maglock.build_repro.log` (cache is not a deliverable).

In-engine screenshot, SDK attachment and gameplay review remain Claude's integration work. No runtime code, room scene, room.yaml, request file, shared helper or other asset was edited by this task. No commit was made.

## Deliverables

- `tools/blender/props/exit_door_maglock.py`
- `game/assets/core/props/exit_door_maglock.glb`
- `assets/previews/exit_door_maglock_front.png`
- `assets/previews/exit_door_maglock_iso.png`
- `assets/previews/exit_door_maglock_detail.png`
- `assets/meta/exit_door_maglock.json`
- `assets/reports/exit_door_maglock.md`

