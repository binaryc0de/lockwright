# ups_tower

**Status:** open
**Requested by:** Claude Code, 2026-10-02
**Used in:** core library; room night_shift (the UPS whose bypass relay powers the exit keypad once P1 is patched)
**Class:** hero

## Purpose
A floor-standing 3 kVA online UPS with a matching external battery cabinet beside it, in the cage corner. It is the fiction's power source ("UPS RUNTIME" on the wall clock) and the reason the patch panel matters: a printed panel on its front reads `BYPASS RELAY` with an indicator lamp. Décor plus story; not interactable.

All positions below are in **Godot axes after import** (Y up, front toward -Z).

## Dimensions (metres)
- Overall footprint 0.70 W x 0.60 D x 0.90 H: UPS tower 0.25 W at x -0.225 (left as seen from the front), battery cabinet 0.40 W at x +0.15, a 0.05 gap between them, both 0.60 deep and 0.90 tall, sitting on low feet.
- UPS front: a small status LCD (`screen`, 0.09 x 0.05, at about y 0.75), a few buttons, LED bar; below it a printed label `UPS 3kVA`.
- Battery cabinet front: vent grille and a printed panel `BYPASS RELAY` with a round indicator lamp (`relay_lamp`, own emissive material) and a toggle switch.
- Thick black cables from the back of both units running to the floor.

## Style references
- APC Smart-UPS SRT / Eaton 9SX feel without logos: black plastic bezels, perforated steel, slight dust on top.

## Budgets
- Triangles: <= 60000 (hero; 10-25k expected)
- Textures: base colour / normal / ORM at <= 2048 px
- Materials: <= 5 (`M_ups_tower_body`, `M_ups_tower_metal`, `M_ups_tower_screen`, `M_ups_tower_lamp`, optional `M_ups_tower_print`)

## Named parts (exact mesh/object names the SDK will look up)
| Mesh name | Purpose | Separate transform? |
|---|---|---|
| `body` | both units, cables, printed labels | no |
| `screen` | LCD, material `M_ups_tower_screen` (emissive-ready) | yes |
| `relay_lamp` | bypass relay indicator, material `M_ups_tower_lamp` (emissive, white base) | yes |

## Transforms
- Origin: base centre on the floor plane (centre of the 0.70 x 0.60 footprint).
- Forward: fronts toward -Z after Godot import.
- Scale: 1 unit = 1 m, all transforms applied.

## Collision
None in the GLB.

## Animations (glTF, named exactly)
None.

## Text and printables
`UPS 3kVA`, `BYPASS RELAY`; original stroke lettering; no logos.

## Acceptance
- [ ] `tools/blender/build_assets.sh ups_tower` rebuilds the GLB headless
- [ ] `go run ./tools/assetcheck ups_tower` passes
- [ ] previews: front, iso, detail
- [ ] in-engine screenshot by Claude in Revision notes

## Revision notes
(Claude appends dated feedback here; Codex responds in assets/reports/ups_tower.md)
