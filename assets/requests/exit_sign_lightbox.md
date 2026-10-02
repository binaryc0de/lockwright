# exit_sign_lightbox

**Status:** open
**Requested by:** Claude Code, 2026-10-02
**Used in:** core library; room night_shift (corridor and over the exit door)
**Class:** prop

## Purpose
An illuminated emergency exit sign (green running man, arrow, door pictogram; no text) on a wall: the corridor's main light source during the airlock and a strong "this is the way out" cue over the office door.

All positions below are in **Godot axes after import** (Y up, face toward -Z).

## Dimensions (metres)
- Wall-mount lightbox 0.36 W x 0.15 H x 0.05 D, back face at z = 0, origin at its centre.
- `face`: the translucent diffuser with the printed pictogram (ISO 7010 E001 style: running figure, arrow to the left, door), own emissive material using the pictogram as emission texture.

## Style references
- White ABS housing, slightly yellowed; green pictogram glowing evenly; a test button and charge LED on the underside.

## Budgets
- Triangles: <= 20000
- Textures: base colour / normal / ORM at <= 1024 px; face texture <= 1024 px
- Materials: <= 3 (`M_exit_sign_lightbox_housing`, `M_exit_sign_lightbox_face`, optional `M_exit_sign_lightbox_led`)

## Named parts (exact mesh/object names the SDK will look up)
| Mesh name | Purpose | Separate transform? |
|---|---|---|
| `housing` | box, test button, LED | no |
| `face` | glowing diffuser, material `M_exit_sign_lightbox_face` (emissive with the pictogram) | no |

## Transforms
- Wall-mount prop: origin at the centre of the back mounting face (z = 0).
- Forward: face toward -Z after Godot import.
- Scale: 1 unit = 1 m, all transforms applied.

## Collision
None in the GLB.

## Animations (glTF, named exactly)
None.

## Text and printables
No text; the pictogram is drawn as geometry or vector paths by the script.

## Acceptance
- [ ] `tools/blender/build_assets.sh exit_sign_lightbox` rebuilds the GLB headless
- [ ] `go run ./tools/assetcheck exit_sign_lightbox` passes
- [ ] previews: front, iso, detail
- [ ] in-engine screenshot by Claude in Revision notes

## Revision notes
(Claude appends dated feedback here; Codex responds in assets/reports/exit_sign_lightbox.md)
