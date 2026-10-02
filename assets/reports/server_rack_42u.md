# server_rack_42u

Original populated 42U rack built from `assets/requests/server_rack_42u.md`. The deterministic Blender source uses the accepted `exit_door_maglock` and `exit_keypad_6` structure for CPU baking, named meshes, export validation, metadata and previews. No third-party models, textures, fonts or downloads are used; no attribution entry is needed.

## Asset and integration

The cabinet is 0.60 × 1.00 × 2.00 m, open at the front, with a welded plinth, folded uprights, removable side-panel seams, closed top and a closed perforated rear door. Front EIA rails have 126 actual square holes each over 42U, starting at y=0.10 m. Recessed mounting screws, brushed drive handles, recessed carriers, punched ventilation, hollow switch ports, KVM pull, finger cable manager, bottom blanking plates, rear PDU and dressed side/rear cables provide physical surface detail. The top has deposited dust; the powder coat has fine grain and restrained edge chips; equipment has service rubs; exposed hardware has brushed grain and scratches. All surface finishes use baked base colour, tangent normal and packed ORM with ray-traced AO.

Exactly two identity-transform mesh nodes are exported: `cabinet` contains all static geometry, and `leds` contains every front indicator. Five materials use the requested names. The LED material shares a small original green/amber palette between albedo and emission, so both colours export correctly while one emission-strength override can blink the entire mesh. Starting emission strength is 0.7. No animations or collision helpers are exported. The room retains its box collider.

The 2U patch-panel opening is centred at y=1.25 m and is clear across the equipment aperture. The 3U plate is centred at y=1.72 m and has a clean matte front face without text. Claude places the stencil decal. Integration anchors, in Godot metres:

```json
{
  "patch_slot_centre": [0, 1.25, -0.47],
  "stencil_plate_centre": [0, 1.72, -0.474],
  "rail_front_z": -0.47
}
```

The patch anchor is the rail mounting plane; the stencil anchor is the plate's front surface. Move the decal slightly toward -Z to avoid coplanar rendering. The front is Godot -Z and the origin is the floor base centre. The exact specified slot and plate heights take priority over putting every chassis boundary on the U grid; short spacer/blanking sections accommodate those centres while the rails retain standard EIA spacing. The stencil has a 0.432 × 0.11335 m clear central area, with screws confined to the ears. No other dimensional deviations are intended.

## Verification

Verified in this checkout on 2026-10-02 with Blender 5.2.2 LTS, Cycles CPU and four threads. All three final 1024 × 1024 previews were visually inspected. The delivered GLB has **57,808 triangles, five materials, two mesh parts, 173 front LEDs and thirteen embedded PNGs**, and is **20,347,248 bytes**. Three 2048 px PBR atlas sets cover cabinet, equipment and metal; a 1024 px set covers cables; one 64 px palette drives LED colour and emission.

`tools/blender/build_assets.sh server_rack_42u` — **exit 0**. Selected real output:

```text
Building server_rack_42u with Blender 5.2.2 (CPU only, 4 threads)
PASS geometry: base centre; 0.60 x 1.00 x 2.00 m; identity transforms; clear 2U slot at y=1.25; two meshes
PREFLIGHT 57808 triangles, 173 LEDs
PASS deterministic export: 5 tangent accessors canonicalized and normalized
PASS geometry: base centre; 0.60 x 1.00 x 2.00 m; identity transforms; clear 2U slot at y=1.25; two meshes
ASSET BUILT: ~/Work/escapebox/game/assets/core/props/server_rack_42u.glb; 57808 triangles; 5 materials
```

`go run ./tools/assetcheck server_rack_42u` — **exit 0**. Real output:

```text
PASS server_rack_42u (57808 tris, 2 parts)
assetcheck: 1 asset(s) checked, 1 passed, 0 failed, 0 warning(s)
```

Additional read-only artifact checks pass: source/pipeline/GLB SHA-256 freshness, identity transforms, exact two-part/material contract, thirteen embedded PNGs within budget, three 1024 px previews, floor origin and requested anchors. Each of the four textured finishes exports base colour, tangent normal and shared ORM/AO. LED albedo and emission reference the same palette image and sampler. The script checks overall bounds to 1 µm, reserved-slot box intersections, and every vertex in the reserved front opening before baking and again after export.

Blender emits four `More than one shader node tex image used for a texture` warnings for the shared ORM links, as in the accepted reference scripts. All exported textures use the same Linear/Clamp sampler; the GLB includes every requested map. Assetcheck itself reports zero warnings.

The initial geometry preflight stopped before baking at 111,056 triangles. The final model uses eight drives per 2U chassis and four per 1U chassis, with simple bevels on repeated small details, to meet the hero budget. A subsequent preview review darkened the cabinet and equipment finishes. The delivered source is the final reviewed version.

Reproducibility passed with an asset-local tangent stabilization step. Two independent complete builds initially differed in exactly one cable tangent component by about 0.0001; their JSON, geometry, UVs, normals and embedded images were identical. The script now quantizes tangent XYZ to 0.001, normalizes the vectors, and retains handedness before writing metadata. Both independently baked exports become byte-identical after this step, and the final source's full rebuild matches that same binary exactly. A read-only audit of 95,959 tangent vectors measured a maximum direction change of 0.049011 degrees and a maximum unit-length error of 0.000000043; every non-tangent byte was preserved. No shared exporter was edited.

Final GLB SHA-256:

```text
1c843d320b3796d92857a3a1ede5d8dcbafbc88e2b2c5a020a680b2b61c04ac5
```

Logs are retained in `assets/cache/server_rack_42u.build_final.log`, `server_rack_42u.build_repro.log`, `server_rack_42u.assetcheck_final.log`, `server_rack_42u.audit.log` and `server_rack_42u.tangent_audit.log` (cache is not a deliverable).

In-engine screenshot, lighting review, decal placement and SDK integration remain Claude's work. No runtime code, room scenes, room.yaml, request file, shared helper or another asset's files were edited. No commit was made.

## Deliverables

- `tools/blender/props/server_rack_42u.py`
- `game/assets/core/props/server_rack_42u.glb`
- `assets/previews/server_rack_42u_front.png`
- `assets/previews/server_rack_42u_iso.png`
- `assets/previews/server_rack_42u_detail.png`
- `assets/meta/server_rack_42u.json`
- `assets/reports/server_rack_42u.md`
