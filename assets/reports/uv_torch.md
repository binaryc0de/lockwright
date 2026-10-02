# uv_torch

Built the requested pocket 365 nm torch from original geometry and artwork. No third-party assets, textures, fonts or downloads were used; no attribution entry is needed. The deterministic headless source is `tools/blender/props/uv_torch.py` with entry point `build(out_dir)`.

## Build and integration

The aluminium housing is 105 mm long, with a 22 mm barrel and a 26 mm flared head. It has chamfered machining steps, three recessed head grooves, faceted diamond tail knurling, restrained bare-metal wear on the knurl tips and bezel, an axial scuff, a recessed matte rubber push switch with concentric traction ribs, an eyelet and a two-turn split ring. The curved identification band reads `UV 365nm`; the small ivory inventory sticker reads `KL-IT-0118`. Both use original antialiased stroke lettering.

Exactly two identity-transform meshes are exported: `body` contains all static housing, switch, ring and label geometry; `lens` contains the recessed 18 mm frosted lens and small LED die behind it. The lens material has a white-ish lavender base and violet emission (linear RGB 0.28, 0.008, 1.0; strength 0.75). Claude can drive `M_uv_torch_lens` emission intensity for the SDK state; the UV beam and ink reveal belong to runtime integration. The concealed die is intentionally occluded by the frosted lens.

The result has **11,936 triangles, four materials and seven embedded 1024 × 1024 PNGs**. Body and rubber use baked base colour, tangent normal and packed ORM with ray-traced AO. The label uses its own base-colour atlas. All preview renders use `common/preview.py`: 1024 px, neutral grey, three studio lights, Cycles CPU, four threads. The preview-only quarter turn presents the lettering horizontally; exported transforms remain identity. All three final previews were visually inspected.

No collision helpers or animations are present. The lens faces Godot −Z. The floor origin is at Y = 0, and X/Z are centred on the complete bounds, including the split ring. Overall Godot W × D × H is **0.026 × 0.113229 × 0.026 m**. The ring accounts for the extra overall length beyond the nominal 105 mm housing. This is not a change to the requested body size.

The lens surface centre is recorded in `assets/meta/uv_torch.json` as a Godot integration anchor. No room scene, runtime code, room.yaml, request status, shared helper or other asset file was edited. No commit was made. In-room screenshot, gameplay wiring and final artistic acceptance remain Claude's review; no in-engine visual approval is claimed.

## Verification actually run

`tools/blender/build_assets.sh uv_torch` — **exit 0**, Blender 5.2.2 LTS. Real final output excerpts:

```text
Building uv_torch with Blender 5.2.2 (CPU only, 4 threads)
PASS geometry: two identity-transform meshes; floor min y=0; lens faces Godot -Z; no collision
PASS deterministic export: 3 tangent accessors canonicalized and normalized
ASSET BUILT: ~/Work/escapebox/game/assets/core/props/uv_torch.glb; 11936 triangles; 4 materials
```

The exporter emits two existing shared-ORM warnings:

```text
WARNING: More than one shader node tex image used for a texture. The resulting glTF sampler will behave like the first shader node tex image.
```

A direct artifact audit verified that AO and metallic/roughness share the intended texture indices and all sampler settings agree. It also checked source/GLB hash freshness, seven embedded images, four material names, exactly two identity-transform nodes, no animations and three 1024 px previews.

`go run ./tools/assetcheck uv_torch` — **exit 0**, real output:

```text
PASS uv_torch (11936 tris, 2 parts)
assetcheck: 1 asset(s) checked, 1 passed, 0 failed, 0 warning(s)
```

An isolated asset-only **Godot 4.7.2 headless** import and scene check also exited **0**:

```text
PASS Godot headless: two identity-transform meshes; four PBR materials; embedded body/rubber base/normal/ORM; violet emissive lens facing -Z; floor origin; no collision
```

The first two unchanged exports differed in two bytes of one body tangent component; their JSON, geometry, UVs, normals and texture bytes agreed. Following the accepted `server_rack_42u` approach, this asset now quantizes tangent XYZ to 0.001 and normalizes the vectors, retaining handedness. The audit of 14,721 tangent vectors measured a maximum direction change of 0.047266693 degrees and maximum unit-length error of 0.000000042749. Every non-tangent byte is preserved; no shared exporter was changed.

**Two complete builds of the final unchanged source both exited 0 and produced byte-identical GLBs.** Metadata is identical except `built_at`. The final export also matches both earlier independently generated exports after the same stabilization. Preview PNGs contain render timing/date metadata, so no whole-PNG byte-identity claim is made. Final GLB: **4,888,324 bytes**. SHA-256:

```text
55e432707f90ccf5c71bb4df120e71b235580a61478d3495bb2addb4ffc57ada
```

Logs are retained in this asset's ignored `assets/cache/uv_torch/` directory: `build-stable.log`, `build-stable-repro.log`, `assetcheck-final.log`, `godot-import-final.log`, `godot-check-final.log`, `audit.log`, `repro-check.log` and `tangent-audit.log`. Earlier iteration logs are also retained.

## Deliverables

- `tools/blender/props/uv_torch.py`
- `game/assets/core/props/uv_torch.glb`
- `assets/previews/uv_torch_front.png`
- `assets/previews/uv_torch_iso.png`
- `assets/previews/uv_torch_detail.png`
- `assets/meta/uv_torch.json`
- `assets/reports/uv_torch.md`
