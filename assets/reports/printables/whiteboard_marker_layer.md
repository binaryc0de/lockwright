# whiteboard_marker_layer — M1 look test

Transparent original stroke writing in blue dry-wipe marker, with slight pressure variation, tiny starved segments, a black dashed right arrow and a black empty code rectangle. A faint three-box/two-link network sketch in the upper right has no text. All six writing lines remain within the left 55% of the surface, with nominal 59 px cap height, about 45 mm at the specified physical size.

Personally inspected the full RGBA texture, the full-size white-backed review copy, and the 512 x 316 quarter-size preview. Read all six exact requested lines. The arrow points right toward the empty code box. Independently decoded PNG pixels confirm that x=1188..1802 and y=657..1009, the entire specified interior, have zero RGBA. There is no baked UV code.

Exactly 2048 x 1262 RGBA with a transparent background; top-left is pixel (0,0). The border sits just outside the reserved x=58%-88%, y=52%-80% interior so antialiasing cannot contaminate the UV placement area. The quarter preview is composited over white enamel for legibility; only the main texture is delivered with transparency. The opaque full review copy is ignored scratch output in assets/cache/printables/. Composite this ink onto the existing board; the UV code remains in-engine, so no _uv.png is generated.

## Deliverables

- Source: `tools/printables/templates/whiteboard_marker_layer.svg`.
- Entry point: `tools/printables/build_printables.sh` (optionally followed by this request ID).
- Metadata: `assets/meta/printables/whiteboard_marker_layer.json` with dimensions, exact text, source/request/output hashes and Blender version.
- Texture: `game/rooms/night_shift/assets/docs/whiteboard_marker_layer.png`.
- Preview: `assets/previews/printables/whiteboard_marker_layer_25.png`.
- Texture SHA-256: `afb3a90f1f16bd11a9b8e3ac32bf93780d9c5e5ab76a47c94bd1ad561d6f3a76`.

## Verification actually run

On the Alienware development machine, 2026-10-02: `tools/printables/build_printables.sh` completed two full batches with **exit 0 each**, under Blender **5.2.2 LTS**. The shared prop/printable flock permits one Blender process at a time; factory startup, disabled audio and four threads are retained. All rasterization is CPU-only through bundled Python/NumPy, with no render engine, GPU context, network or package install.

`tools/printables/verify.py --record` with Blender's bundled `python3.13 -B` returned **exit 0**. It independently decoded PNG chunks and pixels, checked CRCs, sRGB/gamma metadata, actual request dimensions, required opacity/transparent code interior, preview dimensions and metadata hashes. Exact text coverage is also checked by the builder. SVG syntax, placeholder IDs, handwritten character coverage and Python syntax passed. Visual review above was performed on the delivered files, not inferred from source strings.

The second full `tools/printables/build_printables.sh` run completed with **exit 0**. Running `tools/printables/verify.py --compare` through Blender's bundled `python3.13 -B` returned **exit 0** and the actual result:

```text
PASS reproducibility: all 6 outputs, 6 previews and 5 metadata records byte-identical
```

The output and preview hashes listed above match both builds, and metadata is byte-identical with no timestamp exception. The second build log is `assets/cache/printables/second_build.log`; the first checksum manifest is `assets/cache/printables/first_build.sha256.json`. All current source/request hashes were independently checked against the metadata. The build's exact-text, opacity and transparent-interior assertions passed on both runs.

Printed text uses only the locally installed Blender-bundled Inter (OFL-1.1); handwriting, shapes and wear overlays are original. See `tools/printables/ATTRIBUTION.md`. No third-party art, downloaded fonts, shared Blender-helper changes, runtime/scene/room.yaml edits or git commits. GLB-only assetcheck/build_assets do not apply to printables, as explained in assets/requests/printables/README.md. No Godot integration screenshot or distance test is claimed.
