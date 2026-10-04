# Room authoring guide

For people and AI agents building an escapebox room. Read it fully, then the example room `game/rooms/night_shift/`. **Status: M1.** The SDK nodes marked as built in Section 2 work offline (single-player); multiplayer replication arrives in M2 without changes to rooms.

## 1. What a room is

A room is a directory `game/rooms/<room_id>/` inside the game repo (you work in a clone; rooms are trusted code). It is exported to `<room_id>-<version>.pck` and loaded at runtime by both the game server and the clients. The core game knows nothing about your room. You build it from **SDK nodes** that handle networking, locks, and state for you.

```
game/rooms/<room_id>/
  room.yaml        # manifest: metadata, variables, puzzle graph, hints, CTF, solution (you edit this)
  room.json        # generated from room.yaml by roomcheck -write-json (never edit by hand)
  room.tscn        # entry scene; root node uses the RoomRoot SDK script
  scenes/          # sub-scenes
  scripts/         # room GDScript (SDK API only; no class_name, see below)
  assets/          # room-specific models/textures/audio/documents; CC0 or owned; ATTRIBUTION.md
  briefing/        # intro.md, win.md, timeout.md, gm_notes.md
  ctf/<challenge>/ # Dockerfile + app per CTF challenge (built by the platform, not shipped in the pack)
  README.md        # how to play-test, design notes, play-test log
```

`<room_id>` matches `[a-z0-9_]+` and equals the manifest `id`.

## 2. SDK nodes (`res://addons/escapebox_sdk/`)

Compose your scene from these. They replicate themselves; you never write netcode. Every node's state has a `state` string that `node_state` conditions match. "Planned" nodes are specified in PLAN.md 8.2 but not built yet; ask for them rather than scripting around them.

| Node | Use it for | Key exports | `state` values |
|---|---|---|---|
| `RoomRoot` | Scene root | `spawn_point` | |
| `Item` | Things players pick up into the shared inventory; optionally carries a file players can copy or save to their own computer | `item_id`, `display_name`, `description`, `uv_text`, `file_name`, `file_text` | world, inventory, consumed |
| `UVTorch` | Item that reveals UV content while selected | as `Item` | as `Item` |
| `Document` | Paper, cards, photos; auto-pinned to the evidence board when read | `title`, `text_md`, `back_text_md` (Flip), `uv_text`, `texture` | unread, read |
| `ContainerProp` | Drawers, cabinets, safes, hatches (Godot already has `Container`, ADR-0008) | `locked_by`, `moving_part`, `open_offset`, `open_rotation_deg`, `contents`, `start_open` | closed, open |
| `Door` | Doors and cage gates | as `ContainerProp` minus `contents`, plus `is_exit` | closed, open |
| `KeypadLock` | Number pad with focused UI | `code` (may be `{{var}}`), `display_length`, `starts_powered`, `status_light`, `status_label` | locked, unlocked |
| `KeyLock` | Opened by using an inventory item on it | `key_item_id`, `consume_key` | locked, unlocked |

Every lock also has `unlock_tone_hz` / `unlock_tone_count` (a bell struck N times when it opens; the count may be `{{var}}`), `show_when_unlocked` / `hide_when_unlocked` (nodes shown or hidden once it opens: a fitted wheel, a hung pendulum) and `dead_message` / `dead_prompt` (what players see while it has no power).

