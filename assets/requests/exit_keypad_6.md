# exit_keypad_6

**Status:** open
**Requested by:** Claude Code, 2026-10-02
**Used in:** room night_shift / SDK node `KeypadLock` (the META puzzle: 6-digit override code SITE+RACK opens the exit)
**Class:** hero

## Purpose
The maglock override panel beside the exit door: a wall-mounted access-control keypad with a 6-character display, unpowered (dark) until the UPS bypass is patched, then lit. Above it, a separate engraved steel plate carries the clue that tells players how to build the code. Players enter the code in a focused view, so the keys must read clearly at 0.3 m. Model it like the accepted `keypad_4` (same key naming and press convention; read `assets/requests/keypad_4.md`, `assets/reports/keypad_4.md` and `tools/blender/props/keypad_4.py` first) but larger and wall-mounted.

All positions below are in **Godot axes after import** (Y up, key face toward -Z).

## Dimensions (metres)
- Keypad housing: 0.12 W x 0.18 H x 0.028 D, back face at z = 0, centred on the origin.
- Keys: 3 x 4 grid `1 2 3 / 4 5 6 / 7 8 9 / CLR 0 ENT`, caps 0.022 x 0.017, pitch 0.028 x 0.022, in the lower part of the housing.
- Display window above the keys: 0.085 W x 0.020 H (fits 6 characters), recessed 0.001; status LED to its right.
- `label_plate`: separate brushed-steel plate, 0.36 W x 0.13 H x 0.004, back at z = 0, centred at (0, +0.32, z), four countersunk screws. Engraved black-filled text, two lines, centred, uppercase sans-serif, cap height about 0.022: `MAGLOCK OVERRIDE:` / `SITE + RACK`. This is a puzzle clue: it must be legible at 1.5 m.
- Key press travel 0.0025 m into the housing, which is +Z in Godot. Claude animates it in-engine.

## Style references
- Commercial access-control keypad (stainless or dark powder-coat bezel, backlit-ready translucent key legends), 2015-2025. Light wear around 0, 4, 1, 7 and ENT.

## Budgets
- Triangles: <= 60000 (hero; 6-15k expected)
- Textures: base colour / normal / ORM at <= 2048 px; legend atlas <= 1024 px; plate engraving <= 2048 px
- Materials: <= 6 (`M_exit_keypad_6_body`, `M_exit_keypad_6_key`, `M_exit_keypad_6_screen`, `M_exit_keypad_6_led`, `M_exit_keypad_6_plate`, optional `M_exit_keypad_6_screw`)

## Named parts (exact mesh/object names the SDK will look up)
| Mesh name | Purpose | Separate transform? |
|---|---|---|
| `body` | housing | no |
| `btn_0` .. `btn_9` | digit keys | yes, origin at the key's base centre on the housing face |
| `btn_clear` | CLR | yes |
| `btn_enter` | ENT | yes |
| `screen` | display window, material `M_exit_keypad_6_screen` | yes |
| `led_status` | status LED, material `M_exit_keypad_6_led` (emissive, white base) | yes |
| `label_plate` | engraved clue plate | yes |
| `body-colonly` | collision box over the housing only (not the plate) | no |

## Transforms
- Wall-mount prop: origin at the centre of the keypad housing's back mounting face (z = 0); everything else at z < 0.
- Forward: key face toward -Z after Godot import.
- Scale: 1 unit = 1 m, all transforms applied (parts keep only their location).

## Collision
`body-colonly`: one box over the housing.

## Animations (glTF, named exactly)
None.

## Text and printables
Key legends `0`-`9`, `CLR`, `ENT`; plate text above. No external fonts: reuse or extend keypad_4's original stroke alphabet.

## Extra metadata
`"anchors_godot_m": {"screen_centre": [x,y,z], "screen_size": [w,h], "plate_centre": [x,y,z]}`.

## Acceptance
- [ ] `tools/blender/build_assets.sh exit_keypad_6` rebuilds the GLB headless
- [ ] `go run ./tools/assetcheck exit_keypad_6` passes
- [ ] previews: front, iso, detail (detail = plate text legible)
- [ ] in-engine screenshot by Claude in Revision notes

## Revision notes
(Claude appends dated feedback here; Codex responds in assets/reports/exit_keypad_6.md)
