# cage_door_maglock

Owner-made security cage door built from the request, with the accepted
`exit_door_maglock` and `exit_keypad_6` scripts as structural references.
The standalone script uses only Blender, the standard library and existing
`tools/blender/common/` helpers. No downloads, external fonts or attribution
entries are needed. No common helpers or other assets were edited.

## Construction and finish

- Four exported meshes: `leaf`, `frame`, `maglock`, `maglock_led`.
- Leaf tube frame: 40 mm square, x 0.01–0.99, y 0–2.08. The lower 250 mm
  is a solid kick plate; the upper free corner has a solid lock mounting plate,
  armature spacer and brushed steel armature. The office-facing pull is
  carried by two mounting tabs welded to the free-edge tube.
- Weld mesh: 50 mm pitch, 4 mm wire, round-wire tangent normals and swollen
  weld intersections. Open cells have zero alpha. The exported material is
  double-sided glTF `MASK`, cutoff 0.5, so the rack remains visible through it.
- Charcoal powder coat has baked grain, broken ring scratches, boot scuffs,
  polished hand contact and exposed metal at worn marks. Hardware has baked
  directional brushing, subtle grime and roughness variation. Tube welds,
  retaining clips, hinge knuckles, recessed cruciform fasteners, end caps,
  extrusion flutes, bracket and conduit couplers are physical geometry.
  Tube section, mesh pitch/diameter and paint palette match the concurrently
  built `cage_partition_kit`; the door has additional hand and boot contact wear.
- Text-free yellow/black hazard strip on the lock mounting plate. LED has a
  separate white emissive Principled material (strength 0.65) for runtime tint.
- Base colour, tangent normal and packed ORM textures are embedded. Frame
  and metal are CPU-baked at 2048 px; hazard strip at 512 px; the unique mesh
  sheet atlas is generated at 2048 px. Bake margins are 8 px. No high-to-low
  baking or external texture dependencies.

## Integration

`leaf` has identity rotation/scale and origin `(0,0,0)` on the floor hinge
axis. Rotate it about Godot Y by **-100 degrees** to swing into the cage
(+Z). All leaf hardware and the cutout sheet move with this mesh. There are
no collision helpers, animations, cameras or lights in the GLB.

The 40 x 40 mm hinge post keeps x=-0.02 and full 2.10 m height, but is
centred at z=-0.035 (35 mm toward the office). Its offset butt-hinge wings
bridge to the specified hinge axis. A post centred at z=0 would intersect
the thick leaf past 90 degrees; this placement resolves that conflict without
changing the opening, hinge origin or tube section. The strike post is at
x=1.02, z=0. The separate partition header is not included.

`anchors_godot_m` includes:

- `maglock_label_centre`: `[0.85, 2.05, -0.11]` (housing office-face centre).
- `maglock_led`: `[0.741, 2.05, -0.1114]` (lens base centre).

The central housing face has a 0.13 x 0.037 m clear label area. Place the
Label3D slightly toward the office from the supplied face anchor to avoid
z-fighting. Runtime LED colour and room label remain Claude's integration.

## Verification

Ran on 2026-10-02 in `~/Work/escapebox`, Blender **5.2.2 LTS**,
Cycles **CPU only**, one serialised Blender process, **four threads**.
The final build completed in approximately **3 min 19 s** after acquiring
the shared build lock. Both required commands returned **exit 0**.

`tools/blender/build_assets.sh cage_door_maglock` — real output excerpts:

```text
Building cage_door_maglock with Blender 5.2.2 (CPU only, 4 threads)
PASS swing: 26331 complete solid section pairs, 0–100 degrees into Godot +Z
PASS export: four named meshes; hinge origin; MASK double-sided mesh; no animations/collision
ASSET BUILT: ~/Work/escapebox/game/assets/core/props/cage_door_maglock.glb; 28860 triangles; 5 materials
```

Full final build output is in `assets/cache/cage_door_maglock_build_final.log`
(local, gitignored). Blender emitted five sampler warnings:

```text
WARNING: More than one shader node tex image used for a texture. The resulting glTF sampler will behave like the first shader node tex image.
```

These arise from glTF packing shared texture references; all involved nodes
use matching interpolation and `EXTEND`, so selecting the first sampler
does not change the result. The exported mesh material was checked directly
for `alphaMode: MASK` and `doubleSided: true`.

`go run ./tools/assetcheck cage_door_maglock` — complete real output:

```text
WARN cage_door_maglock: hinge origin not checked automatically; verify in-engine (bounds min (-0.0400, 0.0000, -0.1127) max (1.0420, 2.3600, 0.0200))
PASS cage_door_maglock (28860 tris, 4 parts)
assetcheck: 1 asset(s) checked, 1 passed, 0 failed, 1 warning(s)
```

The hinge warning is expected by the request. The script checks the exported
leaf's origin and identity rotation/scale explicitly. Solid section envelopes
pass separating-axis overlap checks every 0.5 degrees through 100 degrees;
intentional concentric hinge bearing contact is excluded. The cutout mesh
atlas has **84.6454% open area**. All three 1024 px previews were rendered
with `common/preview.py` and visually reviewed; front and iso show the whole
door, detail shows the office-facing maglock.

No animations or collisions are exported. Metadata records the final script,
pipeline and GLB hashes and both requested anchors. A byte-for-byte repeat
comparison was not run: the earlier successful build was revised to add the
handle mounting tabs and match the partition palette.

In-engine screenshots, final room-lighting appearance and runtime SDK
integration remain pending Claude review. No runtime code, room scenes,
`room.yaml`, requests or docs outside this asset's report were edited, and
no git commit was made.
