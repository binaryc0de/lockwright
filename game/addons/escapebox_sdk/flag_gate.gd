@icon("res://addons/escapebox_sdk/icons/eb_node.svg")
class_name FlagGate
extends EBNode
## Bridges CTF to the world (PLAN.md 7.5): when `challenge_id`'s flag is
## accepted, activates every target (e.g. releases a MaglockGate).
## State: {state: "waiting" | "fired"}

@export var challenge_id: String = ""
@export var targets: Array[NodePath] = []


func _initial_state() -> Dictionary:
	return {"state": "waiting"}


func _server_flag_accepted(id: String) -> void:
	if id != challenge_id or current_state.get("state") == "fired":
		return
	set_state({"state": "fired"})
	for t in targets:
		authority.activate(room_path_of(t))
