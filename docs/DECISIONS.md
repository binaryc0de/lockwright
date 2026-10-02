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
