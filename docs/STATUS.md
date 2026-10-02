# Status

Milestone checklist from PLAN.md Section 11. Check an item only when it was actually run; each milestone ends with a verification note saying what ran, where, and with which command. Untested things are listed as untested.

**Current milestone: M3 (platform and CTF).** M0 closed 2026-10-01. M1 closed 2026-10-02 (owner play-test escaped; Codex branch review clean). Server cage dressed (pulled forward from M4) and merged. M2 closed 2026-10-02.

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

- [x] Session authority (`RoomAuthority`): intents only, reach/availability/item/prerequisite checks, WorldState snapshot + restore (ADR-0009, ADR-0010)
- [x] `PuzzleGraph` (closed `solved_when` vocabulary, sticky solves, prerequisite order) and `HintService` (tiers, auto-nudge, logged reveals)
- [x] `RoomLoader`: mounts `.pck` with `replace_files=false`, verifies manifest id and entry scene; dev mode from `res://rooms/`
- [x] SDK nodes: Item, UVTorch, Document, ContainerProp, Door, KeypadLock, KeyLock, MaglockGate, Lever, PatchPanel, Terminal (remote + simulated), FlagGate, UVReveal, Intercom, SessionClock, RoomRoot (ADR-0008 renames)
- [x] First-person controller, interaction ray, highlight, context prompt
- [x] UI: inspect view (documents with flip/UV, items in a rotatable 3D view), team inventory bar, evidence board with notes, keypad and patch focused panels, terminal panel, hints panel, intercom banner, clock, end screen, pause/settings, main menu
- [x] CTF stub: `DevFlagValidator` accepts any non-empty flag offline
- [x] Greybox Night Shift (office + cage, 5 puzzles, 3 hint tiers each, no room scripts)
- [x] `tools/packroom` (export, sha256, catalog entry, `-verify` replays room tests from the pack alone)
- [x] Codex adversarial review of the authority: 4 findings, all fixed with regression tests (ADR-0010)
- [x] Look test (owner request after the greybox review): office corner (desk, whiteboard, filing cabinet) dressed with CC0 PBR materials, six Codex hero props, SDFGI lighting, fog and glow (ADR-0012). Before/after in `docs/screenshots/m1-looktest/` (`compare.png`); owner sign-off on the visual bar pending
- [x] Full office dressing (owner request 2026-10-02): rendered and reviewed; before/after in `docs/screenshots/m1-office/` (`compare.png`); owner sign-off on the look pending
- [x] Owner play-test: Night Shift played solo to the win screen in a window, 2026-10-02 (dressed office, greybox cage), on the Alienware. Launched in dev mode (`godot --path game -- --room night_shift`, room loaded from `res://rooms/`); play from the `.pck` is covered by `packroom -verify` (solution replay), not by a human run
- [x] Codex review of the look-test and office-dressing branch (`codex review --base main`, gpt-6.1-sol high, 2026-10-02): no actionable findings; it also re-ran gdUnit4 55/55, the pack replay and the printable checks
- [x] **M1 closed 2026-10-02**; `m1-look-pass` merged into `main`
- [x] Codex milestone review of M1 triaged: 3 findings (P2 clock started behind the briefing, P2 image-only documents blank on the evidence board, P3 keypad result overwritten), all fixed with tests; gdUnit4 now 53/53

Deferred to later milestones, noted from the room build: camera move-in for focused views (M4 polish); in-world patch cable visuals (M4); "use UV torch on X" as an explicit intent (the reveal is passive, solution uses `examine`); MaglockGate is an Interactable that is never targetable; `godot --script` tools cannot reference SDK classes because the `Game` autoload is absent in that mode; Planned SDK nodes in ROOM_AUTHORING.md.

