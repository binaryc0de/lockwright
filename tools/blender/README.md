# Headless asset builds

From the repository root:

```bash
tools/blender/build_assets.sh             # every props/*.py with a request
tools/blender/build_assets.sh keypad_4    # selected ids only
BLENDER="$HOME/.local/bin/blender" tools/blender/build_assets.sh keypad_4
```

The wrapper accepts Blender 5.2.x only (the M0 build uses 5.2.2 LTS), checks
all scripts and matching requests before building, and stops on any error.
An advisory `flock` in `assets/cache/` serializes wrapper invocations,
including the version check. It runs each script sequentially with `-b`,
`--factory-startup`, `--threads 4`, `-noaudio`, and `--python-exit-code 1`.
Avoid running standalone Blender commands concurrently with the wrapper.

Each asset exports its GLB into `--out`, writes 1024 x 1024 PNG previews
to `assets/previews/`, and writes its metadata to `assets/meta/`. Generated
texture intermediates and local verification logs live in the ignored
`assets/cache/` directory. No `.blend` or external image/font is required.

## Shared helpers

- `common/scene.py`: background/version checks, fixed seed, metric units,
  empty scene, Cycles CPU with four render threads, no GPU compute backend.
- `common/materials.py`: Principled PBR, `M_<id>_<part>` names, generated
  `T_<id>_<map>` PNGs, packed ORM and tangent-space normal connections.
- `common/geometry.py`: applied bevels/normals, mesh joining, UV projection,
  and explicit triangulation. Front UVs reverse X so text reads from +Y.
- `common/export.py`: selected meshes only, GLB, applied modifiers, Y-up,
  animations enabled, AUTO embedded images, no cameras/lights. Metadata
  counts actual exported triangles (including collision) and records
  W/D/H bounds, parts, textures, source hashes, version and UTC build time.
- `common/preview.py`: front/iso/detail cameras supplied by the prop,
  neutral-grey world, three area lights scaled to the prop, 32 samples,
  CPU, denoise, 1024 px square. Collision meshes are hidden for rendering.
- `common/cli.py`: `--out` parsing, tracebacks and exit status. Blender
  native shutdown stalls on this host inside the sandbox even with audio
  disabled. After synchronous build/export/render operations complete,
  the CLI flushes its output and exits directly. `build(out_dir)` itself
  returns normally when imported; exceptions in the CLI return status 1.

The front face points along Blender +Y. The glTF Y-up conversion maps that
to Godot -Z; Blender Z becomes Godot Y. Wall props use the centre of their
back mounting plane, floor props use the base centre. Each keypad key keeps
an identity rotation/scale and a location at its base on the plate.

For exact GLB reproducibility use the same script, shared helpers, and
Blender patch version. Metadata's `built_at` intentionally changes;
source and GLB hashes make stale outputs detectable. Do not add build
timestamps to the GLB or generate asset geometry in preview helpers.

Reports are review documents maintained after visual QA and verification;
the builder regenerates GLB, textures, previews and metadata, leaving the
report's recorded review evidence intact.
