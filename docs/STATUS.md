# Status

Milestone checklist from PLAN.md Section 11. Check an item only when it was actually run; each milestone ends with a verification note saying what ran, where, and with which command. Untested things are listed as untested.

**Current milestone: M0 (repo and specs)**

## M0: Repo and specs

- [x] Repo layout (PLAN.md 14), `CLAUDE.md`, `AGENTS.md`, `.gitignore`
- [x] `docs/DECISIONS.md` seeded (ADR-0001 to ADR-0007)
- [x] `docs/STATUS.md` (this file)
- [x] `docs/schema/room.schema.json` (JSON Schema 2020-12, ADR-0005)
- [x] `docs/ROOM_AUTHORING.md` first draft (its example is schema-checked by `go test`)
- [x] `docs/API.md` endpoint list
- [x] Godot 4.7.2 installed on the dev box (`~/.local/bin/godot`, ADR-0002)
- [x] Godot project skeleton: `project.godot`, boot scene with client/server arg parsing, SDK stub
- [x] Export presets: client-linux, client-win, server-linux, room-pack-night_shift (pack export verified; binary exports need export templates, not installed yet)
- [x] gdUnit4 v6.2.1 vendored; tests run headless
- [x] Go module, `platform/` skeleton (`/healthz`, `/api/version`) with `go test`
- [x] `tools/roomcheck`: schema, graph (cycle, unknown prerequisite, exit, orphans), node paths through instanced scenes, CTF Dockerfile, template references, literal-flag scan, forbidden-API warnings, `room.json` freshness
- [x] `tools/test.sh` runs every check; `.github/workflows/ci.yml` runs it (CI not yet run: no remote configured)
- [ ] `tools/assetcheck` (budgets, parts, animations, origin, meta, previews)
- [ ] `tools/blender/build_assets.sh` + `tools/blender/common/` (Codex)
- [ ] `docs/ASSET_PIPELINE.md` finalised after the smoke test
- [ ] First Codex handoff: `keypad_4` built by Codex (`gpt-6.1-sol`), passes assetcheck, visible in a Godot test scene with per-button meshes
- [ ] Acceptance: CI green; roomcheck rejects a cyclic graph; keypad_4 in a Godot test scene

## M1: Single-player room core
Not started.

## M2: Multiplayer
Not started.

## M3: Platform service and CTF orchestration
Not started. Known blocker: the dev user is not in the `docker` group (`permission denied` on `/var/run/docker.sock`); decide rootless Docker vs group membership before M3 (PLAN.md open question 1).

## M4: Night Shift content and polish
Not started.

## M5: LAN deployment and sign-off
Not started.

## Verification log

### 2026-10-01, M0 (dev box: Omarchy Linux, i5 Kaby Lake-R, UHD 620, 31 GB)
- The machine hard-crashed about three minutes into the first Codex asset task; `.git` objects were corrupted and the repo was re-initialised from the intact working tree (history before that point: two docs commits, recreated). Cause not captured in the journal; mitigation in ADR-0003.
- `go test ./internal/room/` : 14 tests pass (valid room, cycle, unknown prerequisite, missing exit, orphan warning, instanced node paths, too few hints, unknown key, multi-key condition, flag nonce, literal flag without echoing the value, stale room.json, undeclared template var, forbidden API, ROOM_AUTHORING example).
- `go test ./platform/...` : health/version endpoint test passes.
- `godot --headless --path game --import` : clean, no errors (Godot 4.7.2).
- gdUnit4 headless: `tests/core/test_app_args.gd` 5/5 pass.
- `godot --headless --path game -- --smoke` prints client mode; `-- --server --session s1 --room night_shift --smoke` prints server mode; `-- --server` exits 1 with "requires --session/--room".
- `godot --headless --export-pack room-pack-night_shift` with a README in the room: PCK contains the room file plus Godot's `project.binary` and `.godot` caches (ADR-0007).
