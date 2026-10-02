# sticky_note_username — M1 look test

Yellow sticky note with original black felt-tip lettering, a darker adhesive band and subtle bottom-edge curl shadow/highlight. Three lines, with user: mreyes larger than the surrounding context and underlined exactly once. No font is used for handwriting.

Personally inspected the delivered 1024 x 1024 image and 256 x 256 quarter-size preview. Read all three lines against the request, including the complete final line and smiley. user: mreyes remains clear at quarter size; its cap height is 113 px (28.25 px in the preview).

Exactly 1024 x 1024, opaque sRGB RGBA, following the request over Section 7's general long-edge minimum. Curl is texture shading, not added geometry. The note can use a matte paper material; the requested 1 m readability remains an in-engine lighting/scale check.

## Deliverables

- Source: `tools/printables/templates/sticky_note_username.svg`.
- Entry point: `tools/printables/build_printables.sh` (optionally followed by this request ID).
- Metadata: `assets/meta/printables/sticky_note_username.json` with dimensions, exact text, source/request/output hashes and Blender version.
- Texture: `game/rooms/night_shift/assets/docs/sticky_note_username.png`.
- Preview: `assets/previews/printables/sticky_note_username_25.png`.
- Texture SHA-256: `826b78f3d460dfdce7fc2b204d007ce0bbca9967a37c36b6b9bd39d92c5e866b`.

## Verification actually run

On the Alienware development machine, 2026-10-02: `tools/printables/build_printables.sh` completed two full batches with **exit 0 each**, under Blender **5.2.2 LTS**. The shared prop/printable flock permits one Blender process at a time; factory startup, disabled audio and four threads are retained. All rasterization is CPU-only through bundled Python/NumPy, with no render engine, GPU context, network or package install.

`tools/printables/verify.py --record` with Blender's bundled `python3.13 -B` returned **exit 0**. It independently decoded PNG chunks and pixels, checked CRCs, sRGB/gamma metadata, actual request dimensions, required opacity/transparent code interior, preview dimensions and metadata hashes. Exact text coverage is also checked by the builder. SVG syntax, placeholder IDs, handwritten character coverage and Python syntax passed. Visual review above was performed on the delivered files, not inferred from source strings.

The second full `tools/printables/build_printables.sh` run completed with **exit 0**. Running `tools/printables/verify.py --compare` through Blender's bundled `python3.13 -B` returned **exit 0** and the actual result:

```text
PASS reproducibility: all 6 outputs, 6 previews and 5 metadata records byte-identical
```

The output and preview hashes listed above match both builds, and metadata is byte-identical with no timestamp exception. The second build log is `assets/cache/printables/second_build.log`; the first checksum manifest is `assets/cache/printables/first_build.sha256.json`. All current source/request hashes were independently checked against the metadata. The build's exact-text, opacity and transparent-interior assertions passed on both runs.

Printed text uses only the locally installed Blender-bundled Inter (OFL-1.1); handwriting, shapes and wear overlays are original. See `tools/printables/ATTRIBUTION.md`. No third-party art, downloaded fonts, shared Blender-helper changes, runtime/scene/room.yaml edits or git commits. GLB-only assetcheck/build_assets do not apply to printables, as explained in assets/requests/printables/README.md. No Godot integration screenshot or distance test is claimed.
