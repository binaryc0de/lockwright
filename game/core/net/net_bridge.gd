class_name NetBridge
extends Node
## The one RPC endpoint (ADR-0015). Lives at /root/Game/Net on every peer, so
## RPCs resolve the same node everywhere. It only moves bytes: SessionServer
## (server) and SessionClient (client) hold the logic. Payloads name SDK nodes
## by eb_path; world snapshots travel as JSON text.

## CLIENT: fired once the server accepted us. info = {player_id, room_id,
## room_version, snapshot_json, server_now}.
signal welcomed(info: Dictionary)
## CLIENT: the server refused the join.
signal rejected(reason: String)
## CLIENT: everyone's positions, {player_id: {name, pos, yaw}}.
signal roster_updated(roster: Dictionary)

var server: SessionServer = null
var client: SessionClient = null

var _next_req: int = 1
## Last position this client reported; sent with every intent so the server's
## reach check never races the unreliable position stream (ADR-0010, ADR-0015).
var _last_pos: Vector3 = Vector3.ZERO
var _last_yaw: float = 0.0
var _pending: Dictionary = {}   # req_id -> Callable


func is_server() -> bool:
	return server != null


# --- Client side: outgoing ---------------------------------------------------

func send_join(token: String, display_name: String) -> void:
	rpc_join.rpc_id(1, token, display_name)


func send_intent(path: String, verb: String, payload: Dictionary, on_result: Callable) -> void:
	if not _connected():
		on_result.call({"ok": false, "error": "not_connected"})
		return
	var id := _next_req
	_next_req += 1
	_pending[id] = on_result
	rpc_intent.rpc_id(1, id, path, verb, payload, _last_pos, _last_yaw)


func send_note(text: String, on_result: Callable) -> void:
	if not _connected():
		if on_result.is_valid():
			on_result.call({"ok": false, "error": "not_connected"})
		return
	var id := _next_req
	_next_req += 1
	if on_result.is_valid():
		_pending[id] = on_result
	rpc_note.rpc_id(1, id, text)


func send_remove_note(note_id: int) -> void:
	if _connected():
		rpc_remove_note.rpc_id(1, note_id)


func send_hint_request(puzzle_id: String) -> void:
	if _connected():
		rpc_hint.rpc_id(1, puzzle_id)


func send_auto_nudge(enabled: bool) -> void:
	if _connected():
		rpc_auto_nudge.rpc_id(1, enabled)


func send_start_clock() -> void:
	if _connected():
		rpc_start_clock.rpc_id(1)


func send_position(pos: Vector3, yaw: float) -> void:
	_last_pos = pos
	_last_yaw = yaw
	if _connected():
		rpc_position.rpc_id(1, pos, yaw)


func send_examining(title: String) -> void:
	if _connected():
		rpc_examining.rpc_id(1, title)


func disconnect_client() -> void:
	if client:
		client.close()
		client.queue_free()
		client = null
	_fail_pending()


func _connected() -> bool:
	return client != null and client.is_joined()


func _fail_pending() -> void:
	var pending := _pending
	_pending = {}
	for id: int in pending:
		(pending[id] as Callable).call({"ok": false, "error": "not_connected"})


# --- RPCs: client -> server ---------------------------------------------------

@rpc("any_peer", "call_remote", "reliable")
func rpc_join(token: String, display_name: String) -> void:
	if server:
		server.on_join(multiplayer.get_remote_sender_id(), token, display_name)


@rpc("any_peer", "call_remote", "reliable")
func rpc_intent(req_id: int, path: String, verb: String, payload: Dictionary, pos: Vector3, yaw: float) -> void:
	if server:
		var peer := multiplayer.get_remote_sender_id()
		server.on_position(peer, pos, yaw)
		server.on_intent(peer, req_id, path, verb, payload)


@rpc("any_peer", "call_remote", "reliable")
func rpc_note(req_id: int, text: String) -> void:
	if server:
		server.on_note(multiplayer.get_remote_sender_id(), req_id, text)


@rpc("any_peer", "call_remote", "reliable")
func rpc_remove_note(note_id: int) -> void:
	if server:
		server.on_remove_note(multiplayer.get_remote_sender_id(), note_id)


@rpc("any_peer", "call_remote", "reliable")
func rpc_hint(puzzle_id: String) -> void:
	if server:
		server.on_hint(multiplayer.get_remote_sender_id(), puzzle_id)


@rpc("any_peer", "call_remote", "reliable")
func rpc_auto_nudge(enabled: bool) -> void:
	if server:
		server.on_auto_nudge(multiplayer.get_remote_sender_id(), enabled)


@rpc("any_peer", "call_remote", "reliable")
func rpc_start_clock() -> void:
	if server:
		server.on_start_clock(multiplayer.get_remote_sender_id())


@rpc("any_peer", "call_remote", "unreliable_ordered")
func rpc_position(pos: Vector3, yaw: float) -> void:
	if server:
		server.on_position(multiplayer.get_remote_sender_id(), pos, yaw)


@rpc("any_peer", "call_remote", "reliable")
func rpc_examining(title: String) -> void:
	if server:
		server.on_examining(multiplayer.get_remote_sender_id(), title)


# --- RPCs: server -> client ---------------------------------------------------

@rpc("authority", "call_remote", "reliable")
func rpc_welcome(info: Dictionary) -> void:
	welcomed.emit(info)


@rpc("authority", "call_remote", "reliable")
func rpc_rejected(reason: String) -> void:
	rejected.emit(reason)


@rpc("authority", "call_remote", "reliable")
func rpc_state(snapshot_json: String, server_now: float) -> void:
	var snap = JSON.parse_string(snapshot_json)
	if snap is Dictionary:
		Game.apply_server_state(snap, server_now)


@rpc("authority", "call_remote", "reliable")
func rpc_event(kind: String, data: Dictionary) -> void:
	Game.apply_server_event(kind, data)


@rpc("authority", "call_remote", "reliable")
func rpc_result(req_id: int, result: Dictionary) -> void:
	var cb: Callable = _pending.get(req_id, Callable())
	_pending.erase(req_id)
	if cb.is_valid():
		cb.call(result)


@rpc("authority", "call_remote", "reliable")
func rpc_place(eye_position: Vector3) -> void:
	_last_pos = eye_position
	Game.local_player_placed.emit(eye_position)


@rpc("authority", "call_remote", "unreliable_ordered")
func rpc_roster(roster: Dictionary) -> void:
	roster_updated.emit(roster)
