# office_chair

**Status:** open
**Requested by:** Claude Code, 2026-10-02
**Used in:** core library (décor; Night Shift desk)
**Class:** prop

## Purpose
A standard swivel task chair pushed slightly back from the desk, as if the sysadmin just got up. Décor only, never interactable, but it sits in the middle of the most-viewed shot of the first room, so it must read as a real chair under a low warm desk lamp.

All positions below are in **Godot axes after import** (Y up, the seat front faces -Z).

## Dimensions (metres)
- Overall about 0.66 W x 0.66 D x 1.00 H (to the top of the backrest).
- Five-star base with castors, 0.66 diameter; gas lift column; seat 0.48 W x 0.46 D, seat top at y = 0.47; mesh or fabric backrest 0.46 W, top at y = 1.00; fixed loop armrests with pads at y = 0.66.

## Style references
- 2010s contract-range office task chair (Staples/IKEA Markus-ish without logos): black or charcoal fabric seat with visible weave in the normal map, black mesh or fabric backrest, black nylon base, grey plastic castors, chrome or black gas column.
- Wear: seat fabric slightly compressed and pilled at the front edge, dusty base. 

## Budgets
- Triangles: <= 20000
- Textures: base colour / normal / ORM at <= 2048 px
- Materials: <= 4 (`M_office_chair_fabric`, `M_office_chair_plastic`, `M_office_chair_metal`, optional `M_office_chair_mesh`)

## Named parts (exact mesh/object names the SDK will look up)
| Mesh name | Purpose | Separate transform? |
|---|---|---|
| `base` | star base, castors, gas column | no |
| `seat` | seat, backrest, armrests | yes; origin on the gas column axis so it can swivel |

## Transforms
- Origin: base centre on the floor plane, at the centre of the overall bounding-box footprint.
- Forward: seat front faces -Z after Godot import.
- Scale: 1 unit = 1 m, all transforms applied (`seat` keeps only its location).

## Collision
None in the GLB. The room keeps its own box collider.

## Animations (glTF, named exactly)
None.

## Text and printables
None. No logos.

## Acceptance
- [ ] `tools/blender/build_assets.sh office_chair` rebuilds the GLB headless
- [ ] `go run ./tools/assetcheck office_chair` passes
- [ ] previews: front, iso, detail
- [ ] in-engine screenshot by Claude in Revision notes

## Revision notes
(Claude appends dated feedback here; Codex responds in assets/reports/office_chair.md)
