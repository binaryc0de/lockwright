# Decision log (ADRs)

Short records: context, decision, consequences. Newest at the bottom. Never edit an accepted ADR; supersede it with a new one.

## ADR-0001: Locked decisions from the owner interview (2026-10-01)

**Context.** Planning interview and five research reports (`docs/research/`).
**Decision.** Adopt PLAN.md Section 2 as written: Godot 4.7.x Forward+, first-person free roam, authoritative headless dedicated server (ENet, plus WebSocket from M2), CTF via in-game terminal and sandboxed Docker containers, room packs are full Godot scenes/scripts from trusted authors, prototype is the one-room "Night Shift" vertical slice, tiered text hints, Go platform service, SQLite then Postgres, Discord voice, Windows + Linux desktop clients, CC0 PBR art, Blender 5.2 LTS headless scripts as asset source, Codex `gpt-6.1-sol` as asset agent, Python only under `tools/blender/` and `tools/printables/`.
**Consequences.** Changing any of these needs a new ADR approved by the owner.

## ADR-0002: Pinned tool versions for M0 (2026-10-01)

**Context.** Godot was not installed; CI and local runs must match.
**Decision.** Godot **4.7.2-stable** (official Linux x86_64 build, installed to `~/.local/opt/godot-4.7.2/`, symlinked as `~/.local/bin/godot`). Blender **5.2.2 LTS**. Go **1.27**. gdUnit4 **v6.2.x** vendored under `game/addons/gdUnit4/` (test-only addon, not shipped in exports). CI downloads the same Godot build.
**Consequences.** Bumping a version is a one-line change in CI plus a note here.

## ADR-0003: No GPU-heavy rendering on the dev box (2026-10-01)

**Context.** The dev box is a laptop with an Intel UHD 620 (Kaby Lake-R) iGPU and 8 threads / 31 GB RAM. The kernel log shows an i915 GPU hang earlier the same day, and the machine hard-crashed (reboot, corrupted `.git` objects) about three minutes into the first Codex asset task. The exact cause was not captured in the journal.
**Decision.** Asset previews render with Blender Workbench or Cycles on CPU only, never Eevee or GPU compute; one Blender process at a time with `--threads 4`. Automated Godot runs on the dev box use `--headless`. Interactive Godot editor use is the owner's call. The 60 fps Forward+ target (PLAN.md Section 4.6) is measured on the LAN player PCs, not on this box.
**Consequences.** Previews are less pretty than Eevee; in-engine screenshots for asset review need a windowed Godot run, done deliberately and briefly (or on another PC). Revisit if the host machine changes (PLAN.md open question 1).

## ADR-0004: Go dependencies for the platform and tools (2026-10-01)

