class_name SessionServer
extends Node
## Dedicated-server side of a session (PLAN.md 7, ADR-0015): owns the peer,
## the joined players and the snapshot file, and turns RoomAuthority changes
## into RPCs. Game must already be in SERVER mode with the room loaded.

const ROSTER_HZ := 15.0
const SNAPSHOT_DEBOUNCE_S := 0.5
const SNAPSHOT_PERIOD_S := 30.0
const MAX_PLAYERS := 6
## Movement sanity check (PLAN.md 6.2, review M2-P1): reported positions may
## move at most this fast, plus slack for jitter and the first report.
const MAX_SPEED_MPS := 6.0
const MOVE_SLACK_M := 1.0

var session_id: String = ""
var room_id: String = ""
var room_version: String = ""
var verifier: JoinVerifier
var store: SnapshotStore
## Test-only (--trust-positions): accept teleports so headless bots can stand
## at each target. Never set on a server real players use.
var trust_positions := false
## M3: the platform this server reports to (null = standalone M2 server).
var platform: PlatformClient = null
## Exit (code 0, after a final snapshot) once nobody has been connected for
## this long; 0 disables (PLAN.md 7.3: 300 s under the platform).
var idle_exit_s := 0.0

const EVENT_FLUSH_S := 2.0
var _events: Array = []
var _events_t := 0.0
var _idle_t := 0.0

## peer id -> {id: player id, name: display name}
var players: Dictionary = {}
## player id -> {name, pos: Vector3, yaw: float} (roster)
var _positions: Dictionary = {}
## player id -> {pos: Vector3, t: float}: last accepted position and when.
var _last_move: Dictionary = {}
## player id -> last accepted position, kept across disconnects for rejoin.
var _known_pos: Dictionary = {}

var _net: NetBridge
var _auth: RoomAuthority
var _dirty := false
var _outbox: Array = []          # [[peer or 0 for all, kind, payload...]] sent after the state push
var _roster_t := 0.0
var _save_due := -1.0
var _save_period_t := 0.0


## Opens the listening socket. Returns OK or an Error.
func start(port: int, transport: String, p_verifier: JoinVerifier, p_store: SnapshotStore) -> Error:
	verifier = p_verifier
	store = p_store
	_net = Game.net
	_auth = Game.authority
	_net.server = self
	var err: Error
	var peer: MultiplayerPeer
	if transport == "ws":
		var ws := WebSocketMultiplayerPeer.new()
		err = ws.create_server(port)
		peer = ws
	else:
		var enet := ENetMultiplayerPeer.new()
		err = enet.create_server(port, MAX_PLAYERS)
		peer = enet
	if err != OK:
		return err
	multiplayer.multiplayer_peer = peer
	multiplayer.peer_disconnected.connect(_on_peer_disconnected)
	for sig: Signal in [_auth.node_state_changed, _auth.inventory_changed, _auth.evidence_changed, _auth.puzzles_changed]:
		sig.connect(func(_a = null, _b = null) -> void: _mark_dirty())
	_auth.event_logged.connect(func(_k: String, _d: Dictionary) -> void: _mark_dirty())
	_auth.puzzle_solved.connect(func(id: String) -> void: _queue_event(0, "puzzle_solved", {"puzzle": id}))
	_auth.hint_revealed.connect(func(p: String, t: int, text: String, a: bool) -> void:
		_queue_event(0, "hint_revealed", {"puzzle": p, "tier": t, "text": text, "automatic": a}))
	_auth.narrated.connect(func(t: String) -> void: _queue_event(0, "narrated", {"text": t}))
	_auth.time_up.connect(func() -> void: _queue_event(0, "time_up", {}))
	_auth.session_finished.connect(func(won: bool) -> void: _queue_event(0, "session_finished", {"won": won}))
	if platform:
		_auth.event_logged.connect(_on_event_logged)
		_auth.session_finished.connect(_report_finished)
		_start_challenges()
	print("escapebox server: session %s room %s listening on %s:%d" % [session_id, room_id, transport, port])
	return OK


func stop() -> void:
	_save_now()
	if multiplayer.multiplayer_peer:
		multiplayer.multiplayer_peer.close()
	multiplayer.multiplayer_peer = null
	if _net and _net.server == self:
		_net.server = null


# --- Incoming (called by NetBridge) -----------------------------------------

func on_join(peer: int, token: String, display_name: String) -> void:
	if players.has(peer):
		return
	verifier.verify_async(token, func(v: Dictionary) -> void: _complete_join(peer, display_name, v))


