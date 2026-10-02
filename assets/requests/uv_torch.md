# uv_torch

**Status:** open
**Requested by:** Claude Code, 2026-10-02
**Used in:** core library; room night_shift / SDK node `UVTorch` (an `Item`; puzzle A1 find, A2 reveal the cabinet code on the whiteboard)
**Class:** hero

## Purpose
A pocket UV (365 nm) torch of the kind used to check banknotes and audit-mark equipment. Players find it under papers in the desk drawer, pick it up, and turn it in their hands in the inspect view; selected in the inventory it reveals UV ink. It is small, so detail matters at inspect distance (0.25 m, filling most of a 1080p screen).

All positions below are in **Godot axes after import** (Y up). The torch lies along Z, lens toward **-Z**.

## Dimensions (metres)
- Body 0.105 long, 0.022 diameter (anodised aluminium tube, knurled tail), lens end slightly flared to 0.026, tail cap with a rubber push switch, a split-ring lanyard loop.
- `lens`: the lens disc at the -Z end (0.018 diameter) with a purple LED behind it, own emissive material.
- A small printed label band on the body: `UV 365nm` (and a tiny asset sticker `KL-IT-0118`).

## Style references
- Dark grey or black anodised aluminium, slight edge wear to bare metal on the knurling, a scuff on the body. Matte rubber tail switch.

## Budgets
- Triangles: <= 60000 (hero; 3-12k expected)
- Textures: base colour / normal / ORM at <= 1024 px
- Materials: <= 4 (`M_uv_torch_body`, `M_uv_torch_rubber`, `M_uv_torch_lens`, optional `M_uv_torch_label`)

## Named parts (exact mesh/object names the SDK will look up)
| Mesh name | Purpose | Separate transform? |
|---|---|---|
| `body` | tube, switch, loop, label | no |
| `lens` | lens + LED, material `M_uv_torch_lens` (emissive violet, white-ish base so Godot can drive intensity) | yes |

## Transforms
- Origin: base centre on the floor plane (the torch lying on a surface: underside at y = 0, centred in X and Z).
- Forward: lens toward -Z after Godot import.
- Scale: 1 unit = 1 m, all transforms applied.

## Collision
None in the GLB.

## Animations (glTF, named exactly)
None.

## Text and printables
`UV 365nm`, `KL-IT-0118`; original stroke lettering; no font downloads.

## Acceptance
- [ ] `tools/blender/build_assets.sh uv_torch` rebuilds the GLB headless
- [ ] `go run ./tools/assetcheck uv_torch` passes
- [ ] previews: front, iso, detail (detail = lens and label)
- [ ] in-engine screenshot by Claude in Revision notes

## Revision notes
(Claude appends dated feedback here; Codex responds in assets/reports/uv_torch.md)
