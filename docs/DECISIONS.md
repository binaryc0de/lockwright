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

## ADR-0025: Room packs are downloaded from the platform (2026-10-02)

**Context.** Browser builds carry no rooms (ADR-0023), and desktop builds needed packs copied next to the executable by hand. PLAN.md planned `/download` for M5.
**Decision.**
- **Platform.** With `-packs <dir>` (the output of `tools/packroom`), the catalog lists each room's current pack as `{file, sha256, size, url}`, and `GET /download/packs/{file}` serves it. Only `<room>-<semver>.pck` names are accepted, and an entry whose size disagrees with its file is hidden.
- **Client.** `RoomPackFetcher` downloads a pack the game lacks into `user://packs/`, verifies the SHA-256 and reuses a cached copy that still matches. It runs on join via the platform (any build) and for local play in the browser. It writes the response body itself, because the web build's `HTTPRequest.download_file` leaves the file empty.
- **Web serving.** `-web <dir>` serves the browser client at `/play/` on the API's own origin. The page URL carries the join details (`?code=&name=`, plus `room`/`difficulty` for local play; `bot`/`flag` are for tests only). Precompressed `.gz` copies (`tools/export.sh`) are sent to browsers that accept gzip.
**Consequences.** A friend needs only the link `http://<host>:<port>/play/?code=XXXXXX`. `tools/web_smoke.sh` plays both difficulties to the win in headless Chrome on the integrated GPU; `tools/test.sh` runs it when Chrome is installed. Packs are verified but not signed; signing is on the roadmap (PLAN.md 12.2).

## ADR-0026: Browsers reach games over HTTPS through the platform; Tailscale provides HTTPS for the friends test (2026-10-02)

**Context.** Godot's web build refuses to start outside a secure context: on `http://100.x.y.z` it shows "Secure Context - use HTTPS". It works only on HTTPS or localhost, which is why the localhost tests passed. A page served over HTTPS may only open `wss://` on the page's own origin, and every game server listens on its own port. (This replaces the first version of this ADR, which assumed plain HTTP over Tailscale and failed in the first remote test.)
**Decision.**
- **Proxy.** The platform proxies game WebSockets at `/ws/{session}` to that session's game server, and the join reply includes `ws_path`. Browser clients always connect through it on the page's origin (`wss://` on HTTPS pages), so only the platform's port has to be reachable from a browser. Desktop clients still connect to the game server port directly.
- **Friends test.** `tailscale serve --bg --https=443 http://127.0.0.1:8090` gives `https://<machine>.<tailnet>.ts.net/` with a real certificate, reachable only on the tailnet and by machines it is shared with. `tools/play.sh --tailscale` advertises the Tailscale IP (the CTF card and desktop game ports) and prints the HTTPS link.
- **CTF cards** stay plain `http://<tailscale-ip>:200NN/`. Players open them in a separate tab, which browsers allow from an HTTPS page.
- **Cloud.** The same proxy sits behind a TLS terminator (Caddy or a load balancer).
**Consequences.** Verified from a second machine on the tailnet (the Omarchy box):
- headless Chromium opened the `.ts.net` link, downloaded the room pack, joined through `/ws/`, and played hard mode to the win (the platform recorded it);
- the desktop client joined through the HTTPS platform and the direct game port;
- the CTF login page answered over Tailscale.
On HTTPS the clipboard works too. ufw needs 8090 only for local access; Tailscale serve reaches the platform over loopback.

## ADR-0027: Instanced-scene overrides need [editable] markers; the pack cache is only trusted after a hash check (2026-10-03)

**Context.** In the owner's browser, Night Shift showed loose papers, sticky pads and stacks of wall trim. Two bugs combined.
- **Lost overrides.** The room hides the unused variants inside CC0 kit models (notepads, trim, fixtures, cage panels, trays) with overrides on the instance's children. Our hand-written `room.tscn` had no `[editable path=...]` lines (the editor adds them), so Godot's export dropped all 133 such overrides from the room pack: only 6 of 139 hidden nodes stayed hidden. Material overrides on model parts, such as the rack LEDs' blink shader, were lost the same way.
- **Stale cache.** `RoomLoader.find_local_pack` also searched `user://packs/`, the fetcher's download cache, without checking the platform's current hash, so the browser kept loading the broken pack after it was fixed.
**Decision.**
- `room.tscn` marks the 34 instances it overrides as editable.
- `roomcheck` rejects child overrides on a non-editable instance.
- A room test (also run from the pack by `packroom -verify`) checks hidden variants and the LED material.
- `find_local_pack` only looks next to the executable, and never on the web. `user://packs/` is used only through `RoomPackFetcher`, which verifies the SHA-256 against the catalog first.
**Consequences.** Verified in the owner's Chrome over the Tailscale HTTPS link: the pack downloads fresh and the desk and walls match the desktop build. Room authors who edit scenes by hand must keep the markers, and roomcheck tells them.

