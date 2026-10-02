# desk_3drawer

**Status:** open
**Requested by:** Claude Code, 2026-10-02
**Used in:** room night_shift / SDK node `ContainerProp` (the top drawer holds the UV torch, puzzle A1)
**Class:** hero

## Purpose
The sysadmin's office desk in Night Shift: a plain corporate panel-end desk with a three-drawer pedestal on the seated user's right. It is the first thing players see and the first puzzle (the UV torch is under papers in the top drawer), so it sets the visual bar for the whole room. The **top drawer** opens: the SDK slides it 0.40 m straight toward the player, and the inside of the drawer (an open-top tray) must look like a real drawer when open. The two lower drawers are décor and never open. A monitor, a laptop and a sticky note sit on the top (separate assets); leave the top clear.

All positions below are in **Godot axes after import** (Y up, the desk front faces -Z, the seated user sits on the -Z side; the user's right hand side is **-X**).

## Dimensions (metres)
- Overall: 1.60 W x 0.75 D x 0.76 H. Desktop 0.04 thick (y 0.72 to 0.76), front edge at z = -0.375, back edge at z = +0.375.
- End panels (the "legs"): two slab panels 0.04 thick, 0.70 deep, 0.72 tall, centred at x = +0.78 and x = -0.78.
- Modesty panel at the back: 1.52 W x 0.40 H x 0.02 thick, spanning y 0.30 to 0.70, centred at z = +0.325.
- Pedestal under the top on the user's right, between x = -0.74 and x = -0.10, from a 0.04 kick plinth up to the underside of the top. Three drawer fronts:
  - `drawer_top`: front panel 0.60 W x 0.14 H x 0.02, centred at (x -0.42, y 0.62), outer face at z = -0.395 (proud of the desk edge by 0.02), with a pull handle. Behind it an open-top tray: interior 0.56 W x 0.46 D x 0.11 H, floor at y = 0.56, tray back wall at z = +0.08. Sides/back 0.01 thick. Must look correct from above when slid 0.40 m toward -Z (no missing faces, finished interior).
  - `drawer_mid`: a second 0.14 H front below it.
  - `drawer_file`: a deep file drawer front filling the rest of the pedestal down to the plinth.
- Nothing may intrude into the top drawer's tray volume or its 0.40 m travel path.

## Style references
- 2010s commercial office furniture, budget contract range: light grey oak-effect laminate desktop with 2 mm dark ABS edge banding; warm-grey (RAL 7044-ish) melamine end panels, modesty panel and pedestal; brushed aluminium bar handles.
- Wear: light. Faint scuffs on the desktop edge where wrists rest, a couple of very faint mug rings on the top surface, kick marks on the plinth. Not grungy; this is a working office.
- Drawer tray interior: plain light-grey melamine with slightly darker inner corners (AO).

## Budgets
- Triangles: <= 60000 (hero; 10-25k expected)
- Textures: base colour / normal / ORM at <= 2048 px
- Materials: <= 4 (`M_desk_3drawer_top`, `M_desk_3drawer_carcass`, `M_desk_3drawer_metal`, optional `M_desk_3drawer_interior`)

## Named parts (exact mesh/object names the SDK will look up)
| Mesh name | Purpose | Separate transform? |
|---|---|---|
| `body` | desktop, end panels, modesty panel, pedestal carcass, plinth | no |
| `drawer_top` | top drawer: front, handle and open tray as one object | yes; object origin at the centre of the front panel's outer face, (-0.42, 0.62, -0.395) |
| `drawer_mid` | middle drawer front + handle (static décor) | yes |
| `drawer_file` | file drawer front + handle (static décor) | yes |

## Transforms
- Origin: base centre on the floor plane (centre of the 1.60 x 0.75 footprint, y = 0 at the floor).
- Forward: the drawer fronts face -Z after Godot import (model with the front toward Blender +Y; `docs/ASSET_PIPELINE.md` Section 6).
- Scale: 1 unit = 1 m, all transforms applied (drawer objects keep only their location).

## Collision
None in the GLB. The room keeps its own box colliders that already match the dimensions above.

## Animations (glTF, named exactly)
None. The SDK slides `drawer_top` in Godot.

## Text and printables
None. No logos.

## Extra metadata
In `assets/meta/desk_3drawer.json` add `"anchors_godot_m": {"drawer_top": [x,y,z], "desktop_surface_y": y}` with the exported values.

## Acceptance
- [ ] `tools/blender/build_assets.sh desk_3drawer` rebuilds the GLB headless
- [ ] `go run ./tools/assetcheck desk_3drawer` passes
- [ ] previews: front, iso, detail (detail = top drawer pulled 0.40 m out, seen from above at 45 degrees, to prove the tray interior)
- [ ] in-engine screenshot by Claude in Revision notes

## Revision notes
(Claude appends dated feedback here; Codex responds in assets/reports/desk_3drawer.md)

**2026-10-02, Claude: revise origin (request bug, not a build bug).** The first build did exactly what this request said, but the request contradicted assetcheck's base-centre rule: the drawer fronts and handles stand proud of the desktop's front edge, so the overall bounds centre sits 25.5 mm toward -Z from the footprint centre (`FAIL ... bounds centre z = -0.0255`). Change only the origin: put it at the centre of the **overall** bounding-box footprint (handles included), exactly like `filing_cabinet_keypad` and `laptop_open`. Every position in this request shifts by the same amount; recompute `anchors_godot_m` from the export and add `"desktop_front_edge_z"`. Geometry, materials and part names stay as they are.
