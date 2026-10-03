@icon("res://addons/escapebox_sdk/icons/eb_node.svg")
class_name AllOfGate
extends EBNode
## Activates `targets` once, when every node in `inputs` is in its required
## state: three gears fitted -> the automaton runs; pendulum hung and clock
## wound -> its hands can be set. Not interactable. Server-side wiring only.
## State: {state: "waiting" | "fired"}

@export var inputs: Array[NodePath] = []
## Required `state` per input, same order; missing entries mean "unlocked".
@export var states: Array[String] = []
@export var targets: Array[NodePath] = []


func _ready() -> void:
	for i in inputs:
		var n := get_node_or_null(i) as EBNode
		if n:
			n.state_applied.connect(func(_s: Dictionary) -> void: _check())
		else:
			push_error("%s: no SDK node at input %s" % [name, i])


func _initial_state() -> Dictionary:
	return {"state": "waiting"}


func _check() -> void:
	if authority == null or authority.state == null or not authority.state.nodes.has(eb_path):
		return
	if my_state().get("state") == "fired":
		return
	for i in inputs.size():
		var n := get_node_or_null(inputs[i]) as EBNode
		var want := states[i] if i < states.size() else "unlocked"
		if n == null or state_of(n).get("state") != want:
			return
	set_state({"state": "fired"})
	for t in targets:
		authority.activate(room_path_of(t))
