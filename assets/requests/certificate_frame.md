# certificate_frame

**Status:** open
**Requested by:** Claude Code, 2026-10-02
**Used in:** core library; room night_shift (frames the fire inspection certificate, puzzle D1)
**Class:** prop

## Purpose
A cheap wall-hung document frame with glass. Claude puts the printed certificate texture on the `picture` part; players read it (the site number is a clue), so the glass must stay readable: a faint reflection, not a mirror.

All positions below are in **Godot axes after import** (Y up, front toward -Z).

## Dimensions (metres)
- Frame outer 0.34 W x 0.44 H x 0.018 D, back face at z = 0, origin at the centre.
- `picture`: flat quad 0.30 W x 0.40 H, UV 0..1 upright (u to the right, v up), 0.004 behind the glass.
- `glass`: flat quad over the opening, its own material.
- Thin moulding profile (0.02 face), mitred corners.

## Style references
- Black or dark-walnut plastic moulding, A3-ish office certificate frame, slightly dusty top edge, a corner of the frame a little scuffed.

## Budgets
- Triangles: <= 20000
- Textures: base colour / normal / ORM at <= 1024 px
- Materials: <= 3 (`M_certificate_frame_moulding`, `M_certificate_frame_picture`, `M_certificate_frame_glass`)

## Named parts (exact mesh/object names the SDK will look up)
| Mesh name | Purpose | Separate transform? |
|---|---|---|
| `moulding` | frame and backing | no |
| `picture` | document quad, UV 0..1 | no |
| `glass` | glass quad | no |

## Transforms
- Wall-mount prop: origin at the centre of the back mounting face (z = 0).
- Forward: front toward -Z after Godot import.
- Scale: 1 unit = 1 m, all transforms applied.

## Collision
None in the GLB.

## Animations (glTF, named exactly)
None.

## Text and printables
None (the certificate is a printable).

## Extra metadata
`"anchors_godot_m": {"picture_centre": [x,y,z]}`.

## Acceptance
- [ ] `tools/blender/build_assets.sh certificate_frame` rebuilds the GLB headless
- [ ] `go run ./tools/assetcheck certificate_frame` passes
- [ ] previews: front, iso, detail
- [ ] in-engine screenshot by Claude in Revision notes

## Revision notes
(Claude appends dated feedback here; Codex responds in assets/reports/certificate_frame.md)
