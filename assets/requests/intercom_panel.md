# intercom_panel

**Status:** open
**Requested by:** Claude Code, 2026-10-02
**Used in:** core library; room night_shift / SDK node `Intercom` (in-fiction hint delivery from the night guard)
**Class:** prop

## Purpose
A wall-mounted building intercom station the night guard talks through. Hints appear as text on its LCD (Claude renders the text in-engine on the `screen` part) with a chime. Décor-level interaction: players do not press its buttons.

All positions below are in **Godot axes after import** (Y up, front toward -Z).

## Dimensions (metres)
- Housing: 0.22 W x 0.32 H x 0.04 D, back face at z = 0.
- `screen`: LCD window 0.18 W x 0.10 H, upper part of the housing, recessed 0.002, UV 0..1.
- Speaker grille (perforated) below the screen, a large round "CALL" button (`btn_call`, décor) and a small microphone hole; `led_status` beside the call button.
- Engraved/printed small text on the housing: `SECURITY` above the screen.

## Style references
- 2010s commercial door/lift intercom (Aiphone/Commend feel, no logos): brushed stainless or dark anodised faceplate, tamper screws, slight fingerprint smudging around the button.

## Budgets
- Triangles: <= 20000
- Textures: base colour / normal / ORM at <= 1024 px
- Materials: <= 5 (`M_intercom_panel_body`, `M_intercom_panel_screen`, `M_intercom_panel_led`, `M_intercom_panel_button`, optional `M_intercom_panel_grille`)

## Named parts (exact mesh/object names the SDK will look up)
| Mesh name | Purpose | Separate transform? |
|---|---|---|
| `body` | housing, grille | no |
| `screen` | LCD, material `M_intercom_panel_screen` (dark, emissive-ready) | yes; origin at the screen centre |
| `btn_call` | call button | yes |
| `led_status` | LED, material `M_intercom_panel_led` (emissive, white base) | yes |

## Transforms
- Wall-mount prop: origin at the centre of the back mounting face (z = 0).
- Forward: front toward -Z after Godot import.
- Scale: 1 unit = 1 m, all transforms applied.

## Collision
None in the GLB.

## Animations (glTF, named exactly)
None.

## Text and printables
`SECURITY` (small, engraved or printed), original stroke lettering or geometry; no font downloads.

## Extra metadata
`"anchors_godot_m": {"screen_centre": [x,y,z], "screen_size": [w,h]}`.

## Acceptance
- [ ] `tools/blender/build_assets.sh intercom_panel` rebuilds the GLB headless
- [ ] `go run ./tools/assetcheck intercom_panel` passes
- [ ] previews: front, iso, detail
- [ ] in-engine screenshot by Claude in Revision notes

## Revision notes
(Claude appends dated feedback here; Codex responds in assets/reports/intercom_panel.md)