**Context.** `roomcheck` must parse YAML and validate against `docs/schema/room.schema.json`; the platform needs SQLite later (pure-Go driver per PLAN.md).
**Decision.** Allowed dependencies: `go.yaml.in/yaml/v3` (YAML), `github.com/santhosh-tekuri/jsonschema/v6` (JSON Schema 2020-12). SQLite driver chosen in M3 with its own ADR. Everything else from the standard library (including `assetcheck`'s GLB parser, which only needs the JSON chunk plus accessor metadata).
**Consequences.** One Go module at the repo root (`github.com/binaryc0de/escapebox`) holding `platform/` and `tools/*`, so tools and platform share packages without replace directives.

## ADR-0005: Room YAML is validated as JSON Schema 2020-12 (2026-10-01)

**Context.** PLAN.md Section 8.3 defines `room.yaml` v1 by example.
**Decision.** `docs/schema/room.schema.json` is the normative definition. Unknown top-level keys are rejected (`additionalProperties: false`) so typos fail loudly; growth is additive by bumping the schema in place while `spec_version` stays 1. `solved_when` is a closed vocabulary: `item_picked_up`, `node_state`, `flag_accepted`, `all_of`, `any_of`.
**Consequences.** Every room-format change touches the schema, `roomcheck` tests, and `ROOM_AUTHORING.md` in the same commit.

## ADR-0006: Runtime reads a generated room.json; room.yaml stays the source (2026-10-01)

**Context.** Godot has no built-in YAML parser, and PLAN.md forbids adding dependencies casually. The server and client both need the manifest at runtime.
**Decision.** Authors edit `room.yaml`. `go run ./tools/roomcheck -write-json <room_dir>` writes `room.json` next to it (same document, sorted keys). Both files are committed and both ship in the pack. `roomcheck` fails if `room.json` is missing or stale. The Godot `RoomLoader` reads `room.json` and verifies its `id` (PLAN.md 8.1 says room.yaml; read this as "the manifest").
**Consequences.** One extra command for authors, enforced by CI. No YAML code in GDScript.

## ADR-0007: What a room pack contains, and class_name in rooms (2026-10-01)

**Context.** Exporting the `room-pack-night_shift` preset (only `res://rooms/night_shift/**`) on Godot 4.7.2 showed the PCK always also contains `project.binary`, `.godot/global_script_class_cache.cfg` and `.godot/uid_cache.bin`.
**Decision.** Packs are loaded with `load_resource_pack(path, false)` (already a non-negotiable), so those engine files never override the base game's. Because the pack's class cache is therefore ignored, **room scripts must not declare `class_name`**; they reference SDK classes (which live in the base game) and their own scripts by path. `roomcheck` will warn on `class_name` in room scripts from M1. The room pack preset excludes `res://core`, `res://addons`, `res://assets` (shipped in the client and server builds).
**Consequences.** Room-specific shared types use `preload("res://rooms/<id>/scripts/x.gd")`. Revisit if Godot gains per-pack class registration.

## ADR-0008: SDK node names that collide with Godot built-ins (2026-10-01)

**Context.** PLAN.md 8.2 names SDK nodes `Container` and `Button`; Godot 4.7 already has `Container` (Control) and `Button`, and a `class_name` may not shadow an engine class.
**Decision.** The SDK uses `ContainerProp` and `PushButton`. Every other plan name is used as written (checked against the 4.7 class reference). Shared open/close behaviour lives in an `Openable` base used by `ContainerProp` and `Door`; `EBNode` is the base of all replicated SDK nodes.
**Consequences.** `ROOM_AUTHORING.md` uses the new names.

## ADR-0009: Authority model in M1 (2026-10-01)

**Context.** M1 is offline single-player, but M2 must add a dedicated server without rewriting gameplay (PLAN.md 7.2).
**Decision.** All gameplay changes go through `RoomAuthority.handle_intent(player, node_path, verb, payload)`, which validates (reach, availability, item ownership), calls the SDK node's `_server_intent`, and mutates the `WorldState` only through `set_node_state`/`give_item`/`pin_document`/`activate`/`submit_flag`. The authority applies each change to its own scene immediately and announces it by signal. The client hub (`Game` autoload) only calls `request()`, `request_hint()`, `add_note()`. M1 runs the authority in the same process and scene; M2 moves it to the server and turns the signals into RPCs. Locks: activating an unpowered lock powers it; activating a powered lock unlocks it.
**Consequences.** Room authors wire puzzles with exports (`locked_by`, `targets`, `challenge_id`) and need no scripts for Night Shift. Every SDK node state has a `state` string so `node_state` conditions work uniformly.

## ADR-0010: Server-side prerequisite gating and authority hardening (2026-10-01)

**Context.** Codex's adversarial review of the M1 authority found four bypasses: mechanisms could fire before their puzzle's prerequisites; SDK nodes held writable references into the WorldState; scene visibility decided whether closed-container contents could be taken; players with no known position skipped the reach check.
**Decision.** (1) A node is *gated* by every puzzle whose `solved_when` watches it (`node_state` path, `item_picked_up` item id, `flag_accepted` challenge); intents on it are refused with `not_yet` until those puzzles' prerequisites are solved, before any mutation. Room authors get this for free from room.yaml. (2) Nodes and signal listeners only ever receive deep copies of state; server decisions read the authoritative table via `EBNode.my_state()`/`state_of()`. (3) Server availability comes from the WorldState (`_server_available()` plus "no closed ContainerProp holds this in its contents"); visibility is presentation only. (4) Intents from players with no reported position are refused unless `allow_unpositioned` is set by a trusted caller (tests, solution replay).
**Consequences.** Sequence breaks are impossible by construction; a puzzle whose clue can be bypassed physically must declare that in its prerequisites. M2 must send a player's position before (or with) their first intent. `Game.world()` still returns the authority's table in M1 (single process); M2 replaces it with a client-side mirror.

## ADR-0011: Development moves to the RTX 3080 Ti laptop; ADR-0003 applies only to the old box (2026-10-01)

**Context.** The original dev box (Intel UHD 620) cannot safely render the game, so nobody could see the greybox or judge visuals. The owner has an Alienware m17 R5 (Ubuntu 24.04, RTX 3080 Ti Laptop 16 GB, driver 595, 16 threads, 30 GB) at 192.168.1.20, user `jason`, Cinnamon on X11 (`DISPLAY=:0`).
**Decision.** The Alienware is the development machine: repo at `~/Work/escapebox`, Godot 4.7.2 / Blender 5.2.2 / Go 1.27.0 installed under `~/.local/opt` with symlinks in `~/.local/bin` (no sudo), Codex 0.160 (`gpt-6.1-sol`, high) and Claude Code already present. Full Forward+ rendering, windowed Godot and GPU Blender rendering (Cycles OptiX, Eevee) are allowed there. ADR-0003's CPU-only rules remain only for the old UHD 620 box, which becomes the candidate LAN host (headless game server, platform, CTF containers need no GPU; PLAN.md open question 1). Visual review uses `game/tests/scenes/room_shots.tscn` (screenshots from fixed viewpoints).
**Consequences.** Asset previews may use Eevee/Cycles GPU on the Alienware. The 60 fps target (PLAN.md 4.6) still needs one measurement on a mid-range GPU because a 3080 Ti is above target. The `.pck` sha256 differs between machines (packs are not byte-reproducible across builds); the catalog records each pack's own hash.

## ADR-0012: M1 look test: SDFGI, CC0 shell materials, and how hero props attach to SDK nodes (2026-10-02)

**Context.** The owner judged the greybox "way too simple". Before closing M1, one corner of Night Shift (desk, whiteboard, filing cabinet) is dressed to PLAN.md's art direction to prove the visual bar.
**Decision.** (1) Global illumination is **SDFGI** with SSAO, SSIL, glow, low volumetric fog and AgX tonemapping in the room's `Environment`. LightmapGI was not used because baking needs the editor (no headless bake path) and the shell is still changing; revisit in M4 against the 60 fps mid-range target. (2) Lighting is diegetic "emergency power": two fluorescent battens on with shadowed spotlights on the puzzle workspaces (whiteboard, cabinet), one dead batten, a warm desk lamp as the key light, faint screen glow; colour is never the only cue. (3) Shell surfaces use shared CC0 PBR materials in `game/assets/core/materials/` with world-space triplanar mapping, so greybox boxes need no UVs. Downloads come from `tools/thirdparty/fetch_cc0.sh` and are listed in `game/assets/core/third_party/ATTRIBUTION.md`. (4) Hero GLBs are added as visual children of the existing SDK nodes; greybox meshes lose their `mesh` but keep their colliders, so node paths, reach and replay tests are unchanged. Moving parts follow the SDK's moving node through a `RemoteTransform3D` pointing at the GLB's named part (no SDK change). Multi-variant CC0 files (Poly Haven showcases) are instanced with per-child `visible = false` overrides.
**Consequences.** SDFGI cost on a GTX 1660-class GPU is unmeasured (PLAN.md 4.6); the M4 performance pass decides SDFGI vs baked. Requests must give the origin as the overall bounds centre whenever parts stand proud (the desk request got this wrong once). Godot `-col` helper meshes stay visible; requests use `-colonly`.

## ADR-0013: Codex runs unsandboxed on the Alienware (2026-10-02)

**Context.** On the Alienware (Ubuntu 24.04, ADR-0011), Codex tasks started from Claude Code fail before running anything: Codex's vendored bubblewrap cannot set up its namespaces (`bwrap: loopback: Failed RTM_NEWADDR: Operation not permitted`; `kernel.apparmor_restrict_unprivileged_userns = 1`). The same setup works on the owner's other machines.
**Decision.** At the owner's request, asset tasks run as `codex exec --dangerously-bypass-approvals-and-sandbox -m gpt-6.1-sol -c model_reasoning_effort=high -o <last-message file> "<prompt>"`, launched in the background from Claude Code. The plugin's `codex-companion.mjs task` is not used for write tasks here because it hardcodes `workspace-write`. Lane rules (ASSET_PIPELINE.md Section 2) are enforced by the prompt and by Claude's review of the diff, not by a sandbox.
**Consequences.** Codex has the user's full permissions on this machine; prompts must name the files it may touch, and Claude reviews `git status` after every task. If the owner later installs an AppArmor profile that lets Codex's bwrap create user namespaces, the sandboxed companion path can return.

## ADR-0014: Exit door swings out; printables live outside assetcheck's request set (2026-10-02)

**Context.** Dressing the rest of the Night Shift office. The greybox exit door had a push bar on the room side but swung into the room, which no real panic-bar door does, and it would hide the maglock. `tools/assetcheck` treats every `assets/requests/*.md` as a GLB asset, but printed documents (PLAN.md 8.6) are PNG textures.
**Decision.** (1) The exit door swings 90 degrees out into the corridor: `Hinge` sits on the corridor-side face of the leaf (local x -0.06) so the open leaf lies along the corridor wall instead of passing through it; the maglock is on the room side where players can see it. `test_open_doors_clear_their_doorways` still holds. (2) Printable requests live in `assets/requests/printables/`, build through `tools/printables/` into `game/rooms/<room>/assets/docs/`, and ship inside the room pack. In-world they are textured quads; the `Document` keeps its `text_md` (inspect view and evidence board) and also gets the texture.
**Consequences.** assetcheck does not validate printables yet; their reports and 25 % legibility previews are the check until a `printcheck` exists.

## ADR-0015: M2 network design (2026-10-02)

**Context.** M2 (PLAN.md 7, 11) moves the in-process RoomAuthority onto a headless dedicated server and lets 2-6 clients share the room. M1 already routes every change through `RoomAuthority` signals and every client action through `Game.request()`/`request_hint()`/`add_note()` (ADR-0009, ADR-0010).
**Decision.**
1. **One RPC endpoint.** `Game` gets a child `Net` (`core/net/net_bridge.gd`, path `/root/Game/Net` on every peer) holding every `@rpc`. Payloads name SDK nodes by `eb_path`, never by NodePath, so the room may sit anywhere in each peer's tree.
2. **Three modes in `Game`:** LOCAL (M1 offline, authority in-process), SERVER (headless; authority + room, no player/HUD), CLIENT (no authority; a mirror `WorldState`). SDK nodes keep `authority == null` on clients.
3. **State sync = whole-snapshot push, coalesced per frame.** After any authority change the server sends the full `WorldState.to_dict()` (a few KB for Night Shift) reliably to every joined client, at most once per frame. The client diffs it against its mirror and emits the same `Game` signals as LOCAL mode (`node_state_changed` only for changed paths, `inventory_changed`, `evidence_changed`, `puzzles_changed`). Non-state events (puzzle solved, hint revealed, narration, time up, session finished, "X is examining Y") are separate reliable RPCs. Simpler than per-field deltas and identical on join/rejoin; revisit if rooms grow large.
4. **Intents are asynchronous.** `Game.request(node, verb, payload, on_result := Callable())` returns nothing useful; the result arrives through `on_result` and `intent_result`. LOCAL mode calls back synchronously, so single-player behaviour and tests are unchanged. The four UI panels that read results (keypad, patch panel, terminal, evidence notes) use the callback.
5. **Players.** Clients send their eye position and yaw unreliably at 15 Hz (and before their first intent); the server stores it for the reach check (no `allow_unpositioned` on a networked server) and broadcasts all positions at 15 Hz. Remote players render as a capsule with a name tag, interpolated.
6. **Join.** First RPC from a new peer: `join(token, display_name)`. M2 verifies against a `JoinVerifier` stub (`--token` on the server is a shared invite; empty accepts all). M3 swaps in `POST /internal/sessions/{id}/verify`. Player id = sanitised display name (unique per session) so a rejoin keeps identity.
7. **Clock.** `started_at` stays in server unix time; every state push carries `server_now`, and clients keep an offset so `remaining_s()` matches the server across machines.
8. **Snapshots.** The server writes `WorldState` JSON to `--snapshot <path>` (default `user://snapshots/<session>.json`) at most every 0.5 s after a change and every 30 s, and restores it at start. M3 replaces the file with `POST /internal/.../snapshot`.
9. **Transports.** `--transport enet` (default, UDP) or `ws` (WebSocket); same MultiplayerAPI.
10. **Testing.** A headless bot client (`--bot`) replays `room.yaml`'s `solution` through the network, teleporting its reported position to each target. `tools/m2_smoke.sh` runs server + bots + a server kill/restart in one script; gdUnit covers the diff/mirror logic in-process.
**Consequences.** Per-session `vars` (e.g. the cabinet code) reach every client because clients render templated text; a player who reads process memory could cheat. Accepted for trusted friends; flags never enter the WorldState. Real flags, platform join verification and snapshot POSTs stay M3.

## ADR-0016: Server-side movement validation; reported positions are not trusted (2026-10-02)

**Context.** Codex's M2 review (P1) showed that ADR-0015's "intents carry the player's position" let a modified client claim to stand next to any node and bypass the reach check (ADR-0010).
**Decision.** The server owns each player's starting position (spawn on first join, last accepted position on rejoin within the server's lifetime) and sends it in `rpc_welcome`; the client places its player there. A reported position, whether from `rpc_position` or carried by `rpc_intent`, is accepted only if it is within `1 m + 6 m/s x elapsed` of the last accepted one; otherwise it is ignored and the reach check uses the last accepted position. `--trust-positions` turns the check off for headless test bots only and prints a warning.
**Consequences.** Real players can no longer teleport for reach; a player who lags badly may briefly fail reach checks until their next plausible report. Physics-level validation (walls, noclip) is still client-authoritative and out of scope for trusted friends.

