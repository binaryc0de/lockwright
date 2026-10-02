# monitor_24

**Status:** open
**Requested by:** Claude Code, 2026-10-02
**Used in:** core library (décor; Night Shift desk, and any office room)
**Class:** prop

## Purpose
A 24-inch office desktop monitor on its stand. Décor, but it carries puzzle B1: a sticky note with the username is stuck to the lower-right corner of the bezel (Claude places the note in-engine), and its screen glows faintly in the dark office. The screen must be a clean, separately-materialled rectangle with UVs spanning 0..1.

All positions below are in **Godot axes after import** (Y up, the display faces -Z toward the user).

## Dimensions (metres)
- Panel (bezel shell): 0.56 W x 0.34 H x 0.045 D at the back bulge (0.015 at the edges), bottom edge 0.12 above the desk, so the panel centre sits at y = 0.29.
- Display (`screen`): 0.531 W x 0.299 H (16:9), thin 6-8 mm side/top bezels, a slightly deeper bottom bezel (about 0.02) with a tiny power LED at the right.
- Stand: rectangular foot 0.22 W x 0.17 D x 0.015, a flat neck rising behind the panel; the panel clamps onto it.

## Style references
- 2015-2022 corporate monitor (Dell P-series / HP E-series feel, no logos): matte black plastic, slightly glossy bottom-bezel strip, silver-grey foot optional.
- Wear: dust on the top edge of the panel and the foot, faint fingerprints at the bottom right of the bezel.

## Budgets
- Triangles: <= 20000
- Textures: base colour / normal / ORM at <= 1024 px
- Materials: <= 4 (`M_monitor_24_plastic`, `M_monitor_24_screen`, `M_monitor_24_led`, optional `M_monitor_24_metal`)

## Named parts (exact mesh/object names the SDK will look up)
| Mesh name | Purpose | Separate transform? |
|---|---|---|
| `stand` | foot and neck | no |
| `panel` | bezel shell | no |
| `screen` | display quad, UV 0..1, material `M_monitor_24_screen` (black, emissive-ready, low roughness) | yes; origin at the display centre |
| `led_power` | power LED, material `M_monitor_24_led` (emissive, white base so Godot can tint it) | yes |

## Transforms
- Origin: base centre on the floor plane (y = 0 is the underside of the foot; the "floor" here is the desktop) at the centre of the overall bounding-box footprint.
- Forward: display faces -Z after Godot import.
- Scale: 1 unit = 1 m, all transforms applied.

## Collision
None in the GLB.

## Animations (glTF, named exactly)
None.

## Text and printables
None. No logos.

## Extra metadata
In `assets/meta/monitor_24.json` add `"anchors_godot_m": {"screen_centre": [x,y,z], "bezel_front_z": z, "bezel_bottom_right": [x,y,z]}`.

## Acceptance
- [ ] `tools/blender/build_assets.sh monitor_24` rebuilds the GLB headless
- [ ] `go run ./tools/assetcheck monitor_24` passes
- [ ] previews: front, iso, detail
- [ ] in-engine screenshot by Claude in Revision notes

## Revision notes
(Claude appends dated feedback here; Codex responds in assets/reports/monitor_24.md)
