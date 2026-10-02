extends Node
## Autoload "Game": the client-side hub between the local player, the UI,
## the room's SDK nodes, and the session authority.
##
## M1 runs the authority in-process (offline single-player). M2 keeps this
## API and swaps the direct calls for RPCs to the dedicated server, which is
## why everything goes through request()/request_hint()/add_note() rather
## than touching the WorldState.

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

const ERROR_TEXT := {
	"locked": "It's locked.",
	"already_taken": "Someone already took it.",
	"out_of_reach": "Too far away.",
	"wrong_code": "Wrong code.",
	"no_power": "No power.",
	"wrong_flag": "Flag rejected.",
	"item_not_held": "You don't have that.",
}

var local_player_id: String = "p1"
var display_name: String = "Player"
var manifest: RoomManifest
var room: RoomRoot
var authority: RoomAuthority
## The UI layer (core/ui/hud.gd); null in tests and on the server.
var hud: Node = null
## Inventory item the local player has selected (client-local), "" for none.
var selected_item: String = "":
	set(v):
		selected_item = v
		selected_item_changed.emit(v)

var _nodes: Dictionary = {}


func _ready() -> void:
	InputActions.register()


## Starts an offline session: `room_instance` must already be in the tree.
func start_local_session(p_manifest: RoomManifest, room_instance: RoomRoot, session_id: String, snapshot: Dictionary = {}, flags: FlagValidator = null) -> void:
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
	session_started.emit()
	room.room_ready.emit()


func end_session() -> void:
	if authority:
		authority.queue_free()
	authority = null
	room = null
	manifest = null
	_nodes = {}
	selected_item = ""


func has_session() -> bool:
	return authority != null


## The local view of the world. M1: the authority's own state.
func world() -> WorldState:
	return authority.state if authority else null


func vars() -> Dictionary:
	return world().vars if authority else {}


func remaining_s() -> float:
	return world().remaining_s(Time.get_unix_time_from_system()) if authority else 0.0


func node_at(path: String) -> EBNode:
	return _nodes.get(path)


## True while the local player's selected item reveals UV content.
func uv_active() -> bool:
	var item := node_at(selected_item) as Item
	return item != null and item.is_uv_source()


func inventory() -> Array[String]:
	return world().inventory if authority else ([] as Array[String])


# --- Intents ---------------------------------------------------------------

func request(node: EBNode, verb: String, payload: Dictionary = {}) -> Dictionary:
	if authority == null:
		return {"ok": false, "error": "no_session"}
	var result := authority.handle_intent(local_player_id, node.eb_path, verb, payload)
	if not result.get("ok", false):
		var msg: String = result.get("message", ERROR_TEXT.get(result.get("error", ""), ""))
		if not msg.is_empty():
			toast(msg)
	intent_result.emit(node.eb_path, verb, result)
	return result


func request_hint(puzzle_id: String) -> Dictionary:
	return authority.request_hint(local_player_id, puzzle_id) if authority else {}


func set_auto_nudge(enabled: bool) -> void:
	if authority:
		authority.set_auto_nudge(local_player_id, enabled)


func add_note(text: String) -> Dictionary:
	return authority.add_note(local_player_id, display_name, text) if authority else {}


func remove_note(note_id: int) -> Dictionary:
	return authority.remove_note(local_player_id, note_id) if authority else {}


func report_position(pos: Vector3) -> void:
	if authority:
		authority.update_player_position(local_player_id, pos)


# --- UI hooks used by SDK nodes ---------------------------------------------

func toast(text: String) -> void:
	toasted.emit(text)


func ui_inspect_document(doc: Document) -> void:
	if hud:
		hud.open_document(doc)


func ui_inspect_item(item: Item) -> void:
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