| `MaglockGate` | Lock with no input, released by activation | | locked, unlocked |
| `DialLock` | Letter rings, number wheels, clock hands: opens the moment every wheel shows the code (ADR-0033) | `wheels` (one entry per wheel: `"ABC..."` one symbol per character, or `"12,1,2,..."`), `separator` (`":"` -> `"4:40"`), `wheel_labels`, `start_code`, `hand_parts` + `hand_turn` (parts turned by each wheel), `code` | locked, unlocked |
| `SequenceLock` | Chime bars, piano keys, button rows: opens when its `SequencePad` children are struck in `code` order (the latest strikes count; one character per symbol) | `code` (may be `{{var}}`) | locked, unlocked |
| `SequencePad` | One bar/key of a `SequenceLock`; rings a synthesised note on every client | `symbol`, `tone_hz`, `tone_kind` (`bell`, `whistle`), `moving_part` | idle |
| `SequencePlayer` | Music box, songbird: Wind/Play plays `sequence` as notes and points `pointer` at each symbol, so it reads without sound too; dead until activated unless `starts_powered` | `sequence` (may be `{{var}}`), `symbols`, `tones_hz`, `pointer`, `pointer_step`, `dead_message` | dead, ready |
| `AllOfGate` | Activates `targets` once every node in `inputs` is in its state (three gears fitted -> the automaton runs) | `inputs`, `states` (default `unlocked`), `targets` | waiting, fired |
| `Lever` | Two-position lever/switch; activates `targets` once when switched on | `targets`, `moving_part`, `on_rotation_deg` | off, on |
| `PatchPanel` | Loose cables to plug into ports; activates `targets` when solved | `cable_ids`, `cable_labels` (never colour alone), `port_count`, `solution` ("A:3,B:1"), `targets` | idle, solved |
| `Terminal` | `remote`: CTF connection card + flag field; `simulated`: offline shell | `mode`, `challenge_id`, `banner`, `commands` | open, solved |
| `FlagGate` | Activates `targets` when a challenge's flag is accepted | `challenge_id`, `targets` | waiting, fired |
| `UVReveal` | UV-ink text on a surface, visible with a UV torch selected nearby | `label` (a Label3D), `text` (may be `{{var}}`), `reveal_range` | |
| `Intercom` | Shows hints and narration in the room | `label`, `chime`, `speaker_name` | |
| `SessionClock` | Countdown display, or with `wall_start` ("23:00") a clock in story time that runs forward to the deadline, with optional hands | `label`, `wall_start`, `hour_hand`, `minute_hand`, `hand_turn` | |
| `AirlockGate` | Optional onboarding (ADR-0020): players start outside at `spawn_point`; seals `door`, starts the clock and narrates `seal_text` when everyone is inside (or `seal_after_s` after the first); stragglers and later joiners go to `late_spawn`. While it waits, the HUD shows the controls tutorial instead of the briefing | `door`, `inside_min`/`inside_max` (room coordinates), `seal_after_s`, `seal_text`, `late_spawn` | waiting, sealed |
| `AmbientZone` | Positional room tone synthesised at start-up (mains hum, fan noise, tube buzz, clock tick); no audio files. With `only_when` it sounds only while that SDK node's `state[only_when_key]` equals `only_when_value` (a clock that ticks once wound) | `hum_hz`, `hum_level`, `harmonics`, `noise_level`, `noise_cutoff_hz`, `buzz`, `tick_per_s`, `tick_level`, `only_when`, `only_when_key`, `only_when_value`, `volume_db` | |
| Planned | `DirectionalLock`, `PushButton`, `Switch`, `Dial`, `FuseBox`, `TriggerVolume`, `PuzzleMarker` | | |

**Every SDK node** also has `difficulties` (empty = all levels; see section 3).

**Wiring.** `locked_by` points an openable at its lock. `targets` (on `FlagGate`, `PatchPanel`, `Lever`, `AllOfGate`) *activate* other nodes: an unpowered lock gains power, a powered lock unlocks, a dead `SequencePlayer` comes alive, a closed door or container whose lock allows springs open (wire an `AllOfGate` from a lock to its drawer so solving it pops the drawer). Locks say `dead_message` (and show `dead_prompt`) while unpowered. That covers "the flag releases the cage maglock" and "the patch panel powers the exit keypad" without scripts.

**Collision.** Every interactable needs a `StaticBody3D` + `CollisionShape3D` below it (the SDK puts it on the interaction layer). Walls and furniture use layer 1. Things inside a closed `ContainerProp`'s `contents` are hidden and untargetable automatically.

**Room script rules.** Connect to SDK signals and call SDK methods (`set_state`, `unlock`, `give_item`, `narrate`, `play_sfx`, `set_var`). Do not call `rpc`, touch `multiplayer`, use `HTTPRequest`/`OS.execute`/raw sockets, read files outside your room directory, or declare `class_name` (pack class caches are ignored, ADR-0007; use `preload` instead). `roomcheck` warns on these.

**Sound.** SDK nodes already sound right: doors, drawers, keypads (including wrong codes), maglocks, pick-ups, patch panels and levers play a CC0 library sound (`EBSound`) on every client when their state changes, never on join or restore. Override with `open_sound`/`close_sound` on openables, or a custom `chime` on the intercom. An airlock exit door must not be the room's exit condition by itself, because it starts open.

Node paths are the room's public interface: `room.yaml` refers to nodes as paths from the scene root (`Cabinet/Keypad`). Keep them stable; renaming a node breaks saved sessions.

## 3. `room.yaml`

The normative schema is `docs/schema/room.schema.json` (JSON Schema 2020-12). Unknown keys are errors. Minimal complete example:

