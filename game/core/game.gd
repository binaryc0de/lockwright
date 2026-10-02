extends Node
## Autoload "Game": the hub between the local player, the UI, the room's SDK
## nodes, and the session authority.
##
## Three modes (ADR-0015):
##   LOCAL  - offline single-player; the authority runs in this process (M1).
##   SERVER - headless dedicated server; authority + room, no player or HUD.
##   CLIENT - networked player; no authority, a mirror WorldState fed by the
##            server through the `Net` child (core/net/net_bridge.gd).
## The UI and SDK nodes only use request()/request_hint()/add_note() and the
## signals below, so they work the same in every mode.

signal session_started
signal node_state_changed(path: String, state: Dictionary)
signal inventory_changed(inventory: Array[String])
signal evidence_changed(evidence: Array[Dictionary])
signal puzzles_changed(puzzles: Dictionary)
signal puzzle_solved(puzzle_id: String)
signal hint_revealed(puzzle_id: String, tier: int, text: String, automatic: bool)
signal narrated(text: String)
signal toasted(text: String)
signal time_up
signal session_finished(won: bool)
signal selected_item_changed(item_path: String)
## The requesting player's result for an intent.
signal intent_result(path: String, verb: String, result: Dictionary)
## CLIENT: connection status for the HUD ("connecting", "connected", "lost", "rejected").
signal connection_changed(status: String, detail: String)

enum Mode { NONE, LOCAL, SERVER, CLIENT }

const ERROR_TEXT := {
	"locked": "It's locked.",
	"already_taken": "Someone already took it.",
	"out_of_reach": "Too far away.",
	"wrong_code": "Wrong code.",
	"no_power": "No power.",
	"wrong_flag": "Flag rejected.",
	"item_not_held": "You don't have that.",
	"not_connected": "Not connected to the server.",
}

var mode: Mode = Mode.NONE
var local_player_id: String = "p1"
var display_name: String = "Player"
var manifest: RoomManifest
var room: RoomRoot
## LOCAL and SERVER only.
var authority: RoomAuthority
## The UI layer (core/ui/hud.gd); null in tests and on the server.
var hud: Node = null
## Inventory item the local player has selected (client-local), "" for none.
var selected_item: String = "":
	set(v):
		selected_item = v
		selected_item_changed.emit(v)
## The RPC endpoint (always present so its node path is identical on every peer).
var net: NetBridge

var _nodes: Dictionary = {}
## CLIENT: the server's world as last received.
var _mirror: WorldState = null
## CLIENT: server unix time minus local unix time.
var _clock_offset: float = 0.0


func _ready() -> void:
	InputActions.register()
	net = NetBridge.new()
	net.name = "Net"
	add_child(net)


## LOCAL: starts an offline session; `room_instance` must already be in the tree.
func start_local_session(p_manifest: RoomManifest, room_instance: RoomRoot, session_id: String, snapshot: Dictionary = {}, flags: FlagValidator = null) -> void:
	_start_authority(p_manifest, room_instance, session_id, snapshot, flags)
	mode = Mode.LOCAL
	session_started.emit()
	room.room_ready.emit()


## SERVER: hosts the authority for networked clients (no local player).
func start_server_session(p_manifest: RoomManifest, room_instance: RoomRoot, session_id: String, snapshot: Dictionary = {}, flags: FlagValidator = null) -> void:
	_start_authority(p_manifest, room_instance, session_id, snapshot, flags)
	mode = Mode.SERVER
	room.room_ready.emit()


## CLIENT: binds the loaded room to a server snapshot (called by NetBridge on join).
func start_client_session(p_manifest: RoomManifest, room_instance: RoomRoot, player_id: String, snapshot: Dictionary, server_now: float) -> void:
	end_session()
	mode = Mode.CLIENT
	manifest = p_manifest
	room = room_instance
	local_player_id = player_id
	_nodes = EBNode.register_all(room, null)
	_mirror = WorldState.new()
	apply_server_state(snapshot, server_now, true)
	session_started.emit()
	room.room_ready.emit()


