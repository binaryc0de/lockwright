# drawer_cabinet

**Status:** in_review | accepted | rejected
**Requested by:** Claude Code, 2026-10-01
**Used in:** room night_shift / SDK node `Drawer`
**Class:** hero

## Purpose
Template-shaped request used by the assetcheck parser tests.

## Budgets
- Triangles: <= 20,000 (prop) | <= 60000 (hero)
- Textures: base colour / normal / ORM at <= 2048 px; emissive at <= 512 px
- Materials: <= 3

## Named parts (exact mesh names the SDK will look up)
| Mesh name | Purpose | Separate transform? |
|---|---|---|
| `body` | static shell | no |
| `btn_0` .. `btn_9`, `btn_enter`, `btn_clear` | pressable keys | yes, individually |
| `drawer_01` .. `drawer_03` | drawers | yes |
| `screen` | emissive LED area; separate material `M_drawer_cabinet_screen` | no |

## Transforms
- Origin: base centre on the floor plane (or wall-mount plane for wall props)
- Forward: faces -Z after Godot import
- Scale: 1 unit = 1 m, all transforms applied

## Animations (glTF, named exactly)
| Name | Frames | Description |
|---|---|---|
| `open` | 0-24 | drawer slides out 0.35 m |
| `close` | 0-24 | reverse |
