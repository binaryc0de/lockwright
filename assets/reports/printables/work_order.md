# work_order

Built from `assets/requests/printables/work_order.md` with the existing printable
pipeline: Blender 5.2.2 headless, four threads, shared process lock, CPU SVG
rasterization and 2× antialiasing. No GPU, rendering engine, network access,
new dependencies or downloaded art were used.

Deliverables:

- `tools/printables/templates/work_order.svg`
- `game/rooms/night_shift/assets/docs/work_order.png`: 1448 × 2048, opaque RGBA, sRGB.
- `assets/previews/printables/work_order_25.png`: 362 × 512.
- `assets/meta/printables/work_order.json`: all ten exact strings, actual wrapped lines/baselines, cap sizes, dimensions, source/request/output/preview hashes, Blender version and seed.

The portrait laser-printed form has a restrained clipboard clip at the top,
a teal company header, work-order identifier, site/date fields, a shaded
cutover task, contractor/security briefing and a warm-tinted UPS warning.
A blue pen tick marks the sign-in instruction; a second tick and original
signature scrawl finish the page. The handwritten bottom message is the exact
requested sentence, including the plus sign and apostrophe. The original
stroke alphabet gained these two characters additively. Coffee residue is
confined to an unused lower-right corner above the message. Seeded paper
fibres, subtle print banding, slight margin handling and a fine edge crease
keep the form realistic without obscuring content.

All ten text strings come from the request. The double space in
`CONTRACTOR WORK ORDER  KL-WO-2026-0417` and the three spaces before `Window:`
are preserved. Long fields use opt-in word wrapping at fixed cap height,
with reserved-height assertions. Quarter-size printed caps range from 9 to
14.25 px; body text is 10–10.5 px and the handwritten caps are 10.5 px.
The wrapped lines retain every word and punctuation mark. No content or
size deviations; no UV layer was requested or generated. Font/procedural
provenance is covered by `tools/printables/ATTRIBUTION.md`.

Personally inspected the full-size output and its actual quarter-size preview
on the final build. All instructions and names are readable: 22:30–02:00,
cutover 23:30, M. Reyes OFF SITE, whiteboard notes, Dale/intercom, the one-hour
UPS statement, sign-in instruction and Mark's-desk message. Coffee wear,
clip, ticks and signature do not cross required text. No unresolved visual
issue observed.

Independent `tools/printables/verify.py` checks PNG CRCs, sRGB metadata, exact
size, opacity, quarter-size dimensions and SHA-256 hashes. It additionally
checks all ten exact strings, reconstructed wrapped wording and minimum cap
sizes. Python syntax, SVG parsing/unique placeholder IDs and
`git diff --check` passed.

Only the two assigned printable deliverables and additive shared printable
support were changed. No other asset/template/output, runtime code, room
scene, room.yaml, request status or docs outside the printable lane were
edited by this task; no commit was made. Godot assignment, inspect lighting
and in-room approval remain Claude's work. Per ADR-0014 and the printable
request README, `tools/blender/build_assets.sh` and GLB-only `assetcheck` do
not apply to PNG printables.

## Final build and repeat-build evidence — 2026-10-02

Ran the final source twice with:

```bash
tools/printables/build_printables.sh network_diagram_laminated work_order
```

Both final builds exited **0**. Actual build output (identical for both):

```text
BUILT network_diagram_laminated: 2048x1448, 18 text lines
BUILT work_order: 1448x2048, 10 text lines
```

Between the two builds, ran Blender's bundled Python on
`tools/printables/verify.py --record network_diagram_laminated work_order`;
after the second, ran the same command with `--compare`. Both exited **0**.
Actual comparison output:

```text
PASS exact text/mappings/pixel stripe counts: A=1, B=2, C=3, D=0 at full and 25% size
PASS PNG/CRC/sRGB/dimensions/alpha/preview: network_diagram_laminated.png
PASS exact text/word wrapping/cap sizes: all ten work-order strings
PASS PNG/CRC/sRGB/dimensions/alpha/preview: work_order.png
PASS reproducibility: all 2 outputs, 2 previews and 2 metadata records byte-identical
```

This compares whole file bytes, including all PNG chunks and metadata; no
timestamp exceptions were needed. Current source-hash freshness also passed.
The full-size and 25% images inspected on the first final build are identical
to the delivered second build. No remaining required build/check is pending.

Output SHA-256: `141a0f3e4e63dcb2ec4edab3efe757c7c89c90d5c603d2494cc7770b8242f584`.

Preview SHA-256: `3a919c9e6e5e0d907b0f30dbe141d56d2381ab040436c7e39dc2c08ed7d908db`.

Build and verification logs: `assets/cache/printables2_build_final.log`,
`printables2_build_repro.log`, `printables2_verify_first.log` and
`printables2_verify_repro.log`. The six-hash baseline is
`assets/cache/printables/network_diagram_laminated_work_order_first_build.sha256.json`.
