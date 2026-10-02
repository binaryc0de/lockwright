# office_trim_kit

**Status:** open
**Requested by:** Claude Code, 2026-10-02
**Used in:** core library (shell dressing for any office room); room night_shift
**Class:** prop

## Purpose
Small architectural details that make a box room read as a real office: skirting, sockets, a light switch, a ceiling return-air vent, a smoke detector, and a twin-spot emergency light (the diegetic source of light in a room on emergency power). All décor, never interactable. Delivered as one GLB whose parts Claude instances individually, so **every part sits at the origin** (they overlap; that is intended).

All positions below are in **Godot axes after import** (Y up). Every part's mounting face lies on the plane z = 0 and the part faces **-Z** (Claude rotates the ceiling parts to face down).

## Dimensions (metres)
- `skirting_1m`: painted MDF skirting board, 1.00 long along X (x -0.5 to +0.5), 0.10 tall (y 0 to 0.10), 0.015 deep, ogee/pencil-round top edge. Claude scales it along X for long runs, so keep its texture nearly uniform along X (no features that would visibly stretch).
- `outlet_double`: UK/EU-neutral double power socket faceplate 0.146 x 0.086 x 0.01, centred on the origin, switches and two socket faces.
- `light_switch`: single rocker switch plate 0.086 x 0.086 x 0.01, centred.
- `vent_600`: return-air ceiling grille 0.595 x 0.595 x 0.02, centred, louvres with dark void behind.
- `smoke_detector`: round ceiling smoke detector, 0.11 diameter x 0.045, centred, tiny `smoke_led` dot.
- `emergency_light`: twin-spot ("bug-eye") emergency light, battery box 0.30 W x 0.12 H x 0.08 D centred on the origin, two adjustable lamp heads on top angled 30 degrees down and outward, red/green charge LED.
- `smoke_led`: LED dot of the smoke detector, own material (emissive, white base).

## Style references
- Off-white plastic for sockets/switch/detector (slightly yellowed), white powder-coat vent, satin white skirting with a few scuffs, emergency light in off-white ABS with chrome lamp reflectors (2000s commercial).

## Budgets
- Triangles: <= 20000
- Textures: base colour / normal / ORM at <= 1024 px
- Materials: <= 5 (`M_office_trim_kit_plastic`, `M_office_trim_kit_paint`, `M_office_trim_kit_metal`, `M_office_trim_kit_lamp`, `M_office_trim_kit_led`)

## Named parts (exact mesh/object names the SDK will look up)
| Mesh name | Purpose | Separate transform? |
|---|---|---|
| `skirting_1m` | skirting board | yes |
| `outlet_double` | double socket | yes |
| `light_switch` | light switch | yes |
| `vent_600` | ceiling vent | yes |
| `smoke_detector` | smoke detector | yes |
| `smoke_led` | smoke detector LED | yes |
| `emergency_light` | twin-spot emergency light; lamp lenses use `M_office_trim_kit_lamp` (emissive-ready) | yes |

## Transforms
- Wall-mount kit: every part's origin is the centre of its own back mounting face, placed at (0, 0, 0), except `skirting_1m` whose origin is at the bottom of its back face (y = 0) and `smoke_led`, which sits on the detector.
- Forward: every part faces -Z after Godot import.
- Scale: 1 unit = 1 m, all transforms applied.

## Collision
None in the GLB.

## Animations (glTF, named exactly)
None.

## Text and printables
None.

## Extra metadata
`"anchors_godot_m": {"emergency_lamp_left": [x,y,z], "emergency_lamp_right": [x,y,z], "emergency_lamp_dir_left": [x,y,z], "emergency_lamp_dir_right": [x,y,z]}` (lens centres and beam directions, so Claude can put spotlights in them).

## Acceptance
- [ ] `tools/blender/build_assets.sh office_trim_kit` rebuilds the GLB headless
- [ ] `go run ./tools/assetcheck office_trim_kit` passes (the overlapping layout may make the bounds-centre check warn; report it)
- [ ] previews: front, iso, detail (lay the parts out side by side for the previews only)
- [ ] in-engine screenshot by Claude in Revision notes

## Revision notes
(Claude appends dated feedback here; Codex responds in assets/reports/office_trim_kit.md)
