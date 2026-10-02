# laptop_open

**Status:** open
**Requested by:** Claude Code, 2026-10-02
**Used in:** room night_shift / SDK node `Terminal` (puzzle B3: the intranet login; it shows the CTF connection card)
**Class:** hero

## Purpose
Mark Reyes's work laptop, open on the desk with the lid up, its screen glowing in the dark office. Players interact with it to open the terminal panel. The screen content is drawn in-engine (a Label3D or texture sits on the `screen` part), so the screen must be a clean, separately-materialled rectangle with UVs spanning 0..1 across the visible display area.

All positions below are in **Godot axes after import** (Y up, the keyboard/screen face -Z toward the user, who sits on the -Z side).

## Dimensions (metres)
- Base: 0.33 W x 0.23 D x 0.018 H, rounded corners, keyboard and touchpad on top.
- Lid: 0.33 W x 0.22 H x 0.006, hinged along the back edge of the base, open to 105 degrees from the base (leans 15 degrees back from vertical, toward +Z).
- Display (`screen`): 0.300 W x 0.188 H (16:10, about 14 inch), centred in the lid with thin bezels, 0.5 mm in front of the bezel plane.

## Style references
- Generic 2020s business laptop (ThinkPad / Latitude feel without logos): matte charcoal plastic and soft-touch paint, black chiclet keys with white legends (QWERTY; legends can be texture only), a red or grey pointing stick optional, a plain touchpad, small status LEDs.
- An IT asset tag sticker on the lid back reading `KL-LT-0332` and a small barcode (texture).
- Wear: light shine on the palm rests and the most-used keys, a few dust specks on the keyboard. 

## Budgets
- Triangles: <= 60000 (hero; 8-20k expected)
- Textures: base colour / normal / ORM at <= 2048 px; the keyboard legend atlas may be its own texture at <= 2048 px
- Materials: <= 4 (`M_laptop_open_shell`, `M_laptop_open_keys`, `M_laptop_open_screen`, optional `M_laptop_open_sticker`)

## Named parts (exact mesh/object names the SDK will look up)
| Mesh name | Purpose | Separate transform? |
|---|---|---|
| `base` | lower half: shell, keyboard, touchpad | no |
| `lid` | lid shell and bezel | yes; origin on the hinge axis |
| `screen` | display quad, UV 0..1 over the visible area, material `M_laptop_open_screen` (black, emissive-ready, low roughness) | yes; origin at the display centre, its local -Z is the display normal |

## Transforms
- Origin: base centre on the floor plane (y = 0 is the underside of the base) at the centre of the **overall** bounding-box footprint, lid included, so assetcheck's base-centre test passes.
- Forward: keyboard and display face -Z after Godot import.
- Scale: 1 unit = 1 m, all transforms applied except the part locations/rotations noted above.

## Collision
None in the GLB. The room keeps its own box collider.

## Animations (glTF, named exactly)
None.

## Text and printables
Asset tag `KL-LT-0332` legible at 0.4 m. Key legends readable at 0.5 m (texture is fine).

## Extra metadata
In `assets/meta/laptop_open.json` add `"anchors_godot_m": {"screen_centre": [x,y,z], "screen_normal": [x,y,z], "screen_size": [w,h]}`.

## Acceptance
- [ ] `tools/blender/build_assets.sh laptop_open` rebuilds the GLB headless
- [ ] `go run ./tools/assetcheck laptop_open` passes
- [ ] previews: front, iso, detail (detail = keyboard and asset tag)
- [ ] in-engine screenshot by Claude in Revision notes

## Revision notes
(Claude appends dated feedback here; Codex responds in assets/reports/laptop_open.md)
