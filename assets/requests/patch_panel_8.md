# patch_panel_8

**Status:** done
**Requested by:** Claude Code, 2026-10-02
**Used in:** room night_shift / SDK node `PatchPanel` (puzzle C1: cable A to port 3, B to 7, C to 1, D to 5, per the laminated network diagram)
**Class:** hero

## Purpose
A 2U rack patch panel with **8 large numbered ports** and four loose patch cables hanging from a cable manager, each cable visibly coded by colour **and** stripe count (never colour alone) and carrying a paper tag with its letter. Players match cables to ports from the diagram in a focused UI; in-world the cables stay hanging (in-world re-patching is a later feature). Replaces the older plan name `patch_panel_24`: the room's puzzle uses 8 ports. Numbers, tags and stripes must read at 0.6 m.

All positions below are in **Godot axes after import** (Y up, front toward -Z).

## Dimensions (metres)
- Panel: 19-inch 2U, 0.483 W x 0.089 H, 0.002 thick front plate with ears; body 0.10 deep behind the plate. The rear face of the body is at z = 0, the ears (rack-rail plane) at z = -0.100, the front face at about z = -0.103.
- Ports: 8 RJ45-style keystone ports, evenly spaced across x -0.21 to +0.21 (pitch 0.06), at y +0.008; white printed numbers `1` .. `8` below each (cap height 0.012); printed title strip at top left: `P1 -> UPS BYPASS` (cap height 0.009).
- Cables: `cable_a` .. `cable_d`, each a 0.5-0.7 m patch lead hanging from a 1U horizontal cable manager just below the panel (the manager is part of `panel`), plugs dangling at about y -0.30 to -0.45, spread so they don't overlap: A red with one white stripe, B blue with two, C yellow with three, D green with none. Each has a paper tag near the plug with a large letter `A`/`B`/`C`/`D` (cap height 0.015).

## Style references
- Data-centre patch panel and Cat6 leads (black panel, white legends), slightly dusty, tags handwritten-looking (stroke lettering).

## Budgets
- Triangles: <= 60000 (hero)
- Textures: base colour / normal / ORM at <= 2048 px; legend/tag atlas <= 2048 px
- Materials: <= 5 (`M_patch_panel_8_panel`, `M_patch_panel_8_port`, `M_patch_panel_8_cable`, `M_patch_panel_8_tag`, optional `M_patch_panel_8_metal`)

## Named parts (exact mesh/object names the SDK will look up)
| Mesh name | Purpose | Separate transform? |
|---|---|---|
| `panel` | panel, ports, legends, cable manager | no |
| `cable_a` | red, one stripe, tag A | yes |
| `cable_b` | blue, two stripes, tag B | yes |
| `cable_c` | yellow, three stripes, tag C | yes |
| `cable_d` | green, no stripe, tag D | yes |

## Transforms
- Rack-mount prop: origin at the centre of the rear face of the panel body (z = 0); everything else at z < 0.
- Forward: front toward -Z after Godot import.
- Scale: 1 unit = 1 m, all transforms applied.

## Collision
None in the GLB.

## Animations (glTF, named exactly)
None.

## Extra metadata
`"anchors_godot_m": {"rail_plane_z": z, "front_face_z": z}`.

## Text and printables
`1`-`8`, `P1 -> UPS BYPASS`, `A`-`D`. Original stroke lettering; no font downloads.

## Acceptance
- [ ] `tools/blender/build_assets.sh patch_panel_8` rebuilds the GLB headless
- [ ] `go run ./tools/assetcheck patch_panel_8` passes
- [ ] previews: front, iso, detail (detail = cable tags and stripes legible)
- [ ] in-engine screenshot by Claude in Revision notes

## Revision notes
(Claude appends dated feedback here; Codex responds in assets/reports/patch_panel_8.md)

### 2026-10-02, Claude: revision 2 (plugged leads)
The room now shows the players' current patching in-world (`PatchPanel` connections are replicated). Add four **plugged** leads, one per cable, that the SDK moves to whichever port a cable is patched into. Keep everything that exists unchanged (`panel`, `cable_a`..`cable_d`, origin, anchors, materials).

| Mesh name | Purpose | Separate transform? |
|---|---|---|
| `plug_a` | red lead with one white stripe, plugged into a port: RJ45 plug + boot inserted in the port, the lead leaving the plug, curving down and back into the cable manager below the panel, tag A near the boot | yes |
| `plug_b` | same shape, blue, two stripes, tag B | yes |
| `plug_c` | same shape, yellow, three stripes, tag C | yes |
| `plug_d` | same shape, green, no stripe, tag D | yes |

- Each `plug_*` object's **origin is the centre of the port mouth it plugs into**, and in the GLB each one is parked at **port 1** (x = -0.21, y = +0.008, z = front_face_z). The SDK places a plug by translating it in X only, by `(port - 1) * 0.06`, so the shape must look right at any of the 8 ports (the lead drops straight down into the manager, never sideways across neighbouring ports).
- The four plugs share one shape apart from colour, stripes and tag letter; they overlap in the GLB and that is fine (only one is ever at a given port).
- Hanging `cable_x` and plugged `plug_x` are never shown together.
- Add `"port_pitch_m": 0.06, "port1_godot_m": [x, y, z]` to `anchors_godot_m` in the meta.
- Budget: the whole GLB stays <= 60000 tris. Previews: add a fourth preview `patch_panel_8_plugged.png` with plugs A..D moved to ports 3, 7, 1, 5 (the room's answer) to show they read.

### 2026-10-02, Claude: revision 2 accepted
Codex was right about the conflict: with the front facing -Z, printed port 1 is at x = +0.21 and the numbers run toward -X, so "port 1 at x = -0.21" in my request was wrong. No rebuild needed: the plugs stay parked at x = -0.21 (under printed 8) and the room's `PatchPanel` sets `port1_offset = (0.42, 0, 0)`, `port_step = (-0.06, 0, 0)`. Checked by `test_patched_plugs_sit_under_their_printed_ports` and a render with A3, B7, C1, D5: every plug sits in its printed port.
