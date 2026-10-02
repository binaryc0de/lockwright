# server_rack_42u

**Status:** open
**Requested by:** Claude Code, 2026-10-02
**Used in:** core library; room night_shift (the cage's rack; holds the patch panel P1 and the RACK 062 stencil)
**Class:** hero

## Purpose
A populated 42U server rack, the centrepiece of the cage and visible through the mesh from the office: dark, with many small green/amber LEDs blinking-ready (Claude animates emission). The patch panel (separate asset) mounts in an empty 2U slot; the "RACK 062" stencil (a decal Claude places) goes on a blank 3U plate. No front door (removed, so players reach the panel).

All positions below are in **Godot axes after import** (Y up, front toward -Z).

## Dimensions (metres)
- Cabinet: 0.60 W x 1.00 D x 2.00 H, front face plane at z = -0.50, origin at the base centre. Side panels and top closed, rear door closed, front open with 19-inch rails set 0.03 behind the front face.
- Rack units from the bottom: 1U = 0.04445 m, U1 starts at y 0.10 (plinth below).
- Empty 2U slot for the patch panel, centred at **y 1.25** (nothing there but rails and cage nuts).
- Blank 3U plate (matte black, flat) centred at **y 1.72**, for the stencil decal.
- Fill the rest believably: 1U switches with port rows and LEDs, 2U and 1U servers with drive bays and bezels, a KVM drawer, a 1U cable manager under the patch-panel slot, blanking plates, a vertical PDU at the rear, cable bundles visible through the side gaps. Leave the bottom 0.35 m of the front empty except blanking plates.
- `leds`: every front LED as one separate mesh with its own emissive material, so Claude can blink them as one.

## Style references
- 2015-2025 data-centre rack (APC/Dell feel, no logos): black powder coat, perforated rear, dust on top. Equipment in black/dark grey with silver drive handles.

## Budgets
- Triangles: <= 60000 (hero)
- Textures: base colour / normal / ORM at <= 2048 px; an emissive mask for LEDs if useful
- Materials: <= 5 (`M_server_rack_42u_cabinet`, `M_server_rack_42u_equipment`, `M_server_rack_42u_metal`, `M_server_rack_42u_led`, optional `M_server_rack_42u_cables`)

## Named parts (exact mesh/object names the SDK will look up)
| Mesh name | Purpose | Separate transform? |
|---|---|---|
| `cabinet` | cabinet, rails, equipment, cables | no |
| `leds` | all front LEDs, material `M_server_rack_42u_led` (emissive) | no |

## Transforms
- Origin: base centre on the floor plane.
- Forward: front toward -Z after Godot import.
- Scale: 1 unit = 1 m, all transforms applied.

## Collision
None in the GLB. The room keeps its own box collider.

## Animations (glTF, named exactly)
None.

## Text and printables
None (stencil is a decal).

## Extra metadata
`"anchors_godot_m": {"patch_slot_centre": [x,y,z], "stencil_plate_centre": [x,y,z], "rail_front_z": z}`.

## Acceptance
- [ ] `tools/blender/build_assets.sh server_rack_42u` rebuilds the GLB headless
- [ ] `go run ./tools/assetcheck server_rack_42u` passes
- [ ] previews: front, iso, detail
- [ ] in-engine screenshot by Claude in Revision notes

## Revision notes
(Claude appends dated feedback here; Codex responds in assets/reports/server_rack_42u.md)
