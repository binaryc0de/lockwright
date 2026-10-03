@icon("res://addons/escapebox_sdk/icons/eb_node.svg")
class_name EBNode
extends Node3D
## Base of every replicated SDK node (PLAN.md 8.2). State lives in the
## session's WorldState under this node's path; the node renders it.
##
## Server side (authority != null): override _initial_state, _server_intent,
## _server_activate, _server_flag_accepted and change state with set_state().
## Both sides: override _apply_state to make the scene match the state. Room
## authors normally only set exports and connect to signals.

## Emitted on every side whenever this node's state changes.
signal state_applied(state: Dictionary)

## Path relative to the room root; the node's identity in the WorldState.
var eb_path: String = ""
## The session authority when this process owns the world; null on clients.
var authority: RoomAuthority = null
## The room scene root (RoomRoot) this node belongs to.
var room_root: Node = null
## Room difficulties this node exists in (room.yaml `difficulties` ids);
## empty = all. In other difficulties it is hidden, inert and unregistered.
@export var difficulties: Array[String] = []


## Every SDK node in `root`'s subtree, in tree order.
static func find_all(root: Node) -> Array[EBNode]:
	var out: Array[EBNode] = []
	_collect(root, out)
	return out


static func _collect(n: Node, out: Array[EBNode]) -> void:
	for c in n.get_children():
		if c is EBNode:
			out.append(c)
		_collect(c, out)


## Copy of the state as last applied, for presentation. Server decisions
## must use my_state()/state_of(), which read the authoritative table.
var current_state: Dictionary = {}


func _initial_state() -> Dictionary:
	return {"state": "idle"}


## Server: whether players may act on this node at all, from the WorldState.
## (Closed containers are handled by the authority.)
func _server_available() -> bool:
	return true


## Authoritative state of this node on the server; the applied copy on clients.
func my_state() -> Dictionary:
	return state_of(self)


func state_of(n: EBNode) -> Dictionary:
	if n == null:
		return {}
	return authority.state.node_state(n.eb_path) if authority else n.current_state


## Handles a player's intent on the server. Return {ok: true} or
## {ok: false, error: <code>, message?: <player-facing text>}.
func _server_intent(_player_id: String, _verb: String, _payload: Dictionary) -> Dictionary:
	return {"ok": false, "error": "unsupported_verb"}


## Called when another node (FlagGate, PatchPanel, Lever) activates this one.
func _server_activate() -> void:
	pass


func _server_flag_accepted(_challenge_id: String) -> void:
	pass


## Makes the scene reflect `state`. Called on server and clients, including
## once at session start or rejoin with the full state.
func _apply_state(_state: Dictionary) -> void:
	pass


## Server only: merges `patch` into this node's state.
func set_state(patch: Dictionary) -> void:
	assert(authority != null, "set_state() is server-only")
	authority.set_node_state(eb_path, patch)


## Resolves an exported NodePath to the target's room path ("" if unset or
## missing).
func room_path_of(target: NodePath) -> String:
	if target.is_empty() or room_root == null:
		return ""
	var t := get_node_or_null(target)
	if t == null:
		push_error("%s: no node at %s" % [eb_path, target])
		return ""
	return str(room_root.get_path_to(t))


## Assigns eb_path/room_root (and authority on the server) to every SDK node
## under `room`. Returns path -> node.
static func register_all(room: Node, p_authority: RoomAuthority, difficulty: String = "") -> Dictionary:
	var out := {}
	for n in find_all(room):
		if not n.difficulties.is_empty() and not difficulty in n.difficulties:
			n._deactivate()
			continue
		n.eb_path = str(room.get_path_to(n))
		n.room_root = room
		n.authority = p_authority
		out[n.eb_path] = n
	return out


## Takes a node out of play for this session's difficulty.
func _deactivate() -> void:
	set_meta("eb_inactive", true)
	if self is Node3D:
		(self as Node3D).visible = false
	process_mode = Node.PROCESS_MODE_DISABLED
	for cs: CollisionShape3D in find_children("*", "CollisionShape3D", true, false):
		cs.disabled = true


## Called by the session layer; not for room scripts.
func receive_state(state: Dictionary) -> void:
	var old := current_state
	current_state = state
	_apply_state(state)
	state_applied.emit(state)
	# Sound only for real changes, never for the first state (join/restore).
	if not old.is_empty() and old != state:
		var s: Variant = _state_sound(old, state)
		if s != null and not (s is String and s.is_empty()):
			EBSound.play_at(self, s)


## The sound for a state change: an EBSound key, an AudioStream, or "" for
## none. Plays on every client, positioned at this node.
func _state_sound(_old: Dictionary, _new: Dictionary) -> Variant:
	return ""


## Enables or disables every CollisionShape3D under `n` (hidden things must
## not block the interaction ray).
static func set_collisions_enabled(n: Node, enabled: bool) -> void:
	for c in n.get_children():
		if c is CollisionShape3D:
			(c as CollisionShape3D).set_deferred("disabled", not enabled)
		set_collisions_enabled(c, enabled)
