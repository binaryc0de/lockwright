# desk_lamp_arm_01

**Status:** open
**Requested by:** Claude Code, 2026-10-02
**Used in:** room night_shift, `Office/Desk` desk lamp (currently the Poly Haven glTF instanced directly)
**Class:** set dressing (budget fix of a CC0 source)

## Purpose
`game/assets/core/third_party/polyhaven/desk_lamp_arm_01/desk_lamp_arm_01_1k.gltf` (Poly Haven, CC0) is about 25.7k triangles, over the 20k prop budget (PLAN.md 13.8). Produce a game-ready version that looks the same at desk distance.

## Deliverable
- `tools/blender/props/desk_lamp_arm_01.py`: imports the CC0 source glTF (do not modify or move the source files), reduces it, and exports `game/assets/core/props/desk_lamp_arm_01.glb`.
- Keep the source's two materials and textures (`desk_lamp_arm_01`, `desk_lamp_arm_01_light`, emission included) and its UVs; reuse the source textures (re-export is fine, <= 1024 px as now).
- Reduce with care: keep the silhouette, the arm joints, springs and the shade rim; flatten hidden/underside detail first. Target <= 12000 triangles, hard limit 20000.
- Same transform as the source (origin, scale, orientation) so it is a drop-in replacement: the room instance's transform must not need to change.
- Mesh names: `lamp` (everything but the bulb/light surface) and `lamp_light` (the emissive part).

## Acceptance
- [ ] `tools/blender/build_assets.sh desk_lamp_arm_01` rebuilds headless
- [ ] `go run ./tools/assetcheck desk_lamp_arm_01` passes
- [ ] previews front, iso, detail, and a side-by-side against the source at the same camera in the report
- [ ] attribution: report and meta credit Poly Haven `desk_lamp_arm_01` (CC0)

## Revision notes
(Claude appends dated feedback here; Codex responds in assets/reports/desk_lamp_arm_01.md)
