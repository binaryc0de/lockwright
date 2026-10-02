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
| GET | `/api/catalog` | M3 | Room packs: `[{room_id, title, version, duration_minutes, players, pack_url, sha256, size}]` |
| POST | `/api/sessions` | M3 | Create a session: `{room_id}` -> `{session_id, invite_code}`. LAN prototype: anyone on the LAN may create. |
| GET | `/api/sessions/{id}` | M3 | `{session_id, room_id, status: idle|starting|running|finished, players: [display_name], started_at, duration_minutes}` |
| POST | `/api/sessions/{id}/join` | M3 | `{display_name, invite_code}` -> `{host, port, transport: "enet"|"ws", join_token}`. Starts or restores the game server if it is idle (PLAN.md 7.3, 7.4). `join_token` is single-use, 60 s TTL. |
| GET | `/download/version.json` | M5 | `{client_version, files: {linux, windows}}` for the client update check |
| GET | `/download/{file}` | M3 | Client zips and room packs (`*.pck`), served from the platform data dir |
| GET | `/api/files/{token}` | M3 | One-time download of a room-provided file (e.g. Night Shift's `shadow.bak`); token minted by the game server |

## Internal (game server -> platform)

| Method | Path | Since | Purpose |
|---|---|---|---|
| POST | `/internal/sessions/{id}/verify` | M3 | `{join_token}` -> `{player_id, display_name}` or 403. Consumes the token. |
| GET | `/internal/sessions/{id}/snapshot` | M3 | Latest snapshot `{version, saved_at, world, puzzles, evidence, timer}` or 404 if none (fresh start) |
| PUT | `/internal/sessions/{id}/snapshot` | M3 | Store the latest snapshot (PLAN.md 7.3: on every world-state change and every 30 s) |
| POST | `/internal/sessions/{id}/events` | M3 | Append `[{at, kind, player_id?, data}]` to `session_events` (puzzle solved, hint revealed, item picked up, ...) |
| POST | `/internal/sessions/{id}/flags` | M3 | `{challenge_id, value, player_id}` -> `{accepted: bool, retry_after_s?: int}`. Constant-time compare against the per-instance HMAC flag or static hash; 10 wrong/min/team then escalating cooldown (429 with `retry_after_s`). Every attempt is logged without the value. |
| POST | `/internal/sessions/{id}/challenges/start` | M3 | `{challenges: [<ctf.challenges entries from room.json>]}` -> `{handles: {challenge_id: {url?, host, port, terminal_token?}}}`. Creates the per-session network, generates or reuses per-instance flags, starts hardened containers, waits for health checks. Idempotent per session. |
| POST | `/internal/sessions/{id}/challenges/stop` | M3 | Tear down the session's containers and network. Flags stay in the store. |
| POST | `/internal/sessions/{id}/files` | M3 | `{room_file}` -> `{download_url}` one-time link for `/api/files/{token}` |
| POST | `/internal/sessions/{id}/finished` | M3 | `{win: bool, elapsed_s, hints_used}` marks the session finished |

## Session manager (not HTTP)

The platform spawns one `escapebox-server` per running session (PLAN.md 7.1) with `--session --room --pack --port --platform --token [--transport]`, restarts it on the next join after an idle stop (exit code 0 after 5 minutes with no players), and treats any other exit code as a crash: restart from the last snapshot, at most 3 times in 10 minutes.

## Game server protocol (Godot RPC, ADR-0015)

Not HTTP: Godot high-level multiplayer over ENet (UDP, default) or WebSocket (`--transport ws`), all RPCs on `/root/Game/Net` (`core/net/net_bridge.gd`). SDK nodes are named by `eb_path` (path from the room root). World snapshots travel as JSON text (`WorldState.to_dict()`).

Launch: `godot --headless --path game -- --server --session <id> --room <room_id> [--pack <file.pck>] [--port 7777] [--transport enet|ws] [--token <invite>] [--snapshot <file.json>]` (`--trust-positions` is for test bots only). Join: `godot --path game -- --connect <host[:port]> --name <display name> [--token <invite>] [--transport ws]`.

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
| server -> client | `rpc_roster({player_id: {name, pos, yaw}})` | unreliable ordered, 15 Hz | everyone's position |

Snapshots are written to `--snapshot` (default `user://snapshots/<session>.json`) 0.5 s after a change and every 30 s, and restored at start (M3: posted to the platform instead).
