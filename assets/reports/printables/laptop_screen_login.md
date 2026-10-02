# laptop_screen_login — M1 look test

A restrained 2020s intranet screenshot: minimal browser chrome, text-only Kestrel Logistics wordmark, a centred white login card on dark blue, orange session-expiry notice, two empty fields, a Sign in button and taskbar clock 23:12. Subtle LCD banding is local generated detail; there is no physical paper wear or prefilled credential.

Personally inspected the delivered full image and 512 x 321 quarter-size preview. Read the exact heading, notice, field labels, button and clock against the request. The fields are empty. All requested UI text remains readable at quarter size.

Exactly 2048 x 1283, opaque sRGB RGBA, retaining the exact approximate 16:10 request. Browser tab/address text is decorative in-fiction context, not a dynamic challenge connection card. Assign the PNG to laptop_open's screen albedo/emission with restrained brightness; actual emission, glare and 0.6 m readability need in-engine review.

## Deliverables

- Source: `tools/printables/templates/laptop_screen_login.svg`.
- Entry point: `tools/printables/build_printables.sh` (optionally followed by this request ID).
- Metadata: `assets/meta/printables/laptop_screen_login.json` with dimensions, exact text, source/request/output hashes and Blender version.
- Texture: `game/rooms/night_shift/assets/docs/laptop_screen_login.png`.
- Preview: `assets/previews/printables/laptop_screen_login_25.png`.
- Texture SHA-256: `84c2593031e9148adf6df6951d38cb19143eb0586fe3d40a86c248436e00eef9`.

## Verification actually run

On the Alienware development machine, 2026-10-02: `tools/printables/build_printables.sh` completed two full batches with **exit 0 each**, under Blender **5.2.2 LTS**. The shared prop/printable flock permits one Blender process at a time; factory startup, disabled audio and four threads are retained. All rasterization is CPU-only through bundled Python/NumPy, with no render engine, GPU context, network or package install.

`tools/printables/verify.py --record` with Blender's bundled `python3.13 -B` returned **exit 0**. It independently decoded PNG chunks and pixels, checked CRCs, sRGB/gamma metadata, actual request dimensions, required opacity/transparent code interior, preview dimensions and metadata hashes. Exact text coverage is also checked by the builder. SVG syntax, placeholder IDs, handwritten character coverage and Python syntax passed. Visual review above was performed on the delivered files, not inferred from source strings.

The second full `tools/printables/build_printables.sh` run completed with **exit 0**. Running `tools/printables/verify.py --compare` through Blender's bundled `python3.13 -B` returned **exit 0** and the actual result:

```text
PASS reproducibility: all 6 outputs, 6 previews and 5 metadata records byte-identical
```

The output and preview hashes listed above match both builds, and metadata is byte-identical with no timestamp exception. The second build log is `assets/cache/printables/second_build.log`; the first checksum manifest is `assets/cache/printables/first_build.sha256.json`. All current source/request hashes were independently checked against the metadata. The build's exact-text, opacity and transparent-interior assertions passed on both runs.

Printed text uses only the locally installed Blender-bundled Inter (OFL-1.1); handwriting, shapes and wear overlays are original. See `tools/printables/ATTRIBUTION.md`. No third-party art, downloaded fonts, shared Blender-helper changes, runtime/scene/room.yaml edits or git commits. GLB-only assetcheck/build_assets do not apply to printables, as explained in assets/requests/printables/README.md. No Godot integration screenshot or distance test is claimed.