## M2: Multiplayer
Started 2026-10-02 on branch `m2-multiplayer` (design: ADR-0015).
- [x] Dedicated server mode: `godot --headless --path game -- --server --session --room [--port --transport --token --snapshot]` (export templates still not installed, so no `escapebox-server` binary yet; the same project runs headless)
- [x] ENet and WebSocket transports
- [x] Join token handshake against a stub verifier (shared invite token; platform verify is M3); rejection reaches the client
- [x] World sync: whole-snapshot push coalesced per frame, client mirror diff re-applies only changed nodes; events and intent results ordered after the state push
- [x] Async intents (`Game.request(..., on_result)`); offline mode unchanged
- [x] Player positions 15 Hz, sent with every intent; remote avatars (capsule, head lamp, name tag)
- [x] Pickup conflicts (first intent wins, server-serialised), evidence notes, hints, auto-nudge, clock start through the server; server-owned timer with client clock offset
- [x] Co-inspection notice ("X is examining Y") and join/leave toasts
- [x] Snapshot export/import to JSON; server restart resumes from the snapshot; clients reconnect automatically (2 s retry, ~6 s dead-server detection)
- [x] `tools/m2_smoke.sh` (in `tools/test.sh`): server + 3 bots + crash/restore + rejected token + WebSocket
- [x] Owner LAN test, 2026-10-02: 2 players on two computers on the home network; disconnect and rejoin worked; stopping and restarting the server worked (owner's report: "it worked great"). 3 simultaneous human players not tried; 3 concurrent clients are covered by `tools/m2_smoke.sh`
- [x] Acceptance (PLAN.md M2): disconnect/rejoin and server restart verified by the owner on two LAN machines; 3 concurrent clients verified by the smoke test (headless, one machine); a 3-human session is still worth doing before M5
- [x] Codex review of `m2-multiplayer` (`codex review --base main`): 4 findings, all fixed with regression tests in `tests/core/test_net.gd`: P1 reach bypass through client-reported positions (ADR-0016: server-owned start position, speed check, `--trust-positions` for bots only); P2 no end screen when (re)joining a finished session (`Hud.sync_end_state`); P2 client stuck on "Connecting..." when the room fails to load after joining (now returns to the menu with the reason); P2 timeout debrief used the local clock (now server time)
- [x] **M2 closed 2026-10-02**; merged into `main`
- [x] Main menu "Join a game server" form (address, invite password, WebSocket option; remembers the last server) and a "Connecting..." screen with Cancel; a wrong password returns to the menu with the reason

## M3: Platform service and CTF orchestration
Started 2026-10-02 on branch `m3-platform` (design: ADR-0018; Docker access: ADR-0017).
- [x] SQLite store (`modernc.org/sqlite`): sessions, players, single-use join tokens (60 s), snapshots, events, flag attempts, challenge instances
- [x] Flags: per-instance HMAC flags, static SHA-256 flags, constant-time checks, 10 wrong/min then doubling cooldown, attempts logged without values
- [x] Docker Engine client (stdlib, `DOCKER_HOST`) with hardened containers: cap_drop ALL, no-new-privileges, read-only rootfs + tmpfs, pids/mem/CPU limits, internal (no egress) per-session network
- [x] Orchestrator: image build with content-hash tags, health wait, LAN TCP proxy on 20000-20999, idempotent start, full teardown and start-up cleanup
- [x] Session manager: one headless game server per session (7777-7799), idle exit, crash restart (max 3 per 10 min)
- [x] HTTP API: catalog, sessions (create/get/join, join by code), internal verify/snapshot/events/flags/challenges/finished, per-session server tokens
- [x] Game server in platform mode: platform join verification (async), snapshot load/save, events batched every 2 s, flag checks, challenge handles on the connection card, finish report, idle exit after 5 minutes
- [x] Client joins with platform address + join code; fresh join ticket on every reconnect; bad code returns to the menu
- [x] Kestrel Intranet challenge (Go, stdlib, scratch image, uid 65534): login with room credentials, IDOR on `?id=`, flag from `$FLAG`
- [x] `tools/m3_smoke.sh` (in `tools/test.sh`): platform + spawned game servers + join-code bots + flag + game-server crash/restore + recorded win + bad code
- [ ] Real Docker run: build the intranet image, attack it with curl, end-to-end with containers (waiting on the owner's `sudo usermod -aG docker $USER` + re-login)
- [ ] `docker compose up` (platform + challenge images) per PLAN.md M3 acceptance
- [x] Main menu: platform address + join code joins through the platform; "Host the selected room on the platform" creates a game and joins it; the join code shows on joining and in the pause menu (`tests/ui/test_join_flow.gd` 5 tests; layout checked in a windowed capture)
- [ ] Codex review of the branch

## M4: Night Shift content and polish
Pulled forward at the owner's request (2026-10-02), on branch `m4-cage-dressing`:
- [x] Server cage dressed: `cage_partition_kit`, `cage_door_maglock`, `server_rack_42u`, `patch_panel_8` (replaces the planned `patch_panel_24`: the puzzle uses 8 ports), `ups_tower`, `cable_tray_kit`, `rack_stencil` printable, CC0 painted-concrete cage floor; lit battens and spots in the cage. Before/after in `docs/screenshots/m4-cage/`.
- [ ] Everything else in M4 (audio, airlock briefing, remaining hero props such as `uv_torch`, performance pass, blind play-tests)

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

### 2026-10-01, M1 (same dev box)
- `tools/test.sh`: exit 0. gofmt/vet/go test pass; roomcheck PASS night_shift (0 warnings); assetcheck PASS keypad_4; Godot import clean; gdUnit4 50/50 (5 args, 3 world state, 6 graph/hints, 15 authority incl. 4 Codex regressions, 6 HUD/panels, 4 keypad asset, 11 Night Shift).
- `go run ./tools/packroom -verify night_shift`: `build/packs/night_shift-0.1.0.pck` 75,336 bytes, sha256 `300888113602b1c044633cd6d3d6d86301cb1d8c344572430c6d505d4f287b3d`; the 11 Night Shift tests (including the full solution replay to a win) pass in a copy of the project with no `rooms/` directory, i.e. loaded from the pack only.
- Night Shift geometry checked headless by the room-building subagent: every Interactable is reachable by the player's 3 m eye-height ray from open floor; spawn is clear; doors clear their doorways when open.
- Known noise: gdUnit4's runner prints "Remote Debugger: Unable to connect to host 127.0.0.1:0" on every run (also on M0 code); harmless.
- Not verified: anything visual (UI layout, lighting, mouse feel) because nothing here runs windowed (ADR-0003). That is the owner play-test above.

### 2026-10-01, move to the Alienware (RTX 3080 Ti)
- Repo copied with history to `user@192.168.1.20:~/Work/escapebox` (clean tree, `git fsck` OK). Godot 4.7.2, Blender 5.2.2 LTS, Go 1.27.0 installed in `~/.local` (ADR-0011).
- `tools/test.sh` on the Alienware: exit 0; gdUnit4 53/53; `packroom -verify night_shift` 11/11 from the pack alone.
- `room_shots.tscn` rendered 6 viewpoints with `forward_plus on NVIDIA GeForce RTX 3080 Ti Laptop GPU`, no errors, GPU at 49 C. Baseline greybox shots in `docs/screenshots/m1-greybox/`.
- Owner feedback on the greybox: "the graphics are way way too simple". Agreed next step: a look test (dress one office corner with CC0 PBR materials, Codex hero props, proper lighting) before closing M1, to prove the visual bar early.

### 2026-10-02, M1 look test (Alienware, RTX 3080 Ti, Godot 4.7.2, Blender 5.2.2, Codex 0.160 gpt-6.1-sol)
- Codex's sandbox could not start from Claude Code here (`bwrap: loopback: Failed RTM_NEWADDR`); per the owner, asset tasks now run unsandboxed via `codex exec --dangerously-bypass-approvals-and-sandbox` (ADR-0013).
- Six asset requests (`desk_3drawer`, `filing_cabinet_keypad`, `laptop_open`, `monitor_24`, `whiteboard_wall`, `office_chair`) built by six parallel Codex tasks in about 40 minutes; each reported two byte-identical builds. `desk_3drawer` failed assetcheck once because the request contradicted the base-centre rule; the request was revised and Codex rebuilt it.
- `go run ./tools/assetcheck`: 7/7 PASS (desk 17,884 tris, cabinet 13,720, laptop 28,130, monitor 9,314, whiteboard 12,154, chair 16,256, keypad_4 5,674).
- CC0 downloads via `tools/thirdparty/fetch_cc0.sh` (ambientCG Carpet012, OfficeCeiling001; Poly Haven painted_plaster_wall, desk_lamp_arm_01, mounted_fluorescent_lights, office_notepads, clipboard, cardboard_box_01, stationery_supplies), about 55 MB, listed in `game/assets/core/third_party/ATTRIBUTION.md`.
- gdUnit4: 55/55 (two new: GLB drawers follow their SDK containers by exactly 0.4 m; cabinet status light is the keypad model's LED). `go run ./tools/roomcheck game/rooms/night_shift`: PASS. `go run ./tools/packroom -verify night_shift`: room tests pass from the pack alone.
- `tools/shots/looktest_views.sh` rendered the same six viewpoints before and after, `forward_plus on NVIDIA GeForce RTX 3080 Ti Laptop GPU`, no errors, GPU 52 C.
- Not done / untested: frame rate (SDFGI + volumetric fog not measured on a GTX 1660-class GPU, PLAN.md 4.6); the rest of the office (exit door, pinboard, certificate, intercom, clock) and the cage are still greybox; documents and whiteboard writing are still Label3D in the default font (printables are M4); the keypad `LOCKED` label is too small to read except in the focused view; `keypad_4`'s `-col` helper is hidden by a scene override until its revision (request file); `desk_lamp_arm_01` is over the 20k prop budget; the UV torch and the papers in the desk drawer are still greybox.

### 2026-10-02, full office dressing (integrated, render pending)
- Codex (unsandboxed, ADR-0013) built seven more props and the printables pipeline: `exit_door_maglock`, `exit_keypad_6` (with the engraved SITE + RACK plate), `intercom_panel`, `wall_clock_countdown`, `pinboard_cork`, `certificate_frame`, `office_trim_kit`; `tools/printables/` with five documents (fire certificate, WiFi card front/back, sticky note, whiteboard marker layer, laptop login screen) in `game/rooms/night_shift/assets/docs/`. `keypad_4` helper renamed to `body-colonly` (scene override removed).
- Room: exit door now swings out into the corridor on a corridor-side hinge (ADR-0014); door, keypad, intercom, clock, pinboard and certificate frame replace their greybox meshes (colliders and node paths kept); printed textures replace the Label3D text in-world while `text_md` stays for inspect/evidence (all nine clue strings verified identical to the previous commit); skirting, sockets, switch, vent, smoke detector, twin-spot emergency light with two shadowed spots, a third lit batten over the south wall; CC0 fire-alarm call point and security camera.
- Ran (headless only): `godot --import` clean; roomcheck PASS; assetcheck 14/14 PASS (2 expected warnings: door hinge origin, keypad plate offset); gdUnit4 55/55; `packroom -verify night_shift` passes from the pack.
- **Not run:** no GPU render of this state. The NVIDIA GPU (which also drives HDMI) got stuck at 09:57 after a lid-close suspend failed (`nvidia-suspend/resume/hibernate.service` disabled while `PreserveVideoMemoryAllocations=1`; ACPI hot-eject of its HDMI audio function hung). Unrelated to this work; needs a reboot, and `sudo systemctl enable nvidia-suspend.service nvidia-resume.service nvidia-hibernate.service` to stop it recurring.
- Next: reboot; `tools/shots/looktest_views.sh docs/screenshots/m1-office/after` plus door/pinboard/clock views; check label sizes on the intercom, clock and keypad screens, the marker layer alignment with the UV box, and the emergency light aim; then commit screenshots and ask the owner for sign-off.
- After the reboot (kernel 7.0.0-34, HDMI back at 3440x1440): `tools/shots/office_views.sh` rendered 10 viewpoints (the six look-test views plus exit wall, override keypad, intercom/clock, south wall) on `forward_plus on NVIDIA GeForce RTX 3080 Ti Laptop GPU`, no errors. "Before" rendered from a temporary worktree of `ea73a1b` (the greybox). One fix from review: the laptop login screen bloomed to white (emission 0.9 -> 0.3).
- Seen in review, left for M4: the corridor's green light leaks along the ceiling seam above the exit door (SDFGI/thin-wall leak); the intercom LCD text is only readable close up; the cage partition (east wall) is still greybox; the NVIDIA suspend services on the dev laptop are still disabled.

### 2026-10-02, owner play-test
- Owner escaped Night Shift solo, windowed on the RTX 3080 Ti with a 3440x1440 HDMI monitor; the game window was the default 1600x900 (letterboxed), clock showed 44:25 left mid-run, around the CTF step.
- Bug found: pressing Enter on an empty flag field showed "Flag rejected." (and would cost a rate-limited attempt once M3 lands). Fixed in `terminal_panel.gd` with a regression assertion in `test_hud_panels.gd`; gdUnit4 55/55. Commit 4f06bfb.
- Owner's report: about 30 minutes, taking time to explore everything; "pretty easy"; "everything felt pretty smooth" (movement, controls, performance). Hint use not reported. The game does not log solves or hints to disk yet.
- Caveat: the owner co-designed the room (PLAN.md section 10 lists every answer), so this is not a blind run and says little about difficulty. Difficulty is judged by the 3 blind play-tests in M4 (target par 35-45 min for a team of 3); if those also come in fast, harden the cage half.

### 2026-10-02, server cage dressing (branch m4-cage-dressing)
- Codex (unsandboxed, ADR-0013) built six cage props and the rack stencil printable; each reported two byte-identical builds. `go run ./tools/assetcheck`: 20/20 PASS (4 expected warnings: two hinge origins, keypad plate and patch-panel cables shifting bounds centres).
- Room: greybox cage meshes stripped, colliders and node paths kept; door leaf follows the SDK hinge via RemoteTransform3D; cage maglock LED and patch panel visuals from the GLBs; RACK 062 is a textured decal on the rack's blank plate (Document text unchanged; all nine clue strings verified identical to main).
- Ran: Godot import clean; roomcheck PASS; gdUnit4 55/55; `packroom -verify night_shift` passes from the pack; `tools/shots/cage_views.sh` rendered 7 views after and 7 "before" from a worktree of main (16d93a6), no errors.
- Review notes: the "slab" in `05_cage_inside` is the back of the rack (solid black cabinet near the east wall), not a stray mesh. The painted-concrete floor is busy (worn patches); swap or tone down if the owner dislikes it. Patch cables stay hanging after the puzzle is solved (in-world re-patching is still deferred). Rack LEDs are static emissive (no blink yet).

### 2026-10-02, M2 networking (branch m2-multiplayer)
- `tools/test.sh`: exit 0. go test, roomcheck, assetcheck 20/20, Godot import clean, gdUnit4 63/63 (8 new in `tests/core/test_net.gd`: client/server args, snapshot store incl. corrupt file, join verifier, unique player ids, every Night Shift solution step maps to an intent, client mirror applies and announces only changes, offline intents still synchronous, disconnected client fails fast), pack replay, and `tools/m2_smoke.sh` PASS.
- `tools/m2_smoke.sh` passed 4 runs in a row on the Alienware (all headless, one machine): Carol (idle observer) joins; Alice plays solution steps 0-8 over ENet; the server is `kill -9`ed and restarted with `restored snapshot`; Carol reconnects on her own; Bob plays steps 9-15 and wins; Carol receives the live win event; Mallory with a wrong token is rejected (exit 3); Dana joins over WebSocket and plays two steps.
- Found and fixed while building: a 2 s server-side ENet timeout dropped clients that were still loading the room (the load blocks the main loop for seconds); the server now keeps ENet defaults and the client tightens its own timeout only after loading. The rejection RPC was lost when the peer was dropped in the same frame; the drop is now delayed 0.5 s.
- Not verified: anything visual or interactive in multiplayer (avatars, HUD toasts, two windows at once), a second physical machine, the 60 fps target with avatars.
- Join UI (2026-10-02): `tests/ui/test_join_flow.gd` (3 tests: form builds the same args as the CLI, bad input shown, overlay appears and Cancel closes the connection). Windowed captures of the menu and the connecting screen on the Alienware showed a layout bug inherited from M1 (menu drawn off the top-left, background not filling the window; anchors set without offsets); fixed with full-rect CenterContainers. `tools/m2_smoke.sh` now holds 3 clients at once (Carol, Erin, Alice). `tools/test.sh` exit 0, gdUnit4 66/66.
- Review fixes (2026-10-02): `tools/test.sh` exit 0; gdUnit4 70/70 (4 new regression tests); `tools/m2_smoke.sh` PASS with `--trust-positions` on the test server.

### 2026-10-02, M3 platform (branch m3-platform; Docker not yet accessible to the user)
- `go test -race ./platform/...`: 7 packages pass (api 6 tests incl. join/verify/token reuse/foreign server token, flags with the 10-wrong cooldown and no echo of values, snapshots/events/challenges/finish, join by code, no-Docker 503; docker client against a fake Engine incl. hardening fields and unix socket; orchestrator with a fake Engine and a real proxied HTTP server incl. rollback, path confinement, rebuild on edit, cleanup; sessions with fake processes incl. idle, crash limit, intentional stop; store; rooms against the real night_shift room.json).
- Intranet challenge: `go test` 5 tests (health, wrong creds, forged cookie, intended IDOR path, flag only on ticket 1040, escaping).
- `tools/m3_smoke.sh` PASS without Docker: platform spawned the game server, Alice joined by code (platform-issued player id), server killed with -9 and restarted by the platform from its stored snapshot, Bob joined and won with the flag (computed from the platform secret because no container could run), platform recorded the win, flag value absent from the platform log, a wrong code returned exit 3.
- `tools/test.sh` exit 0: gdUnit4 70/70, pack replay, m2 and m3 smoke.
- Not verified: anything involving real containers (image build, internal network reachability from the host, proxy to a container, rootless Docker), Windows clients, a second machine against the platform.