```yaml
spec_version: 1
id: tiny_vault
title: Tiny Vault
version: 0.1.0
authors: [your_name]
requires: { platform: ">=0.1", sdk: ">=0.1" }
mode:
  duration_minutes: 60            # 60 | 1440 | 2880 typical
  players: { min: 1, max: 4 }
  auto_nudge_minutes: 6           # 0 disables the automatic intercom nudge
entry_scene: res://rooms/tiny_vault/room.tscn
briefing:
  intro_md: briefing/intro.md
  win_md: briefing/win.md
  timeout_md: briefing/timeout.md
  gm_notes_md: briefing/gm_notes.md   # for game masters (human or AI); never shown to players
variables:
  safe_code: { type: digits, length: 4 }   # also: letters (length), choice (choices)
puzzles:
  - id: find_note
    title: Find the note
    requires: []
    solved_when: { item_picked_up: torn_note }
    hints:                          # >= 3 tiers, gentlest first, last tier is the answer
      - "Someone was in a hurry to hide something."
      - "Look under the desk lamp."
      - "The torn note is under the desk lamp."
  - id: open_safe
    title: Open the safe
    requires: [find_note]
    solved_when: { node_state: { path: "Safe/Keypad", state: unlocked } }
    hints: ["...", "...", "Enter the four digits from the note on the safe keypad."]
exit:
  puzzle: open_safe
solution:
  - { act: pick_up, item: torn_note }
  - { act: input_code, lock: "Safe/Keypad", value: "{{safe_code}}" }
```

**Draft rooms (ADR-0030).** Add `draft: true` at the top level while a room is being built. `roomcheck`, dev mode and `packroom` treat it like any room, but the platform leaves it out of the catalog, game creation and pack downloads unless it runs with `-drafts` (`tools/play.sh --drafts`; the always-on service never does). Delete the line to ship.

`solved_when` vocabulary (closed, grows additively): `item_picked_up: <item_id>`, `node_state: {path, state}`, `flag_accepted: {challenge}`, `all_of: [...]`, `any_of: [...]`. Exactly one key per condition.

Templates: `{{var}}` refers to a declared variable; `{{flags.<challenge_id>}}` to a challenge's per-session flag (solution only); `{{nonce}}` appears only inside a flag `format`.

`solution` acts: `examine`, `pick_up`, `use`, `use_on`, `combine`, `input_code`, `interact`, `submit_flag`. It is replayed by play-testers now and by the auto-solver later.

### Difficulty levels (optional, ADR-0022)

Offer levels with a `difficulties` list; the first is the default and players pick one when hosting (main menu, `POST /api/sessions`, `--difficulty`). A level can replace fields of puzzles (`title`, `requires`, `hints`, `gm_notes`) and challenges (`hints`) by id, and can replace the whole `solution`. `roomcheck` checks every level as its own room.

```yaml
difficulties:
  - { id: standard, title: Standard, description: "The classic room." }
  - id: hard
    title: Hard
    description: "No password handed to you: crack it."
    puzzles:
      hack_intranet: { requires: [open_cabinet], hints: ["...", "...", "..."] }
    solution: [ ... ]   # the hard path, replayed by the tests
```

In the scene, set `difficulties` on any SDK node that only exists at some levels (e.g. two versions of a clue at the same spot). Outside its levels the node is hidden, untouchable and not part of the world state.

## 4. CTF challenges

```yaml
ctf:
  challenges:
    - id: intranet
      title: Kestrel Intranet
      kind: service                    # file | service | terminal
      difficulty: easy                 # easy | medium | hard (shown to players)
      build: ctf/intranet              # Docker build context inside the room dir
      ports: [{ container: 8080, protocol: http }]
      flag: { type: per_instance, format: "FLAG{{{nonce}}}", inject_env: FLAG }
      healthcheck: { path: /healthz, timeout_s: 30 }
      resources: { cpu: 0.5, memory_mb: 256 }
      hints: ["...", "...", "..."]
```

