# whiteboard_wall

**Status:** open
**Requested by:** Claude Code, 2026-10-02
**Used in:** core library; room night_shift (puzzle A2: marker notes plus a 4-digit code in UV ink, both drawn in-engine)
**Class:** prop

## Purpose
A wall-mounted office whiteboard. In Night Shift it carries the migration checklist in marker, and the UV torch reveals a hidden 4-digit code on it. All writing is rendered in-engine on top of the `surface` part, so the surface must be one flat rectangle with its own material and UVs spanning 0..1. The board is lit by a spotlight in a dark room, so the surface's subtle sheen and ghosting are what make it read as a real whiteboard.

All positions below are in **Godot axes after import** (Y up, the writing surface faces -Z).

## Dimensions (metres)
- Board outer: 1.60 W x 1.00 H x 0.025 D, aluminium frame profile about 0.018 wide with rounded grey plastic corner caps.
- `surface`: the white writing area inside the frame, 0.003 behind the frame's front lip.
- `tray`: aluminium pen tray along the bottom edge, full width, protruding 0.06 from the board face, top lip 0.012 tall, holding two dry-wipe markers (black, blue; capped) and a felt eraser block, all part of `tray`.

## Style references
- Standard melamine office whiteboard (Nobo/Quartet feel, no logos): satin white surface with faint ghosting of old, badly-erased writing (boxes, arrows, a grey smudge band where someone wipes with their hand), a little dust in the frame corners.
- Ghosting must stay very subtle (under about 6 percent darker than the clean surface) and stay out of the left-centre region (x -0.65 to +0.65, y -0.35 to +0.30 from the board centre) where Claude draws the real text, so the clue stays clean.

## Budgets
- Triangles: <= 20000
- Textures: base colour / normal / ORM at <= 2048 px (surface base colour may be 2048 x 1024)
- Materials: <= 4 (`M_whiteboard_wall_surface`, `M_whiteboard_wall_frame`, `M_whiteboard_wall_plastic`, optional `M_whiteboard_wall_markers`)

## Named parts (exact mesh/object names the SDK will look up)
| Mesh name | Purpose | Separate transform? |
|---|---|---|
| `frame` | aluminium frame and corner caps | no |
| `surface` | writing area, UV 0..1, material `M_whiteboard_wall_surface` | no |
| `tray` | pen tray with markers and eraser | no |

## Transforms
- Origin: wall-mount prop, origin at the centre of the board's back mounting face (the board's centre on the wall plane; back face at z = 0, everything else at z < 0).
- Forward: writing surface faces -Z after Godot import.
- Scale: 1 unit = 1 m, all transforms applied.

## Collision
None in the GLB.

## Animations (glTF, named exactly)
None.

## Text and printables
None (all writing is in-engine).

## Extra metadata
In `assets/meta/whiteboard_wall.json` add `"anchors_godot_m": {"surface_front_z": z, "surface_size": [w,h]}`.

## Acceptance
- [ ] `tools/blender/build_assets.sh whiteboard_wall` rebuilds the GLB headless
- [ ] `go run ./tools/assetcheck whiteboard_wall` passes
- [ ] previews: front, iso, detail (detail = tray with markers)
- [ ] in-engine screenshot by Claude in Revision notes

## Revision notes
(Claude appends dated feedback here; Codex responds in assets/reports/whiteboard_wall.md)
