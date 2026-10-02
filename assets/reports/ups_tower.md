# ups_tower

Original procedural 3 kVA UPS and matching external battery cabinet, built with
Blender 5.2.2. The accepted `exit_door_maglock` and `exit_keypad_6` scripts
supplied structural references for surface baking, original stroke lettering,
mesh export and metadata. Relevant routines are copied locally; the build does
not import another asset's script. No external resources, fonts, downloads or
new dependencies were used. No attribution entry is needed.

## Construction

The cabinets use rounded sheet jackets, separate cap geometry, low rubber
feet, inset front bezels, battery access covers, and real panel reveals. The
UPS has a recessed 90 × 50 mm LCD, four navigation caps, a five-segment LED
bar and the exact printed `UPS 3kVA` label. The battery cabinet has a recessed
metal relay panel, the exact `BYPASS RELAY` label, a retained white pilot lens,
and a hex-mounted physical toggle. Lower vents use individual UPS louvers and
252 actual punched apertures with 1.2 mm bore walls on the battery cabinet.
Recessed Torx heads, rear terminal plates, cable glands and two thick black
hoses complete the assembly. The hoses descend from the rear terminals to
floor runs within the footprint.

Baked surface detail includes fine plastic/powder-coat grain, slight top dust,
localized exposed-edge chips, lower front scuffs, polished control contact,
metal brushing, minor surface stains, and print-stock variation. Label strokes
are stamped into the baked atlas, including roughness/metallic changes.
The LCD has subdued original monochrome `ONLINE` / `230V` diagnostics and
load bars. These are decorative telemetry; no puzzle answer or vendor logo
is printed.

The enclosure uses 2048 px base colour, tangent normal and packed ORM maps.
Metal and print use 1024 px equivalents. The screen uses one 512 px shared
colour/emission map; the lamp uses a constant white emissive material.
All ten images are embedded. ORM is AO in R, roughness in G, metallic in B.
Procedural emission bakes, tangent normal bakes and ray AO use Cycles CPU,
16 samples, with unique UV islands and 8 px packing/bake margins. Previews
use the shared neutral-grey three-point studio, Cycles CPU, 32 samples,
denoising, 1024 × 1024 and four threads. The shared build lock serializes
Blender with the other concurrent asset tasks.

## Transform and integration contract

Both cabinets occupy the nominal **0.70 W × 0.60 D × 0.90 H m** footprint,
with the origin at its base centre on the floor. The UPS is 0.25 m wide,
centred at Godot X = −0.225 m; the battery is 0.40 m wide, centred at
X = +0.15 m. The gap is 0.05 m. Explicit numeric positions from the request
are preserved. A conventional camera looking at the −Z front shows negative
X on screen-right, so the request's parenthetical “left as seen from the
front” differs from its numeric X placement; the model follows the numbers.
Blender +Y faces Godot −Z. All scales/rotations are applied.

There are exactly three exported mesh nodes: `body`, `screen`, `relay_lamp`.
The latter two retain their own transform and material. No collision helpers,
animations, cameras or lights are exported. The five materials are exactly
`M_ups_tower_body`, `M_ups_tower_metal`, `M_ups_tower_print`,
`M_ups_tower_screen`, and `M_ups_tower_lamp`.

The metadata includes an additional `anchors_godot_m` block for integration:

```json
{
  "screen_centre": [-0.225, 0.752, -0.299],
  "screen_size": [0.09, 0.05],
  "screen_front_z": -0.2995,
  "relay_lamp": [0.227, 0.726, -0.277],
  "relay_lamp_front_z": -0.2822,
  "ups_centre_x": -0.225,
  "battery_centre_x": 0.15
}
```

The lens base and emission are white for runtime tinting. Claude can set its
emission/base tint when the bypass relay changes state, and adjust the LCD's
modest emission to the room lighting. Re-extract embedded textures if Godot
cached an earlier rebuild. Room integration and in-room visual acceptance
remain Claude's work; no in-room screenshot or gameplay approval is claimed.

