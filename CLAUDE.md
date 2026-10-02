# escapebox

Virtual escape room platform with pluggable rooms and CTF challenges. Godot 4.7 client + dedicated server, Go platform service, YAML room manifests.

**Read `PLAN.md` in full before doing anything.** It holds the locked decisions, the architecture, the prototype room, the milestones, and the agent operating rules (Section 13). Research behind the plan lives in `docs/research/`.

Start every task by checking `docs/STATUS.md` for the next unchecked milestone item and `docs/DECISIONS.md` for prior decisions. Work only the current milestone. Record any new decision as an ADR in `docs/DECISIONS.md`.

Dev machine: the Alienware RTX 3080 Ti laptop (ADR-0011); GPU rendering is fine there. Two agents: Claude Code owns runtime code (Godot, Go, rooms, deploy). Codex (`gpt-6.1-sol`, via the `codex:rescue` skill with `--write --background --model gpt-6.1-sol`) owns 3D assets and printed documents built through headless Blender scripts. The contract is `docs/ASSET_PIPELINE.md`; never hand-model real props in Godot, write an asset request instead.

Non-negotiables:
- Clients send intents; the server owns all world and puzzle state.
- No room-specific code in `game/core/`, `game/addons/escapebox_sdk/`, or `platform/`.
- Challenge containers are hardened and have no egress; flags are templates, never literals; never log flag values.
- Load room packs with `ProjectSettings.load_resource_pack(path, false)`.
- Tests and docs ship with the code; update `docs/STATUS.md` with what was actually run and where.