## ADR-0028: Lobby site and an always-on platform (2026-10-03)

**Context.** The owner wants a front-facing site where a game can be started on demand, instead of a terminal command. Spawning, isolation and teardown already existed (sessions start game servers on first join; challenges start and stop with the game).
**Decision.**
- **Site.** Plain HTML/CSS/JS embedded in the platform (`platform/internal/web`, spec in `SPEC.md`), served at `/` (rooms, Start a game, Join with a code) and `/g/{code}` (shareable game page: invite link, players, status, Play). No framework or build step. Accounts and payments come later, on the same API.
- **API.** `GET /api/games/{code}` (a public view: no tokens) and `GET /api/status` (counts only).
- **Guardrails.** `-max-games` (default 4) caps unfinished games; one client may create 6 games per 10 minutes; games nobody joins finish after 30 minutes (a one-minute sweeper).
- **Always on.** `tools/install-service.sh` installs a systemd user service (port 8090, Tailscale address advertised) and makes sure `tailscale serve` provides HTTPS. `tools/play.sh` stays for development and points to the service when it holds the port.
- **Division of work.** Claude built the backend, the tests and the service; Codex (gpt-6.1-sol) built the site's front end from `SPEC.md` and reviews the milestone.
**Consequences.** Anyone the owner shares the machine with can start a game from a browser. Without `loginctl enable-linger` (sudo) the service stops at logout.

## ADR-0029: A public switch with Tailscale Funnel; everything behind one HTTPS address (2026-10-03)

**Context.** The owner does not want friends to install anything (no Tailscale for them), and is fine with the machine being reachable for short windows they control. Sharing the machine on the tailnet would expose SSH, remote desktop and other local services to friends. Funnel exposes only one HTTPS handler, but web challenges used per-game ports (`http://<ip>:200NN`) that a tunnel does not carry.
**Decision.**
- **CTF through the platform.** With `-public-url`, challenge cards point at `/ctf/{session}/{challenge}/`, which the platform proxies to the running challenge with `X-Forwarded-Prefix`. Night Shift's intranet builds links, redirects and its cookie path from a validated prefix, so different games' logins never mix. Rule for room authors: ROOM_AUTHORING design rule 10.
- **Hardening for public exposure.** Internal endpoints accept only direct loopback calls. Joins and code lookups are limited to 30 per minute per client. Game creation was already capped and limited (ADR-0028).
- **The switch.** `tools/public.sh on|off|status` turns Funnel on for the platform (the site, the browser game, `/ws/` game connections, `/ctf/` challenges) and back to tailnet-only. Nothing else on the machine is exposed. `install-service.sh` sets `-public-url` to the `.ts.net` address, so the tailnet and the public use the same links.
- **Tunnel choice.** Funnel over ngrok for this: ngrok's free plan has a small monthly transfer allowance (a new player downloads about 92 MB) and shows browsers an interstitial page. The platform is tunnel-agnostic, so `ngrok http 8090` with `-public-url` works too.
**Consequences.** Friends need only the link and a browser. Verified: the m3 smoke attacks the real challenge container through `/ctf/`. Turning Funnel on is the owner's action (the first time, Tailscale asks to allow Funnel for the machine). The site is public while it is on.

## ADR-0030: Draft rooms stay off the platform until they ship (2026-10-03)