## ADR-0017: Docker access for M3 development (2026-10-02)

**Context.** M3 runs CTF challenge containers through the Docker API. On the Alienware, Docker 27 is installed and running but the user is not in the `docker` group. PLAN.md (Risks, M5) intends rootless Docker on the LAN host; rootless on Ubuntu 24.04 also needs an AppArmor rule for rootlesskit.
**Decision.** Owner's choice: on the development laptop, add the user to the `docker` group (`sudo usermod -aG docker $USER`, then log out and in). The LAN host gets rootless Docker (plus gVisor if feasible) in the M5 runbook. The platform talks to whatever `DOCKER_HOST` points at, so both work unchanged.
**Consequences.** On the dev laptop, docker group membership is root-equivalent; acceptable for a single-user dev machine. Container hardening (no egress, cap_drop ALL, no-new-privileges, read-only rootfs, pids/mem/cpu limits) is required regardless of daemon mode, and the M3 tests check it on the created containers.

## ADR-0018: M3 platform architecture and dependencies (2026-10-02)

**Context.** M3 (PLAN.md 7.3-7.6, 11) builds the Go platform: store, sessions, join tokens, flags, Docker challenge orchestration, and the game-server side of those calls. ADR-0004 deferred the SQLite driver; PLAN.md 13.7 asks for an ADR per dependency and prefers the standard library.
**Decision.**
1. **SQLite: `modernc.org/sqlite`** (pure Go, no cgo, so the platform stays one static binary as PLAN.md 2 wants). Schema migrations are plain SQL applied in order at start; WAL mode.
2. **Docker: the Engine API over the unix socket with the standard library**, not the Docker Go SDK. M3 needs about ten calls (ping, build from a tar context, network create/remove, container create/start/inspect/stop/remove); `net/http` + `encoding/json` + `archive/tar` cover them, and a fake Engine in `httptest` makes the orchestrator testable. `DOCKER_HOST` is honoured, so rootless Docker (M5) works unchanged.
3. **No egress, but LAN ingress: internal network + platform TCP proxy.** Each session gets a Docker network created with `internal: true` (no route out; Docker refuses published ports on internal networks). The platform listens on an allocated host port (20000-20999) and copies bytes to the container's address on that network. Containers also get `cap_drop: ALL`, `no-new-privileges`, read-only root filesystem (tmpfs `/tmp`), pids/memory/CPU limits from `room.yaml`, and run as a non-root user in the image.
4. **Flags:** `per_instance` flags are `HMAC-SHA256(platform_secret, session_id | challenge_id)`, hex-truncated into the room's `format` template, so a restarted instance gets the same flag without storing it in plaintext; the platform secret lives in the data dir (0600). `static` flags store only a SHA-256. Comparison is constant-time. Rate limit per session and challenge: 10 wrong attempts per rolling minute, then a cooldown that doubles each time (30 s, 60 s, 120 s, ...). Every attempt is stored and logged without its value.
5. **Game servers** are spawned by the platform as `godot --headless --path <game_dir> -- --server ...` (no export templates yet) from a configurable command, one process per running session, game port from 7777-7799; idle exit (code 0) and crash restart as docs/API.md describes.
6. **Game server -> platform calls** use Godot `HTTPRequest` for join verification, snapshot PUT, events and challenge start (asynchronous). Flag submission stays synchronous from the authority's point of view (a blocking localhost HTTP call bounded by a 3 s timeout), because the authority's intent API is synchronous by design (ADR-0009); acceptable for a rare, human-paced action on a LAN host, and revisited if it shows up in frame times.
7. **The challenge app** is room content: `game/rooms/<room>/ctf/<challenge>/` is its own Go module (Docker builds from that directory alone), stdlib only, multi-stage build to a static binary on `scratch`, run as uid 65534. `tools/test.sh` runs its tests.
**Consequences.** One new Go dependency (with its transitive pure-Go set). The TCP proxy means challenge traffic passes through the platform process; fine for one LAN. Rootless Docker (M5) puts container IPs in another network namespace, so the proxy will need rootlesskit's port driver or `--net=slirp4netns` tweaks then; recorded as an M5 risk.

