# certificate_frame

Built from `assets/requests/certificate_frame.md` for the M1 look test. The
script follows the accepted keypad's shared scene/export/metadata/preview/CLI
structure and the desk's CPU procedural-to-PBR baking approach. No shared
helpers, other assets, runtime code, room scenes, manifests or requests changed.

## Delivered

- `tools/blender/props/certificate_frame.py`: seeded, headless `build(out_dir)`;
  Blender 5.2.x, stdlib + bpy/mathutils + existing common helpers, no network.
- `game/assets/core/props/certificate_frame.glb`: 640 triangles, exactly three
  mesh/object names and three requested material names, six embedded PNG maps.
- `assets/previews/certificate_frame_{front,iso,detail}.png`: three 1024 × 1024
  neutral-grey studio renders, Cycles CPU, 32 samples, denoise, four threads.
- `assets/meta/certificate_frame.json`: exported counts, actual bounds,
  material/texture lists, hashes, Blender version, render/bake settings, anchors.

## Geometry and materials

Outer size 0.34 W × 0.44 H × 0.018 D metres. The back mounting face is at Godot
z=0; origin is its centre and the front faces Godot -Z. All scale/rotation
transforms are applied. No collisions or animations.

`moulding` contains four closed mitred sections with a swept 20 mm face profile:
rounded outer nose, shallow crown, small inner bead and glazing rebate. There
is a 0.12 mm mitre seam and a recessed bevelled backing panel. The black plastic
has fine surface grain, uneven roughness, restrained settled dust on the upper
rail and local handling scuffs around the lower screen-right corner. Colour,
roughness/metallic and tangent normal maps are baked at 1024 px with an 8 px
margin; moulding AO is packed into ORM R. Metallic is zero.

`picture` is a flat 0.30 × 0.40 m blank paper quad with subtle paper grain,
512 px baked base colour/normal/ORM and UVs covering 0..1 upright. It contains
no certificate text. Viewed from Godot -Z, u increases to screen-right (-X)
and v increases upward (+Y), matching the accepted keypad's front UV convention.

`glass` is a separate flat 0.30 × 0.40 m quad, Godot z=-0.012. Principled alpha
0.055 exports as glTF `BLEND`, roughness 0.20, metallic zero, IOR 1.45. This gives
a faint reflection while leaving the underlying document visible. Transmission
is left at zero to keep this thin glazing overlay straightforward to import.

Required metadata anchor:

```json
"anchors_godot_m": {"picture_centre": [0, 0, -0.008]}
```

The picture is exactly 0.004 m behind the glass. The build asserts exported
quad dimensions, anchor translations, applied transforms, mesh names,
transparency, outer dimensions, material count and triangle budget.

## Verification actually run

On this checkout, Blender 5.2.2 LTS, 2026-10-02:

`tools/blender/build_assets.sh certificate_frame` exited 0. Final build lines:

```text
PASS geometry: 300 x 400 mm upright UV quads; 4 mm separation; mount origin; three parts; faint BLEND glass
ASSET BUILT: ~/Work/escapebox/game/assets/core/props/certificate_frame.glb; 640 triangles; 3 materials
```

The same command was run a second time through the shared `flock` queue and
also exited 0. The two GLBs were byte-identical, SHA-256:

```text
0588aba40674f02ccfe402678550666b4937143ce88c295cf7a45d79b2326f6f
```

`sha256sum -c assets/cache/certificate_frame/first_build.sha256` returned:

```text
game/assets/core/props/certificate_frame.glb: OK
assets/previews/certificate_frame_front.png: FAILED
assets/previews/certificate_frame_iso.png: FAILED
assets/previews/certificate_frame_detail.png: FAILED
sha256sum: WARNING: 3 computed checksums did NOT match
```

That comparison exited 1 because whole-preview PNG hashes differ. Inspection
confirmed the PNGs embed volatile `Date`, `RenderTime` and Cycles timing text
chunks. Preview byte equality and pixel equality are not claimed; GLB byte
equality is verified. Metadata `built_at` also changes between builds.

All six texture passes and the moulding AO bake ran on CPU; all three previews
were saved and visually inspected. Independent inspection of the exported GLB
binary confirmed both quad normals face Godot -Z and their UV coordinates cover
0..1 upright, including the glTF image-v conversion. The exporter printed its existing
"More than one shader node tex image used for a texture" sampler warning for
the packed PBR materials. The texture nodes use identical Linear/EXTEND sampler
settings, so selecting the first produces the intended sampler.

`go run ./tools/assetcheck certificate_frame` exited 0 after previews completed,
and again after the second build, with the same final output:

```text
PASS certificate_frame (640 tris, 3 parts)
assetcheck: 1 asset(s) checked, 1 passed, 0 failed, 0 warning(s)
```

An earlier check while rendering was still running passed with three missing
preview warnings; the completed run above resolved all three.

## Integration and limits

No request deviations or third-party content; no attribution entry needed.
Replace the picture material's base colour texture with the certificate
printable, using the existing upright UVs. Its roughness can remain near 0.8.
Keep the glass alpha blending enabled and opacity near 0.055; the moody room
lights should produce only a slight glint. No in-engine material change is
required by the asset contract.

Godot import, room screenshot and legibility with the actual certificate
printable were not run here: these remain Claude's integration/review steps.
No commit was made.