func _complete_join(peer: int, display_name: String, v: Dictionary) -> void:
	if players.has(peer) or not peer in multiplayer.get_peers():
		return  # joined twice, or left while the platform was answering
	if not v.get("ok", false):
		_net.rpc_rejected.rpc_id(peer, v.get("reason", "rejected"))
		print("join rejected for peer %d: %s" % [peer, v.get("reason")])
		# Let the rejection reach the client before dropping it.
		get_tree().create_timer(0.5).timeout.connect(func() -> void:
			if multiplayer.multiplayer_peer and not players.has(peer):
				multiplayer.multiplayer_peer.disconnect_peer(peer))
		return
	if not str(v.get("display_name", "")).is_empty():
		display_name = str(v["display_name"])
	var pid := _unique_player_id(display_name if str(v.get("player_id", "")).is_empty() else str(v["player_id"]))
	players[peer] = {"id": pid, "name": display_name.strip_edges().left(32)}
	# The server decides where a (re)joining player stands: where they were
	# last seen this server lifetime, else the spawn point.
	var start: Vector3 = _known_pos.get(pid, _spawn_eye())
	_last_move[pid] = {"pos": start, "t": _now()}
	_auth.update_player_position(pid, start)
	_auth.event_logged.emit("player_joined", {"player": pid})
	_net.rpc_welcome.rpc_id(peer, {
		"position": start,
		"player_id": pid,
		"room_id": room_id,
		"room_version": room_version,
		"snapshot_json": JSON.stringify(_auth.snapshot()),
		"server_now": _auth.clock.call(),
	})
	_queue_toast_others(peer, "%s joined." % players[peer]["name"])
	print("player %s joined (peer %d)" % [pid, peer])


func on_intent(peer: int, req_id: int, path: String, verb: String, payload: Dictionary) -> void:
	var pid := _player(peer)
	if pid.is_empty():
		return
	var r := _auth.handle_intent(pid, path, verb, payload)
	_mark_dirty()
	_outbox.append([peer, "result", req_id, r])


func on_note(peer: int, req_id: int, text: String) -> void:
	var pid := _player(peer)
	if pid.is_empty():
		return
	var r := _auth.add_note(pid, players[peer]["name"], text)
	_mark_dirty()
	_outbox.append([peer, "result", req_id, r])


func on_remove_note(peer: int, note_id: int) -> void:
	var pid := _player(peer)
	if not pid.is_empty():
		_auth.remove_note(pid, note_id)
		_mark_dirty()


func on_hint(peer: int, puzzle_id: String) -> void:
	var pid := _player(peer)
	if not pid.is_empty():
		_auth.request_hint(pid, puzzle_id)
		_mark_dirty()


func on_auto_nudge(peer: int, enabled: bool) -> void:
	var pid := _player(peer)
	if not pid.is_empty():
		_auth.set_auto_nudge(pid, enabled)
		_mark_dirty()


func on_start_clock(peer: int) -> void:
	var pid := _player(peer)
	if not pid.is_empty():
		_auth.start_clock(pid)
		_mark_dirty()


func on_position(peer: int, pos: Vector3, yaw: float) -> void:
	var pid := _player(peer)
	if pid.is_empty():
		return
	var now := _now()
	var last: Dictionary = _last_move.get(pid, {"pos": _spawn_eye(), "t": now})
	if not trust_positions and not move_allowed(last["pos"], pos, now - float(last["t"])):
		return  # implausible jump: keep the last accepted position
	_last_move[pid] = {"pos": pos, "t": now}
	_known_pos[pid] = pos
	_auth.update_player_position(pid, pos)
	_positions[pid] = {"name": players[peer]["name"], "pos": pos, "yaw": yaw}


static func move_allowed(from: Vector3, to: Vector3, dt: float) -> bool:
	return from.distance_to(to) <= MOVE_SLACK_M + MAX_SPEED_MPS * maxf(dt, 0.0)


func _now() -> float:
	return Time.get_ticks_msec() / 1000.0


func _spawn_eye() -> Vector3:
	var room := Game.room
	var origin: Vector3 = room.spawn_transform().origin if room else Vector3.ZERO
	return origin + Vector3.UP * FirstPersonPlayer.EYE_HEIGHT


func on_examining(peer: int, title: String) -> void:
	if players.has(peer):
		_queue_toast_others(peer, "%s is examining %s." % [players[peer]["name"], title.left(60)])


func _on_peer_disconnected(peer: int) -> void:
	if not players.has(peer):
		return
	var p: Dictionary = players[peer]
	players.erase(peer)
	_positions.erase(p["id"])
	_last_move.erase(p["id"])
	_auth.player_positions.erase(p["id"])
	_auth.event_logged.emit("player_left", {"player": p["id"]})
	_queue_toast_others(peer, "%s left." % p["name"])
	print("player %s left" % p["id"])


# --- Outgoing ---------------------------------------------------------------