**Context.** The owner picked the second room, The Clockmaker's Study, and asked to keep it off the public site until it is ready. The platform loads every `game/rooms/*/room.json` at start-up and the always-on service runs from this working tree, so a half-built room would appear in the lobby as soon as it had a `room.json`. `/download/packs/{file}` also served any well-named file in the packs directory, whether or not its room was listed.
**Decision.**
- `room.yaml` gains an optional top-level `draft: true` (schema; carried into `room.json`).
- The platform's catalog (`rooms.Load`) leaves draft rooms out, so they are absent from `/api/catalog`, the lobby and the web start screen, and `POST /api/sessions` for them is 404. `-drafts` (`rooms.LoadWithDrafts`) includes them, for a private development platform; `tools/play.sh --drafts` passes it. The start-up log lists hidden drafts.
- `/download/packs/{file}` serves only the current pack of a room in the catalog, so a draft's pack built by `tools/export.sh` is not downloadable, and neither are stale versions.
- Everything else (roomcheck, dev mode, `packroom`, tests) treats a draft like any room. Shipping is deleting the line.
- **Packs hold only their own room** (found 2026-10-03): room-pack presets export every resource no filter excludes, so Night Shift's pack built on this branch carried Clockmaker's design README. Each `room-pack-<id>` preset now excludes every other room's directory; `packroom` refuses a preset that does not, and rejects a built pack that contains another room's paths (`tools/packroom/scope.go`, tested against the real presets). Room-specific props live under `game/rooms/<id>/assets/` so they ship only in that room's pack (client builds exclude `res://rooms/*`).
**Consequences.** The always-on service never shows a draft, even if it restarts on a branch that contains one. It still runs game servers from this checkout (`-game game`), so SDK changes made for a new room reach live games when a new game starts; running the service from its own worktree on a release branch would separate the two (not done; the owner's call).

## ADR-0031: Second room is The Clockmaker's Study, a standard 60-minute room (2026-10-03)

**Context.** The owner asked for a second room with a classic escape-room theme to sit beside the hacker room, chose the clockmaker theme from a brainstorm (others: séance parlour, night train, tomb, bunker, pirate cabin, speakeasy, alchemist), and decided the format.
**Decision.**
- Room id `clockmaker`, *The Clockmaker's Study*: a standard room (no CTF), so browser only (ADR-0023).
- 60 minutes, 1-4 players, the team **starts together** (no split-start asymmetry, so no per-group spawns in the SDK).
- **Long formats (24/48 h) are reserved for harder hacker rooms.** Standard rooms are 60 minutes.
- Design, puzzle chart, SDK needs and asset list: `game/rooms/clockmaker/README.md`. The room stays `draft: true` until its blind play-tests pass (ADR-0030).
**Consequences.** The room drives generic SDK additions (`DialLock`, which also covers the planned `LetterLock`; `SequenceLock`; `SequencePlayer`; `AllOfGate`; analog `SessionClock`), built and tested before the greybox. A Hard level is undecided.

## ADR-0032: A platform cleans up only the challenges it created (2026-10-03)

**Context.** On 2026-10-03 a friend's public game lost its CTF challenge mid-session: at 15:30 a `tools/test.sh` run started a throwaway platform (m3 smoke), whose start-up `Cleanup` removed every `escapebox.managed` container on the Docker host, including the always-on service's live intranet. The service still held its in-memory handle and proxy, so the laptop link answered with connection resets until the game idle-stopped. Fixed live by letting it idle-stop and rejoining (a fresh container with the same flag; state restored from the snapshot).
**Decision.** Everything the orchestrator creates also carries `escapebox.owner`, an id derived from the platform's data directory (`OwnerFor`). Start-up and shutdown cleanup remove only containers and networks with their own owner id; containers of other platforms, and unlabelled ones from older builds, are left alone. Development happens in a separate worktree (`../escapebox-clockmaker`); the main checkout stays on the branch the service runs, because the service starts game servers from it (ADR-0030 consequence).
**Consequences.** Test platforms (temporary data directories) can no longer touch the service's games. Leftovers from a crashed platform are cleaned by the next start of that same platform; containers from builds before this change are no longer removed automatically (`docker rm -f` by label if ever needed).

## ADR-0033: Clockwork SDK nodes for the second room (2026-10-03)

**Context.** The Clockmaker's Study (ADR-0031) needs letter rings, settable clock hands, chime bars, a songbird that plays a per-session melody, and "when all of these are done" wiring. PLAN.md 8.2 planned `DialLock` and `LetterLock` separately.
**Decision.**
- **`DialLock`** covers both: N wheels, each with its own symbol list, a separator for multi-character symbols ("4:40"), a start position, and optional parts turned by each wheel (clock hands, letter rings). Every turn is an intent, so teammates see the wheels move; it opens the moment the wheels show the code, like a real combination lock. `submit_code` sets every wheel at once (solution replay). No separate `LetterLock`.
- **`SequenceLock` + `SequencePad`**: pads ring a synthesised note on every client and feed one symbol each; the lock compares the latest strikes with its code, so players can restart any time. Unlocking also needs the watching puzzle's prerequisites (`RoomAuthority.prerequisites_met`), because pads change the lock without an intent on it.
- **`SequencePlayer`**: replayable sequence of notes plus a pointer to each symbol (readable without sound, PLAN.md 9 accessibility). Dead until activated.
- **`AllOfGate`**: watches its inputs' states on the server and activates targets once.
- **`SessionClock.wall_start`**: story-time clock with hands (11:00 -> midnight).
- **Notes are synthesised** (`EBSound.tone`: bell or whistle), played without pitch jitter. No audio files, same approach as `AmbientZone`.
- **Activation opens an `Openable`** whose lock allows it (added for the greybox): solving a lock can spring its drawer, flap or case open through an `AllOfGate`, so players do not need a second click.
- **`Lock.dead_message`/`dead_prompt`** replace the hard-coded "The panel is dead." / "no power" (defaults unchanged).
**Consequences.** All new exports are `Array[String]`, `Array[NodePath]` or `Array[float]` (not packed arrays, ADR-0022); the room's pack replay will confirm `Array[float]` survives export. A clock-tick `AmbientZone` that starts when the clock runs is left for the audio pass.

## ADR-0034: How The Clockmaker's Study is dressed (2026-10-03)

**Context.** R3 replaces the greybox with real props: 16 Codex GLBs, 6 printables and about 20 CC0 Poly Haven models and 6 textures, while the room stays a draft that must not grow the public client.
**Decision.**
- **Room-specific assets live in the room.** CC0 downloads go to `game/rooms/clockmaker/assets/third_party/` (a room section in `fetch_cc0.sh`, its own `ATTRIBUTION.md`), Codex props to `game/rooms/clockmaker/assets/props/` (requests name it in `**Output:**`, which `build_assets.sh` now honours), materials to `assets/materials/`. Client builds exclude `res://rooms/*`, so none of it reaches the public client; only the room's pack carries it.
- **The builder stays the source of the scene** (`game/tests/scenes/_build_clockmaker.gd`): each prop is used only if its GLB exists (`model()`/`part()`), greybox meshes lose their mesh but keep their colliders (`ghost()`), moving parts follow the SDK's moving nodes through `RemoteTransform3D` (`follow()`, ADR-0012), model hands/rings/tails are driven directly by `hand_parts`/`pointer` with the model's own axis convention (clockwise = +Z in model space), multi-part kits and multi-variant CC0 files show their parts as meshes extracted once to `assets/kit/*.res` (`extract()`): editable instances of imported scenes embedded a copy of every mesh they touched, which had made `room.tscn` 9 MB; it is now about 120 KB. Parts that appear when a lock opens start hidden from the lock's own state at runtime, not by the builder. Regenerate after `godot --import` (an unimported GLB is invisible to `ResourceLoader`, and the builder silently keeps the greybox).
- **Locks can show and hide parts** (`show_when_unlocked`/`hide_when_unlocked`): fitted wheels, the hung pendulum, the hung calipers.
- **The trunk rides on the swinging case** (`Study/LongcaseClock/Case/Swing/Trunk`), a nested interactable inside the exit door, so its door, hook and contents go with the case when it swings aside.
- A room test fails on any Godot auto-renamed node (`@Type@n`), after a name clash silently broke the trunk's path once.
- **Audio stays synthesised** (no files): `AmbientZone` gains a tick track and an `only_when` condition (the long-case clock ticks once its face has power, i.e. pendulum hung and wound), and `Lock` an unlock bell struck `unlock_tone_count` times (the long-case strikes the master's hour, `{{true_hour}}` times, at the win). The fire crackle is filtered noise.
- **Browser look checked, no separate lighting setup**: the room uses unshadowed omni lights, which the Compatibility renderer draws like Forward+ (renders compared with `--rendering-method gl_compatibility`), so no baked variant is needed for this room.
- **Texture budget for room assets** (`tools/texture_budget.py`): room props and CC0 model textures at 512 px, tiling room surfaces at 1024, and only the five colour maps that carry lettering (`ROOM_TEXT_MAPS`) at full size. The pack went from 182 MB to 82 MB (50 MB gzipped).
**Consequences.** Lighting is still omni lights without baking (works on both renderers; the browser pass is M5's open item). A browser player of this room downloads the client plus about 50 MB; the remaining weight is mostly mesh data in the imported scenes, to revisit before shipping.

## ADR-0035: The Clockmaker's Study ships before its blind play-tests (2026-10-03)

**Context.** The owner played the dressed room through on the desktop ("played through looks good") and asked to deploy it. ROOM_AUTHORING's definition of done also asks for three blind play-tests, which have not happened; the owner co-designed the room, so that run is not blind.
**Decision.** Ship now: `draft: true` is removed, so the platform lists the room, hosts games and serves its pack. The blind play-tests stay on the list and are logged in the room README when they happen; if they show a puzzle is too hard or unclear, it is fixed in place (packs are versioned and re-downloaded by hash). Room packs are now also sent gzipped (`packroom` writes `<pack>.gz`; `/download/packs/` serves it to clients that accept gzip): Clockmaker's 82 MB pack travels as about 50 MB.
Found by the browser smoke: the web build must leave decompression to the browser (`RoomPackFetcher` sets `accept_gzip` off on the web), or Godot decompresses an already-decompressed body and fails (`RESULT_BODY_DECOMPRESS_FAILED`).
**Consequences.** Friends see two rooms in the lobby. Download progress, measured in both clients: a browser counts decompressed bytes (so the pack's size is the total), a desktop build counts compressed bytes against the response's Content-Length, which the platform now sets explicitly on the gzipped copy (Go's `ServeContent` drops it when `Content-Encoding` is set); the desktop bar had stopped at 64.5 % before.
