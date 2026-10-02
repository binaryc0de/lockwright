# exit_sign_lightbox

Built from `assets/requests/exit_sign_lightbox.md` on 2026-10-02, with
Blender 5.2.2 LTS, Cycles CPU and four threads through the shared
`build_assets.sh` lock. Only this asset's deliverables and ignored scratch
files were written. No shared helper, runtime, room, request or other asset
file was edited; no commit was made.

The 0.360 W × 0.150 H × 0.050 D m lightbox has lightly yellowed white ABS,
rounded case edges, a rear-cover seam, rear mounting pockets, underside
cover-latch slots, a recessed test button with a tactile dot, and a small
green charge LED. The recessed opal diffuser carries original vector-path
artwork: a white left arrow, doorway and left-running figure on green,
without text. The first preview review completed the doorway outline and
reduced diffuser reflections to preserve the green in the underside view.

Exactly two identity-transform meshes export: `housing` (including controls
and LED) and `face`. Both origins are at the back mounting-plane centre.
Godot bounds are (-0.180, -0.075, -0.050) to (+0.180, +0.075, 0) m;
the front faces Godot -Z. There is no collision, animation, camera or light
in the GLB. No dimensional or naming deviation is intended.

The GLB contains **2,586 triangles, three Principled materials and four
embedded 1024 × 1024 PNGs**, and is **1,064,776 bytes**. The ABS uses locally
adapted procedural baking from the accepted `exit_keypad_6`: base colour,
tangent normal and packed ORM with ray-traced AO, unique UV islands and
8 px margins. Fine moulding grain and a restrained warm ageing/dust tint
remain subtle. The antialiased pictogram uses one image for both face
albedo and emission, with emission strength 0.85; the charge LED uses a
constant green material with emission strength 0.4. Diffuser translucency
is represented by even emissive colour on an opaque opal-plastic surface.
No external model, texture, font, download or dependency was used, so no
attribution entry is needed.

## Deliverables

- `tools/blender/props/exit_sign_lightbox.py` — deterministic `build(out_dir)` and shared headless CLI.
- `game/assets/core/props/exit_sign_lightbox.glb`.
- `assets/previews/exit_sign_lightbox_front.png`.
- `assets/previews/exit_sign_lightbox_iso.png`.
- `assets/previews/exit_sign_lightbox_detail.png`.
- `assets/meta/exit_sign_lightbox.json` — actual counts, texture sizes, bounds, anchors, source/pipeline/GLB hashes and build timestamp.
- `assets/reports/exit_sign_lightbox.md`.

All three 1024 × 1024 previews were visually inspected. They use the shared
neutral-grey three-point studio, 32 CPU samples and denoising. The front
shows upright, unmirrored pictograms; iso shows the diffuser inset and
cover seam; detail shows the underside button, LED and latch recess.

## Verification actually run

`tools/blender/build_assets.sh exit_sign_lightbox` — **exit 0** for the
initial draft and both independent refined final builds. Selected real output from the final
build:

```text
Building exit_sign_lightbox with Blender 5.2.2 (CPU only, 4 threads)
PASS geometry: 0.360 x 0.150 x 0.050 m; back z=0; two parts; identity transforms; no collision
ASSET BUILT: ~/Work/escapebox/game/assets/core/props/exit_sign_lightbox.glb; 2586 triangles; 3 materials; 4 embedded textures
```

Blender emits its existing shared-ORM warning:

```text
WARNING: More than one shader node tex image used for a texture. The resulting glTF sampler will behave like the first shader node tex image.
```

The exported ORM is shared by occlusion and metallic/roughness, and sampler
settings agree. The face albedo and emission reference the same embedded
image and sampler. No export failure is reported.

`go run ./tools/assetcheck exit_sign_lightbox` — **exit 0**. Complete real
output:

```text
PASS exit_sign_lightbox (2586 tris, 2 parts)
assetcheck: 1 asset(s) checked, 1 passed, 0 failed, 0 warning(s)
```

Godot 4.7.2 loaded the GLB with `GLTFDocument` in an isolated asset-only
project under this asset's ignored cache, **exit 0**:

```text
PASS Godot headless: GLB loads; two identity-transform meshes; exact wall mount and bounds; face points -Z; textured PBR and pictogram emission; no collision or animation
```

A read-only artifact audit also passes source/pipeline/GLB hash freshness,
allowed imports, exact bounds, material/part counts, embedded PNG sizes,
shared pictogram albedo/emission, packed ORM/AO, and three 1024 px previews.

Two independent complete builds of the refined final source produce
**byte-identical GLBs**, including the embedded texture bytes. Metadata is
identical except `built_at`. The final assetcheck rerun and artifact audit
both exit **0**. Real comparison output:

```text
PASS reproducibility: byte-identical GLB including embedded textures; metadata identical except built_at
SHA256 1b9858e72894db2b76a9700d3b4a7758175bd25e507ad3c2e26e27fa18aa989d
```

Preview PNG byte identity is not claimed: Blender adds timing/date metadata
to rendered images. The delivered GLB matches the one checked in Godot.

Claude retains the in-room screenshot and visual acceptance step. Keep
room lighting and glow settings in the room: the face emission is already
exported, and the metadata records its centre and dimensions. If the sign
needs direct corridor illumination, add a room-owned light during
integration. No in-room screenshot or gameplay approval is claimed.

Build and check logs are retained under `assets/cache/exit_sign_lightbox.*.log`;
the isolated Godot check and artifact audit are under
`assets/cache/exit_sign_lightbox/`.