## Deviations and iteration

The detailed geometry is above the anticipated 10–25k triangle range, while
remaining within the binding 60k hero budget. The physical perforation bore
walls alone use 12,096 triangles; there are also real recesses, rounded
hardware, and curved cables. No LOD was requested.

An initial attempt was stopped before export to recess controls within the
footprint and provide clearance behind the grilles. The first complete build
passed the isolated Godot import; preview review then caught coplanar jacket
and lid tops and overly broad wear on side faces. The script was corrected
so the jacket meets the lid's underside, wear stays near exposed edges,
the finish is darker, printed strokes are more robust, and the hoses rest
on the floor. The final previews and checks below refer to the corrected
build.

## Verification actually run

The corrected `tools/blender/build_assets.sh ups_tower` completed with exit 0.
Actual output excerpt:

```text
Building ups_tower with Blender 5.2.2 (CPU only, 4 threads)
STAMP print: UPS 3kVA / BYPASS RELAY, original stroke lettering
PASS geometry: three named meshes, identity rotation/scale, no collisions or animations; feet y=0
ASSET BUILT: ~/Work/escapebox/game/assets/core/props/ups_tower.glb; 33028 triangles; 5 materials
```

The exporter emitted its existing shared-ORM sampler warning three times:

```text
WARNING: More than one shader node tex image used for a texture. The resulting glTF sampler will behave like the first shader node tex image.
```

The image nodes have the same sampler settings. Exported-data checks confirmed
that the metallic/roughness and occlusion bindings share the packed texture
index for all three mapped materials.

Actually ran `go run ./tools/assetcheck ups_tower`, with exit 0:

```text
PASS ups_tower (33028 tris, 3 parts)
assetcheck: 1 asset(s) checked, 1 passed, 0 failed, 0 warning(s)
```

Direct GLB/PNG checks passed for all named nodes, material slots, embedded
PBR/ORM bindings, the white emissive pilot lens, exact anchor translations,
identity rotations/scales, current script/GLB hashes, and three 1024 px previews.
Actual exported bounds are approximately **(−0.350, 0, −0.300)** to
**(+0.350, +0.900, +0.300) m** in Godot, i.e. the requested footprint and height
within floating-point precision. There are **33,028 triangles, five materials,
three named mesh nodes, ten embedded images, and no animations or collision**.

A fresh isolated **Godot 4.7.2 headless** import and imported-scene check ran in
`assets/cache/ups_tower/godot-check/`, with exit 0. Real output:

```text
PASS Godot headless: GLB imports; three named meshes; five PBR materials with baked colour/normal/ORM; separate LCD and white emissive relay lamp; exact anchors; no collision
```

All three corrected previews were visually inspected for surface detail,
vent depth, top closure, label/LCD readability and control separation. No
shared helper, other asset, request, room, runtime or `docs/` file was
modified by this task. No commit was made.

Two unchanged corrected builds completed with exit 0. Their GLBs, including
all embedded texture bytes, are **byte-identical**; their metadata is identical
except `built_at`. Actual comparison output:

```text
PASS reproducibility: byte-identical GLB including all embedded textures; metadata identical except built_at
GLB 9723924 bytes; SHA256 32904e36b74e20b94dd21c5a615e80ef19e3cd681f1e77cc4e00fb58d30412c2
```

An additional comparison of the preview RGB pixel hashes did **not** pass:
all three views had different pixel hashes. No preview pixel-identity claim
is made. The delivered second-build previews were visually inspected again;
all retain the same composition, readable text, surface finish and geometry.
The isolated Godot check used the first corrected GLB, which is byte-identical
to the delivered repeat. Assetcheck was rerun against the delivered files,
with exit 0 and the same zero-warning output above.

Full logs are in this asset's ignored cache: `final-build.log`,
`repro-build.log`, `assetcheck.log`, `verify-glb.log`, `repro-check.log`,
`godot-import.log`, and `godot-check.log`.