func _process(delta: float) -> void:
	if _net == null:
		return
	if _dirty:
		_dirty = false
		var json := JSON.stringify(_auth.snapshot())
		var now: float = _auth.clock.call()
		for peer: int in players:
			_net.rpc_state.rpc_id(peer, json, now)
		_save_due = SNAPSHOT_DEBOUNCE_S if _save_due < 0.0 else _save_due
	# Results and events follow the state push so a client's callback and
	# signal handlers already see the world they describe.
	var out := _outbox
	_outbox = []
	for m: Array in out:
		var target: int = m[0]
		match m[1]:
			"result":
				if players.has(target):
					_net.rpc_result.rpc_id(target, m[2], m[3])
			"event":
				for peer: int in players:
					if target == 0 or (target < 0 and peer != -target):
						_net.rpc_event.rpc_id(peer, m[2], m[3])
	_roster_t -= delta
	if _roster_t <= 0.0 and not players.is_empty():
		_roster_t = 1.0 / ROSTER_HZ
		for peer: int in players:
			_net.rpc_roster.rpc_id(peer, _positions)
	if _save_due >= 0.0:
		_save_due -= delta
		if _save_due < 0.0:
			_save_now()
	_save_period_t += delta
	if _save_period_t >= SNAPSHOT_PERIOD_S:
		_save_period_t = 0.0
		_save_now()
	if platform:
		_events_t += delta
		if _events_t >= EVENT_FLUSH_S:
			_events_t = 0.0
			_flush_events()
	if idle_exit_s > 0.0:
		_idle_t = _idle_t + delta if players.is_empty() else 0.0
		if _idle_t >= idle_exit_s:
			_idle_exit()


# --- Platform (M3) ------------------------------------------------------------

func _start_challenges() -> void:
	platform.request_async(HTTPClient.METHOD_POST, platform.internal_path("challenges/start"), {}, func(code: int, data: Variant) -> void:
		if code == 200 and data is Dictionary and data.get("handles") is Dictionary:
			_auth.set_challenge_handles(data["handles"])
			print("challenges ready: %s" % ", ".join(PackedStringArray(data["handles"].keys())))
		else:
			var reason: String = data.get("message", "") if data is Dictionary else ""
			push_warning("challenge start failed (HTTP %d) %s" % [code, reason])
			var notes := {}
			for c: Dictionary in Game.manifest.challenges:
				notes[c["id"]] = {"note": "This challenge's service is unavailable right now (%s). Tell the host." % (reason if not reason.is_empty() else "no answer from the platform")}
			_auth.set_challenge_handles(notes), 600.0)


func _on_event_logged(kind: String, data: Dictionary) -> void:
	_events.append({"at": _auth.clock.call(), "kind": kind, "player_id": str(data.get("player", "")), "data": data})


func _flush_events() -> void:
	if _events.is_empty():
		return
	var batch := _events
	_events = []
	platform.request_async(HTTPClient.METHOD_POST, platform.internal_path("events"), batch, func(code: int, _d: Variant) -> void:
		if code != 204:
			_events = batch + _events  # keep them for the next flush
			push_warning("event upload failed (HTTP %d)" % code))


func _report_finished(won: bool) -> void:
	var s := _auth.state
	platform.request_async(HTTPClient.METHOD_POST, platform.internal_path("finished"),
		{"win": won, "elapsed_s": int(maxf(0.0, s.finished_at - s.started_at)), "hints_used": s.hints_used()}, Callable())


func _idle_exit() -> void:
	print("no players for %d s: saving and exiting (idle stop)" % int(idle_exit_s))
	idle_exit_s = 0.0
	if platform:
		_flush_events()
	if store is PlatformSnapshotStore:
		(store as PlatformSnapshotStore).save_blocking(_auth.snapshot())
	elif store:
		store.save(_auth.snapshot())
	get_tree().quit(0)


func _mark_dirty() -> void:
	_dirty = true


## Target 0 = everyone; a negative target -p = everyone except peer p.
func _queue_event(target: int, kind: String, data: Dictionary) -> void:
	_outbox.append([target, "event", kind, data])


func _queue_toast_others(peer: int, text: String) -> void:
	_queue_event(-peer, "toast", {"text": text})


func _save_now() -> void:
	_save_due = -1.0
	if store and _auth and _auth.state:
		store.save(_auth.snapshot())


func _player(peer: int) -> String:
	return players[peer]["id"] if players.has(peer) else ""


## Player id from the display name; a name that is already connected gets a
## suffix, a name that left keeps its id (rejoin keeps identity).
func _unique_player_id(display_name: String) -> String:
	var base := display_name.strip_edges().to_lower().validate_node_name().replace(" ", "_").left(24)
	if base.is_empty():
		base = "player"
	var taken := {}
	for peer: int in players:
		taken[players[peer]["id"]] = true
	var pid := base
	var n := 2
	while taken.has(pid):
		pid = "%s_%d" % [base, n]
		n += 1
	return pid
