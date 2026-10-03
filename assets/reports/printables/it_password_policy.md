# it_password_policy

Built the requested plain-paper IT notice using the existing offline printable
pipeline: Blender 5.2.2 LTS headless, four threads, shared Blender process lock,
CPU SVG rasterization and 2× antialiasing. No render engine, GPU, network,
downloaded artwork or new dependency was used.

Deliverables:

- Source: `tools/printables/templates/it_password_policy.svg`, registered in `tools/printables/render.py`.
- Output: `game/rooms/night_shift/assets/docs/it_password_policy.png`, 1024 × 1448, opaque RGBA, sRGB.
- Preview: `assets/previews/printables/it_password_policy_25.png`, 256 × 362.
- Metadata: `assets/meta/printables/it_password_policy.json`, with nine exact request strings, wrapped lines/baselines, cap sizes, request/source/output/preview hashes, Blender version and seed.

Original kestrel geometry heads the corporate notice. The six symbols share a
large shaded row in the exact order `!   #   $   %   &   *`. Seeded paper fibres,
light print banding, a faint pin hole, a top-right dog-ear and restrained bottom
curl shading add wear without crossing the text. Printed font provenance is
already recorded in `tools/printables/ATTRIBUTION.md` (Blender-bundled Inter).

Personally inspected the full PNG and its actual 25% preview. All nine strings
are readable; the six symbols are distinct, and the example is exactly
`Example:  Falcon!2016`, including capitalization, exclamation mark and double
space. Quarter-size caps range from 7.5 to 11 px; the symbol row uses 11 px.
Long instructions wrap without losing words or punctuation.

No content or output-size deviation. The request's explicit 1448-pixel long
edge takes precedence over the pipeline's general 2048-pixel guideline, as
with the existing smaller printables. No UV texture was requested.

## Verification — 2026-10-02

Two successful final builds:

```bash
tools/printables/build_printables.sh it_password_policy anniversary_card
```

Between builds, ran Blender's bundled Python on `tools/printables/verify.py
--record it_password_policy anniversary_card`; after rebuilding, ran it with
`--compare` and the same IDs. Both exited 0. PNG CRCs, sRGB chunks, opacity,
dimensions, preview dimensions, exact wording/order, wrapped words and clue
sizes passed. Both outputs, both previews and both metadata files were
byte-identical. Python syntax, SVG parsing, unique ordered placeholders,
current source-hash freshness and `git diff --check` also passed.

Output SHA-256: `ce8de23dbe22ee2fabf30c2872afe581667742095ce1223251a9e59f6038d59a`.

Preview SHA-256: `5420d9c287e12792719845458be482f6e1cb191ad8e033fe2777c5063b4533af`.

Repeat-build and verification logs are in ignored `assets/cache/`, prefixed
`it_password_policy_anniversary_card_`. The six-artifact baseline is
`assets/cache/printables/it_password_policy_anniversary_card_first_build.sha256.json`.

The optional all-printable check stops at stale request metadata for the
existing `network_diagram_laminated`. Confirmed the unchanged HEAD verifier
fails identically; that asset was left untouched. The two assigned printables
pass their selected verification. Shared tooling changes are additive and
confined to these IDs. No runtime, room scene, manifest, request or unrelated
asset was edited by this task; no commit was made. In-engine assignment and
lighting review remain integration work. GLB build/assetcheck commands do not
apply to PNG printables (ADR-0014 and the printable request README).
