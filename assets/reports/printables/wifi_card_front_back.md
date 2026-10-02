# wifi_card_front_back — M1 look test

Two sides of one in-house laminated guest notice. Front has a company-blue header, original WiFi arc pictogram and printed sans text. Back has original, gently slanted blue ballpoint strokes. Both faces have the matching top-centre pinhole, restrained lamination sheen, edge wear and sparse surface scratches.

Personally inspected both delivered full images and both 384 x 256 quarter-size previews. Read all seven required strings against the request. Password: Kestrel#2019 is unambiguous, with a clear two-bar # and distinct 2/0/1/9. There is no smudge over it.

Both outputs are exactly 1536 x 1024, opaque sRGB RGBA, following the explicit request dimensions over Section 7's general 2048 px minimum. One combined SVG selects front/back by data-page. Reuse the same physical card dimensions and swap the two textures for inspect/flip. A low-roughness laminate material supplies the actual moving reflection; the PNG contains only a restrained visual sheen.

## Deliverables

- Source: `tools/printables/templates/wifi_card_front_back.svg`.
- Entry point: `tools/printables/build_printables.sh` (optionally followed by this request ID).
- Metadata: `assets/meta/printables/wifi_card_front_back.json` with dimensions, exact text, source/request/output hashes and Blender version.
- Texture: `game/rooms/night_shift/assets/docs/wifi_card_front.png`.
- Preview: `assets/previews/printables/wifi_card_front_25.png`.
- Texture SHA-256: `bb6c7c8838a61e1cdb406ea55034b699c8e4f2db59a8204a3ac716e431309a12`.
- Texture: `game/rooms/night_shift/assets/docs/wifi_card_back.png`.
- Preview: `assets/previews/printables/wifi_card_back_25.png`.
- Texture SHA-256: `74381cd5c67f51ed5964754725c7c0e6d2bb53664ff911edcbf2d5099f8a9873`.

## Verification actually run

On the Alienware development machine, 2026-10-02: `tools/printables/build_printables.sh` completed two full batches with **exit 0 each**, under Blender **5.2.2 LTS**. The shared prop/printable flock permits one Blender process at a time; factory startup, disabled audio and four threads are retained. All rasterization is CPU-only through bundled Python/NumPy, with no render engine, GPU context, network or package install.

`tools/printables/verify.py --record` with Blender's bundled `python3.13 -B` returned **exit 0**. It independently decoded PNG chunks and pixels, checked CRCs, sRGB/gamma metadata, actual request dimensions, required opacity/transparent code interior, preview dimensions and metadata hashes. Exact text coverage is also checked by the builder. SVG syntax, placeholder IDs, handwritten character coverage and Python syntax passed. Visual review above was performed on the delivered files, not inferred from source strings.

The second full `tools/printables/build_printables.sh` run completed with **exit 0**. Running `tools/printables/verify.py --compare` through Blender's bundled `python3.13 -B` returned **exit 0** and the actual result:

```text
PASS reproducibility: all 6 outputs, 6 previews and 5 metadata records byte-identical
```

The output and preview hashes listed above match both builds, and metadata is byte-identical with no timestamp exception. The second build log is `assets/cache/printables/second_build.log`; the first checksum manifest is `assets/cache/printables/first_build.sha256.json`. All current source/request hashes were independently checked against the metadata. The build's exact-text, opacity and transparent-interior assertions passed on both runs.

Printed text uses only the locally installed Blender-bundled Inter (OFL-1.1); handwriting, shapes and wear overlays are original. See `tools/printables/ATTRIBUTION.md`. No third-party art, downloaded fonts, shared Blender-helper changes, runtime/scene/room.yaml edits or git commits. GLB-only assetcheck/build_assets do not apply to printables, as explained in assets/requests/printables/README.md. No Godot integration screenshot or distance test is claimed.
