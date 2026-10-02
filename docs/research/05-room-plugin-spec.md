# Pluggable room packages and AI-agent authoring: research (as of 2026-10-01)

> Research report produced by a sub-agent during planning. NOTE: the owner chose the "full Godot scenes/scripts, trusted authors" trust model for the prototype, so the "zero executable content" stance below is the *future* hardened mode, not the prototype rule. The manifest, puzzle-graph, validator and prefab ideas apply to both.

## 1. What the precedents teach

**Spectrum of trust models**
- **No scripts, pure data** - Minecraft datapacks (JSON + `pack.mcmeta` with `pack_format`/`min_format`/`max_format`; out-of-range packs warn and need confirmation). Safest; expressiveness via a fixed vocabulary of "function"-like actions. Portal 2 PeTI works similarly: `editoritems.txt` defines a fixed palette of items with `Properties` that export as `$fixup` variables into pre-built instances; the puzzle file only references items + connections. This is the closest precedent to "compose prefabs, don't model."
- **Interpreted sandbox with allowlisted API** - Escape Simulator (Lua 5.2 via MoonSharp; scripts attach to Logic "Script" objects; events like `Init/Update/SwitchDone/TriggerEnter/DialMoved/Unlock`; typed handles to Switch/Lock/Slot/Trigger/Dial/Turnable; `api.*` helpers). Factorio (Lua, tight sandbox, no sockets, `info.json` with `dependencies` strings like `? optional-mod >= 1.2`, `factorio_version`). Roblox Luau (allowlist stdlib, no io/os, capability-gated threads). All run on the authors' own game loop and exposed types; none give raw engine access.
- **Native code, trust-based** - RimWorld (XML Defs + optional C# DLL; `About.xml` with `packageId`, `supportedVersions`, `loadAfter/loadBefore`, PatchOperations), Garry's Mod (`addon.json` -> `.gma`, Lua shipped to clients), Godot Mod Loader (`manifest.json` with namespace-name IDs, semver, `compatible_game_version`, script-extension chaining), Unreal SimpleUGC/mod.io ModioUGC (PAK mount at runtime; mod.io says "sandboxed storage", not sandboxed code). Appropriate only for trusted authors.
- **WASM sandbox** - hordeforge/7dtd-wasm ("Quarantine"): wasm32-wasip1 guests under Wasmtime with fuel budgets, memory caps checked at load, module size cap, ABI-only host imports (`log`, `send_chat`, `queue`, `sense`), layered `wasm.toml`/`wasm-mod.toml` limits where a mod may only tighten memory, and "a guest fault never throws." Extism generalises this. Best modern pattern if scripting is ever needed.

**Godot-specific hazards** - `.tscn/.tres` text files can embed GDScript that executes on `ResourceLoader.load()`; `ProjectSettings.load_resource_pack()` of a third-party PCK is arbitrary code execution. godot-safe-resource-loader parses files itself, rejects embedded `GDScript` sub-resources and non-`res://` ext paths; Gyrcas/Godot-SafeLoad is a 4.5 equivalent; proposal #10968 (trusted stand-in loader) is still open. Unity Addressables/AssetBundles are data-only but can't add code; Unreal PAKs can carry Blueprint bytecode. gilzoide/lua-gdextension and fernforestgames/luau-gdextension (4.5+) offer sandboxed Lua/Luau states with explicit allowlisted globals.

## 2. Recommended packaging approach and security stance (hardened mode)

**Room = a signed ZIP ("`.room`") containing only data and assets; zero executable content.**
```
myroom.room/
  room.yaml          # manifest + spec (single source of truth)
  layout/            # glTF/GLB scenes OR a prefab-placement list (preferred)
  assets/            # glb, png/ktx2, ogg, pdf/markdown documents
  ctf/               # Dockerfile or image ref + compose fragment (server-side only)
  hints.yaml, story.yaml, solution.yaml
  README.md / AGENTS.md
```
- The core game ships a **fixed prefab library** (Godot scenes) with standardised hooks; a room may only *instantiate and parametrise* prefabs, never ship scenes/scripts. Loader rejects any `.tscn/.tres/.gd/.pck/.so/.wasm` inside a pack (allowlist of extensions: `yaml json glb gltf png jpg ktx2 ogg wav md pdf txt Dockerfile`).
- Logic is expressed as an **event-condition-action (ECA) graph** in YAML with a closed vocabulary (Minecraft/PeTI model), evaluated by a core interpreter. Numeric/string expressions use a tiny side-effect-free expression language (e.g. `expr-eval`-style, no calls out).
- **Escape hatch, phase 2 only**: Luau or WASM "logic modules" compiled against a published ABI (`on_event`, `set_state`, `emit`), with fuel/memory caps per the 7dtd-wasm model. Not needed for 60-minute rooms; keep it off until a real room can't be expressed declaratively.
- **CTF services** run in isolated containers (per-session network, no egress), spawned by the orchestrator from a `challenge` descriptor modelled on CTFd's `challenge.yml` (`image`, `protocol`, `ports`, `flags` with static/regex, `hints` with cost, `requirements`). Flags are templated per session (`flag{%SESSION_SECRET%}`) and injected as env vars; the room never contains the real flag.
- **Versioning**: `spec_version` (semver of the room schema), `requires.platform: ">=1.2 <2"`, `requires.prefabs: ">=1.0"`. Loader refuses out-of-range majors, warns on minors. Prefab library follows additive-only changes within a major.
- Packs are hashed and signed on publish; the platform validator runs in CI before a room is listed.

## 3. Room spec outline (AI-agent-friendly)

```yaml
spec_version: 1.0.0
id: acme.server-closet
title: The Server Closet
version: 0.3.1
requires: { platform: ">=1.0 <2.0", prefabs: ">=1.0" }
mode: { duration_minutes: 60, players: {min: 1, max: 4}, co_op: true }
briefing: { intro: "...", win_text: "...", gm_notes: "..." }

spaces:                           # rooms/areas, each a prefab "shell"
  - id: closet
    shell: prefab:room_shell/industrial_4x6
    lighting: {preset: dim_cool, uv_enabled: true}

props:                            # prefab instances; agents compose, never model
  - id: desk1
    prefab: prefab:furniture/desk_drawer_3
    at: {space: closet, pos: [1.2, 0, 2.0], rot_y: 90}
    params: { drawers: [{id: top, lock: keypad4, code: "{{code_a}}"}] }
  - id: note_payroll
    prefab: prefab:document/paper
    at: {inside: desk1.top}
    params: { text_md: docs/payroll.md, uv_text: "4-7-1-?" }
  - id: term1
    prefab: prefab:tech/terminal
    params: { banner: "...", accepts: flag_submit, challenge: web_login }

variables:                        # per-session randomisation
  code_a: { type: digits, length: 4 }

ctf:
  challenges:
    - id: web_login
      image: ghcr.io/acme/room-web:1.0
      ports: [{container: 8080, protocol: http}]
      flag: { template: "flag{{{nonce}}}", inject_env: FLAG }
      hints: [{cost: 0, text: "..."}, {cost: 50, text: "..."}]

puzzles:                          # the dependency DAG (Gilbert PDC)
  - id: p1_find_uv
    title: Find the UV torch
    requires: []
    solved_when: { event: picked_up, prop: uv_torch }
    unlocks: [p2_read_note]
    hints: ["Look under things.", "The shelf has a loose panel.", "Shelf, bottom-left panel."]
  - id: p2_read_note
    requires: [p1_find_uv]
    solved_when: { state: {prop: desk1.top, is: open} }
    unlocks: [p3_terminal]
  - id: p3_terminal
    requires: [p2_read_note]
    solved_when: { event: flag_accepted, challenge: web_login }
    unlocks: [exit]

logic:                            # ECA rules (closed vocabulary)
  - on: { event: flag_accepted, challenge: web_login }
    do: [{ action: set_state, prop: exit_door, to: unlocked },
         { action: play_sound, id: sfx/latch }, { action: narrate, text: "..." }]

exit: { prop: exit_door, win_when: { state: {prop: exit_door, is: open} } }

solution:                         # drives the headless auto-solver
  steps:
    - { act: examine, prop: shelf }
    - { act: pick_up, prop: uv_torch }
    - { act: use_on, item: uv_torch, target: note_payroll }
    - { act: input_code, prop: desk1.top, value: "{{code_a}}" }
    - { act: submit_flag, challenge: web_login, value: "{{flags.web_login}}" }
    - { act: use, prop: exit_door }
```
This mirrors Gilbert's advice (edges are *dependencies*, not flow; aim for "bushy" diamonds with act bottlenecks; no dead ends) and the GALA-2025 "Formalizing Escape Game Mechanics" static-graph/dynamic-graph model, which is explicitly meant for automated solvability checks. Keep narrative in Ink-/Arcweave-style JSON if branching dialogue is needed; otherwise plain markdown fields.

## 4. Prefab / interaction-primitive list

Shells: `room_shell/*` (sizes, styles), `door` (locked/unlocked/exit), `window`, `vent`.
Containers: `drawer`, `cabinet`, `safe`, `chest`, `hidden_compartment`, `wall_panel`, `floor_hatch`, `book_hollow`.
Locks (all expose `locked/unlocked`, `try(value)`, `on_unlock`): `padlock_key`, `padlock_3dial`, `padlock_4dial`, `keypad4/6`, `directional_lock`, `letter_dial`, `rfid_reader`, `maglock_switch`.
Mechanisms: `lever`, `switch`, `button`, `valve_wheel`, `rotary_dial`, `slider`, `pressure_plate`, `trigger_volume`, `fusebox`, `cable_patch_panel`.
Information: `document/paper|book|photo|poster|map`, `whiteboard`, `monitor_static`, `audio_player`, `radio`, `uv_ink_layer` (readable with `uv_torch`), `mirror_text`, `blacklight_stamp`.
Items: `key`, `uv_torch`, `magnet`, `screwdriver`, `battery`, `fuse`, `rfid_card`, `cipher_wheel`, `combinable` (A+B->C).
Tech/CTF: `terminal` (ssh/http launcher + flag input), `keyboard_console`, `usb_stick`, `server_rack` (blinkenlights state), `network_jack`.
Ambient: `lamp`, `spotlight`, `desk`, `chair`, `shelf`, `crate`, `plant`, `clock` (counts down session time).

Player verbs (what `solution.steps` and the UI share): `examine`, `pick_up`, `drop`, `combine`, `use`, `use_on`, `input_code`, `turn_dial`, `pull/push`, `open/close`, `read`, `illuminate_uv`, `submit_flag`, `give_to_player`, `say`.

## 5. Validator / linter checks

Schema: JSON Schema validation of `room.yaml`; unknown keys rejected; extension allowlist; file size caps; no executable content (hardened mode only).
References: every `prefab:` exists at the required prefab version; every `prop`, `space`, `challenge`, `variable`, `hint` ID referenced resolves; assets exist and are glTF 2.0 / supported codecs; every prop has a position or `inside`.
Graph: puzzle DAG is acyclic; exactly one root set and a reachable `exit`; no orphan puzzles (unreachable or never unlocking anything); every lock has at least one obtainable key/code; every `variable` used in a lock is surfaced somewhere readable; no dead-end items (picked up but never consumed); linearity metric (longest chain vs. width, Gilbert "bushiness"); bottleneck count.
Hints: >=3 tiers per puzzle, escalating; last tier equals the answer.
CTF: image pullable, ports declared, flag template contains the nonce, healthcheck present, no hard-coded real flags.
Simulation: headless auto-solver replays `solution.steps` against the interpreter; must reach `win_when`; also runs a BFS/random agent to confirm no step is reachable before its prerequisites (sequence-break detector) and estimates par time from step count.
Hygiene: text length limits, profanity/PII scan, localization keys optional.

Off-the-shelf pieces: JSON Schema + `ajv`/`check-jsonschema`; graph checks via `networkx`; GraphEG (GALA 2025) for visual/solvability inspection; CTFd `ctfcli` conventions and `docker compose` for services; godot-safe-resource-loader/Godot-SafeLoad if you ever accept `.tres` from strangers; Godot MCP servers (godot-ai, Godot-MCP, StraySpark) let agents drive the editor during authoring; hot reload = watch `room.yaml` and re-instantiate the scene from data.

## 6. Asset sourcing

Ship a curated **core CC0 library** so agents rarely need new models: Kenney (consistent low-poly, GLB), Quaternius (GLB low-poly props), Poly Haven (realistic props, HDRIs, textures, glTF), ambientCG (PBR materials). Sketchfab requires per-asset license filtering (CC0/CC-BY): allow but require attribution field. For novel hero props, allow agents to call text-to-3D APIs (Meshy, Tripo, Hunyuan3D 3.x; TRELLIS.2 self-hosted) in a "generate -> decimate -> KTX2" pipeline, with the validator enforcing triangle/texture budgets; 2026 reviews agree these are fine for static props, poor for hero/hard-surface precision. Sloyd's parametric approach is a good model for prefab parametrisation.

Agent guide (`AGENTS.md` + `CLAUDE.md` importing it via `@AGENTS.md`): keep under ~150 lines; list build/validate/solve commands, the prefab catalogue path, the verb vocabulary, PDC rules (bushy, no dead ends, 3 hint tiers), CTF rules (no real flags, use templates), and a worked starter room.

## Sources
- Escape Simulator Lua: https://github.com/SuperJura/ESDocs/blob/main/docs/room-editor/lua-scripting.md ; https://store.steampowered.com/news/app/2879840/view/519716851054281257
- Godot PCK docs: https://docs.godotengine.org/en/stable/tutorials/export/exporting_pcks.html ; safe loaders: https://github.com/derkork/godot-safe-resource-loader , https://github.com/Gyrcas/Godot-SafeLoad , proposal https://github.com/godotengine/godot-proposals/issues/10968
- Godot Mod Loader manifest: https://wiki.godotmodding.com/guides/modding/mod_files/
- Luau sandboxes: https://luau.org/sandbox/ , https://github.com/fernforestgames/luau-gdextension , https://github.com/gilzoide/lua-gdextension
- WASM mod sandbox: https://github.com/hordeforge/7dtd-wasm ; Extism https://news.ycombinator.com/item?id=37751270
- Factorio modding: https://wiki.factorio.com/Modding ; RimWorld About.xml: https://rimworldwiki.com/wiki/Modding_Tutorials/About.xml
- Minecraft pack_format: https://minecraft.wiki/w/Pack_format
- Portal 2 editoritems: https://developer.valvesoftware.com/wiki/Portal_2_Puzzle_Maker/editoritems.txt
- Unreal UGC: https://www.unrealengine.com/blog/new-example-project-and-plugin-for-mod-support-released ; https://github.com/modio/modio-ue-modiougc
- Unity Addressables modding: https://discussions.unity.com/t/modding-with-addressables/707646
- Gilbert PDC: https://grumpygamer.com/puzzle_dependency_charts
- Escape-game graph formalism (GALA 2025, GraphEG): https://link.springer.com/chapter/10.1007/978-3-032-11043-5_26
- GenEscape (ICCV 2025): https://arxiv.org/abs/2506.21839 ; DB-driven 3D level gen (AIIDE 2025): https://arxiv.org/abs/2508.18533 ; PCG benchmark: https://arxiv.org/pdf/2503.21474
- CTFd challenge.yml: https://github.com/CTFd/ctfcli/blob/master/ctfcli/spec/challenge-example.yml ; https://docs.ctfd.io/docs/custom-challenges/application-target/
- Godot MCP: https://github.com/hi-godot/godot-ai ; https://www.strayspark.studio/blog/godot-mcp-setup-claude-code-2026
- Text-to-3D comparisons: https://wavect.io/blog/ai-3d-model-generators-game-development-2026/ ; https://www.3daistudio.com/blog/best-3d-model-generation-apis-2026
- CC0 libraries: https://quaternius.com/ ; https://app.cinevva.com/guides/free-3d-model-sites
- Arcweave JSON export: https://www.arcweave.com/docs/1.0/export
- AGENTS.md practice: https://codex.danielvaughan.com/2026/05/27/agent-instruction-files-agents-md-claude-md-cross-tool-portability-codex-cli/
