@icon("res://addons/escapebox_sdk/icons/eb_node.svg")
class_name Narration
extends EBNode
## A story beat (ADR-0040): the room's voice says `text` once, the first time
## a watched SDK node's state[watch_key], as text, equals watch_value (the
## building opens; a relief proves the families arrived). Shown on every
## client through the room's Intercom. Not interactable.
## State: {state: "waiting" | "told"}

@export var watch: NodePath
@export var watch_key: String = "state"
@export var watch_value: String = "unlocked"
@export_multiline var text: String = ""


func _ready() -> void:
	var w := get_node_or_null(watch) as EBNode
	if w:
		w.state_applied.connect(func(_s: Dictionary) -> void: _check())
	else:
		push_error("%s: no SDK node at %s" % [name, watch])


func _initial_state() -> Dictionary:
	return {"state": "waiting"}


func _check() -> void:
	if authority == null or authority.state == null or not authority.state.nodes.has(eb_path):
		return
	if my_state().get("state") == "told":
		return
	var w := get_node_or_null(watch) as EBNode
	if w == null or str(state_of(w).get(watch_key, "")) != watch_value:
		return
	set_state({"state": "told"})
	authority.narrate(authority.resolve(text))
