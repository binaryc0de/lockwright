# filing_cabinet_keypad

**Status:** open
**Requested by:** Claude Code, 2026-10-02
**Used in:** room night_shift / SDK nodes `ContainerProp` + `KeypadLock` (puzzle A3: the UV code from the whiteboard opens it)
**Class:** hero

## Purpose
A steel three-drawer filing cabinet that IT retrofitted with an electronic keypad lock. Players type the code they found under UV on the whiteboard into the keypad; the **top drawer** then opens (the SDK slides it 0.40 m toward the player) to reveal a laminated network diagram and a USB stick lying in it. The keypad itself is the existing `keypad_4` asset (0.075 W x 0.115 H x 0.022 D), which Claude mounts in-engine; this cabinet only provides a flat mounting area for it, a header band above the top drawer, and a label-card holder on the top drawer front.

All positions below are in **Godot axes after import** (Y up, the drawer fronts face -Z, the player stands on the -Z side).

## Dimensions (metres)
- Carcass: 0.50 W x 0.60 D x 1.20 H. Back face of the carcass at z = +0.30, front face of the carcass at z = -0.30. Drawer fronts and handles stand proud of the front face.
- Header band (fixed, part of `body`) from y = 0.97 to y = 1.19 with a flat mounting area for `keypad_4`, its back face centred at (x 0, y 1.12) and flush with the front face plane. Optionally a subtle drilled cable grommet beside it. Do not model the keypad.
- `drawer_top`: front 0.46 W x 0.22 H x 0.02, centred at (x 0, y 0.85), outer face at z = -0.32. Recessed or bar pull handle plus a small steel label-card holder (card slot about 0.09 x 0.03) above the handle. Behind the front an open-top steel tray: interior 0.42 W x 0.50 D, sides 0.16 tall, floor at y = 0.755. Must look correct from above when slid 0.40 m toward -Z (finished interior, no missing faces).
- `drawer_mid` and `drawer_low`: two fronts filling y = 0.02 to 0.72 (0.34 H each, small gaps), each with a handle and label-card holder. Static décor.
- Nothing may intrude into the top drawer's tray volume or its 0.40 m travel path.

## Style references
- Classic steel office filing cabinet, powder-coated light office grey (RAL 7035), 1990s-2010s. Slight orange-peel texture in the paint (normal map), rolled front edges.
- Wear: chipped paint on the top front corners and around handles showing dark steel, fingerprints and dull scuffs on the top drawer, a faint rust bloom at the plinth. Lived-in but not derelict.
- Handles: chrome or brushed steel. Label-card holders: steel frames; Claude places the label text in-engine, so leave the card blank off-white.
- Tray interior: bare grey galvanised steel.

## Budgets
- Triangles: <= 60000 (hero; 8-20k expected)
- Textures: base colour / normal / ORM at <= 2048 px
- Materials: <= 4 (`M_filing_cabinet_keypad_paint`, `M_filing_cabinet_keypad_metal`, `M_filing_cabinet_keypad_interior`, optional `M_filing_cabinet_keypad_card`)

## Named parts (exact mesh/object names the SDK will look up)
| Mesh name | Purpose | Separate transform? |
|---|---|---|
| `body` | carcass, header band, keypad mounting area, plinth | no |
| `drawer_top` | top drawer: front, handle, card holder and open tray | yes; object origin at the centre of the front panel's outer face, (0, 0.85, -0.32) |
| `drawer_mid` | middle drawer front (static) | yes |
| `drawer_low` | bottom drawer front (static) | yes |

## Transforms
- Origin: base centre on the floor plane, at the centre of the **overall** bounding-box footprint (fronts and handles included) so assetcheck's base-centre test passes. Report where the carcass ended up relative to it (see Extra metadata).
- Forward: drawer fronts face -Z after Godot import.
- Scale: 1 unit = 1 m, all transforms applied (drawer objects keep only their location).

## Collision
None in the GLB. The room keeps its own box colliders.

## Animations (glTF, named exactly)
None. The SDK slides `drawer_top` in Godot.

## Text and printables
None (labels are placed in-engine).

## Extra metadata
In `assets/meta/filing_cabinet_keypad.json` add `"anchors_godot_m": {"carcass_back_z": z, "carcass_front_z": z, "drawer_top": [x,y,z], "keypad_mount": [x,y,z], "label_card_top": [x,y,z]}` with the exported values (`keypad_mount` = where keypad_4's back face centre goes).

## Acceptance
- [ ] `tools/blender/build_assets.sh filing_cabinet_keypad` rebuilds the GLB headless
- [ ] `go run ./tools/assetcheck filing_cabinet_keypad` passes
- [ ] previews: front, iso, detail (detail = top drawer pulled 0.40 m out, seen from above)
- [ ] in-engine screenshot by Claude in Revision notes

## Revision notes
(Claude appends dated feedback here; Codex responds in assets/reports/filing_cabinet_keypad.md)
