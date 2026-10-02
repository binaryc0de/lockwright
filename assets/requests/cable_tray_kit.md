# cable_tray_kit

**Status:** open
**Requested by:** Claude Code, 2026-10-02
**Used in:** core library; room night_shift (overhead in the server cage)
**Class:** prop

## Purpose
Overhead ladder-type cable tray with a cable bundle and a drop to the rack: makes the cage read as a working server room. Décor. Delivered as a kit; **every part sits at the origin**.

All positions below are in **Godot axes after import** (Y up). Straight runs go along X.

## Dimensions (metres)
- `tray_1m`: galvanised ladder tray, 1.00 long (x -0.5 to +0.5), 0.30 wide (z -0.15 to +0.15), 0.10 tall (y 0 to 0.10), with a cable bundle (mixed blue/grey/yellow Cat6, black power) lying in it, plus two threaded hanger rods rising to y +0.35. Claude scales it along X for runs up to 2.5 m, so keep the rung spacing pattern in the texture/geometry tolerant of stretching up to 2.5x (or provide `tray_2m` too).
- `tray_2m`: the same, 2.00 long, if stretching would look wrong.
- `drop_1m`: a cable waterfall going down from a tray 1.0 m to a rack top, cables loosely bundled with velcro.

## Style references
- Data-centre wire/ladder tray, galvanised steel, neat but not pristine cabling.

## Budgets
- Triangles: <= 20000
- Textures: base colour / normal / ORM at <= 1024 px
- Materials: <= 3 (`M_cable_tray_kit_metal`, `M_cable_tray_kit_cables`, optional `M_cable_tray_kit_velcro`)

## Named parts (exact mesh/object names the SDK will look up)
| Mesh name | Purpose | Separate transform? |
|---|---|---|
| `tray_1m` | 1 m tray with cables and rods | yes |
| `tray_2m` | 2 m tray with cables and rods | yes |
| `drop_1m` | cable waterfall | yes |

## Transforms
- Origin: base centre on the floor plane for every part (the underside of the tray at y = 0; `drop_1m` hangs from y +1.0 down to 0).
- Forward: not significant; runs along X.
- Scale: 1 unit = 1 m, all transforms applied.

## Collision
None in the GLB.

## Animations (glTF, named exactly)
None.

## Text and printables
None.

## Acceptance
- [ ] `tools/blender/build_assets.sh cable_tray_kit` rebuilds the GLB headless
- [ ] `go run ./tools/assetcheck cable_tray_kit` passes
- [ ] previews: front, iso, detail
- [ ] in-engine screenshot by Claude in Revision notes

## Revision notes
(Claude appends dated feedback here; Codex responds in assets/reports/cable_tray_kit.md)
