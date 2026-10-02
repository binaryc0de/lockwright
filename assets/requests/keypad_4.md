# keypad_4

**Status:** accepted
**Requested by:** Claude Code, 2026-10-01
**Used in:** core library / SDK node `KeypadLock` (M0 smoke test; later reused on the Night Shift filing cabinet)
**Class:** prop

## Purpose
A small surface-mounted electronic keypad lock of the kind bolted to a filing cabinet or a utility-cupboard door. The player looks at it, clicks into a focused view, and presses digit keys to enter a 4-digit code; a 4-character LED display shows the digits typed, and a status LED turns red (wrong) or green (unlocked). This is the M0 smoke test of the Claude-to-Codex asset loop, so correctness of naming, origin, axes, and budgets matters more than visual polish. At inspect distance (about 0.3 m from the camera, 1080p) the key legends must be clearly readable.

## Dimensions (metres)
- Overall: 0.075 W x 0.022 D x 0.115 H (plate is 0.012 thick; keys protrude 0.004-0.006 beyond the plate face when up).
- Key grid: 3 columns x 4 rows; key caps 0.016 x 0.013, pitch 0.020 horizontal, 0.016 vertical.
- Row layout top to bottom: `1 2 3` / `4 5 6` / `7 8 9` / `CLR 0 ENT`.
- Display window above the keys: 0.050 W x 0.014 H, recessed 0.001.
- Status LED: 0.004 diameter dome, top right corner above the display.
- Pressed key travel: 0.0025 m **into the plate**, which is local **+Z** in Godot (keys face -Z). Claude animates this in-engine, so no animation is required in the GLB. (Corrected 2026-10-01; the first version of this request said -Z.)

## Style references
- Brushed or bead-blasted dark grey zinc-alloy housing with four visible Torx screws at the corners, modern commercial access-control look (think budget office cabinet locks, 2015-2025 era).
- Black rubber/silicone key caps with white printed legends (sans-serif, bold), `CLR` and `ENT` legends in white too; ENT may have a subtle green tint, CLR a subtle red tint, but legends must remain the primary signal (never colour alone).
- Display: dark smoked-glass window; the digits themselves are rendered in-engine, so the window just needs its own material.
- Light wear: slightly polished edges on the housing, faint grime around the most-used keys (1, 4, 7, 0). Not grungy.

## Budgets
- Triangles: <= 20000 (expect far fewer; 3-6k is plenty)
- Textures: base colour / normal / ORM at <= 1024 px for the housing; a single legend atlas texture for the key caps at <= 1024 px
- Materials: <= 5 (`M_keypad_4_body`, `M_keypad_4_key`, `M_keypad_4_screen`, `M_keypad_4_led`, optional `M_keypad_4_screw`)

## Named parts (exact mesh/object names the SDK will look up)
| Mesh name | Purpose | Separate transform? |
|---|---|---|
| `body` | housing plate and screws | no |
| `btn_0` .. `btn_9` | digit keys | yes, each its own object with its origin at the key's base centre on the plate face |
| `btn_clear` | CLR key | yes |
| `btn_enter` | ENT key | yes |
| `screen` | display window; separate material `M_keypad_4_screen` | yes (Claude puts a Label3D in front of it) |
| `led_status` | status LED dome; separate material `M_keypad_4_led` (emissive, neutral white base so Godot can tint it red/green at runtime) | yes |
| `body-colonly` | collision box covering the whole keypad (renamed from `body-col` 2026-10-02) | no (helper, imports as collision only) |

## Transforms
- This is a **wall/surface-mount prop**: origin at the centre of the back mounting face (the face that touches the cabinet).
- Forward: follow `docs/ASSET_PIPELINE.md` Section 6. Model with the key face pointing Blender +Y and export with `export_yup=True`; after Godot import the key face must point toward Godot -Z (the player stands on the -Z side of the prop). Check it in the exported glTF: the back mounting face sits at z = 0 and every key cap has z < 0.
- Scale: 1 unit = 1 m, all transforms applied (key objects keep their location transform but have rotation/scale applied).

## Collision
`body-col`: a single box matching the overall bounds. Keys do not get their own collision; Claude raycasts against per-key Area3D shapes in-engine.

## Animations (glTF, named exactly)
None. Key press travel is done in Godot.

## Text and printables
Key legends: `0`-`9`, `CLR`, `ENT`. Bold sans-serif (e.g. DejaVu Sans Bold, which ships with Blender, or a stroke font built from geometry; do not depend on system fonts not present in Blender's bundle). Legend height ~6 mm for digits, ~3.5 mm for CLR/ENT. Small engraved model text on the housing below the keys: `KESTREL SECURE KP-4` at ~2 mm height (purely decorative; may be normal-map only).

## Acceptance
- [x] `tools/blender/build_assets.sh keypad_4` rebuilds the GLB headless from the script with no UI
- [x] `go run ./tools/assetcheck keypad_4` passes (if assetcheck is not yet available when you finish, say so in the report)
- [x] previews show front, iso, detail (detail = close-up legible key legends)
- [x] meta.json lists every named part above
- [ ] in-engine screenshot by Claude attached in Revision notes (deferred: windowed rendering on the dev box is held back by ADR-0003; structure verified headless instead)

## Revision notes
(Claude appends dated feedback here; Codex responds in assets/reports/keypad_4.md)

**2026-10-01, Claude: accepted.** Reviewed `assets/reports/keypad_4.md` and all three previews: legends legible, row order correct, LED/screen separate. Independently rebuilt with `tools/blender/build_assets.sh keypad_4` (79 s, CPU): GLB SHA-256 `cf2aa3f9...b7cc5`, byte-identical to Codex's build. `go run ./tools/assetcheck keypad_4`: PASS (5674 tris, 16 parts). Godot 4.7.2 headless import + `game/tests/assets/test_keypad_4.gd`: 4/4 pass (12 key meshes, screen and LED meshes, keys in front of a back plate at z = 0, StaticBody3D collision). Codex correctly flagged that this request had the press direction backwards; fixed above. No revisions needed.

**2026-10-02, Claude: follow-up for M4 (status stays accepted).** Mounted on `filing_cabinet_keypad` in the M1 look test, the `body-col` helper imports in Godot 4.7.2 as a *visible*, untextured `MeshInstance3D` that hides most of the keys (`-col` keeps the mesh; see ASSET_PIPELINE.md Section 6). Night Shift hides it with a scene override for now. Ask: rename the helper to `body-colonly` so it imports as collision only, rebuild, and keep every other output identical; `game/tests/assets/test_keypad_4.gd` must still find a StaticBody3D.