Rules: **flags are templates, never literals** (`roomcheck` fails on anything that looks like `flag{...}` in room files; static flags are stored only as `sha256`). Your app reads the flag from the env var at runtime and should refuse to start without it. Build everything inside the Dockerfile from the challenge directory alone (it is the whole build context); the image runs as a non-root user and listens on the declared port. If the app is Go, give it its own `go.mod` in the challenge directory: `tools/test.sh` runs `go test` in every `ctf/*/go.mod` module (see Night Shift's `ctf/intranet`). The platform proxies the port to players on the LAN (a `remote` Terminal shows the address) and checks submitted flags itself; it reads challenge definitions from its own copy of your `room.json`. Containers run with no internet access, a read-only root filesystem, all capabilities dropped, and CPU/memory/pid limits; design for that. The health check must pass within `timeout_s`. Challenges must be solvable with free tools and must not need brute force (wrong submissions are rate-limited). In-world clues should narrow the attack, e.g. a username on a sticky note. Wire the payoff with a `FlagGate` node and a `flag_accepted` puzzle.

## 5. Design rules (PLAN.md Section 9)

1. Multi-linear: 2-4 parallel threads converging on a meta; linear only at the climax. First solve within 2-3 minutes; 15-25 steps per hour.
2. Fair: one answer, self-validating, clue visibly linked to its lock, feedback on every input, no outside knowledge, no destroyable states, <= 5 minutes to execute once understood.
3. No designed red herrings, no pixel hunts. Everything interactable matters; décor is not interactable.
4. Spread clues across zones so 3-4 players can work in parallel.
5. Three escalating hint tiers per puzzle, written in the room's voice. If a puzzle almost always needs a hint, it is broken.
6. Every puzzle has a reason to exist in the story. Never encode by colour alone. Text readable at inspect distance; light the workspaces.
7. 24/48-hour rooms: cap open threads, keep high-variance puzzles off the critical path.
8. Play-test blind with at least 3 groups; log hesitation points and solve times in the room README.
9. Barrier to entry (ADR-0023): the game is played in a web browser. A standard room (no `ctf.challenges`) needs nothing else: no installs, no VPN, no command line. A hacker room (has `ctf.challenges`) may ask players to set up their own tools or connection for its CTF components only; the rest of the room must still play in the browser, and the room's description says what setup its CTF parts need.
10. Web challenges run behind a path prefix (ADR-0029): players reach them at `https://<site>/ctf/<game>/<challenge>/`, and the platform sends `X-Forwarded-Prefix: /ctf/<game>/<challenge>`. Build every link, form action, redirect and cookie path from that prefix (validate it, as Night Shift's intranet does), or use only relative links.

## 6. Assets

Use CC0 assets (Poly Haven, ambientCG, Kenney, Quaternius) or your own; record each in `assets/ATTRIBUTION.md` with URL and licence. Assets only your room uses live under `game/rooms/<id>/assets/` (CC0 downloads in `assets/third_party/` via `tools/thirdparty/fetch_cc0.sh`, Codex props in `assets/props/` via a request whose `**Output:**` names that path), so they ship in your pack only, not in every client (ADR-0034). Textures <= 2048 px; props <= 20k triangles (hero props <= 60k). Custom props for the core library go through an asset request (`docs/ASSET_PIPELINE.md`).

## 6a. Intro video (optional, ADR-0036)

The site shows a room's intro video on its lobby card and game page when `media/rooms/<id>/intro.mp4` exists. To make one:

1. Write `media/rooms/<id>/trailer.json`: `{"quality": "high", "fov": 68, "shots": [{"duration": 4, "from": [x, y, z, yaw, pitch], "to": [...], "caption": "...", "title": "...", "set": {"Node/Path": {"state": "unlocked"}}}]}`. A shot without `to` holds still; `title` draws a title card (the poster is taken 2.25 s in, so open with one); `set` stages node states. Plan paths around props.
2. Optional narration: `narration.json` (`voice`, `style`, `text` with `<short pause>` tags, `start_s`), then `go run ./tools/narrate media/rooms/<id>` (needs a Gemini API key, see ADR-0036).
3. Optional story clips from Flow (Veo): save them as `media/rooms/<id>/clips/01-*.mp4`; they play first, in name order.
4. `tools/trailer/build.sh <id>` writes `intro.mp4` and `poster.jpg`. Watch it, and check the sound is there (`ffmpeg -i media/rooms/<id>/intro.mp4 -af volumedetect -f null -`).

Videos are never part of the room pack.

## 7. Commands

```bash
go run ./tools/roomcheck -write-json game/rooms/<room_id>   # regenerate room.json, then validate
go run ./tools/roomcheck                                    # validate every room
godot --headless --path game --import                       # import assets
godot --path game -- --room <room_id>                       # play in dev mode
go run ./tools/packroom -verify <room_id>                   # export build/packs/<id>-<ver>.pck + sha256 + catalog entry,
                                                            # then replay your tests against the pack alone
```

## 8. Done means

`roomcheck` passes with no errors; the room plays start to win in dev mode and from its `.pck`; three blind play-tests are logged in the room README; every puzzle was solved without its last hint tier by at least one group.
