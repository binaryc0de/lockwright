# Lockwright

Co-op virtual escape rooms, played in the browser, where some rooms contain a **real CTF challenge**: a laptop in the 3D room is a real, intentionally vulnerable web app running in an isolated container. When the team captures its flag, a door opens in the game world.

This repository holds the platform and its one hacker room, **Night Shift**. It is a working prototype built in October 2026. It ran on a home server and was play-tested with friends over the internet.

A *lockwright* is a master maker of locks, and every room is one of his locks. The project's working codename was `escapebox`, which is why it still appears in code identifiers (the room SDK `escapebox_sdk`, Docker labels, file names) and in the older docs and commits.

![The Night Shift office](docs/screenshots/m1-office/after/00_wide_north.png)

| Lobby | The server cage |
|---|---|
| ![Lobby](docs/screenshots/lobby/lobby-1440x900.png) | ![Server cage](docs/screenshots/m4-cage/after/00_cage_from_office.png) |

## Night Shift

23:10 at a logistics company's regional office. The badge system has crashed, the mains have gone, and the office maglock has shut the team in. They find clues in the room (a sticky note, a reused Wi-Fi password, a password policy, an anniversary card) and use them against the company intranet, which really runs:

- **The intranet** (`game/rooms/night_shift/ctf/intranet/`) is a small Go web app with one deliberate flaw, an IDOR in ticket access. Everything else is done properly (sessions, escaping, constant-time comparisons, login lockout), so the IDOR is the only way in. The facilities ticket holds a per-session flag.
- **Hard difficulty** removes the password from the room. Players get a `shadow.bak` from a USB stick with a sha512crypt hash and decoy accounts, plus clues to the password pattern. Online guessing is blocked by the lockout, so they crack it offline with John, hashcat (`-m 1800`) or their own script. A Go test fails if the hash and the challenge password drift apart.
- Pasting the flag into the in-world cage controller drops the server cage's maglock. The flag is validated server-side by the platform, never by the client.

The rest of the room is physical puzzles: UV ink, a keypad cabinet, a patch panel wired from a network diagram, and an exit override code.

## Architecture

```mermaid
flowchart LR
  B[Browser client<br/>Godot web export] -- WSS --> P
  subgraph Host
    P[Platform<br/>Go, one binary] -- spawns --> G[Game server<br/>headless Godot, authority]
    P -- Docker Engine API --> C[Challenge container<br/>internal network, no egress]
    P -- TCP proxy /ctf/ --> C
    G -- join, snapshots, flag checks --> P
  end
  B -- HTTPS second tab --> P
```

- **Game** (`game/`): Godot 4.7, GDScript. A headless game server is the only authority over world and puzzle state; clients send intents and get state back. Movement is validated server-side, and puzzle prerequisites are gated before any change (`docs/DECISIONS.md`, ADR-0009/0010/0016).
- **Rooms are plug-ins** (`game/rooms/<id>/`): a `room.yaml` manifest (puzzle graph, solution, hints, difficulties) validated against a JSON Schema by `tools/roomcheck`, plus a scene built from SDK nodes (`game/addons/escapebox_sdk/`). The core never names a room.
- **Platform** (`platform/`): Go standard library plus a pure-Go SQLite driver. It handles sessions and join codes, the lobby site, room-pack downloads, game-server processes and CTF orchestration.

### Sandboxing the challenge (ADR-0018, ADR-0032)

- Each game gets its own Docker network created with `internal: true`, so a challenge has no route out. Players reach it only through the platform's TCP/HTTPS proxy.
- Containers run with `cap_drop: ALL`, `no-new-privileges`, a read-only root filesystem (tmpfs `/tmp`), and pids/memory/CPU limits from `room.yaml`. They run as uid 65534 from a static binary on `scratch`. Tests check these settings on the created containers.
- The platform talks to the Docker Engine API over the unix socket with the standard library, about ten calls. A fake Engine in `httptest` keeps the orchestrator testable. `DOCKER_HOST` is honoured, so rootless Docker works unchanged.
- Flags are `HMAC-SHA256(platform_secret, session | challenge)`. Nothing is stored in plaintext, and a restarted container gets the same flag. Comparison is constant-time. Wrong attempts are rate limited with a doubling cooldown and logged without their value.
- Cleanup removes only containers and networks labelled with the platform's own owner id. This came from a real incident: a test platform once removed a live game's challenge.

## Running it

Needs Go 1.27+, Godot 4.7.2 (on `PATH` as `godot`), and Docker for the CTF challenge. Linux is the tested host.

```bash
tools/test.sh                  # everything CI runs: gofmt, go vet/test, roomcheck, assetcheck,
                               # the challenge's tests, gdUnit4, pack replay, touch play-through
tools/play.sh night_shift      # platform + game server + Docker challenge, opens the game
tools/play.sh --hard night_shift
```

Without Docker, `godot --path game -- --room night_shift` plays the room locally. The CTF step then has no live intranet.

## Repository map

| Path | What |
|---|---|
| `PLAN.md` | The original plan: decisions, architecture, milestones |
| `docs/DECISIONS.md` | Architecture decision records (ADRs), in order |
| `docs/STATUS.md` | Milestone checklist with what was actually run, and where |
| `docs/research/03-ctf-integration.md` | Research behind the CTF design |
| `docs/ROOM_AUTHORING.md`, `docs/API.md` | Room SDK and platform API |
| `platform/` | Go platform (sessions, flags, Docker orchestrator, web) |
| `game/` | Godot project: core, SDK, the Night Shift room, tests |
| `tools/` | Room and asset checks, room packer, play and test scripts, Blender asset pipeline |

## How it was built

Built by one developer working with AI coding agents. Claude Code wrote the runtime code (Godot, Go, rooms). Codex built the 3D props and printed documents through scripted, headless Blender. The plan, ADRs and status log record each decision and each verification run.
