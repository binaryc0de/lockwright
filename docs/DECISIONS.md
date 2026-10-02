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
