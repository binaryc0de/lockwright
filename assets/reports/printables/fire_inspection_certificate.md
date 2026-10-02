# fire_inspection_certificate — M1 look test

Cream-paper fire safety certificate with restrained red double rules, an original geometric flame/shield crest and laurels, pen signature scrawl, round PASS stamp, slight handling discoloration and a small punch-shadow mark. No wear covers SITE 417.

Personally inspected the delivered full image and 384 x 512 quarter-size preview. Read every required line against the request. The title reads clearly on one line; SITE 417 has a 171 px cap height (42.75 px in the preview) and high contrast.

No dimensional deviation: 1536 x 2048, opaque sRGB RGBA. No UV content. Use as paper albedo in the certificate frame, with matte paper roughness; room lighting and the requested 2 m readability need Claude's in-engine review.

## Deliverables

- Source: `tools/printables/templates/fire_inspection_certificate.svg`.
- Entry point: `tools/printables/build_printables.sh` (optionally followed by this request ID).
- Metadata: `assets/meta/printables/fire_inspection_certificate.json` with dimensions, exact text, source/request/output hashes and Blender version.
- Texture: `game/rooms/night_shift/assets/docs/fire_inspection_certificate.png`.
- Preview: `assets/previews/printables/fire_inspection_certificate_25.png`.
- Texture SHA-256: `b02b8ee2caf8b29351689827aac1e47f8283334d81c846dbe4ceac5a1cd0dfc5`.

## Verification actually run

On the Alienware development machine, 2026-10-02: `tools/printables/build_printables.sh` completed two full batches with **exit 0 each**, under Blender **5.2.2 LTS**. The shared prop/printable flock permits one Blender process at a time; factory startup, disabled audio and four threads are retained. All rasterization is CPU-only through bundled Python/NumPy, with no render engine, GPU context, network or package install.

`tools/printables/verify.py --record` with Blender's bundled `python3.13 -B` returned **exit 0**. It independently decoded PNG chunks and pixels, checked CRCs, sRGB/gamma metadata, actual request dimensions, required opacity/transparent code interior, preview dimensions and metadata hashes. Exact text coverage is also checked by the builder. SVG syntax, placeholder IDs, handwritten character coverage and Python syntax passed. Visual review above was performed on the delivered files, not inferred from source strings.

The second full `tools/printables/build_printables.sh` run completed with **exit 0**. Running `tools/printables/verify.py --compare` through Blender's bundled `python3.13 -B` returned **exit 0** and the actual result:

```text
PASS reproducibility: all 6 outputs, 6 previews and 5 metadata records byte-identical
```

The output and preview hashes listed above match both builds, and metadata is byte-identical with no timestamp exception. The second build log is `assets/cache/printables/second_build.log`; the first checksum manifest is `assets/cache/printables/first_build.sha256.json`. All current source/request hashes were independently checked against the metadata. The build's exact-text, opacity and transparent-interior assertions passed on both runs.

Printed text uses only the locally installed Blender-bundled Inter (OFL-1.1); handwriting, shapes and wear overlays are original. See `tools/printables/ATTRIBUTION.md`. No third-party art, downloaded fonts, shared Blender-helper changes, runtime/scene/room.yaml edits or git commits. GLB-only assetcheck/build_assets do not apply to printables, as explained in assets/requests/printables/README.md. No Godot integration screenshot or distance test is claimed.
