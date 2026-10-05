# Platform API

The Go platform service (`platform/`) speaks JSON over HTTP on `:8080` by default. This file lists every endpoint the prototype will have; the **Since** column says which milestone implements it. Keep this file in step with the code (PLAN.md Section 13, rule 9).

Conventions:
- Request and response bodies are `application/json`. Errors are `{"error": "<code>", "message": "<human text>"}` with a 4xx/5xx status.
- `/api/*` is called by game clients. `/internal/*` is called only by game servers and authenticates with `Authorization: Bearer <server_token>` (minted per session by the session manager, passed to `escapebox-server --token`). `/internal/*` is never exposed beyond the host in deploy configs.
- Flag values are never logged, echoed in errors, or returned by any endpoint.
- Ids: `session_id` and `player_id` are random URL-safe strings; `room_id` and `challenge_id` match `[a-z0-9_]+`.

## Public

| Method | Path | Since | Purpose |
|---|---|---|---|
| GET | `/healthz` | M0 | Liveness: `{"status":"ok"}` |
| GET | `/api/version` | M0 | `{"platform":"0.1.0"}`; room packs' `requires.platform` is matched against it |
| GET | `/api/catalog` | M3 | Installed rooms: `[{room_id, title, version, duration_minutes, players: [min, max], challenges, difficulties: [{id, title, description}]}]` plus `pack: {file, sha256, size, url, mobile?: {file, sha256, size, url}}` when the room's pack is built; `mobile` is the same room with phone texture formats (ETC2/ASTC, ADR-0038), taken by clients whose GPU has ETC2 and lacks S3TC. Draft rooms are left out unless the platform runs with `-drafts` (ADR-0030); unknown room ids in `POST /api/sessions` are 404 |
| POST | `/api/sessions` | M3 | Create a session: `{room_id, difficulty?}` -> `{session_id, invite_code}`. Guardrails: 503 `games_full` when `-max-games` unfinished games exist; 429 `too_many_games` after 6 creations in 10 minutes from one client (first `X-Forwarded-For` hop behind a local proxy); games nobody joins finish after `-expire-unjoined` (30 min). `difficulty` is one of the room's level ids ("" or absent = the default; unknown: 400 `unknown_difficulty`). LAN prototype: anyone on the LAN may create. |
| GET | `/api/games/{code}` | M5 | Public view of a game by join code, for the lobby's game page: `{code, room_id, title, difficulty, difficulty_title, status, players, players_max, duration_minutes, hacker_room, created_at, won, elapsed_s}`. No tokens or session id. 404 `bad_invite` |
| GET | `/api/status` | M5 | `{waiting, running, finished, max_games, free}` (`free` -1 = no cap; counts the same games as the cap). Counts only: codes are invitations and are never listed |
| GET | `/`, `/g/{code}`, `/site/*` | M5 | The lobby site (ADR-0028), embedded in the platform |
| any | `/ctf/{session}/{challenge}/...` | M5 | A running game's web challenge, proxied with `X-Forwarded-Prefix` (ADR-0029); 404 when not running or the game is finished. Challenge cards use it when the platform has `-public-url` |
| GET | `/play/`, `/download/packs/{file}`, `/ws/{session}` | M5 | Browser client (`-web`), room packs (`-packs`; only the current pack of a catalog room, ADR-0030), game WebSocket proxy (ADR-0025, ADR-0026) |
| GET | `/api/sessions/{id}` | M3 | `{session_id, room_id, status: idle|starting|running|finished, players: [display_name], started_at, duration_minutes}` |
| POST | `/api/sessions/{id}/join` | M3 | `{display_name, invite_code}` -> `{session_id, room_id, host, port, transport: "enet"|"ws", join_token}`. Starts or restores the game server if it is idle (PLAN.md 7.3, 7.4). `join_token` is single-use, 60 s TTL; clients fetch a new one for every (re)connect. |
| POST | `/api/join` | M3 | Same as above with only the join code: `{display_name, invite_code}`. Codes are unique among unfinished sessions; 404 `bad_invite` otherwise. This is what the game client uses. |
| GET | `/download/version.json` | M5 | `{client_version, files: {linux, windows}}` for the client update check |
| GET | `/download/{file}` | M5 | Client zips and room packs (`*.pck`), served from the platform data dir |
| GET | `/api/files/{token}` | later | One-time download of a room-provided file (e.g. Night Shift's `shadow.bak`); token minted by the game server. Not built: the USB stick is decorative in the prototype (PLAN.md 10) |

## Internal (game server -> platform)

Only direct loopback connections reach these (403 `internal_only` for anything with `X-Forwarded-For`, `Forwarded` or `Tailscale-Funnel-Request`), whatever token they carry. Joins and game lookups by code are limited to 30 per minute per client (429 `too_many_joins`).

| Method | Path | Since | Purpose |
|---|---|---|---|
| POST | `/internal/sessions/{id}/verify` | M3 | `{join_token}` -> `{player_id, display_name}` or 403. Consumes the token. |
| GET | `/internal/sessions/{id}/snapshot` | M3 | Latest snapshot `{version, saved_at, world, puzzles, evidence, timer}` or 404 if none (fresh start) |
| PUT | `/internal/sessions/{id}/snapshot` | M3 | Store the latest snapshot (PLAN.md 7.3: on every world-state change and every 30 s) |
| POST | `/internal/sessions/{id}/events` | M3 | Append `[{at, kind, player_id?, data}]` to `session_events` (puzzle solved, hint revealed, item picked up, ...) |
| POST | `/internal/sessions/{id}/flags` | M3 | `{challenge_id, value, player_id}` -> `{accepted: bool, retry_after_s?: int}`. Constant-time compare against the per-instance HMAC flag or static hash; 10 wrong/min/team then escalating cooldown (429 with `retry_after_s`). Every attempt is logged without the value. |
| POST | `/internal/sessions/{id}/challenges/start` | M3 | Body ignored: the platform reads the session room's challenges from its own `room.json`. -> `{handles: {challenge_id: {url?, host, port}}}`. Builds images if needed, creates the per-session internal network, starts hardened containers with per-instance flags, waits for health checks, opens proxy ports (ADR-0018). Idempotent per session. 503 `docker_unavailable` if Docker is not reachable. |
| POST | `/internal/sessions/{id}/challenges/stop` | M3 | Tear down the session's containers and network. Flags stay in the store. |
| POST | `/internal/sessions/{id}/files` | later | `{room_file}` -> `{download_url}` one-time link for `/api/files/{token}` (with `/api/files`) |
| POST | `/internal/sessions/{id}/finished` | M3 | `{win: bool, elapsed_s, hints_used}` marks the session finished |

## Session manager (not HTTP)

The platform spawns one `escapebox-server` per running session (PLAN.md 7.1) with `--session --room --pack --port --platform --token [--transport]`, restarts it on the next join after an idle stop (exit code 0 after 5 minutes with no players), and treats any other exit code as a crash: restart from the last snapshot, at most 3 times in 10 minutes.

## Game server protocol (Godot RPC, ADR-0015)

Not HTTP: Godot high-level multiplayer over ENet (UDP, default) or WebSocket (`--transport ws`), all RPCs on `/root/Game/Net` (`core/net/net_bridge.gd`). SDK nodes are named by `eb_path` (path from the room root). World snapshots travel as JSON text (`WorldState.to_dict()`).

Launch: `godot --headless --path game -- --server --session <id> --room <room_id> [--pack <file.pck>] [--port 7777] [--transport enet|ws] [--token <invite>] [--snapshot <file.json>] [--difficulty <id>]` (`--trust-positions` is for test bots only). Join: `godot --path game -- --connect <host[:port]> --name <display name> [--token <invite>] [--transport ws]`.

| Direction | RPC | Channel | Purpose |
|---|---|---|---|
| client -> server | `rpc_join(token, display_name)` | reliable | first RPC after connecting; verified by `JoinVerifier` (M2: shared invite; M3: `/internal/.../verify`) |
| client -> server | `rpc_intent(req_id, path, verb, payload, pos, yaw)` | reliable | player action; carries the player's position, accepted only if it is a plausible move (ADR-0016) |
| client -> server | `rpc_note(req_id, text)`, `rpc_remove_note(id)` | reliable | evidence board notes |
| client -> server | `rpc_hint(puzzle_id)`, `rpc_auto_nudge(enabled)`, `rpc_start_clock()` | reliable | hints and clock |
| client -> server | `rpc_position(pos, yaw)` | unreliable ordered, 15 Hz | avatar replication and reach |
| client -> server | `rpc_examining(title)` | reliable | "X is examining Y" for teammates |
| server -> client | `rpc_welcome({player_id, room_id, room_version, snapshot_json, server_now, position})` | reliable | join accepted; full world (also on every rejoin); `position` is where the server says this player stands (ADR-0016) |
| server -> client | `rpc_rejected(reason)` | reliable | join refused (`bad_token`); the peer is dropped 0.5 s later |
| server -> client | `rpc_state(snapshot_json, server_now)` | reliable, at most once per frame | whole world after any change; clients diff it |
| server -> client | `rpc_event(kind, data)` | reliable, after the state push | `puzzle_solved`, `hint_revealed`, `narrated`, `toast`, `time_up`, `session_finished` |
| server -> client | `rpc_result(req_id, result)` | reliable, after the state push | answer to an intent or note |
| server -> client | `rpc_place(eye_position)` | reliable | the server moved this player (airlock stragglers, ADR-0020); the client teleports |
| server -> client | `rpc_roster({player_id: {name, pos, yaw}})` | unreliable ordered, 15 Hz | everyone's position |

Snapshots are written to `--snapshot` (default `user://snapshots/<session>.json`) 0.5 s after a change and every 30 s, and restored at start (M3: posted to the platform instead).

## Running the platform (M3)

`go run ./platform/cmd/platform -data data -rooms game/rooms -game game -godot godot` from the repo root. Flags: `-addr :8080`, `-advertise <LAN IP>` (default: auto-detected), `-game-ports 7777-7799`, `-challenge-ports 20000-20999`, `-transport enet|ws`, `-platform-url` (how game servers reach the platform, default `http://127.0.0.1:<port>`). `-test-trust-positions` is for `tools/m3_smoke.sh` only. The data directory holds `platform.db` and `secret.key` (0600; per-instance flags derive from it). Docker is optional at start-up: without it, challenge start returns 503 and the room's connection card says so.

Players join with the game's main menu (platform address + join code) or `godot --path game -- --join <platform address> --code <CODE> --name <name>`. Create a game with `curl -X POST <platform>/api/sessions -d '{"room_id":"night_shift"}'` or the main menu's "Host the selected room on the platform" button.
