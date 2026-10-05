@icon("res://addons/escapebox_sdk/icons/eb_node.svg")
class_name IndexedMechanism
extends Interactable
## A control with a fixed set of positions that stays where it is left: a
## sliding plate, a stone screen, a shutter, a valve handle, a mirror that
## turns in steps (ADR-0040). Each use moves it to the next position (a large
## tap target on phones, no dragging). It never opens anything itself:
## MechanismLock and OpticalNetwork read its position.
## State: {state: "ready", index: int, powered: bool}

signal moved(index: int)

## Position labels, in order. Used in prompts, in `set` intents and in a
## MechanismLock's `solutions` ("open", "closed"; or "0", "1", "2").
@export var detents: Array[String] = ["0", "1"]
@export var start_index: int = 0
## False for controls that need something else first (activation powers it).
@export var starts_powered: bool = true
@export var dead_message: String = "It won't move."
## Fixed in place once this SDK node's `state` is `freeze_state` (the lock it
## belongs to has opened).
@export var freeze_when: NodePath
@export var freeze_state: String = "unlocked"
@export var frozen_message: String = "It's fixed in place now."
## The lock whose room.yaml prerequisites also gate this control.
@export var gated_by: NodePath
## Parts moved by the control: part i turns by part_rotation_step[i] degrees
## and moves by part_offset_step[i] metres for every position past the first.
@export var parts: Array[NodePath] = []
@export var part_rotation_step: Array[Vector3] = []
@export var part_offset_step: Array[Vector3] = []
## Node i is shown only while the control is at position i (a veil drawn
## the other way round, a different face of a block).
@export var show_per_detent: Array[NodePath] = []

var _base := {}  # part -> [rotation_degrees, position]


func _init() -> void:
	verbs = ["turn"]


func _ready() -> void:
	super()
	for p in parts:
		var n := get_node_or_null(p) as Node3D
		if n:
			_base[n] = [n.rotation_degrees, n.position]


func _initial_state() -> Dictionary:
	return {"state": "ready", "index": clampi(start_index, 0, maxi(detents.size() - 1, 0)), "powered": starts_powered}


func gate_owner() -> EBNode:
	return get_node_or_null(gated_by) as EBNode if not gated_by.is_empty() else null


## Current position (server: authoritative; client: as last applied).
func index() -> int:
	return int(my_state().get("index", 0))


func label() -> String:
	var i := index()
	return detents[i] if i >= 0 and i < detents.size() else str(i)


## Position for a label or a number written as text; -1 if neither.
func index_of(value: String) -> int:
	value = value.strip_edges()
	for i in detents.size():
		if detents[i].to_lower() == value.to_lower():
			return i
	if value.is_valid_int() and int(value) >= 0 and int(value) < detents.size():
		return int(value)
	return -1


func is_frozen() -> bool:
	if freeze_when.is_empty():
		return false
	var n := get_node_or_null(freeze_when) as EBNode
	return n != null and state_of(n).get("state") == freeze_state


func is_powered() -> bool:
	return bool(my_state().get("powered", true))


func is_available() -> bool:
	return super() and not is_frozen()


func prompt(item_name: String = "") -> String:
	if not is_powered():
		return "%s (won't move)" % display_name
	return "%s (%s)" % [super(item_name), label()]


func _server_intent(_player_id: String, verb: String, payload: Dictionary) -> Dictionary:
	if is_frozen():
		return {"ok": false, "error": "frozen", "message": frozen_message}
	if not is_powered():
		return {"ok": false, "error": "no_power", "message": dead_message}
	var i := index()
	match verb:
		"turn":
			i = posmod(i + (-1 if int(payload.get("step", 1)) < 0 else 1), detents.size())
		"set":
			i = index_of(str(payload.get("value", "")))
			if i < 0:
				return {"ok": false, "error": "bad_position"}
		_:
			return {"ok": false, "error": "unsupported_verb"}
	set_state({"index": i})
	return {"ok": true, "index": i}


func _server_activate() -> void:
	if not is_powered():
		set_state({"powered": true})


func _apply_state(state: Dictionary) -> void:
	var i := int(state.get("index", 0))
	for k in parts.size():
		var n := get_node_or_null(parts[k]) as Node3D
		if n == null or not _base.has(n):
			continue
		var rot: Vector3 = part_rotation_step[k] if k < part_rotation_step.size() else Vector3.ZERO
		var off: Vector3 = part_offset_step[k] if k < part_offset_step.size() else Vector3.ZERO
		n.rotation_degrees = (_base[n][0] as Vector3) + rot * i
		n.position = (_base[n][1] as Vector3) + off * i
	for k in show_per_detent.size():
		var n := get_node_or_null(show_per_detent[k]) as Node3D
		if n:
			n.visible = k == i
	moved.emit(i)


func _state_sound(old: Dictionary, new: Dictionary) -> Variant:
	if int(old.get("index", 0)) != int(new.get("index", 0)):
		return "key"
	return "relay" if new.get("powered", false) and not old.get("powered", false) else ""
