# cage_partition_kit

**Status:** open
**Requested by:** Claude Code, 2026-10-02
**Used in:** core library; room night_shift (the security-cage wall between the office and the server alcove)
**Class:** prop

## Purpose
Welded-mesh security cage partition, seen from the office for the whole game and from inside the cage. Players must see the rack and its blinking lights **through** it before they get in, so the mesh must be clearly see-through (alpha-cutout wire, not a solid sheet). Delivered as a kit of panels that Claude places side by side, so **every part sits at the origin** (they overlap; intended).

All positions below are in **Godot axes after import** (Y up). Panels lie in the X-Y plane centred on z = 0 (about 0.05 thick); the office side looks toward -Z, but the mesh reads the same from both sides.

## Dimensions (metres)
- `panel_1200`: 1.20 W x 2.80 H, x -0.60 to +0.60, y 0 to 2.80. Square-tube frame (40 x 40 mm) on all four sides, welded wire mesh 50 x 50 mm, 4 mm wire, inside. When two panels butt together their frames must read as one post.
- `panel_400`: same construction, 0.40 W x 2.80 H.
- `header_1000`: over a door opening, 1.00 W x 0.70 H (y 0 to 0.70; Claude lifts it to y 2.10), same mesh and frame.
- Small floor anchor plates at the bottom of each vertical frame member; a few cable ties on the mesh are welcome.

## Style references
- Industrial data-centre cage (black or dark-grey powder-coat, Troax/Axelent feel, no logos), light scuffing on the frames at hand height.

## Budgets
- Triangles: <= 20000
- Textures: base colour / normal / ORM at <= 2048 px; the mesh uses an alpha-cutout texture (opacity in base-colour alpha)
- Materials: <= 3 (`M_cage_partition_kit_frame`, `M_cage_partition_kit_mesh` with alpha clip and double-sided, optional `M_cage_partition_kit_metal`)

## Named parts (exact mesh/object names the SDK will look up)
| Mesh name | Purpose | Separate transform? |
|---|---|---|
| `panel_1200` | 1.2 m panel | yes |
| `panel_400` | 0.4 m panel | yes |
| `header_1000` | over-door header | yes |

## Transforms
- Origin: base centre on the floor plane for every part: each panel's bottom centre at (0, 0, 0), geometry centred on z = 0.
- Forward: office side toward -Z after Godot import.
- Scale: 1 unit = 1 m, all transforms applied.

## Collision
None in the GLB. The room keeps its own box colliders.

## Animations (glTF, named exactly)
None.

## Text and printables
None.

## Acceptance
- [ ] `tools/blender/build_assets.sh cage_partition_kit` rebuilds the GLB headless
- [ ] `go run ./tools/assetcheck cage_partition_kit` passes
- [ ] previews: front, iso, detail (lay the parts side by side for previews only)
- [ ] in-engine screenshot by Claude in Revision notes

## Revision notes
(Claude appends dated feedback here; Codex responds in assets/reports/cage_partition_kit.md)