## ADR-0019: `docker compose up` moves from M3 to M5 (2026-10-02)

**Context.** PLAN.md's M3 acceptance includes "`docker compose up` brings platform + builds challenge image". The platform spawns headless Godot game servers itself (ADR-0018), so a platform container would need the Go binary, a headless Godot, the game project and the Docker socket on the host network; M5 already plans `deploy/docker-compose.yml`, the runbook and rootless Docker on the actual LAN host.
**Decision.** Owner's choice: M3 closes on the platform running from the repo (`go run ./platform/cmd/platform ...`) plus a real Docker run of the challenge (image build, hardened container, curl attack, end to end). Compose packaging, the challenge image pre-build, and the runbook move to M5, done once on the real host.
**Consequences.** M3 acceptance in STATUS.md drops the compose line; M5 gains it. Nothing in the code depends on how the platform is launched.

## ADR-0020: Airlock onboarding (2026-10-02)

**Context.** PLAN.md open question 3 asked whether rooms start with a 60-second controls airlock or cold. Owner's answer: the airlock (PLAN.md 9.6, 10).
**Decision.** A generic SDK node `AirlockGate`: players spawn outside the room at `RoomRoot.spawn_point`; the server seals when every connected player is inside `inside_min..inside_max`, or `seal_after_s` (default 60) after the first player entered. Sealing closes `door` (its lock stays in charge from then on), starts the clock (no client "start" button in airlock rooms), narrates `seal_text`, and moves stragglers to `late_spawn` (new `RoomAuthority.place_player` / `rpc_place`). After sealing, joiners spawn at `late_spawn` (`RoomRoot.join_spawn_transform`). A core `TutorialOverlay` teaches move, read, evidence board and hints while the gate waits; it is generic and advances on the player's actions. Night Shift: players start in the exit corridor, read the contractor work order (the briefing as a Document), walk in, the maglock slams, and Dale's intercom line delivers the crisis.
**Consequences.** Rooms without an `AirlockGate` keep the text briefing. Exit doors in airlock rooms start open, so a room's exit puzzle must not be "door is open" (Night Shift's is the keypad). Tests that need a closed door seal the gate first.

