@icon("res://addons/escapebox_sdk/icons/eb_node.svg")
class_name Openable
extends Interactable
## Shared behaviour of ContainerProp and Door: open/close, optionally
## blocked by a Lock, with a moving part animated between two poses.
## State: {state: "closed" | "open"}

signal opened
signal closed

## Lock that must be unlocked before this opens (KeypadLock, KeyLock, MaglockGate...).
@export var locked_by: NodePath
## The part that moves (drawer, lid, door leaf). Its pose when open is its
## closed pose offset by these values.
@export var moving_part: NodePath
@export var open_offset: Vector3 = Vector3.ZERO
@export var open_rotation_deg: Vector3 = Vector3.ZERO
@export var start_open: bool = false
## Seconds the open/close animation takes.
@export var anim_time: float = 0.4
## Override the default open/close sounds (EBSound).
@export var open_sound: AudioStream
@export var close_sound: AudioStream

var _closed_pos: Vector3
var _closed_rot: Vector3
var _tween: Tween


func _init() -> void:
	verbs = ["open", "close"]


func _ready() -> void:
	super()
	var part := get_node_or_null(moving_part) as Node3D
	if part:
		_closed_pos = part.position
		_closed_rot = part.rotation_degrees


func _initial_state() -> Dictionary:
	return {"state": "open" if start_open else "closed"}


func is_open() -> bool:
	return my_state().get("state", "closed") == "open"


func current_verb() -> String:
	return "close" if is_open() else "open"


func lock_path() -> String:
	return room_path_of(locked_by)


## True while the linked lock (if any) is still locked. Authoritative on the
## server, last applied state on clients.
func is_locked() -> bool:
	var lock := get_node_or_null(locked_by) as Lock
	return lock != null and state_of(lock).get("state", "locked") != "unlocked"


func prompt(item_name: String = "") -> String:
	if not is_open() and is_locked() and item_name.is_empty():
		return "%s (locked)" % display_name
	return super(item_name)


func _server_intent(_player_id: String, verb: String, _payload: Dictionary) -> Dictionary:
	if verb == "toggle":
		verb = "close" if is_open() else "open"
	match verb:
		"open":
			if is_locked():
				return {"ok": false, "error": "locked", "message": "It's locked."}
			set_state({"state": "open"})
			return {"ok": true}
		"close":
			if _held_open():
				return {"ok": false, "error": "held_open", "message": "It's held open until everyone is inside."}
			set_state({"state": "closed"})
			return {"ok": true}
	return {"ok": false, "error": "unsupported_verb"}


## An airlock's door stays open while the airlock waits (ADR-0020): closing it
## could shut the team out behind its own lock.
func _held_open() -> bool:
	var gate: AirlockGate = room_root.airlock() if room_root is RoomRoot else null
	return gate != null and not gate.is_sealed() and gate.get_node_or_null(gate.door) == self


func _apply_state(state: Dictionary) -> void:
	var open: bool = state.get("state", "closed") == "open"
	var part := get_node_or_null(moving_part) as Node3D
	if part:
		var pos := _closed_pos + (open_offset if open else Vector3.ZERO)
		var rot := _closed_rot + (open_rotation_deg if open else Vector3.ZERO)
		if _tween:
			_tween.kill()
		if not is_inside_tree() or anim_time <= 0.0 or DisplayServer.get_name() == "headless":
			part.position = pos
			part.rotation_degrees = rot
		else:
			_tween = create_tween().set_parallel().set_trans(Tween.TRANS_SINE)
			_tween.tween_property(part, "position", pos, anim_time)
			_tween.tween_property(part, "rotation_degrees", rot, anim_time)
	if open:
		opened.emit()
	else:
		closed.emit()


func _state_sound(old: Dictionary, new: Dictionary) -> Variant:
	if old.get("state") == new.get("state"):
		return ""
	if new.get("state") == "open":
		return open_sound if open_sound else _default_sound(true)
	return close_sound if close_sound else _default_sound(false)


## Doors and drawers sound different; subclasses pick.
func _default_sound(opening: bool) -> String:
	return "drawer_open" if opening else "drawer_close"
