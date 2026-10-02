# usb_stick

**Status:** done
**Requested by:** Claude Code, 2026-10-02
**Used in:** room night_shift / SDK node `Item` "usb_stick" (in the filing cabinet; decorative in the prototype, the hard-mode variant uses it later)
**Class:** prop

## Purpose
"A scuffed orange USB stick labelled 'MR - backups' in marker." Picked up and inspected; must read at 0.2 m.

All positions below are in **Godot axes after import** (Y up), lying flat, connector toward -Z.

## Dimensions (metres)
- 0.058 L x 0.019 W x 0.009 H plastic body with a swivel metal cover over a USB-A connector (connector end at -Z), a keyring hole at +Z.
- Handwritten black marker on a strip of white label tape on top: `MR - backups`.

## Style references
- Bright orange plastic gone dull with scratches, chipped edge, metal swivel cover slightly bent.

## Budgets
- Triangles: <= 20000
- Textures: base colour / normal / ORM at <= 1024 px
- Materials: <= 3 (`M_usb_stick_plastic`, `M_usb_stick_metal`, `M_usb_stick_label`)

## Named parts (exact mesh/object names the SDK will look up)
| Mesh name | Purpose | Separate transform? |
|---|---|---|
| `body` | whole stick | no |

## Transforms
- Origin: base centre on the floor plane (lying flat: underside at y = 0).
- Forward: connector toward -Z after Godot import.
- Scale: 1 unit = 1 m, all transforms applied.

## Collision
None in the GLB.

## Animations (glTF, named exactly)
None.

## Text and printables
`MR - backups` in marker-style stroke handwriting; no font downloads.

## Acceptance
- [ ] `tools/blender/build_assets.sh usb_stick` rebuilds the GLB headless
- [ ] `go run ./tools/assetcheck usb_stick` passes
- [ ] previews: front, iso, detail
- [ ] in-engine screenshot by Claude in Revision notes

## Revision notes
(Claude appends dated feedback here; Codex responds in assets/reports/usb_stick.md)
