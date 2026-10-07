# Asset import acceptance (owner instruction, 2026-10-06)

Read the root AGENTS.md and docs/ASSET_PIPELINE.md first. Their lane, serial
Blender, CPU-only and four-thread rules continue to apply.

For every asset delivery, `build_assets.sh <id>` and
`go run ./tools/assetcheck <id>` are necessary but insufficient. Refresh the
selected GLB's extracted texture copies before Godot import. Run:

```bash
tools/shots/prop_views.sh rooms/<room>/assets/props/<id>.glb assets/previews/godot/<id>
```

This uses the actual display/GPU and Godot's web Compatibility renderer. Run
it while Blender is idle. **View sheet.png and fix visible import/material
problems before marking the asset done.** Record the command, rendered sheet
and review result in assets/reports/<id>.md. Blender previews alone are not
acceptance. `accept_quiet_sun.py <id>` wraps this refresh/audit/render sequence
for Quiet Sun; the sheet still requires visual inspection.

Every material texture must use the same primary UVMap (glTF TEXCOORD_0,
Godot UV1), including base colour, normal, ORM and emission. Bake/project photo
colour to that UV set. A secondary UV set is allowed only for lightmaps and
must not be referenced by a material texture. Do not use UVPhoto for colour.
Check foliage is green in Godot, not merely in Blender.

The Quiet Sun canyon review also found imported StandardMaterial3D surfaces
with `vertex_color_use_as_albedo=false`. Put required tonal hierarchy in baked
texture pixels or standard material albedo factors; do not assume COLOR_0 will
affect Godot's imported material. Verify the actual imported result.
