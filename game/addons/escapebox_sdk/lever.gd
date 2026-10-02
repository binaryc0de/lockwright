@icon("res://addons/escapebox_sdk/icons/eb_node.svg")
class_name Lever
extends Interactable
## Two-position lever or switch. Activates `targets` the first time it is
## switched on. State: {state: "off" | "on", fired: bool}

signal changed(state: String)

@export var targets: Array[NodePath] = []
## Optional part that rotates by `on_rotation_deg` when on.
@export var moving_part: NodePath
@export var on_rotation_deg: Vector3 = Vector3(-60, 0, 0)

var _off_rot: Vector3


func _init() -> void:
	verbs = ["toggle"]


func _ready() -> void:
	super()
	var p := get_node_or_null(moving_part) as Node3D
	if p:
		_off_rot = p.rotation_degrees


func _initial_state() -> Dictionary:
	return {"state": "off", "fired": false}


func _server_intent(_player_id: String, verb: String, _payload: Dictionary) -> Dictionary:
	if verb != "toggle":
		return {"ok": false, "error": "unsupported_verb"}
	var cur := my_state()
	var on: bool = cur.get("state") != "on"
	var fire: bool = on and not cur.get("fired", false)
	set_state({"state": "on" if on else "off", "fired": cur.get("fired", false) or fire})
	if fire:
		for t in targets:
			authority.activate(room_path_of(t))
	return {"ok": true}


func _apply_state(state: Dictionary) -> void:
	var p := get_node_or_null(moving_part) as Node3D
	if p:
		p.rotation_degrees = _off_rot + (on_rotation_deg if state.get("state") == "on" else Vector3.ZERO)
	changed.emit(state.get("state", "off"))


func _state_sound(old: Dictionary, new: Dictionary) -> Variant:
	return "relay" if old.get("state") != new.get("state") else ""
