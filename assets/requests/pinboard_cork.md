# pinboard_cork

**Status:** open
**Requested by:** Claude Code, 2026-10-02
**Used in:** core library; room night_shift (holds the Guest WiFi card, puzzle B2)
**Class:** prop

## Purpose
The office's "IT NOTICES" cork pinboard. The Guest WiFi card (a separate interactable Document) is pinned on it; the board itself is décor and must **not** carry other papers that look readable (design rule: no red herrings, no pixel hunts). Sparse and believable: a few unused push pins, old pin holes and faded rectangles where notices used to hang, a printed header card.

All positions below are in **Godot axes after import** (Y up, front toward -Z).

## Dimensions (metres)
- Board outer: 1.20 W x 0.80 H x 0.02 D, back face at z = 0, origin at its centre.
- Frame: natural oak or anodised aluminium profile, 0.02 wide.
- `header_card`: printed card 0.30 x 0.07 pinned top-centre (centre at y +0.33), text `IT NOTICES` (bold sans, black on white, cap height 0.03).
- Leave a clear area for the WiFi card: x +0.10 to +0.40, y -0.10 to +0.10 from the board centre (pins only around it, no faded rectangles there).

## Style references
- Standard office cork board, medium-brown cork with visible grain and darker sun-faded margins, scattered pin holes, 5-8 coloured push pins (some holding nothing).

## Budgets
- Triangles: <= 20000
- Textures: base colour / normal / ORM at <= 2048 px
- Materials: <= 4 (`M_pinboard_cork_cork`, `M_pinboard_cork_frame`, `M_pinboard_cork_pins`, `M_pinboard_cork_card`)

## Named parts (exact mesh/object names the SDK will look up)
| Mesh name | Purpose | Separate transform? |
|---|---|---|
| `board` | cork and frame | no |
| `header_card` | printed header card with its pin | no |
| `pins` | loose push pins | no |

## Transforms
- Wall-mount prop: origin at the centre of the back mounting face (z = 0).
- Forward: cork face toward -Z after Godot import.
- Scale: 1 unit = 1 m, all transforms applied.

## Collision
None in the GLB.

## Animations (glTF, named exactly)
None.

## Text and printables
`IT NOTICES` only. Original stroke/geometry lettering; no font downloads.

## Extra metadata
`"anchors_godot_m": {"cork_front_z": z}`.

## Acceptance
- [ ] `tools/blender/build_assets.sh pinboard_cork` rebuilds the GLB headless
- [ ] `go run ./tools/assetcheck pinboard_cork` passes
- [ ] previews: front, iso, detail
- [ ] in-engine screenshot by Claude in Revision notes

## Revision notes
(Claude appends dated feedback here; Codex responds in assets/reports/pinboard_cork.md)
