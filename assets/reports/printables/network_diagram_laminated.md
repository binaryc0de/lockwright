# network_diagram_laminated

Built from `assets/requests/printables/network_diagram_laminated.md` through
`tools/printables/build_printables.sh`, using Blender 5.2.2 headless, four threads,
the shared Blender process lock and the existing CPU SVG rasterizer. No GPU,
render engine, network calls, new dependencies or downloaded art were used.

Deliverables:

- `tools/printables/templates/network_diagram_laminated.svg`
- `game/rooms/night_shift/assets/docs/network_diagram_laminated.png`: 2048 × 1448, opaque RGBA, sRGB.
- `assets/previews/printables/network_diagram_laminated_25.png`: 512 × 362.
- `assets/meta/printables/network_diagram_laminated.json`: exact text, cap sizes, dimensions, source/request/output/preview hashes, Blender version and deterministic seed.

The IT diagram has a muted teal header, subordinate firewall/core-switch/rack/UPS
blocks and a large framed P1 bypass schedule. Red A has one white band and maps
to port 3; blue B has two and maps to 7; yellow C has three and maps to 1; green D
has none and maps to 5. Each cable has an original simplified connector, an
independent letter, an arrow and a large port numeral. Bands are 28 px wide,
with 36 px clear gaps: 7 px bands and 9 px gaps at quarter size. Cable letters
have 18 px caps in the preview and port numerals 19.5 px caps. The instruction
footer has 8.25 px caps; even the small cabinet notice remains readable.

Seeded laminate handling variation, a sealed rounded perimeter, narrow corner
reflection and fine margin scratches provide wear without covering the table.
The installed Blender Inter font and original geometry use the existing
`tools/printables/ATTRIBUTION.md` provenance; no new attribution input is needed.
All request text is filled from the request's backtick strings. No UV layer is
requested or generated. No dimensional or content deviations.

Personally inspected the full-size PNG and the actual 25% PNG after the final
layout correction. All required wording is exact and legible, the rack reads
062, each port matches the request, and the 1/2/3/0 stripe counts are clear.
The initial draft placed the numerals slightly above their boxes; the final
78 px numerals sit fully inside the boxes. No remaining visual issue observed.

`tools/printables/verify.py` independently checks PNG CRCs, sRGB chunks, exact
size, opacity, quarter-size dimensions and artifact hashes. Its new checks
verify exact request text and letter-to-port mapping, then count white runs
in the actual full-size and quarter-size cable pixels, including minimum band
width and separation. Python syntax, SVG parsing/unique placeholder IDs and
`git diff --check` also passed.

The renderer and verifier additions are opt-in/request-specific; existing SVG
templates and delivered documents were not edited. No runtime code, room scene,
room.yaml, other asset, request status or docs outside the printable lane were
edited by this task. No commit was made. Godot import, inspect lighting,
material roughness and in-room acceptance remain Claude's integration work.
Per ADR-0014 and the printable request README, the GLB-only `assetcheck` and
`tools/blender/build_assets.sh` do not apply to this PNG asset.

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

Output SHA-256: `be298572081818ee64bd62ca7d4ae512c1cb10136b9898d2165eb285636e4428`.

Preview SHA-256: `a32879ac35d29d83c5131e018b5ee390b38a03c6abe48c200eaf00b5407cdd06`.

Build and verification logs: `assets/cache/printables2_build_final.log`,
`printables2_build_repro.log`, `printables2_verify_first.log` and
`printables2_verify_repro.log`. The six-hash baseline is
`assets/cache/printables/network_diagram_laminated_work_order_first_build.sha256.json`.
