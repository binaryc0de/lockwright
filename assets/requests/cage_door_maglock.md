# cage_door_maglock

**Status:** open
**Requested by:** Claude Code, 2026-10-02
**Used in:** room night_shift / SDK nodes `Door` + `MaglockGate` (released when the intranet flag is accepted, puzzle B5)
**Class:** hero

## Purpose
The mesh door into the server cage, held by a maglock. It must match `cage_partition_kit` (same frame tube and weld mesh; read that request first) and be see-through. The maglock housing faces the office so players see it from the moment they start; its LED goes red to green when the flag is accepted (Claude tints it). A Label3D "MAGLOCK - CTRL: INTRANET" sits on the housing (Claude places it). The SDK swings the leaf 100 degrees into the cage.

All positions below are in **Godot axes after import** (Y up). The office side looks toward **-Z**; the cage is on the +Z side; the partition plane is z = 0.

## Dimensions (metres)
- Opening: x 0.00 to 1.00, y 0.00 to 2.10 (the header above is a separate partition part).
- `leaf`: 0.98 W x 2.08 H, x 0.01 to 0.99, y 0.00 to 2.08, centred on z = 0 (about 0.05 thick): tube frame, weld mesh, a solid kick plate at the bottom 0.25 m and a solid plate around the lock zone at the top free corner, a pull handle on the office side at y 1.05 near x 0.90, the maglock armature plate on the office face at the top free corner (x 0.72 to 0.98, top at 2.06).
- `frame`: hinge post at x -0.02 (40 x 40 tube, full 2.10) and strike post at x 1.02, with butt hinges on the hinge post. Must not intrude into the leaf's swing: the leaf rotates about the vertical axis at (0, ·, 0) toward **+Z** (into the cage) by up to 100 degrees.
- `maglock`: magnet housing on the office side of the strike post head, x 0.725 to 0.975, y 2.02 to 2.08, z -0.11 to -0.05, with an L-bracket to the frame and a conduit going up.
- `maglock_led`: small LED on the housing's office face near x 0.74, own material (emissive, white base).

## Style references
- As cage_partition_kit; maglock in brushed aluminium (600 lb class); a yellow/black hazard sticker on the lock plate is welcome (no text).

## Budgets
- Triangles: <= 60000 (hero)
- Textures: base colour / normal / ORM at <= 2048 px; weld mesh alpha-cutout
- Materials: <= 5 (`M_cage_door_maglock_frame`, `M_cage_door_maglock_mesh`, `M_cage_door_maglock_metal`, `M_cage_door_maglock_led`, optional `M_cage_door_maglock_sticker`)

## Named parts (exact mesh/object names the SDK will look up)
| Mesh name | Purpose | Separate transform? |
|---|---|---|
| `leaf` | door leaf | yes; origin on the hinge axis at the floor, (0, 0, 0) |
| `frame` | posts and hinges | no |
| `maglock` | maglock housing, bracket, conduit | no |
| `maglock_led` | LED | yes |

## Transforms
- Origin: the hinge axis at floor level, (0, 0, 0).
- Forward: office side toward -Z after Godot import.
- Scale: 1 unit = 1 m, all transforms applied (`leaf` keeps only its location).

## Collision
None in the GLB.

## Animations (glTF, named exactly)
None. The SDK rotates `leaf`.

## Text and printables
None (Claude places the label).

## Extra metadata
`"anchors_godot_m": {"maglock_label_centre": [x,y,z], "maglock_led": [x,y,z]}` (`maglock_label_centre` = centre of the housing's office face).

## Acceptance
- [ ] `tools/blender/build_assets.sh cage_door_maglock` rebuilds the GLB headless
- [ ] `go run ./tools/assetcheck cage_door_maglock` passes (hinge origin warning expected)
- [ ] previews: front, iso, detail (detail = maglock)
- [ ] in-engine screenshot by Claude in Revision notes

## Revision notes
(Claude appends dated feedback here; Codex responds in assets/reports/cage_door_maglock.md)