## CLIENT: after a reconnect, the server's welcome replaces the whole mirror.
func rejoin_client(player_id: String, snapshot: Dictionary, server_now: float) -> void:
	local_player_id = player_id
	apply_server_state(snapshot, server_now, true)


func _start_authority(p_manifest: RoomManifest, room_instance: RoomRoot, session_id: String, snapshot: Dictionary, flags: FlagValidator) -> void:
	end_session()
	manifest = p_manifest
	room = room_instance
	authority = RoomAuthority.new()
	authority.name = "RoomAuthority"
	if flags:
		authority.flags = flags
	add_child(authority)
	authority.setup(manifest, room, session_id, snapshot)
	_nodes = authority._nodes
	authority.node_state_changed.connect(func(p: String, s: Dictionary) -> void: node_state_changed.emit(p, s))
	authority.inventory_changed.connect(_on_inventory_changed)
	authority.evidence_changed.connect(func(e: Array[Dictionary]) -> void: evidence_changed.emit(e))
	authority.puzzles_changed.connect(func(p: Dictionary) -> void: puzzles_changed.emit(p))
	authority.puzzle_solved.connect(_on_puzzle_solved)
	authority.hint_revealed.connect(func(p: String, t: int, text: String, a: bool) -> void: hint_revealed.emit(p, t, text, a))
	authority.narrated.connect(func(t: String) -> void: narrated.emit(t))
	authority.time_up.connect(func() -> void: time_up.emit())
	authority.session_finished.connect(_on_session_finished)


func end_session() -> void:
	if authority:
		authority.queue_free()
	authority = null
	room = null
	manifest = null
	_nodes = {}
	_mirror = null
	_clock_offset = 0.0
	selected_item = ""
	if mode == Mode.CLIENT:
		net.disconnect_client()
	mode = Mode.NONE


func has_session() -> bool:
	return authority != null or _mirror != null


func is_client() -> bool:
	return mode == Mode.CLIENT


## The local view of the world: the authority's own state (LOCAL, SERVER) or
## the mirror of the server's (CLIENT). Read-only for everyone but the authority.
func world() -> WorldState:
	if authority:
		return authority.state
	return _mirror


func vars() -> Dictionary:
	return world().vars if has_session() else {}


## Server unix time as seen from this process.
func server_now() -> float:
	return Time.get_unix_time_from_system() + _clock_offset


func remaining_s() -> float:
	return world().remaining_s(server_now()) if has_session() else 0.0


func node_at(path: String) -> EBNode:
	return _nodes.get(path)


## True while the local player's selected item reveals UV content.
func uv_active() -> bool:
	var item := node_at(selected_item) as Item
	return item != null and item.is_uv_source()


func inventory() -> Array[String]:
	return world().inventory if has_session() else ([] as Array[String])


# --- Intents ---------------------------------------------------------------

## Sends an intent for the local player. The result ({ok, error?, message?})
## arrives through `on_result` and `intent_result`: synchronously in LOCAL
## mode, when the server answers in CLIENT mode.
func request(node: EBNode, verb: String, payload: Dictionary = {}, on_result: Callable = Callable()) -> void:
	if mode == Mode.CLIENT:
		net.send_intent(node.eb_path, verb, payload, func(r: Dictionary) -> void: _deliver_result(node.eb_path, verb, r, on_result))
		return
	var result: Dictionary = {"ok": false, "error": "no_session"}
	if authority:
		result = authority.handle_intent(local_player_id, node.eb_path, verb, payload)
	_deliver_result(node.eb_path, verb, result, on_result)


func _deliver_result(path: String, verb: String, result: Dictionary, on_result: Callable) -> void:
	if not result.get("ok", false):
		var msg: String = result.get("message", ERROR_TEXT.get(result.get("error", ""), ""))
		if not msg.is_empty():
			toast(msg)
	if on_result.is_valid():
		on_result.call(result)
	intent_result.emit(path, verb, result)


func start_clock() -> void:
	if mode == Mode.CLIENT:
		net.send_start_clock()
	elif authority:
		authority.start_clock(local_player_id)


