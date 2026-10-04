@icon("res://addons/escapebox_sdk/icons/eb_node.svg")
class_name Lock
extends Interactable
## Server-checked lock (PLAN.md 6.5). Subclasses add the way players try it.
## State: {state: "locked" | "unlocked", powered: bool, attempts: int, last_ok: bool}
##
## Activation (FlagGate / PatchPanel / Lever targets): an unpowered lock gets
## power; a powered lock unlocks.

signal unlocked
signal attempt_failed

## Correct code; may use per-session variables, e.g. "{{cabinet_code}}".
## Only ever read on the server.
@export var code: String = ""
## False for locks that need power first (e.g. a dead door panel).
@export var starts_powered: bool = true
## Nodes shown only once the lock is open (a fitted wheel, a hung pendulum)
## and nodes hidden then (an empty outline). Presentation only.
@export var show_when_unlocked: Array[NodePath] = []
@export var hide_when_unlocked: Array[NodePath] = []
## What players are told while the lock has no power, and the prompt suffix.
@export var dead_message: String = "The panel is dead."
@export var dead_prompt: String = "no power"
## Optional visuals: a MeshInstance3D or Light3D tinted red/green/off, and a
## Label3D showing status text.
@export var status_light: NodePath
@export var status_label: NodePath

const COLOR_OFF := Color(0.08, 0.08, 0.08)
const COLOR_LOCKED := Color(0.9, 0.12, 0.08)
const COLOR_OPEN := Color(0.1, 0.9, 0.2)


func _initial_state() -> Dictionary:
	return {"state": "locked", "powered": starts_powered, "attempts": 0, "last_ok": false}


func is_unlocked() -> bool:
	return my_state().get("state", "locked") == "unlocked"


func is_powered() -> bool:
	return my_state().get("powered", true)


func is_available() -> bool:
	return super() and not is_unlocked()


func prompt(item_name: String = "") -> String:
	if not is_powered():
		return "%s (%s)" % [display_name, dead_prompt]
	return super(item_name)


## Server: compares a submitted code. Normalises case and surrounding spaces.
func _server_try_code(value: String) -> Dictionary:
	if not is_powered():
		return {"ok": false, "error": "no_power", "message": dead_message}
	if is_unlocked():
		return {"ok": true, "already": true}
	var attempts: int = my_state().get("attempts", 0) + 1
	var correct := authority.resolve(code).strip_edges().to_upper()
	if value.strip_edges().to_upper() == correct and not correct.is_empty():
		set_state({"state": "unlocked", "attempts": attempts, "last_ok": true})
		return {"ok": true}
	set_state({"attempts": attempts, "last_ok": false})
	return {"ok": false, "error": "wrong_code", "message": "Wrong code."}


func _server_activate() -> void:
	if not is_powered():
		set_state({"powered": true})
	elif not is_unlocked():
		set_state({"state": "unlocked", "last_ok": true})


func _apply_state(state: Dictionary) -> void:
	var open: bool = state.get("state", "locked") == "unlocked"
	var powered: bool = state.get("powered", true)
	var color := COLOR_OFF
	if powered:
		color = COLOR_OPEN if open else COLOR_LOCKED
	var light := get_node_or_null(status_light)
	if light is Light3D:
		(light as Light3D).light_color = color
		(light as Light3D).visible = powered
	elif light is GeometryInstance3D:
		var mat := StandardMaterial3D.new()
		mat.albedo_color = color
		mat.emission_enabled = powered
		mat.emission = color
		mat.emission_energy_multiplier = 2.0
		(light as GeometryInstance3D).material_override = mat
	for p in show_when_unlocked:
		var n := get_node_or_null(p) as Node3D
		if n:
			n.visible = open
	for p in hide_when_unlocked:
		var n := get_node_or_null(p) as Node3D
		if n:
			n.visible = not open
	var label := get_node_or_null(status_label) as Label3D
	if label:
		label.text = "" if not powered else ("OPEN" if open else "LOCKED")
	if open:
		unlocked.emit()
	elif state.get("attempts", 0) > 0 and not state.get("last_ok", false):
		attempt_failed.emit()


func _state_sound(old: Dictionary, new: Dictionary) -> Variant:
	if new.get("state") == "unlocked" and old.get("state") != "unlocked":
		return "accept"
	if int(new.get("attempts", 0)) > int(old.get("attempts", 0)) and not new.get("last_ok", false):
		return "deny"
	if new.get("powered", false) and not old.get("powered", false):
		return "relay"
	return ""
