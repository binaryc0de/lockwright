# exit_door_maglock

**Status:** open
**Requested by:** Claude Code, 2026-10-02
**Used in:** room night_shift / SDK node `Door` (`is_exit`; opens when the override keypad accepts SITE+RACK)
**Class:** hero

## Purpose
The office's emergency exit: a painted steel door in a steel frame, sealed by a surface-mounted electromagnetic lock. It is the goal of the room and is in view for the whole game, so it must read instantly as "the way out, magnetically locked". The SDK swings the leaf open (100 degrees, away from the room, into the corridor) when the room is won; the frame and maglock stay put. A Label3D on the leaf reads "MAGLOCKED / USE OVERRIDE PANEL" (Claude places it).

All positions below are in **Godot axes after import** (Y up). The room-side face of the door looks toward **-Z**; the player stands on the -Z side.

## Dimensions (metres)
- Clear opening in the wall: x 0.00 to 1.00, y 0.00 to 2.10, wall face plane at z = 0, wall 0.10 thick (z 0 to +0.10).
- `leaf`: 0.98 W x 2.08 H x 0.05, spanning x 0.01 to 0.99, y 0.00 to 2.08, z +0.005 to +0.055 (it sits in the opening, just behind the wall face). Push bar (panic bar) across the room face at about y 1.00, protruding to about z -0.045, with end caps; steel kick plate at the bottom of the room face; the armature plate of the maglock on the room face at the top free corner (x 0.55 to 0.95, top 0.02 below the leaf top).
- `frame`: pressed-steel frame. Architrave face 0.05 wide around the opening on the room-side wall face (z 0 to -0.015), jamb and head returns lining the opening to z +0.10. Must not intrude into the leaf or its swing: the leaf rotates about the vertical axis at x = 0, z = 0 toward **+Z** (into the corridor).
- `maglock`: magnet housing under the frame head on the room side, x 0.52 to 0.98, y 2.035 to 2.10, z -0.005 to -0.07, with a conduit running up into the ceiling line (to y 2.35 is enough).
- `maglock_led`: small status LED on the maglock housing front, own material (emissive, white base so Godot can tint red/green).
- A short glossy exit sticker (running-man pictogram, green, no text) on the leaf above the push bar is welcome.

## Style references
- Commercial steel fire-exit door, satin grey-blue paint (RAL 5014-ish desaturated), heavy scuffing at push height and kick zone, chipped paint at the leaf edges; frame in darker grey. Maglock: brushed aluminium housing (600 lb class).

## Budgets
- Triangles: <= 60000 (hero)
- Textures: base colour / normal / ORM at <= 2048 px
- Materials: <= 5 (`M_exit_door_maglock_leaf`, `M_exit_door_maglock_frame`, `M_exit_door_maglock_metal`, `M_exit_door_maglock_led`, optional `M_exit_door_maglock_sticker`)

## Named parts (exact mesh/object names the SDK will look up)
| Mesh name | Purpose | Separate transform? |
|---|---|---|
| `leaf` | door leaf with push bar, kick plate, armature plate | yes; origin on the hinge axis at the floor, (0, 0, 0) |
| `frame` | frame | no |
| `maglock` | maglock housing and conduit | no |
| `maglock_led` | status LED | yes |

## Transforms
- Origin: the hinge axis at floor level, (0, 0, 0), which is also where the opening's hinge-side edge meets the room-side face plane (z = 0).
- Forward: room side faces -Z after Godot import.
- Scale: 1 unit = 1 m, all transforms applied (`leaf` keeps only its location).

## Collision
None in the GLB. The room keeps its own box colliders.

## Animations (glTF, named exactly)
None. The SDK rotates `leaf` in Godot.

## Text and printables
No text (Claude places the "MAGLOCKED" label).

## Extra metadata
`"anchors_godot_m": {"leaf_room_face_z": z, "leaf_label_centre": [x,y,z], "maglock_led": [x,y,z]}` (`leaf_label_centre` = a clear flat area on the room face, about 0.40 x 0.15, above the push bar).

## Acceptance
- [ ] `tools/blender/build_assets.sh exit_door_maglock` rebuilds the GLB headless
- [ ] `go run ./tools/assetcheck exit_door_maglock` passes (hinge origin is reported as a warning only)
- [ ] previews: front, iso, detail (detail = maglock and armature)
- [ ] in-engine screenshot by Claude in Revision notes

## Revision notes
(Claude appends dated feedback here; Codex responds in assets/reports/exit_door_maglock.md)
