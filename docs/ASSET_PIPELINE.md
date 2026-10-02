# Asset Pipeline and the Codex Asset Agent

This is the contract between **Claude Code** (orchestrator, Godot/Go implementer) and **Codex** (asset design agent running `gpt-6.1-sol`) for every custom 3D prop, material, and printed document in escapebox. Both agents read this before any asset work. `PLAN.md` Section 8.6 is the summary; this file is the detail.

## 1. Tools and versions

| Tool | Version | Where |
|---|---|---|
| Blender | 5.2 LTS (5.2.2 installed) | `~/.local/bin/blender`; `tools/blender/build_assets.sh` pins and checks the version |
| Codex CLI | 0.159.x, logged in via ChatGPT | model `gpt-6.1-sol`, `model_reasoning_effort = "high"` in `~/.codex/config.toml` |
| Codex plugin for Claude Code | `codex` 1.0.6 | skills `codex:rescue`, `codex:review`, `codex:setup`; agent `codex:codex-rescue` |
| Godot | 4.7.x | import target; glTF 2.0 importer |

## 2. Lanes

| Claude Code owns | Codex owns |
|---|---|
| Deciding which assets exist and why | `tools/blender/**` (build scripts, helpers) |
| `assets/requests/*.md` (writing and closing) | `tools/printables/**` (SVG templates, render scripts) |
| Godot import settings, SDK wiring, in-engine materials/lighting | `game/assets/core/props/*.glb`, `game/rooms/<room>/assets/*.glb` produced by scripts |
| `tools/assetcheck` (Go) | `assets/previews/`, `assets/meta/`, `assets/reports/` |
| Accept/reject in-engine | Revisions in response to "Revision notes" |

Shared: `game/assets/core/third_party/` (CC0 downloads) and its `ATTRIBUTION.md`. Codex may post-process third-party assets through scripts; Claude records their use in rooms.

## 3. Handoff commands

From Claude Code, through the plugin (background so Claude keeps working):

```bash
node "$HOME/.claude/plugins/cache/openai-codex/codex/1.0.6/scripts/codex-companion.mjs" task \
  --write --background --model gpt-6.1-sol \
  "Build the asset described in assets/requests/<asset_id>.md. Follow docs/ASSET_PIPELINE.md exactly. \
   Deliver the build script, GLB, previews, meta.json and report. Run tools/blender/build_assets.sh <asset_id> \
   and tools/assetcheck before finishing. Do not edit files outside your lane."
```

Or via the `codex:rescue` skill with the same prompt text and flags. To iterate after feedback is appended to the request file, resume the same task:

```bash
node ".../codex-companion.mjs" task --write --background --resume-last \
  "Apply the Revision notes now in assets/requests/<asset_id>.md and rebuild."
```

Check progress / fetch output:

```bash
node ".../codex-companion.mjs" status --all
node ".../codex-companion.mjs" result <job-id>
```

The owner can also run `codex` interactively in the repo root for exploratory art sessions; anything kept must end up in a headless script.

## 4. Asset request template (`assets/requests/<asset_id>.md`)

```markdown
# <asset_id>

**Status:** open | in_review | accepted | rejected
**Requested by:** Claude Code, <date>
**Used in:** room <room_id> / SDK node <NodeType> / core library
**Class:** prop | hero | shell | printable

## Purpose
One paragraph: what it is in the fiction, what the player does with it, what must read clearly at inspect distance.

## Dimensions (metres)
W x D x H, plus any critical internal dimensions (button pitch, drawer depth).

## Style references
Bullet list of real-world references (describe; link only CC0/CC-BY images). Era, wear level, colour, materials.

## Budgets
- Triangles: <= 20000 (prop) | <= 60000 (hero)
- Textures: base colour / normal / ORM at <= 2048 px; list any extra maps (emissive)
- Materials: <= 3

## Named parts (exact mesh names the SDK will look up)
| Mesh name | Purpose | Separate transform? |
|---|---|---|
| `body` | static shell | no |
| `btn_0` .. `btn_9`, `btn_enter`, `btn_clear` | pressable keys | yes, individually |
| `screen` | emissive LED area; separate material `M_<asset_id>_screen` | no |

## Transforms
- Origin: base centre on the floor plane (or wall-mount plane for wall props)
- Forward: faces -Z after Godot import
- Scale: 1 unit = 1 m, all transforms applied

## Collision
`body-col` convex hull | box | trimesh; keys excluded

## Animations (glTF, named exactly)
| Name | Frames | Description |
|---|---|---|
| `open` | 0-24 | drawer slides out 0.35 m |
| `close` | 0-24 | reverse |

## Text and printables
Exact strings that must be legible, font feel (dot-matrix, laser-printed, handwritten), languages.

## Acceptance
- [ ] assetcheck passes
- [ ] previews show front, iso, detail
- [ ] in-engine screenshot by Claude attached in Revision notes

## Revision notes
(Claude appends dated feedback here; Codex responds in assets/reports/<asset_id>.md)
```

## 5. Deliverables Codex must produce