## ADR-0021: Exports, local room packs, graphics presets (2026-10-02)

**Context.** M4 needs Windows/Linux client exports and a performance pass, but the target GPU is still unknown (PLAN.md open question 2). Client exports contain no rooms, and pack download from the platform is M5 (`/download`).
**Decision.**
- `tools/export.sh` exports `client-linux`, `client-win` and `server-linux` (release) plus every room pack, and copies the packs into `packs/` next to each binary. Without `--pack`, `RoomLoader.find_local_pack` takes the newest `<room>[-<version>].pck` from `<exe dir>/packs/` or `user://packs/`. The M5 download writes into `user://packs/`.
- The dedicated server export strips visual resources (`customized_files {"res://": "strip"}`): its core pack goes from 274 MB to 0.76 MB. `application/run/flush_stdout_on_print` is on, so release builds log in real time.
- `tools/export_smoke.sh` plays Night Shift to the win with the exported Linux server and client.
- `GraphicsQuality` presets (`Settings.graphics`, pause menu): high is as authored; medium turns off SSIL and cheapens SDFGI, fog and SSAO; low turns off SDFGI (raising ambient light to compensate), fog, SSIL and SSAO, and renders at 77 % with FSR. `tests/scenes/perf_bench.tscn` reports GPU frame time for each preset.
- Exported release builds exposed a race: the client tightened its ENet timeouts in the same frame the room finished loading. ENet checks timeouts before it reads the acks that queued up during the load, so a healthy link was dropped (about 3 runs in 10). The timeouts are now tightened 2 s after the welcome.
**Consequences.** The 60 fps claim is an estimate until the owner names a target GPU. Windows binaries are built but not run here.
**Update (same day, cross-machine test).** On the slower LAN box (i5 + UHD 620) the client froze for about 7 s loading the room synchronously in the welcome handler. That is longer than ENet's 5 s minimum timeout, so links dropped intermittently even with the later timeout tightening. Clients now load the entry scene on a worker thread (`RoomLoader.load_room_async`) while the main loop keeps servicing the network. A rejoin welcome that arrives during the load is applied after it. The solution bot starts on `Game.session_started`. Servers keep the synchronous load (nobody is connected yet).

