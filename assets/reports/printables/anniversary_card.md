# anniversary_card

Built the requested open-faced anniversary card using the existing offline
printable pipeline: Blender 5.2.2 LTS headless, four threads, shared process
lock, CPU SVG rasterization and 2× antialiasing. No render engine, GPU, network,
downloaded artwork or new dependency was used.

Deliverables:

- Source: `tools/printables/templates/anniversary_card.svg`, registered in `tools/printables/render.py`.
- Output: `game/rooms/night_shift/assets/docs/anniversary_card.png`, 1448 × 1024, opaque RGBA, sRGB.
- Preview: `assets/previews/printables/anniversary_card_25.png`, 362 × 256.
- Metadata: `assets/meta/printables/anniversary_card.json`, with all six exact strings, cap sizes, dimensions, request/source/output/preview hashes, Blender version and seed.

Original muted balloon/confetti graphics frame the large `5 YEARS!` heading.
The join-year line has a pale backing for contrast. Three handwritten messages
use the original stroke alphabet with different slants, sizes and pen widths:
Priya's blue fine pen, Dale's upright green felt pen and J.'s slanted plum ink.
A tiny original kestrel mark, faint pin hole, seeded paper fibres, light print
banding and edge handling finish the card. Existing font/procedural provenance
is covered by `tools/printables/ATTRIBUTION.md`.

Personally inspected the full PNG and actual 25% preview. All six exact strings
are readable, including the apostrophe in `Here's`, `(again)`, `(security)` and
J.'s final period. `2019` is distinct at 25%; its printed cap height is 9.5 px.
The greeting uses 11.5 px quarter-size caps and the handwritten messages use
9–9.75 px caps. Artwork and wear do not obscure any message.

No content or output-size deviation. The explicit 1448-pixel long edge takes
precedence over the general 2048-pixel printable guideline, following the
existing smaller-document workflow. No UV texture was requested.

## Verification — 2026-10-02

Two successful final builds:

```bash
tools/printables/build_printables.sh it_password_policy anniversary_card
```

Blender's bundled Python ran `tools/printables/verify.py --record
it_password_policy anniversary_card` between builds, then `--compare` with
the same IDs after rebuilding. Both exited 0. PNG CRCs, sRGB chunks, opacity,
dimensions, preview dimensions, exact wording/order and minimum clue sizes
passed. Both outputs, both previews and both metadata records reproduced
byte for byte. Python syntax, SVG parsing, unique ordered placeholders,
current source-hash freshness and `git diff --check` passed.

Output SHA-256: `c8a6b13325f2af259727147a8113a3cabcb710bcb1719366811e1a943189aa23`.

Preview SHA-256: `b6be07f71ac3f9ebba500886593c09e5ed1701712f1ef4a3a0dbbd2218eb51ea`.

Repeat-build and verification logs are in ignored `assets/cache/`, prefixed
`it_password_policy_anniversary_card_`. The six-artifact baseline is
`assets/cache/printables/it_password_policy_anniversary_card_first_build.sha256.json`.

The optional all-printable check stops at stale request metadata for the
existing `network_diagram_laminated`; the unchanged HEAD verifier fails
identically. That asset was left untouched. Selected verification for both
assigned printables passes. Shared renderer/verifier additions apply only to
these IDs. No runtime, room scene, manifest, request or unrelated asset was
edited by this task; no commit was made. In-engine assignment and lighting
review remain integration work. GLB build/assetcheck commands do not apply
to PNG printables (ADR-0014 and the printable request README).