func request_hint(puzzle_id: String) -> void:
	if mode == Mode.CLIENT:
		net.send_hint_request(puzzle_id)
	elif authority:
		authority.request_hint(local_player_id, puzzle_id)


func set_auto_nudge(enabled: bool) -> void:
	if mode == Mode.CLIENT:
		net.send_auto_nudge(enabled)
	elif authority:
		authority.set_auto_nudge(local_player_id, enabled)


func add_note(text: String, on_result: Callable = Callable()) -> void:
	if mode == Mode.CLIENT:
		net.send_note(text, on_result)
		return
	var r: Dictionary = authority.add_note(local_player_id, display_name, text) if authority else {}
	if on_result.is_valid():
		on_result.call(r)


func remove_note(note_id: int) -> void:
	if mode == Mode.CLIENT:
		net.send_remove_note(note_id)
	elif authority:
		authority.remove_note(local_player_id, note_id)


func report_position(pos: Vector3, yaw: float = 0.0) -> void:
	if mode == Mode.CLIENT:
		net.send_position(pos, yaw)
	elif authority:
		authority.update_player_position(local_player_id, pos)


## Tells teammates what the local player is looking at (PLAN.md 6.3).
func announce_examining(title: String) -> void:
	if mode == Mode.CLIENT:
		net.send_examining(title)


# --- CLIENT: applying the server's world ----------------------------------

## Replaces the mirror with `snapshot` and emits the same signals LOCAL mode
## would for whatever changed. `full` re-applies every node (join/rejoin).
func apply_server_state(snapshot: Dictionary, server_time: float, full: bool = false) -> void:
	if _mirror == null:
		return
	_clock_offset = server_time - Time.get_unix_time_from_system()
	var old := _mirror
	var new_state := WorldState.from_dict(snapshot)
	_mirror = new_state
	for path: String in new_state.nodes:
		var s: Dictionary = new_state.nodes[path]
		if full or old.nodes.get(path, {}) != s:
			var n: EBNode = _nodes.get(path)
			if n:
				n.receive_state(s.duplicate(true))
			node_state_changed.emit(path, s.duplicate(true))
	if full or old.inventory != new_state.inventory:
		_on_inventory_changed(new_state.inventory)
	if full or old.evidence != new_state.evidence:
		evidence_changed.emit(new_state.evidence)
	if full or old.puzzles != new_state.puzzles:
		puzzles_changed.emit(new_state.puzzles)


## CLIENT: a server event that is not part of the WorldState.
func apply_server_event(kind: String, data: Dictionary) -> void:
	match kind:
		"puzzle_solved":
			_on_puzzle_solved(data["puzzle"])
		"hint_revealed":
			hint_revealed.emit(data["puzzle"], int(data["tier"]), data["text"], bool(data["automatic"]))
		"narrated":
			narrated.emit(data["text"])
		"toast":
			toast(data["text"])
		"time_up":
			time_up.emit()
		"session_finished":
			_on_session_finished(bool(data["won"]))


# --- UI hooks used by SDK nodes ---------------------------------------------

func toast(text: String) -> void:
	toasted.emit(text)


func ui_inspect_document(doc: Document) -> void:
	announce_examining(doc.title)
	if hud:
		hud.open_document(doc)


func ui_inspect_item(item: Item) -> void:
	announce_examining(item.display_name)
	if hud:
		hud.open_item(item)


func ui_open_keypad(lock: KeypadLock) -> void:
	if hud:
		hud.open_keypad(lock)


func ui_open_patch_panel(panel: PatchPanel) -> void:
	if hud:
		hud.open_patch_panel(panel)


func ui_open_terminal(term: Terminal) -> void:
	if hud:
		hud.open_terminal(term)


func _on_inventory_changed(inv: Array[String]) -> void:
	if not selected_item.is_empty() and not selected_item in inv:
		selected_item = ""
	inventory_changed.emit(inv)


func _on_puzzle_solved(id: String) -> void:
	puzzle_solved.emit(id)
	if room:
		room.puzzle_solved.emit(id)


func _on_session_finished(won: bool) -> void:
	session_finished.emit(won)
	if room:
		room.session_finished.emit(won)