## ADR-0022: Selectable room difficulty; Night Shift hard mode (2026-10-02)

**Context.** The owner's first run of Night Shift took about 30 minutes and "was actually pretty easy". PLAN.md planned a hard variant where the USB stick's `shadow.bak` has to be cracked. The owner asked for it as a selectable difficulty, not a replacement.
**Decision.**
- **Room format.** `room.yaml` gains `difficulties: [{id, title, description, puzzles, challenges, solution}]`. The first entry is the default. A level replaces fields (`title`, `requires`, `hints`, `gm_notes`) of puzzles with the same id, and `hints` of challenges, and may replace the whole `solution`.
- **Validation.** `roomcheck` validates each level as its own room: graph, node paths, templates, and override ids.
- **Runtime.** `RoomManifest.for_difficulty` (GDScript) and `Manifest.Variant` (Go) apply the same rules. Scene nodes can be limited to levels with the SDK `EBNode.difficulties` export; outside them a node is hidden, its collisions are off, and it is never registered. The level is part of the world snapshot, so restores and late joiners use it, and clients specialise their manifest from the snapshot.
- **Choosing.** `--difficulty <id>` on the server and for local play. The main menu has a Difficulty picker used by Play and Host. `POST /api/sessions {room_id, difficulty}` stores it (sessions schema v2) and the session manager passes it to the game server. `/api/catalog` lists each room's levels. `tools/play.sh --hard`.
- **`Item.file_name`/`file_text`.** A file "on" an item: the inspect view shows it with Copy to clipboard and Save to Downloads buttons, so players can use real tools. This replaces PLAN.md's one-time platform download link: it works offline, needs no new endpoint, and the file is not secret.
- **Night Shift hard.** The Wi-Fi card's back no longer has the password (`WifiCardHard`, `difficulties: [hard]`). `hack_intranet` requires `open_cabinet`. The USB stick holds `shadow.bak` with Mark's sha512crypt hash, plus decoy accounts with strong random passwords. Clues on the IT pinboard (in both levels) give the pattern Word + one of `! # $ % & *` + join year, and Mark's anniversary card gives 2019. The intranet locks `mreyes` for 3 minutes after 5 wrong passwords, so guessing online is impractical and offline cracking (John, hashcat -m 1800, an openssl loop) is the path. The intranet password is unchanged, so the challenge image is the same in both levels.
**Consequences.** Hard needs players to bring a cracker; the tier-2/3 hints name the tools and tier 3 gives the password. A Go test in the challenge module fails if the USB hash and the challenge password drift apart.
**Found while building this: Godot 4.7.2's export drops `PackedStringArray` properties from scenes.** In the exported room pack every `PackedStringArray` value on a script node (`verbs`, `cable_ids`, `cable_labels`, `difficulties`) was missing: the pack's `SceneState` simply had no such property, while typed `Array[NodePath]` and scalar exports survived. Since M1, packed Night Shift had silently lost the patch panel's "A - red, one stripe" labels. All SDK exports are now `Array[String]`, scene values use `Array[String]([...])`, a core test forbids `@export` packed arrays in the SDK, and a room test (also run from the pack by `packroom -verify`) checks the arrays survive.

