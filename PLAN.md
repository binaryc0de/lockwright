# ESCAPEBOX: Virtual Escape Room Platform with CTF Rooms

**Working codename:** `escapebox` (escape room meets Hack The Box). Rename freely; nothing depends on it.
**Status:** Planning complete, prototype not started. Written 2026-10-01.
**Owner:** binaryc0de (solo developer, prior Godot 4 experience, loves escape rooms and CTFs).
**Audience of this document:** AI coding agents (Claude Code, Codex, etc.) and humans building the prototype. Read this file fully before touching code. The research that produced these decisions is in `docs/research/`.

---

## 0. How to use this document (the prompt)

You are building the **prototype** described in Section 4, in the order given by the milestones in Section 11, following the architecture in Sections 5-9 and the agent rules in Section 13. The prototype is a vertical slice: one escape room, playable co-op by 2-4 people on a home LAN, loaded from a pluggable room package, with one real CTF challenge wired to an in-world door.

Everything beyond the prototype is roadmap (Section 12). Do not build roadmap items unless a milestone says so. When this plan is silent, prefer the simplest thing that keeps the roadmap possible, and record the decision in `docs/DECISIONS.md`.

Two agents share the work. **Claude Code** is the orchestrator and implementer for all runtime code (Godot, Go, room logic, deployment). **Codex** (OpenAI Codex CLI, model `gpt-6.1-sol`) is the **asset design agent**: it builds 3D props, materials, and printed documents through Blender, and provides independent code review. Section 8.6 defines the handoff. Neither agent edits the other's lane without the review step in Section 13.

---

## 1. Vision

