@icon("res://addons/escapebox_sdk/icons/eb_node.svg")
class_name MechanismLock
extends Lock
## Opens when its inputs are set right: plates aligned, shutters set, valve
## handles thrown, idols seated and facing the right way (ADR-0040). Inputs
## are IndexedMechanisms (read by position) or any other SDK node (read by
## its `state`). Either opens the moment the inputs match, or, with
## `on_submit`, when a player uses it ("Push the carriage home").
## State: Lock's.

## The nodes read, in the order `solutions` lists them.
@export var inputs: Array[NodePath] = []
## Right settings, "|"-separated; each a comma list with one value per input:
## a position label or number for an IndexedMechanism, otherwise the input's
## state ("unlocked", "on", "open"); "*" matches anything. May use {{vars}}.
## Server-only.
@export var solutions: String = ""
## Checked only when a player uses this lock, not on every change.
@export var on_submit: bool = false
## Told to players who submit a wrong setting.
@export var wrong_message: String = "It won't go."
## Activated when the lock opens (like a Lever's targets).
@export var targets: Array[NodePath] = []


func _init() -> void:
	verbs = ["use"]


func _ready() -> void:
	super()
	for p in inputs:
		var n := get_node_or_null(p) as EBNode
		if n:
			n.state_applied.connect(func(_s: Dictionary) -> void: _server_check())
		else:
			push_error("%s: no SDK node at input %s" % [name, p])


## What input `i` currently reads as, for matching.
func value_of(i: int) -> String:
	var n := get_node_or_null(inputs[i]) as EBNode
	if n == null:
		return ""
	if n is IndexedMechanism:
		var m := n as IndexedMechanism
		var idx := int(state_of(m).get("index", 0))
		return m.detents[idx] if idx < m.detents.size() else str(idx)
	return str(state_of(n).get("state", ""))


## Whether the inputs currently show one of the solutions.
func matches() -> bool:
	var values: Array[String] = []
	for i in inputs.size():
		values.append(value_of(i))
	for alt in authority.resolve(solutions).split("|", false):
		var want := alt.split(",")
		if want.size() != values.size():
			continue
		var ok := true
		for i in values.size():
			var w := want[i].strip_edges()
			if w != "*" and w.to_lower() != values[i].to_lower() and not _index_match(i, w):
				ok = false
				break
		if ok:
			return true
	return false


func _index_match(i: int, want: String) -> bool:
	var n := get_node_or_null(inputs[i]) as IndexedMechanism
	return n != null and want.is_valid_int() and int(want) == int(state_of(n).get("index", -1))


func _open() -> void:
	set_state({"state": "unlocked", "last_ok": true})
	for t in targets:
		authority.activate(room_path_of(t))


func _server_check() -> void:
	if on_submit or authority == null or authority.state == null or not authority.state.nodes.has(eb_path):
		return
	if is_unlocked() or not is_powered() or not authority.prerequisites_met(self):
		return
	if matches():
		_open()


func _server_intent(_player_id: String, verb: String, _payload: Dictionary) -> Dictionary:
	if not is_powered():
		return {"ok": false, "error": "no_power", "message": dead_message}
	if is_unlocked():
		return {"ok": true, "already": true}
	if verb != "use" or not on_submit:
		return {"ok": false, "error": "unsupported_verb", "message": wrong_message}
	if matches():
		_open()
		return {"ok": true, "opened": true}
	set_state({"attempts": int(my_state().get("attempts", 0)) + 1, "last_ok": false})
	return {"ok": false, "error": "wrong_setting", "message": wrong_message}


func _server_activate() -> void:
	if not is_powered():
		set_state({"powered": true})
		_server_check()
	elif not is_unlocked():
		_open()


func client_interact(_item_path: String = "") -> void:
	if not is_powered():
		Game.toast(dead_message)
		return
	Game.request(self, "use", {})
