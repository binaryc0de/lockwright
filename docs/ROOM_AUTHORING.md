# Room authoring guide

For people and AI agents building an escapebox room. Read it fully, then the example room `game/rooms/night_shift/`. **Status: M0 draft.** The SDK nodes below are specified but not implemented until M1; the manifest format and `roomcheck` work today.

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

Compose your scene from these. They replicate themselves; you never write netcode.

| Node | Use it for | Key exports / signals |
|---|---|---|
| `RoomRoot` | Scene root; exposes `vars` (per-session variables) | `room_ready`, `puzzle_solved(id)`, `session_finished(win)` |
| `Interactable` | Base for anything the player can aim at | `verbs`, `interacted(player, verb)` |
| `Item` | Things players pick up, inspect, combine | `item_id`, `inspect_mesh`, `uv_texture`, `combines_with`, `combine_result` |
| `Document` | Paper, photos, books; auto-pinned to the evidence board | `text_md` or `texture`, `uv_text` |
| `Container` | Drawers, cabinets, safes, hatches | `open`, `opened`, `locked_by` |
| `Lock` and `KeypadLock`, `DialLock`, `LetterLock`, `KeyLock`, `DirectionalLock`, `MaglockGate` | Server-checked locks with a focused UI | `code` (may be `{{var}}`), `unlocked` |
| `Door` | Doors; `is_exit` ends the session | `locked_by`, `is_exit` |
| `Lever`, `Switch`, `Button`, `Dial`, `PatchPanel`, `FuseBox` | Multi-state mechanisms | `state`, `changed(state)` |
| `TriggerVolume` | Player enters/leaves an area | `entered(player)` |
| `UVTorch` | Item that reveals UV layers in range | |
| `Terminal` | In-game terminal: `simulated` shell or `remote` CTF connection card + flag field | `mode`, `challenge_id`, `script` |
| `FlagGate` | Opens/activates targets when a CTF flag is accepted | `challenge_id`, `targets` |
| `PuzzleMarker` | Optional: mark a puzzle solved when a node reaches a state | `puzzle_id`, `solved_state` |
| `Intercom`, `SessionClock`, `AmbientZone` | Hint delivery, countdown display, reverb/ambience | |

**Room script rules.** Connect to SDK signals and call SDK methods (`set_state`, `unlock`, `give_item`, `narrate`, `play_sfx`, `set_var`). Do not call `rpc`, touch `multiplayer`, use `HTTPRequest`/`OS.execute`/raw sockets, read files outside your room directory, or declare `class_name` (pack class caches are ignored, ADR-0007; use `preload` instead). `roomcheck` warns on these.

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

`solved_when` vocabulary (closed, grows additively): `item_picked_up: <item_id>`, `node_state: {path, state}`, `flag_accepted: {challenge}`, `all_of: [...]`, `any_of: [...]`. Exactly one key per condition.

Templates: `{{var}}` refers to a declared variable; `{{flags.<challenge_id>}}` to a challenge's per-session flag (solution only); `{{nonce}}` appears only inside a flag `format`.

`solution` acts: `examine`, `pick_up`, `use`, `use_on`, `combine`, `input_code`, `interact`, `submit_flag`. It is replayed by play-testers now and by the auto-solver later.

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

Rules: **flags are templates, never literals** (`roomcheck` fails on anything that looks like `flag{...}` in room files; static flags are stored only as `sha256`). Your app reads the flag from the env var at runtime. Containers run with no internet access, a read-only root filesystem, all capabilities dropped, and CPU/memory/pid limits; design for that. The health check must pass within `timeout_s`. Challenges must be solvable with free tools and must not need brute force (wrong submissions are rate-limited). In-world clues should narrow the attack, e.g. a username on a sticky note. Wire the payoff with a `FlagGate` node and a `flag_accepted` puzzle.

## 5. Design rules (PLAN.md Section 9)

1. Multi-linear: 2-4 parallel threads converging on a meta; linear only at the climax. First solve within 2-3 minutes; 15-25 steps per hour.
2. Fair: one answer, self-validating, clue visibly linked to its lock, feedback on every input, no outside knowledge, no destroyable states, <= 5 minutes to execute once understood.
3. No designed red herrings, no pixel hunts. Everything interactable matters; décor is not interactable.
4. Spread clues across zones so 3-4 players can work in parallel.
5. Three escalating hint tiers per puzzle, written in the room's voice. If a puzzle almost always needs a hint, it is broken.
6. Every puzzle has a reason to exist in the story. Never encode by colour alone. Text readable at inspect distance; light the workspaces.
7. 24/48-hour rooms: cap open threads, keep high-variance puzzles off the critical path.
8. Play-test blind with at least 3 groups; log hesitation points and solve times in the room README.

## 6. Assets

Use CC0 assets (Poly Haven, ambientCG, Kenney, Quaternius) or your own; record each in `assets/ATTRIBUTION.md` with URL and licence. Textures <= 2048 px; props <= 20k triangles (hero props <= 60k). Custom props for the core library go through an asset request (`docs/ASSET_PIPELINE.md`).

## 7. Commands

```bash
go run ./tools/roomcheck -write-json game/rooms/<room_id>   # regenerate room.json, then validate
go run ./tools/roomcheck                                    # validate every room
godot --headless --path game --import                       # import assets
# M1+: tools/packroom <room_id>  (export .pck + sha256 + catalog entry)
```

## 8. Done means

`roomcheck` passes with no errors; the room plays start to win in dev mode and from its `.pck`; three blind play-tests are logged in the room README; every puzzle was solved without its last hint tier by at least one group.