## ADR-0023: The game is played in the browser; only hacker rooms' CTF parts may need player setup (2026-10-02)

**Context.** The owner (2026-10-02): "Really I would expect all of it to be browser based, just the CTF components in the room may require setup from the user." The dividing line is the kind of room, not the difficulty. A *standard room* (no CTF challenges) must be playable in a browser with nothing else. A *CTF-enhanced "hacker room"* may expect players to set up their own tools or connection (Hack The Box style: own cracker, own VPN), but only for its CTF components. This revises PLAN.md's assumption of a downloaded desktop client.
**Decision.**
- **The browser is the target client** for every room. The desktop builds (Windows/Linux exports) stay as a convenience and a development path, not the requirement.
- **Room kind follows from the manifest.** A room with `ctf.challenges` is a hacker room; one without is a standard room.
- **Standard rooms:** nothing beyond the browser page; no installs, VPN or command line.
- **Hacker rooms:** everything except the CTF components still plays in the browser. CTF steps may need player setup (tools, a VPN-style connection), and the room's description says what setup it needs.
- **ROOM_AUTHORING design rule 9** records this.
**Consequences.**
- A browser client becomes a planned milestone, not an option. Godot 4.7's web export uses the Compatibility renderer (WebGL 2), so rooms need a browser-grade lighting setup (baked lighting) besides the desktop look. Assets need a size diet; game connections must be WSS, platform calls HTTPS, and room packs must be downloadable (`/download`).
- Night Shift is a hacker room: its CTF steps may need player setup at any difficulty (Hard already expects a cracker).
- Hosting plans follow from this. A browser page needs HTTPS and WSS end to end, which matters both for the friends test and for the cloud.

## ADR-0024: Texture budget for the browser build (2026-10-02)

**Context.** The first web export was 280 MB. Every 3D texture was imported lossless: Godot's editor switches 3D textures to VRAM compression only after seeing them used in 3D, and our headless workflow never does that. Lossless is the biggest format on disk and is uploaded to the GPU uncompressed, which is heavy for integrated GPUs.
**Decision.** `tools/texture_budget.py` sets the import options, and `tools/test.sh` fails when an asset is over budget:
- every 3D texture is VRAM-compressed (S3TC/BPTC; normal maps as RGTC);
- normal, ORM/ARM, AO, roughness and metal maps are capped at 1024 px;
- tiling CC0 surfaces and prop colour maps are also capped at 1024 px, except props whose textures carry text players read (patch panel, keypads, intercom, wall clock, laptop, UPS, rack, filing-cabinet keypad, monitor);
- printables stay lossless.
The platform serves the web build gzip-compressed.
**Consequences.** The web pack goes from 280 MB to 256 MB raw and 88 MB gzipped; with the 10 MB engine, the first load is about 98 MB, then cached. Desktop builds shrink the same way and use far less GPU memory. Close-up detail on non-text props is slightly softer (checked in renders). New text-bearing props must be added to `TEXT_PROPS`.
