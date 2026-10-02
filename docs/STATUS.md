# Status

Milestone checklist from PLAN.md Section 11. Check an item only when it was actually run; each milestone ends with a verification note saying what ran, where, and with which command. Untested things are listed as untested.

**Current milestone: M1 (single-player room core).** M0 closed 2026-10-01.

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
- [x] `tools/assetcheck` + `internal/gltf` stdlib GLB reader (budgets, parts, animations, origin, meta freshness, previews, orphan scripts)
- [x] `tools/blender/build_assets.sh` + `tools/blender/common/` (Codex; Blender 5.2.x gate, flock-serialised, CPU-only previews)
- [x] `docs/ASSET_PIPELINE.md` finalised after the smoke test (press direction, `-colonly`, texture refresh, process hygiene)
- [x] First Codex handoff: `keypad_4` built by Codex (`gpt-6.1-sol`, high), passes assetcheck, imports in Godot with per-button meshes (headless test). Windowed screenshot deferred (ADR-0003); showcase scene ready at `game/tests/scenes/keypad_showcase.tscn`
- [x] Acceptance (local): `tools/test.sh` green; roomcheck rejects a cyclic graph (`TestRejectsCycle`); keypad_4 loads in a Godot test scene with per-button meshes. GitHub CI not yet run (no remote).
- [x] Independent `codex:review` of M0 triaged: 1 finding (P2, inherited prefab children skipped under an instance prefix in `internal/room/tscn.go`), fixed with regression test `TestResolvesInheritedPrefabUnderInstance`

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
- `go test ./internal/gltf/ ./tools/assetcheck/`: 8 + 9 tests (17 failure subtests) pass; written by a Claude subagent, spot-reviewed.
- Codex task (gpt-6.1-sol, high) built keypad_4 in ~22 min with no machine instability (CPU-only previews, 4 threads, load average < 2).
- `tools/blender/build_assets.sh keypad_4` rerun by Claude: 79 s, GLB SHA-256 `cf2aa3f98878c7557333974547f08d19234f1b8b09116bc0a70fb7b4a26b7cc5`, byte-identical to Codex's build.
- `go run ./tools/assetcheck`: PASS keypad_4 (5674 tris, 16 parts), 0 warnings.
- Godot import after deleting stale extracted textures, then again with `.godot/` removed (fresh-clone case): no errors; extracted textures are 1024 px.
- `tools/test.sh` (gofmt, vet, go test, roomcheck, assetcheck, Godot import, gdUnit4): exit 0, gdUnit4 9/9 (5 AppArgs + 4 keypad_4).
- Untested: Windows/Linux binary exports (no export templates installed), GitHub Actions run, any windowed rendering.
- `codex review --base 098f3e2` (all M0 code): one P2 finding, fixed; the new test fails on the old code and passes on the fix. `go test ./internal/room/`: 15 tests pass.
