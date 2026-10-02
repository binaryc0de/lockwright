# wall_clock_countdown

**Status:** open
**Requested by:** Claude Code, 2026-10-02
**Used in:** core library; room night_shift / SDK node `SessionClock` (the room's countdown, fiction: UPS runtime left)
**Class:** prop

## Purpose
A wall-mounted LED countdown display above the exit door, showing the time left (rendered in-engine as red digits on the `screen` part). Must read as industrial equipment that someone installed to watch the UPS, not as a game HUD.

All positions below are in **Godot axes after import** (Y up, front toward -Z).

## Dimensions (metres)
- Housing: 0.46 W x 0.16 H x 0.05 D, back face at z = 0; sloped or chamfered edges.
- `screen`: smoked dark-red acrylic window 0.40 W x 0.095 H in the upper part, UV 0..1, recessed 0.003.
- Printed caption on the housing below the window, centred: `UPS RUNTIME` (white, cap height about 0.014), and a small `h:mm:ss` legend at the right.
- A cable gland on the underside with a short cable going up into the wall is welcome.

## Style references
- Industrial/data-centre LED timer (black powder-coat steel box, four corner screws, small vent slots), 2010s. Dusty top edge.

## Budgets
- Triangles: <= 20000
- Textures: base colour / normal / ORM at <= 1024 px
- Materials: <= 3 (`M_wall_clock_countdown_body`, `M_wall_clock_countdown_screen`, optional `M_wall_clock_countdown_print`)

## Named parts (exact mesh/object names the SDK will look up)
| Mesh name | Purpose | Separate transform? |
|---|---|---|
| `body` | housing with printed caption | no |
| `screen` | display window, material `M_wall_clock_countdown_screen` (dark red, low roughness, emissive-ready) | yes; origin at the window centre |

## Transforms
- Wall-mount prop: origin at the centre of the back mounting face (z = 0).
- Forward: front toward -Z after Godot import.
- Scale: 1 unit = 1 m, all transforms applied.

## Collision
None in the GLB.

## Animations (glTF, named exactly)
None.

## Text and printables
`UPS RUNTIME`, `h:mm:ss`, original stroke lettering; no font downloads.

## Extra metadata
`"anchors_godot_m": {"screen_centre": [x,y,z], "screen_size": [w,h]}`.

## Acceptance
- [ ] `tools/blender/build_assets.sh wall_clock_countdown` rebuilds the GLB headless
- [ ] `go run ./tools/assetcheck wall_clock_countdown` passes
- [ ] previews: front, iso, detail
- [ ] in-engine screenshot by Claude in Revision notes

## Revision notes
(Claude appends dated feedback here; Codex responds in assets/reports/wall_clock_countdown.md)
