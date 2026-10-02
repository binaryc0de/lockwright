# escapebox: instructions for Codex and other agents

Virtual escape room platform with pluggable rooms and CTF challenges. Godot 4.7 client + dedicated server, Go platform service, YAML room manifests. **Read `PLAN.md` fully before doing anything**, then `docs/DECISIONS.md` and `docs/STATUS.md`.

## If you are Codex acting as the asset agent (the usual case)

Your contract is `docs/ASSET_PIPELINE.md`. In short:
- Work from one request file, `assets/requests/<asset_id>.md`. Build only what it asks for.
- Your lane: `tools/blender/`, `tools/printables/`, `assets/` (previews, meta, reports), and the GLB target (`game/assets/core/props/` or `game/rooms/<room>/assets/`). Do not edit runtime code (`game/core/`, `game/addons/`, `platform/`, `internal/`, `tools/*check/`), `room.yaml`, or docs outside your lane.
- The Blender script is the deliverable: deterministic, headless (`blender -b`), no network, seeded randomness.
- **Render previews with Workbench or Cycles on CPU only. Never Eevee, never GPU compute** (ADR-0003: this machine's iGPU has hung the system). One Blender process at a time, `--threads 4`.
- Only CC0 or CC-BY third-party assets, each recorded in `ATTRIBUTION.md`.
- Before finishing: `tools/blender/build_assets.sh <asset_id>` and `go run ./tools/assetcheck <asset_id>` must pass; write `assets/meta/<asset_id>.json` and `assets/reports/<asset_id>.md`. Do not commit; Claude Code reviews and commits.

## If you are reviewing (`codex:review`)

Hold the code to PLAN.md Section 13 and the non-negotiables below. Prioritise authority-model violations, flag leaks, container hardening gaps, and room-specific code in core.

## Non-negotiables

- Clients send intents; the server owns all world and puzzle state.
- No room-specific code in `game/core/`, `game/addons/escapebox_sdk/`, or `platform/`.
- Challenge containers are hardened and have no egress; flags are templates, never literals; never log flag values.
- Load room packs with `ProjectSettings.load_resource_pack(path, false)`.
- Tests and docs ship with the code; `docs/STATUS.md` records what was actually run.

## Commands

```bash
tools/test.sh                         # everything CI runs (Go tests, roomcheck, assetcheck, Godot import + gdUnit4)
go test ./...
go run ./tools/roomcheck
go run ./tools/assetcheck [asset_id]
tools/blender/build_assets.sh [asset_id]
godot --headless --path game --import
```