A platform, not a single game. Players meet in a moody, detailed 3D room and escape together, exactly like a physical escape-room venue, but virtual, online, and not bound to 60 minutes. Rooms are plug-in packages that anyone (including other people's AI agents) can author and drop in. Some rooms are classic (locks, ciphers, UV ink, hidden compartments). Some rooms are "escape room meets Hack The Box": a laptop prop in the room is a real vulnerable web app running in a container, and capturing its flag opens a real door in the 3D world. Rooms can last 60 minutes, 24 hours, or 48 hours, with teams dropping in and out.

### Pillars (use these to settle arguments)
1. **Feels like a real escape room.** First-person, physical props you pick up and inspect, locks that click, a countdown clock on the wall, in-fiction hints. Lighting and readability over polygon count.
2. **Co-op first.** Shared live world, shared team inventory and evidence board, nothing hidden inside one player's pockets. Talking is part of the puzzle.
3. **Rooms are plug-ins.** The core game knows nothing about any specific room. A room is a package built on a documented SDK, validated by tooling, authored by humans or agents.
4. **Real hacking, really sandboxed.** CTF props expose real services players attack with their own tools. Flags are validated server-side. Challenge containers can't hurt the host or other teams.
5. **Cheap to run.** LAN now, a home server behind a tunnel next, a single small VPS after that. Idle sessions cost nothing.

---

## 2. Decisions (locked)

These came from the owner interview and the research reports. Do not relitigate without a new decision record.

| Topic | Decision | Why |
|---|---|---|
| Engine | **Godot 4.7.x** (latest stable 4.x at build time; 4.7.2 at planning). Forward+ renderer. | Owner knows it; text-based scenes are agent-friendly; PCK runtime packs; built-in ENet multiplayer and headless dedicated-server export; MIT, $0. See `docs/research/01-engine-evaluation.md`. |
| Perspective | **First-person free roam** (WASD + mouse), with focused close-up views for locks/documents. | Closest to a physical room. |
| Multiplayer | **Shared live world on an authoritative dedicated server** (headless Godot process), 2-6 players, no host migration. | Long rooms must outlive any player's PC; dedicated server is simpler than host migration. |
| CTF execution | **Both**: light puzzles via an in-game terminal panel; real challenges via sandboxed Docker containers on the host, attacked with real tools from the player's PC. | Real targets are the differentiator; the in-game terminal keeps light rooms self-contained. |
| Room trust model | **Full Godot scenes + GDScript in packs, trusted authors only** (owner, friends, their agents). Packs are arbitrary code; treat them as such. | Maximum flexibility for the prototype. Hardened data-only / sandboxed mode is roadmap (Section 12). |
| Prototype scope | **Vertical slice: one room** ("Night Shift", Section 10), 60-minute format, 2-4 players, 5 classic puzzle steps + 1 real web CTF challenge, loaded from a pack. | Proves every layer end to end. |
| Hints | **Tiered text hints** (3 tiers per puzzle, requested in-game, logged). Hint data shaped so an **AI game master** can consume it later. | Authors must write hints anyway; AI GM is roadmap. |
| Backend language | **Go** for the platform service (API, session manager, challenge orchestrator, flag validation). GDScript for the game. YAML for room manifests. No other languages in the prototype. | Single static binary, first-class Docker SDK, easy to containerise; keeps the language count at two. |
| Persistence | **SQLite** in the prototype (pure-Go driver), **Postgres** when leaving the LAN. Session state is a JSON snapshot. | Zero ops on the LAN; identical schema later. |
| Voice | **Discord** (or any external voice). No in-game voice in the prototype. | Zero cost, zero moderation. |
| Client platforms | **Windows and Linux** desktop exports. No web, console, or VR. | LAN PCs are desktops; Godot web export loses the Forward+ renderer. |
| Game transport | **ENet (UDP)** on the LAN; **WebSocket** peer also supported from M2 so the same build can later ride a Cloudflare Tunnel. | Cloudflare Tunnel does not carry UDP. |
| Art direction | **Realistic PBR, dim and moody, spotlit workspaces**, built from CC0 libraries (Poly Haven, ambientCG, Kenney, Quaternius) plus a few hero props. Text on props must be readable at inspect distance. | Matches the physical-venue feel; achievable solo with CC0 assets. |
| Asset tooling | **Blender 5.2 LTS, driven headless by Python scripts** that are the reproducible source of every custom prop; glTF/GLB export into the Godot project. | Scripts can be regenerated, diffed, reviewed, and re-run in CI; no binary `.blend` files as the source of truth. |
| Asset design agent | **Codex CLI with `gpt-6.1-sol`** (high reasoning) writes and runs the Blender scripts, bakes textures, renders previews, and generates printed-document textures. Invoked from Claude Code through the `codex:rescue` skill or directly by the owner. | Owner's choice; keeps Claude Code focused on runtime code and gives a second model for art iteration and review. |
| Languages (amended) | GDScript (game), Go (platform, tools), YAML (rooms), **Python only inside `tools/blender/` and `tools/printables/`** (Blender's scripting language; never in the runtime). | Blender is scripted in Python; everything else stays at two languages. |

---

## 3. Glossary

- **Platform**: the Go service. Accounts (minimal), room catalog, sessions, flag validation, challenge orchestration, persistence, client download.
- **Game server**: a headless Godot process running one session of one room. Authoritative over all puzzle and world state.
- **Client**: the Godot desktop build players run.
- **Room pack**: a Godot `.pck` built from `game/rooms/<room_id>/`, plus its `room.yaml` manifest. The unit of plug-in content.
- **Room SDK**: `game/addons/escapebox_sdk/`, the node library (locks, containers, items, triggers, terminals) that room scenes are composed from. Handles replication so room authors never write netcode.
- **Session**: one team playing one room once. Has an id, a state snapshot, a timer, and zero or more challenge instances.
- **Challenge instance**: the Docker containers spawned for one session's CTF challenge, with per-session flags.
- **Puzzle graph / PDC**: the puzzle dependency chart declared in `room.yaml`; the server tracks which nodes are solved.
- **Asset agent**: Codex (`gpt-6.1-sol`) acting on an asset request (Section 8.6) to produce a Blender build script, a GLB, previews, and metadata.
- **Asset request**: a markdown spec in `assets/requests/<asset_id>.md` that fully describes a prop (dimensions, budgets, named parts, animations) so the asset agent can build it without further questions.

---

## 4. Prototype definition and acceptance

**Definition of done for the prototype (M5):**
1. Three people on three separate PCs on the home LAN (at least one Windows, one Linux) download the client from the host, join the same session, and complete "Night Shift" together.
2. The room is loaded from a `.pck` room pack at runtime; the client and server binaries contain no room-specific code.
3. One player captures the web challenge flag using real tools on their own machine (browser/curl/Burp) against a container on the host, submits it in-game, and a door unlocks for everyone.
4. A player who disconnects mid-session rejoins and sees the current state. The game server process is killed and restarted mid-session, and the team continues from the last snapshot.
5. Hints work: each puzzle offers 3 tiers, requests are logged, and the end screen shows time and hints used.
6. Frame rate: 60 fps at 1080p on a mid-range GPU (GTX 1660 / RX 580 class) with Forward+.
7. Everything runs from one `docker compose up` (platform + challenge images) plus one `escapebox-server` binary, on the Linux host, with a written runbook.

**Explicitly out of scope for the prototype:** accounts with passwords (use display names + a shared invite code), leaderboards, lobby chat, multiple concurrent sessions in the UI (the manager must support it, the UI need not), 24/48-hour room content (persistence must support it), AI game master, in-game voice, room validator beyond schema + graph checks, cloud deployment, VPN, VR, web client, Steam.

---

## 5. Architecture

```
  Player PC (Windows/Linux)                       Linux LAN host (the owner's box)
 +------------------------------+                +----------------------------------------------------+
 | Godot client                 |  HTTP :8080    |  platform (Go, one binary, in docker compose)       |
 |  - menu/lobby UI  ---------------------------->|   REST  /api/*      sessions, join tokens, hints,   |
 |  - room pack loader          |                |                     catalog, flag submission proxy |
 |  - first-person gameplay     |  ENet :7777/udp|   /download/*       client zips + version.json      |
 |  - SDK nodes (client side) --------------+    |   /internal/*       calls from game servers only     |
 |  - in-game terminal panel    |  (or WS) |    |   session manager   spawns escapebox-server per      |
 |  - flag submit UI            |          |    |                     session, idle-stops, restores    |
 +------------------------------+          |    |   orchestrator      docker: per-session networks,    |
 | Player's own tools           |          |    |                     challenge containers, flags      |
 |  browser / curl / nmap / ... --------+  |    |   store             SQLite (sessions, snapshots,     |
 +------------------------------+       |  |    |                     events, flags, hints)            |
                                        |  |    +-----------+---------------------+-------------------+
                                        |  |                | spawn/stop          | docker API
                                        |  v                v                     v
                                        | +-------------------------------+   +------------------------+
                                        | | escapebox-server (Godot       |   | challenge containers   |
                                        | |  headless) session=S room=R   |   |  net: esc_S (bridge,   |
                                        | |  - loads room pack            |   |   no egress)           |
                                        | |  - authoritative world +      |   |  web app :20xxx/tcp    |
                                        | |    puzzle graph state         |   |  ttyd    :21xxx/tcp    |
                                        | |  - snapshot -> platform       |   |  FLAG env injected     |
                                        | |  - flag RPC -> platform ------+-->|                        |
                                        | +-------------------------------+   +------------------------+
                                        +------------------------------------->  (published ports only)
```

**Who owns what**
- **Godot owns the world.** Movement, interaction, props, locks, inventory, hints UI, timer display, puzzle graph evaluation, replication.
- **Go owns the platform.** Sessions, tokens, persistence, Docker, flags, downloads. Nothing in Go knows what a "drawer" is.
- **The room pack owns content.** Scene, props, scripts using SDK nodes, `room.yaml` (manifest, puzzle graph, hints, CTF descriptors, solution).

**Ports (LAN defaults):** platform HTTP `8080`; game ENet `7777-7799/udp` (one per session); WebSocket game transport `7877-7899/tcp`; challenge services `20000-20999/tcp` (allocated per instance); ttyd terminals `21000-21099/tcp`. All configurable.

---

## 6. Game client and gameplay systems (Godot)

### 6.1 Project layout
```
game/
  project.godot
  core/                 # engine-side systems; never room-specific
    main.tscn           # boot: parse args, pick client or server mode
    net/                # peer setup (ENet/WS), join token, snapshot sync
    player/             # first-person controller, interaction raycast, avatar
    ui/                 # menu, lobby, HUD, inspect view, inventory, evidence board, hints, terminal panel, flag submit, end screen
    rooms/              # RoomLoader: load .pck, read room.yaml, instantiate entry scene
    puzzle/             # PuzzleGraph runtime (server-authoritative), HintService, SessionClock
    platform/           # HTTP client for platform /api and /internal
  addons/escapebox_sdk/ # Room SDK (Section 8). Public API for room authors.
  rooms/<room_id>/      # room packs in source form (exported to .pck). Prototype: rooms/night_shift/
  assets/core/          # curated CC0 prop/material library shared by all rooms
  tests/                # gdUnit4 tests
  export_presets.cfg    # client-win, client-linux, server-linux, room-pack-<id>
```

### 6.2 First-person controller
- `CharacterBody3D`, capsule, walk speed ~3 m/s, no jump, no crouch, no sprint (keeps non-gamers comfortable; see Escape Academy lesson). Mouse look with sensitivity setting, invert option, FOV 75-90.
- Interaction: screen-centre raycast (3 m) against `Interactable` SDK nodes; highlight outline + context prompt ("Examine", "Pick up", "Open"). Everything interactable must be visually distinct; no pixel hunts.
- Avatars: simple humanoid or capsule-with-headlamp for other players, name tag, interpolated at 15 Hz. Own movement is client-authoritative; server sanity-checks speed.

### 6.3 Inspect view
- Pick up any `Item`/`Document` to a close-up view: rotate with mouse, zoom, flip. Documents render as high-res textures with readable text at the inspect distance. UV layer appears when a UV torch is active. The Room series is the reference here.
- Inspecting broadcasts "X is examining the ledger" to teammates; documents can be co-inspected (no exclusive lock on reading).

### 6.4 Team inventory and evidence board
- **Team inventory** is server-owned and visible to all. Items show who is holding them. Anyone can use any item from the team inventory; "hand to player" is an intent, not a requirement. Picking up removes from the world for everyone (first intent wins; losers get "already taken").
- **Evidence board** (Tab): every document/photo examined by anyone is pinned automatically; players can add free-text notes and pin notes next to evidence. Shared and persisted in the snapshot. This addresses Escape Simulator's biggest complaint (information trapped in one inventory) and is essential for 24/48-hour rooms.

### 6.5 Locks and focused views
Keypad, dial, letter, directional, key locks open a focused UI (camera moves in, cursor freed). One operator at a time; spectators see the dials move live. Every input gives feedback (click, red/green LED). Correct code is checked **server-side**.

### 6.6 Hints
- Hint button in HUD opens the list of currently-open puzzles (those whose prerequisites are solved and which are unsolved). Player picks one; gets tier 1, then tier 2, then tier 3 (the answer). Each reveal is a server event, logged, counted on the end screen. No hard cap, no cost in the prototype (optional time penalty flag in `room.yaml`).
- Delivered in-fiction: a wall-mounted "facility intercom" panel shows the text and plays a chime.
- Automatic nudge: if no puzzle progress for N minutes (room-configurable, default 6), the intercom offers tier 1 of the most-blocking open puzzle. Opt-out per session.
- Data shape (in `room.yaml`) is per-puzzle ordered tiers plus `gm_notes`, so an AI GM can later read puzzle state + tiers + notes and improvise in character.

### 6.7 Session clock and end states
- Wall clock prop counts down from `duration_minutes`. Server owns the timer (start timestamp stored in the platform, survives restarts). On zero: room stays explorable, hints become free, "time's up" debrief. On exit: win screen with time, hints used, puzzle timeline.

### 6.8 In-game terminal panel
- A `Terminal` prop opens a panel in the HUD. Two modes, chosen by the prop:
  - **simulated**: a tiny fake shell driven by the room's script (`ls`, `cat`, custom commands), fully offline, for narrative/light puzzles. Never gates a real flag alone.
  - **remote**: embeds a WebSocket terminal to a per-session ttyd container (platform mints a one-time token). Prototype implements the plumbing with a minimal in-engine VT renderer (monochrome, no full xterm emulation); full xterm fidelity is roadmap.
- Every terminal prop also shows the challenge's **connection card** (URL/host:port the player attacks from their own machine) and a **flag submit field**.

### 6.9 Audio and look
- Ambient loop per room, spatial SFX for every interaction (lock click, drawer slide, maglock buzz), hint chime, win sting. Reverb bus per space.
- Lighting: baked or SDFGI global illumination, a few shadowed spotlights on puzzle workspaces, emissive screens, volumetric fog low. Colour-blind safe: never encode by colour alone; add labels/shapes. Accessibility settings: text scale, high-contrast UI, mouse sensitivity, FOV.

---

## 7. Multiplayer and server design (Godot)

### 7.1 Topology
- Client and server run the **same Godot project** with different export presets. `escapebox-server` is the Dedicated Server export (no rendering, `--headless`), launched by the platform's session manager:
  `escapebox-server --session <id> --room <room_id> --pack <path.pck> --port 7777 --platform http://127.0.0.1:8080 --token <server_token>`
- Transport: `ENetMultiplayerPeer` by default; `--transport ws` switches to `WebSocketMultiplayerPeer`. Same `MultiplayerAPI` either way.
- Tick: server physics 30 Hz; replication 15 Hz for transforms; puzzle/world state changes are reliable RPCs sent immediately.

### 7.2 Authority model (the one rule)
**Clients send intents. The server mutates state. State flows back as replicated properties or reliable RPCs.** No client ever sets `locked = false`. SDK nodes implement this pattern once; room scripts only react to signals.

- Intents: `request_interact(node_path, verb, payload)`. Server validates (range, prerequisites, item ownership), applies, broadcasts.
- World state table: `Dictionary[node_path] -> state` for every SDK node (lock state, container open/closed, item location: world/inventory/consumed, trigger fired, dial values, terminal unlocked, custom room vars). This table **is** the snapshot.
- Puzzle graph state: `Dictionary[puzzle_id] -> {solved, solved_at, hints_revealed}`.
- Late join / rejoin: server sends the full world table + puzzle state + evidence board + timer; client applies to its identically-structured scene tree, then subscribes to deltas. Node paths are stable because client and server instantiate the same pack scene.

### 7.3 Persistence
- Server POSTs the snapshot to the platform on every world-state change (rare) and every 30 s (timer, positions). Platform stores latest snapshot + appends to `session_events`.
- On start, if a snapshot exists for the session, the server restores it before accepting players.
- Idle stop: when zero players are connected for 5 minutes, the server exits with code 0 after a final snapshot. The platform restarts it on the next join. This is what makes 24/48-hour rooms free when nobody is playing.

### 7.4 Join flow
1. Client: `POST /api/sessions/{id}/join {display_name, invite_code}` -> `{host, port, transport, join_token}`.
2. Client connects via ENet/WS, sends `join_token` in the first RPC.
3. Server: `POST /internal/sessions/{id}/verify {join_token}` -> player identity. Reject on failure.
4. Server sends snapshot; client enters the room.

### 7.5 Flag flow
1. Player submits flag in the terminal UI -> `request_submit_flag(challenge_id, value)` to server.
2. Server: `POST /internal/sessions/{id}/flags {challenge_id, value, player_id}`.
3. Platform validates (per-instance HMAC flag or static hash, constant-time compare, rate limit 10 wrong/min/team with escalating cooldown, every attempt logged) -> `{accepted: bool}`.
4. Server emits `flag_accepted(challenge_id)`; the puzzle graph marks the node solved; room logic (SDK `FlagGate` node) unlocks whatever it is wired to; all clients see it.

### 7.6 Challenge instance flow
1. On session start, server reads `ctf.challenges` from `room.yaml` and calls `POST /internal/sessions/{id}/challenges/start`.
2. Platform orchestrator creates a per-session Docker network, generates per-instance flags, starts containers with `FLAG` env, allocates published ports, waits for healthchecks, returns handles `{challenge_id: {url|host:port, terminal_token}}`.
3. Server stores handles in world state; the `Terminal` prop shows the connection card when examined. Handles are the LAN host IP + port.
4. On session end or idle stop: platform tears down containers; flags are kept in the store so a restarted instance uses the same flags (HTB's lesson: stable flags within a session).

---

## 8. Room packs and the Room SDK

### 8.1 What a room pack is
A room is a directory `game/rooms/<room_id>/` inside the game project (room authors work in a clone of the game repo; this is the trusted-author model). It is exported with the `room-pack-<id>` preset, which includes only `res://rooms/<room_id>/**`, into `<room_id>-<version>.pck`. The platform catalog lists packs with their sha256; client and server download the pack from the platform and load it with `ProjectSettings.load_resource_pack(path, false)` (never `replace_files=true`), then verify `res://rooms/<room_id>/room.yaml` exists and its `id` matches.

Required contents:
```
game/rooms/<room_id>/
  room.yaml            # manifest + puzzle graph + hints + ctf + solution (Section 8.3)
  room.tscn            # entry scene; root node has RoomRoot (SDK) script
  scenes/              # sub-scenes
  scripts/             # room GDScript; may only touch SDK API + its own nodes
  assets/              # room-specific models/textures/audio/docs; CC0 or owned; ATTRIBUTION.md
  ctf/<challenge_id>/  # Dockerfile + app for each challenge (built by platform, not shipped in the .pck)
  README.md            # how to play-test, design notes
```

### 8.2 Room SDK nodes (`addons/escapebox_sdk/`)
All nodes replicate themselves, emit signals on the server and on clients, and expose `@export` parameters so most rooms need little or no script. Node names are the public API; keep them stable and additive.

| Node | Purpose | Key exports / signals |
|---|---|---|
| `RoomRoot` | Scene root. Registers the room with the runtime, reads `room.yaml`, exposes `vars` (room variables incl. per-session randomised ones). | `signal room_ready`, `signal puzzle_solved(id)`, `signal session_finished(win)` |
| `Interactable` (base) | Raycast target with prompt text and verbs. | `verbs: Array[String]`, `signal interacted(player, verb)` |
| `Item` | Pick-up-able object with inspect view, optional UV layer, optional combine recipe. | `item_id`, `inspect_mesh`, `uv_texture`, `combines_with`, `combine_result` |
| `Document` | Readable paper/photo/book; pins to evidence board on first read. | `text_md` or `texture`, `uv_text` |
| `Container` | Drawer/cabinet/safe/hatch with optional lock child and item slots. | `open`, `signal opened`, `locked_by: Lock` |
| `Lock` (+ `KeypadLock`, `DialLock`, `LetterLock`, `KeyLock`, `DirectionalLock`, `MaglockGate`) | Server-checked lock; focused UI on client. | `code` (may reference `{{var}}`), `signal unlocked` |
| `Door` | Walk-through door or exit; `is_exit` ends the session on open. | `locked_by`, `is_exit` |
| `Mechanism` (`Lever`, `Switch`, `Button`, `Dial`, `PatchPanel`, `FuseBox`) | Multi-state props that feed puzzles. | `state`, `signal changed(state)` |
| `TriggerVolume` | Fires when a player enters/leaves. | `signal entered(player)` |
| `UVTorch` | Item that enables UV layers within range. | |
| `Terminal` | In-game terminal prop: simulated or remote; shows connection card and flag field for `challenge_id`. | `mode`, `challenge_id`, `script` (simulated commands) |
| `FlagGate` | Unlocks/activates a target when `flag_accepted(challenge_id)` fires. | `challenge_id`, `targets` |
| `PuzzleMarker` | Declares that a puzzle in `room.yaml` is solved when this node reaches a state. (Optional sugar; most `solved_when` conditions are declared in YAML.) | `puzzle_id`, `solved_state` |
| `Intercom` | Hint delivery surface. | |
| `SessionClock` | Countdown display bound to the server timer. | |
| `AmbientZone` | Reverb/ambience per space. | |

Rule for room scripts: they may connect to SDK signals and call SDK methods (`set_state`, `unlock`, `give_item`, `narrate`, `play_sfx`, `set_var`). They must not call `rpc`, touch `multiplayer`, read files outside the pack, or spawn network requests. The prototype does not enforce this (trusted authors); the validator warns on obvious violations (`grep` for `rpc(`, `HTTPRequest`, `OS.execute`, `FileAccess` outside `res://rooms/<id>`).

### 8.3 `room.yaml` (schema v1, prototype)
```yaml
spec_version: 1
id: night_shift                    # [a-z0-9_]+, matches directory name
title: Night Shift
version: 0.1.0
authors: [binaryc0de]
requires: { platform: ">=0.1", sdk: ">=0.1" }
mode:
  duration_minutes: 60             # 60 | 1440 | 2880 typical
  players: { min: 1, max: 4 }
  auto_nudge_minutes: 6
entry_scene: res://rooms/night_shift/room.tscn
briefing:
  intro_md: briefing/intro.md
  win_md: briefing/win.md
  timeout_md: briefing/timeout.md
  gm_notes_md: briefing/gm_notes.md   # for human/AI game masters; never shown to players
variables:                          # per-session randomisation, injected into RoomRoot.vars
  cabinet_code: { type: digits, length: 4 }
puzzles:                            # dependency DAG; ids referenced by hints and solution
  - id: find_uv
    title: Find the UV torch
    requires: []
    solved_when: { item_picked_up: uv_torch }
    hints:
      - "The night shift keeps odd tools in odd places. Check the desk."
      - "The desk's top drawer isn't locked. Dig under the papers."
      - "The UV torch is under the papers in the top desk drawer."
  - id: whiteboard_code
    requires: [find_uv]
    solved_when: { node_state: { path: "Cabinet/Keypad", state: unlocked } }
    hints: [ "...", "...", "..." ]
  # ...
exit:
  puzzle: override_door             # the puzzle whose solve ends the session with a win
ctf:
  challenges:
    - id: intranet
      title: Kestrel Intranet
      kind: service                 # file | service | terminal
      build: ctf/intranet           # Dockerfile context inside the room dir
      ports: [{ container: 8080, protocol: http }]
      flag: { type: per_instance, format: "FLAG{{{nonce}}}", inject_env: FLAG }
      healthcheck: { path: "/healthz", timeout_s: 30 }
      resources: { cpu: 0.5, memory_mb: 256 }
      hints: [ "...", "...", "..." ]
      unlocks: rack_cage            # documentation only; the FlagGate node does the work
solution:                           # replayed by the auto-solver (M6) and used by play-testers
  - { act: pick_up, item: uv_torch }
  - { act: use_on, item: uv_torch, target: Whiteboard }
  - { act: input_code, lock: "Cabinet/Keypad", value: "{{cabinet_code}}" }
  - { act: submit_flag, challenge: intranet, value: "{{flags.intranet}}" }
  # ...
```
`solved_when` vocabulary (prototype): `item_picked_up`, `node_state {path, state}`, `flag_accepted {challenge}`, `all_of [..]`, `any_of [..]`. Additive growth only.

### 8.4 Tooling (prototype subset)
- `tools/roomcheck` (Go CLI): validates `room.yaml` against the JSON Schema in `docs/schema/room.schema.json`; checks puzzle DAG is acyclic with a reachable exit; every puzzle has >=3 hints; every `node_state` path exists in `room.tscn` (parses the text scene); every CTF challenge has a Dockerfile and healthcheck; no hard-coded real flags; room scripts don't use forbidden APIs. Run in CI and before publishing a pack.
- `tools/packroom` (shell/Go): exports the pack with Godot headless, computes sha256, writes a catalog entry.
- Auto-solver, prefab catalog browser, hot reload: roadmap.

### 8.5 Room author guide
`docs/ROOM_AUTHORING.md` (written in M0, kept under ~150 lines) is the document another person's AI agent reads to build a room. It must contain: the directory layout, the SDK node table, the `room.yaml` schema with a worked example, the design rules from Section 9, CTF rules (flags are templates, never literal; containers must pass healthcheck; no egress), the commands to validate/pack/test, and what "done" means (roomcheck passes, 3 blind play-tests logged in README).

### 8.6 Asset pipeline and the Codex asset agent

Full detail and templates live in `docs/ASSET_PIPELINE.md`. The contract in brief:

**Division of labour**
- **Claude Code** decides *what* assets exist (from the room design and SDK needs), writes the asset request, integrates the GLB into Godot (import settings, SDK node wiring, materials tweaks in-engine), and reviews the result in-game.
- **Codex (`gpt-6.1-sol`)** decides *how* to build it in Blender: writes `tools/blender/props/<asset_id>.py`, runs it headless, bakes textures, exports GLB, renders previews, writes metadata, and iterates on feedback. Codex also generates printed documents (notes, certificates, posters) as textures via `tools/printables/`.
- Either agent may run `codex:review` for an independent review of the other's diff. Codex does not edit `game/core/`, `game/addons/escapebox_sdk/`, or `platform/` except through a review-gated rescue task explicitly requested by the owner.

**Source of truth is the script, not the `.blend`.** Every custom prop is produced by a deterministic Python script that runs under `blender -b --python <script>` with no UI. `.blend` files may be committed as cached intermediates but are regenerable. CC0 downloads from Poly Haven/Kenney/Quaternius are stored as-is in `game/assets/core/third_party/` with `ATTRIBUTION.md`; Codex may post-process them (decimate, re-pack textures, split parts) through the same script pipeline.

**Asset request -> deliverable**
1. Claude writes `assets/requests/<asset_id>.md` from the template in `docs/ASSET_PIPELINE.md`: purpose and room, real-world dimensions in metres, style references, triangle budget, texture budget and maps, named sub-meshes needed by the SDK (e.g. each keypad button is a separate mesh named `btn_0`..`btn_9`, `btn_enter`), origin and forward axis, collision shape, animations (`open`, `close`, with frame ranges), LOD needs, text that must be legible.
2. Claude hands off through the `codex:rescue` skill with a prompt that cites the request file, or the owner runs Codex directly in the repo. Invocation shape:
   `node <plugin>/scripts/codex-companion.mjs task --write --background --model gpt-6.1-sol "Build the asset described in assets/requests/<asset_id>.md following docs/ASSET_PIPELINE.md. ..."`
   (`gpt-6.1-sol` is also the default model in `~/.codex/config.toml`; pass it anyway so the plan is explicit.)
3. Codex produces: `tools/blender/props/<asset_id>.py`, `game/assets/core/props/<asset_id>.glb` (or `game/rooms/<room>/assets/` for room-specific props), `assets/previews/<asset_id>_{front,iso,detail}.png`, `assets/meta/<asset_id>.json` (triangle count, texture list and sizes, bounds, named parts, animations, script hash), and a short `assets/reports/<asset_id>.md` of what it did and any deviations from the request.
4. `tools/assetcheck` (Go, part of CI) verifies budgets, naming, origin, that the GLB loads, and that `meta.json` matches the request.
5. Claude imports into Godot, wires the SDK node, screenshots it in the greybox room, and either accepts (closes the request) or appends feedback to the request file and resumes the Codex task (`--resume`).

**Godot import conventions (Codex must follow)**: 1 unit = 1 metre; Y-up handled by the glTF exporter; origin at the base centre, +Z forward (Godot `-Z` is forward in-engine, so forward-facing props look down `-Z` after import; document the convention once and follow it everywhere); `-col` suffix on mesh names to auto-generate collision, `-noimp` for helper objects; PBR metallic/roughness workflow, textures `<= 2048 px`, packed ORM where possible; animations named exactly as the request says; props `<= 20k` triangles unless the request marks them `hero` (`<= 60k`); no modifiers left unapplied; all materials named `M_<asset_id>_<part>`.

**Printed documents** (`tools/printables/`): SVG templates rendered to PNG (via Blender's compositor or a Python renderer available in the Blender bundle) at `>= 2048 px` long edge, with real typography, wear/stain layers, and a UV-ink variant texture when the document carries UV content. Codex owns these; Claude supplies the text in the request.

**Optional interactive mode**: a Blender MCP server can let Codex drive a live Blender for exploratory work, but anything kept must be captured back into the headless script. CI only runs headless.

---

## 9. Design rules for rooms (from `docs/research/02-escape-room-design.md`)

Every room, including the prototype, follows these. The validator enforces the mechanical ones.

1. **Structure**: path-based / multi-linear. 2-4 parallel threads that converge on a meta. Linear only at the climax. A 60-minute room has ~15-25 steps; the first solve lands within 2-3 minutes.
2. **Fair puzzles**: single answer, self-validating, clue visibly linked to lock (label, colour+shape, location), feedback on every input, no outside knowledge, no external Googling, no destroyable states, <=5 minutes to execute once understood.
3. **No designed red herrings and no pixel hunts.** Every interactable matters. Clutter is décor-only and not interactable.
4. **Parallelism**: distribute clues across zones so 3-4 people spread out. Bottleneck steps either take <2 minutes or involve everyone.
5. **Hints**: 3 escalating tiers per puzzle, last tier is the answer, delivered in fiction. "If a puzzle almost always needs a hint, it's broken."
6. **Cold start**: minimal briefing; teach controls in a 60-second airlock before the clock starts.
7. **Diegetic**: every puzzle has a reason to exist in the story.
8. **Accessibility**: never colour alone; readable text at inspect distance; lit workspaces even in dark rooms.
9. **CTF-specific**: the challenge must be solvable with free tools; the connection card tells players exactly where to point them; difficulty labelled (easy/medium/hard); never require brute force that would trip the rate limit; the in-world clues should narrow the attack (e.g., a username on a sticky note) so it feels like an escape room, not a blind pentest.
10. **Long rooms (24/48h)**: cap simultaneously open threads, persist evidence board and activity log for returning teammates, ramp hint availability with elapsed time, keep high-variance puzzles off the critical path.
11. **Playtest blind** with at least 3 groups before calling a room done; log hesitation points and solve times in the room README.

---

## 10. Prototype room: "Night Shift"

**Premise.** 23:10, Kestrel Logistics regional office. You are contractors finishing a server migration when the building's badge system crashes and the sysadmin office maglock seals you in. The night security guard is on the other side of the building and the generator is failing. Find the maglock override before the UPS dies (60 minutes). Two spaces: the sysadmin office (desk, whiteboard, filing cabinet, laptop, wall certificates, intercom) and a caged server alcove (rack, patch panel, UPS) behind a maglocked cage door.

**Puzzle dependency chart** (edges are prerequisites, bushy by design):

```
 [A1 find UV torch] ---> [A2 UV whiteboard -> 4-digit] ---> [A3 open cabinet]
      (desk drawer)                                            |          |
                                                     network diagram    USB stick
                                                               |          |
 [B1 username on sticky note] ----------\                      |          v
 [B2 password poster (WiFi card, back)] --+--> [B3 log in to intranet] --> [B4 IDOR on tickets -> FLAG] --> [B5 submit flag -> cage opens]
                                                                                                                      |
                                                                              [C1 patch panel per diagram -> UPS powers door panel]
                                                                                                                      |
 [D1 site id on inspection certificate] ----\                                                                        |
 [D2 rack id stencilled inside cage] --------+--> [META override code = site id + rack id] <---------------------------+
                                                                  |
                                                            [EXIT door opens]
```

**Step detail (par 35-45 minutes for a team of 3):**
- **A1** UV torch under papers in the unlocked top desk drawer. (search, easy)
- **A2** UV reveals 4 digits on the whiteboard (per-session variable `cabinet_code`). (UV, easy)
- **A3** Filing cabinet keypad opens: laminated network diagram (patch panel mapping) + USB stick (an `Item` that, when inspected, offers a downloadable `shadow.bak` via the platform file endpoint; decorative in the prototype, used by the hard-mode variant).
- **B1** Sticky note on monitor: username `mreyes`. **B2** "Guest WiFi" card on the pinboard, back side (inspect/flip) has the sysadmin's reused password. (observation, easy)
- **B3** Laptop `Terminal` prop (mode remote-lite: shows connection card `http://<host>:<port>/`). Player logs into the intranet container from their own browser. (web, easy)
- **B4** Tickets page has `?id=1042`; changing to neighbouring ids reveals a facilities ticket from the maglock vendor containing `FLAG{...}`. (IDOR, easy-medium; real tools optional, curl suffices)
- **B5** Submit flag in-game -> `FlagGate` releases the cage maglock; audible buzz, cage swings. (CTF-to-world bridge)
- **C1** Inside cage: `PatchPanel` with 4 loose cables; plug per the network diagram -> UPS "bypass" relay closes, exit door keypad powers on (LED screen lights). (pattern, medium)
- **D1** Fire inspection certificate on the office wall shows "SITE 417". **D2** Stencil inside the cage: "RACK 062". The door panel reads "OVERRIDE: SITE+RACK". (observation + meta)
- **META** Enter `417062` on the exit `KeypadLock` -> maglock releases -> win.

**CTF challenge `intranet`**: small Go or Python web app in a container (one image, <50 MB): login (fixed creds from B1/B2), a tickets list with IDOR, a `/healthz`. Flag read from `FLAG` env. No egress. Hard-mode variant (roadmap): no password on the card; crack the hash from the USB stick with a wordlist derived from room clues.

**Hints**: three tiers for every node above, written in the voice of the night guard over the intercom. **Briefing**: 45-second airlock corridor teaches walk/look/interact/inspect/evidence board, then the maglock slams.

**Assets**: office shell and furniture from Poly Haven / Kenney / Quaternius CC0; server rack, patch panel, UPS, maglock, keypad, UV torch as hero props (modelled or generated, then decimated). All text as readable textures (printed documents at >=1024 px on the long edge).

---

## 11. Milestones

Each milestone ends with a demo and an entry in `docs/STATUS.md`. Do them in order; later ones depend on earlier ones. Estimated effort assumes an agent-assisted solo developer.

### M0: Repo and specs (1-2 days)
- Repo layout (Section 14), `CLAUDE.md`/`AGENTS.md`, `docs/DECISIONS.md` (ADR log, seeded from Section 2), `docs/STATUS.md`.
- `docs/schema/room.schema.json` for Section 8.3; `docs/ROOM_AUTHORING.md` first draft; `docs/API.md` listing platform endpoints (Section 7.4-7.6 plus catalog/download).
- Godot project skeleton with export presets (client-win, client-linux, server-linux, room-pack-night_shift), gdUnit4 installed, CI runs `godot --headless --import` and tests.
- Go module `platform/` with `go test`, `tools/roomcheck` skeleton.
- Install Godot 4.7 on the dev box (not on PATH at planning time); confirm `blender -b --version` runs headless (Blender 5.2.2 LTS is installed at `~/.local/bin/blender`).
- `docs/ASSET_PIPELINE.md` finalised; `tools/blender/build_assets.sh` (runs every `tools/blender/props/*.py` headless), `tools/assetcheck` skeleton, `assets/requests/` with the template.
- **First Codex handoff (smoke test)**: Claude writes `assets/requests/keypad_4.md`; Codex builds it via `gpt-6.1-sol`; the GLB imports into Godot with named buttons and passes `assetcheck`. This proves the two-agent loop before any real art is needed.
- Acceptance: CI green on an empty project; `roomcheck` rejects a `room.yaml` with a cyclic graph; `keypad_4.glb` visible in a Godot test scene with per-button meshes.

### M1: Single-player room core (1-2 weeks)
- First-person controller, interaction raycast, highlight/prompt, inspect view, team inventory UI, evidence board, locks with focused UI, containers, items, UV torch + UV layers, documents, doors, mechanisms (lever, patch panel), session clock, hints UI with tiers, intercom.
- `RoomLoader` loads a `.pck` from a path, reads `room.yaml`, instantiates the entry scene. Dev mode loads from `res://rooms/` without a pack.
- `PuzzleGraph` runtime evaluates `solved_when` and emits `puzzle_solved`.
- A greybox version of Night Shift (no art) is playable solo from start to win, offline, with a stub for the CTF step (dev flag auto-accepts a flag).
- Acceptance: play greybox Night Shift solo to the win screen from a `.pck`; gdUnit4 tests for locks, inventory, puzzle graph.

### M2: Multiplayer (1-2 weeks)
- Dedicated server export, `--headless` launch with args, ENet and WebSocket peers, join token handshake (stubbed platform), player spawning, avatar replication, intent RPCs on every SDK node, world state table, snapshot send on join, snapshot export/import to JSON.
- Pickup conflict handling, co-inspection, evidence board sync, hint requests through server, server-owned timer.
- Acceptance: 3 clients (2 on one PC + 1 remote LAN PC) play greybox Night Shift together; a client disconnects and rejoins with correct state; server restarted from a saved JSON snapshot resumes.

### M3: Platform service and CTF orchestration (1-2 weeks)
- Go `platform`: SQLite store, `/api/catalog`, `/api/sessions` (create with invite code, join), `/download/*`, `/internal/*` (verify, snapshot, events, flags, challenges start/stop), session manager (spawn/stop/restore `escapebox-server`, idle stop), orchestrator (Docker SDK: per-session network with no egress, container hardening `cap_drop ALL`, `no-new-privileges`, read-only rootfs, pids/mem/cpu limits, port allocation, healthcheck wait, teardown), per-instance HMAC flags, static-hash flags, constant-time compare, rate limiting, submission log, optional ttyd container per session with one-time token.
- Godot `core/platform` client: join flow, snapshot push, flag RPC path, challenge handles into world state; `Terminal` connection card; `FlagGate`.
- `intranet` challenge image for Night Shift.
- Acceptance: end-to-end flag flow unlocks the cage on all clients; wrong flags are rate-limited; `docker compose up` brings platform + builds challenge image; killing the server mid-session and rejoining works through the platform.

### M4: Night Shift content and polish (2-3 weeks)
- Full art pass: office and cage shells, props, documents as readable textures, lighting (SDFGI or baked), audio, airlock briefing, win/timeout screens, intercom voice text.
- **Asset batch for Codex** (one request file each, built in parallel background tasks, reviewed in-engine by Claude): hero props `maglock_door_panel`, `exit_keypad_6`, `cage_door_maglock`, `server_rack_42u`, `patch_panel_24` (+ 4 loose cables as separate items), `ups_tower`, `uv_torch`, `filing_cabinet_keypad`, `laptop_open`, `intercom_panel`, `wall_clock_countdown`, `desk_3drawer`; printables `sticky_note_username`, `wifi_card_front_back`, `fire_inspection_certificate`, `network_diagram_laminated`, `whiteboard_uv_layer`, `rack_stencil`. Shells, chairs, shelves, cables trays, and décor come from CC0 libraries, post-processed by Codex where needed.
- Lighting and material polish happen in Godot (Claude's lane); mesh and texture fixes go back to Codex through the request file.
- All hints written; `room.yaml` complete; `roomcheck` passes.
- Performance pass to hit 60 fps on the target GPU; Windows + Linux client exports.
- Acceptance: 3 blind play-tests (log in `game/rooms/night_shift/README.md`), every puzzle solved without tier-3 hints by at least one group.

### M5: LAN deployment and prototype sign-off (3-5 days)
- `deploy/docker-compose.yml` (platform, challenge images, optional Caddy), `deploy/RUNBOOK.md` (host prep incl. rootless Docker, firewall ports, how to add a room pack, how to start a session, how to recover), client download page with version check, LAN discovery (type IP; UDP broadcast optional).
- Run the Section 4 acceptance checklist on real hardware and record results in `docs/STATUS.md`.

### M6+: see roadmap.

---

## 12. Roadmap after the prototype (not for the prototype)

1. **Room SDK for outside agents**: `roomcheck` grows the full validator list from `docs/research/05-room-plugin-spec.md` (asset refs, orphan puzzles, dead-end items, linearity metric); headless auto-solver replays `solution`; prefab catalog with screenshots; hot reload of `room.yaml`; a second room built entirely by an AI agent from `ROOM_AUTHORING.md` as the acceptance test.
2. **Hardened room mode**: data-only rooms (YAML + prefabs, no scripts) and/or godot-sandbox for untrusted authors; pack signing with author keys; forbidden-API checks become errors.
3. **Remote play from home**: Cloudflare Tunnel for the platform HTTP, WebSocket game transport through the tunnel, or Tailscale node sharing for friends; TLS via Caddy. Still EUR 0.
4. **Long-form rooms**: a 24h room using evidence board, activity log, time-ramped hints, idle stop, async teammates; team notifications; "open thread" caps.
5. **AI game master**: Claude persona fed `gm_notes`, puzzle state, hint tiers, and the team's recent events; speaks through the intercom; tiered hints remain the fallback. (Load the `claude-api` skill before implementing.)
6. **CTF depth**: file challenges (stego/forensics via `/api/files`), pwn via nsjail images, per-team WireGuard for "full box" rooms, gVisor runtime for RCE-by-design challenges, checker-script flags, hard-mode variants.
7. **Accounts and social**: real accounts, teams, leaderboards, room ratings, GM console (watch a session, push a hint, trigger an unlock).
8. **Cloud**: Postgres, single Hetzner-class VPS or Oracle free ARM if obtainable, same compose file; later Edgegap for 60-minute rooms or Agones only if concurrency demands it. Hathora is gone; do not plan on it.
9. **In-game voice**, proximity chat, asymmetric-information primitives (per-player visibility, radio channels), VR, web client (Compatibility renderer) if ever wanted.

---

## 13. Agent operating rules

1. **Read first**: this file, `docs/DECISIONS.md`, `docs/STATUS.md`, then the research report relevant to your task. Do not re-research what the reports already settled; do cite them when you rely on them.
2. **Work the current milestone only.** Pick the next unchecked item in `docs/STATUS.md`. If the plan is ambiguous, choose the simplest option that keeps the roadmap possible, implement it, and add a short ADR to `docs/DECISIONS.md` (context, decision, consequences). If the choice would materially change scope or cost, stop and ask the owner.
3. **Never put room-specific knowledge in `core/`, `addons/escapebox_sdk/`, or `platform/`.** If Night Shift needs something, add a generic SDK capability and use it from the room.
4. **Authority rule** (Section 7.2) is non-negotiable: clients send intents; the server decides.
5. **Security defaults**: challenge containers hardened as in M3; no egress; flags are templates; never log a flag value in plaintext; `load_resource_pack(..., false)`.
6. **Tests**: GDScript via gdUnit4 for SDK nodes, puzzle graph, snapshot round-trip; Go via `go test` for store, flags, orchestrator (use a fake Docker client), rate limiter; `roomcheck` on every room. CI must stay green. Report test output honestly; if something is untested, say so in `STATUS.md`.
7. **Conventions**: GDScript typed, `snake_case`, one class per file, `class_name` for SDK nodes, signals over polling, `@export` for author-facing params. Go: standard layout, `internal/` packages, `errors.Is/As`, context everywhere, no global state. Python (asset tooling only): one script per asset, no network calls, deterministic output, runs under `blender -b`. YAML keys `snake_case`. Commit messages in imperative mood, one logical change per commit. Do not add dependencies without an ADR; prefer the standard library and Godot built-ins.
8. **Assets**: CC0 or owner-made only; record every external asset in `ATTRIBUTION.md` with source URL and licence. Keep textures <=2048 px, props <=20k triangles unless hero.
9. **Docs are deliverables**: keep `ROOM_AUTHORING.md`, `API.md`, `RUNBOOK.md` current with the code in the same change.
10. **Definition of done** for any task: code + tests + docs + `STATUS.md` updated + a one-paragraph note of what was verified by actually running it (which command, which machines).
11. **Don't**: build roadmap items, add a lobby chat, add accounts/passwords, switch engines or languages, introduce Kubernetes, or add in-game voice during the prototype.
12. **Codex handoffs (Claude side)**: never model props yourself in Godot primitives beyond greybox. For anything that needs to look real, write an asset request (Section 8.6, template in `docs/ASSET_PIPELINE.md`) and hand it to Codex through the `codex:rescue` skill with `--write --background --model gpt-6.1-sol`. One request per asset; batch independent assets as parallel background tasks. Review the deliverable in Godot, not just the preview PNGs. Feedback goes into the request file's "Revision notes" section, then resume the same Codex task.
13. **Codex rules (Codex side, mirrored in `docs/ASSET_PIPELINE.md`)**: read the request file and the pipeline doc first; build only the requested asset; the script is the deliverable and must re-run cleanly headless; stay inside `tools/blender/`, `tools/printables/`, `assets/`, and the target asset directory; write `meta.json` and the report; do not touch runtime code or `room.yaml`; do not download assets whose licence is not CC0 or CC-BY, and record any download in `ATTRIBUTION.md`.
14. **Reviews**: before closing a milestone, run `codex:review` on the branch for an independent pass; triage its findings in `STATUS.md`. The owner may enable the stop-time review gate (`/codex:setup --enable-review-gate`) to require it on every stop.

---

## 14. Repository layout

```
escapebox/
  PLAN.md                     # this file
  CLAUDE.md / AGENTS.md       # "read PLAN.md first" + the rules in Section 13
  docs/
    DECISIONS.md              # ADR log
    STATUS.md                 # milestone checklist and verification notes
    API.md                    # platform endpoints
    ROOM_AUTHORING.md         # guide for room authors and their agents
    ASSET_PIPELINE.md         # Codex asset-agent contract, request template, Blender conventions
    schema/room.schema.json
    research/                 # the five research reports behind this plan
  game/                       # Godot 4.7 project (client + server + SDK + rooms)
    core/  addons/escapebox_sdk/  rooms/night_shift/  assets/core/{props,third_party}/  tests/
  platform/                   # Go service: cmd/platform, internal/{api,store,sessions,orchestrator,flags}
  assets/                     # asset-agent workspace (not shipped)
    requests/<asset_id>.md    # Claude -> Codex specs
    previews/  meta/  reports/
  tools/
    roomcheck/                # Go CLI validator
    packroom/                 # export + hash + catalog entry
    assetcheck/               # Go CLI: budgets, naming, GLB load, meta vs request
    blender/                  # Codex's lane: props/<asset_id>.py, common/ (export, bake, preview helpers), build_assets.sh
    printables/               # Codex's lane: SVG templates -> PNG document textures
  deploy/
    docker-compose.yml  Caddyfile  RUNBOOK.md
  .github/workflows/ci.yml    # godot import + gdUnit4, go test, roomcheck on all rooms
```

---

## 15. Risks and open questions

**Risks**
- *Visual bar*: "really pretty good graphics" with CC0 assets in Godot is achievable but lighting and readable props take iteration. Mitigation: art pass is its own milestone (M4) with a target GPU and fps.
- *Scope creep*: the platform idea invites building a lobby, accounts, editors. Mitigation: Section 4 out-of-scope list and rule 13.11.
- *Room packs are code*: a malicious or buggy pack can crash or compromise server and clients. Accepted for trusted authors; hardened mode is roadmap item 2. The platform must never run with Docker socket access from inside a Godot process.
- *Docker on the host*: rootless Docker + gVisor have edge cases; test early in M3 on the actual host.
- *Target hardware*: Forward+ needs a Vulkan-capable GPU on every LAN PC; keep a Compatibility-renderer fallback in mind but do not build for it in the prototype.
- *Node-path-based replication* assumes identical scene trees on client and server; dynamically spawned nodes must go through the SDK so paths stay stable.
- *Two-agent drift*: Codex and Claude can disagree on conventions (axes, naming, budgets). Mitigation: the request file and `assetcheck` are the contract; the M0 keypad smoke test exercises the loop before real art.
- *Blender version churn*: scripts target Blender 5.2 LTS; pin the version in `build_assets.sh` and fail loudly on mismatch.

**Open questions for the owner (answer in `docs/DECISIONS.md` when known)**
1. Which Linux box hosts the prototype (CPU/RAM, is rootless Docker already set up)? Determines container limits and whether gVisor is feasible.
2. Are the LAN player PCs Windows, Linux, or mixed, and what GPUs? Sets the M4 performance target precisely.
3. Is a 60-second control-tutorial airlock acceptable, or should the room start cold with a controls card on the wall?
4. Should the prototype room ship the "hard mode" CTF variant (hash cracking) as a toggle, or stay single-difficulty?
5. Project name for real: keep `escapebox` or pick something that can live on a store page later.

---

## 16. References

- `docs/research/01-engine-evaluation.md`: Godot vs Unreal vs Unity vs web, packaging, sandboxing, costs.
- `docs/research/02-escape-room-design.md`: design principles, puzzle taxonomy, lessons from Escape Simulator and peers, long-form hunts.
- `docs/research/03-ctf-integration.md`: CTFd/rCTF/HTB/THM architectures, challenge-to-prop mapping, flag validation, isolation.
- `docs/research/04-multiplayer-hosting.md`: authoritative server design, persistence, LAN specifics, 2026 cloud/free-tier reality, tunnel options.
- `docs/research/05-room-plugin-spec.md`: modding precedents, room spec sketch, prefab list, validator checks, asset sourcing.
- `docs/ASSET_PIPELINE.md`: the Codex asset-agent contract, request template, Blender/Godot conventions, and handoff commands.