| Path | Content |
|---|---|
| `tools/blender/props/<asset_id>.py` | Deterministic build script. Entry point `build(out_dir)`; runnable via `blender -b --python tools/blender/props/<asset_id>.py -- --out <dir>`. Uses only `bpy`, `bmesh`, `mathutils`, stdlib, and `tools/blender/common/`. No network. Seeds any randomness. |
| `game/assets/core/props/<asset_id>.glb` (or room assets dir) | glTF binary, textures embedded or alongside as PNG/KTX2 per request |
| `assets/previews/<asset_id>_front.png`, `_iso.png`, `_detail.png` | 1024 px renders on neutral grey, three-point lighting from `common/preview.py`. **Render with Workbench or Cycles on CPU only** (`cycles.device = "CPU"`, low samples + denoise); never Eevee or GPU compute. The dev box has an Intel UHD 620 iGPU with a history of GPU hangs (ADR-0003). |
| `assets/meta/<asset_id>.json` | `{ "asset_id", "triangles", "materials": [...], "textures": [{name,size}], "bounds_m": [w,d,h], "origin": "base_center", "parts": [...], "animations": [...], "script_sha256", "blender_version", "built_at" }` |
| `assets/reports/<asset_id>.md` | What was built, deviations from the request and why, known issues, suggested in-engine material tweaks |
| `ATTRIBUTION.md` entry | Only if any third-party asset or texture was used |

## 6. Blender and Godot conventions (binding)

- **Units**: metric, 1 BU = 1 m. Apply scale/rotation before export.
- **Axes**: model with +Y forward in Blender; export with the glTF exporter's default `+Y up` conversion. Verify in Godot that the prop faces `-Z`. If a prop ends up backwards in-engine, fix the script, not the import.
- **Origin**: base centre on the floor plane for floor props; mount plane centre for wall props; hinge axis for doors/lids.
- **Naming**: objects and meshes `snake_case`; `-col` suffix generates collision on Godot import; `-noimp` for helpers; `-convcol`/`-colonly` where appropriate. Materials `M_<asset_id>_<part>`. Images `T_<asset_id>_<map>`.
- **Topology**: quads/tris only, no n-gons at export, no loose verts, normals outward, hard edges via auto-smooth/weighted normals, UVs non-overlapping for baked parts, texel density ~512 px/m for props and ~1024 px/m for printables and screens.
- **Materials**: Principled BSDF only; metallic/roughness workflow; emissive for screens/LEDs with strength set so Godot's glow picks it up; ORM packing (occlusion R, roughness G, metallic B) when more than one map is needed.
- **Baking**: bake high-to-low only when the request asks for it; otherwise procedural-to-texture bake at the requested size with 8 px margin.
- **Animations**: NLA tracks named exactly as the request; 24 fps; no scale animation; drawers/doors animate the named part only.
- **Export**: `bpy.ops.export_scene.gltf(export_format='GLB', export_apply=True, export_yup=True, export_animations=True, export_image_format='AUTO')`, selected objects only, no cameras/lights.
- **Determinism**: same script + same Blender version = byte-identical GLB except timestamps. Use fixed seeds; avoid `bpy.ops` that depend on UI context (use low-level API or `bpy.context.temp_override`).
- **No `.blend` as source**: `.blend` may be saved to `assets/cache/` for inspection; it is gitignored.

## 7. Printables (`tools/printables/`)

- One SVG template per document in `tools/printables/templates/<doc_id>.svg` with text in `<tspan id="...">` placeholders; a render script fills text from the request and rasterises at `>= 2048 px` long edge into `game/.../assets/docs/<doc_id>.png`.
- Add a wear layer (coffee ring, creases, print banding) from `tools/printables/overlays/` for realism.
- If the document has UV-ink content, produce `<doc_id>_uv.png` with the hidden text; the SDK `Document.uv_text`/`uv_texture` uses it.
- Legibility test: the render script also writes a 25% downscaled preview; the critical text must still be readable there (that approximates inspect distance at 1080p).

## 8. assetcheck (Claude's lane, runs in CI)

Fails the build if: triangles or texture sizes exceed the request; a required named part is missing; an animation name is missing or empty; origin is not at the base centre (bounds min y != 0 within 1 mm); the GLB fails to load with a glTF validator; `meta.json` is missing or stale (script hash mismatch); a `.py` script in `tools/blender/props/` has no matching request file; a request is `accepted` but its GLB is absent.

## 9. Feedback loop

1. Codex finishes; the report lists deviations.
2. Claude imports into Godot, wires the SDK node, screenshots in the greybox room.
3. Accept: set request `Status: accepted`, close. Reject: append dated **Revision notes** with the screenshot path and precise, measurable asks ("buttons 2 mm too tall", "screen emissive too dim at 0.3 lux"), then resume the Codex task.
4. Two rejections in a row on the same point means the request was unclear: Claude rewrites the request section instead of adding a third note.

## 10. Prototype asset list (Night Shift)

Hero: `maglock_door_panel`, `exit_keypad_6`, `cage_door_maglock`, `server_rack_42u`, `patch_panel_24` (+ `patch_cable_short` x4 as items), `ups_tower`, `uv_torch`, `filing_cabinet_keypad`, `laptop_open`, `intercom_panel`, `wall_clock_countdown`, `desk_3drawer`.
Printables: `sticky_note_username`, `wifi_card_front_back`, `fire_inspection_certificate`, `network_diagram_laminated`, `whiteboard_uv_layer`, `rack_stencil`.
Smoke test (M0): `keypad_4`.
Third-party (CC0): office shell, chairs, shelving, monitors, cable trays, floor/wall/ceiling materials, décor.
