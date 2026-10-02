@icon("res://addons/escapebox_sdk/icons/eb_node.svg")
class_name Item
extends Interactable
## A prop players pick up into the shared team inventory (PLAN.md 6.4).
## First intent wins; everyone sees it leave the world.
## State: {state: "world" | "inventory" | "consumed"}

## Stable id used by room.yaml (`item_picked_up: <item_id>`), keys, and recipes.
@export var item_id: String = ""
## Shown in the inspect view.
@export_multiline var description: String = ""
## Text only readable with a UV torch active (shown in the inspect view).
@export_multiline var uv_text: String = ""


func _init() -> void:
	verbs = ["pick_up"]


func _initial_state() -> Dictionary:
	return {"state": "world"}


func is_available() -> bool:
	return super() and current_state.get("state", "world") == "world"


func _server_available() -> bool:
	return my_state().get("state", "world") == "world"


func _server_intent(player_id: String, verb: String, _payload: Dictionary) -> Dictionary:
	if verb != "pick_up":
		return {"ok": false, "error": "unsupported_verb"}
	if my_state().get("state") != "world":
		return {"ok": false, "error": "already_taken", "message": "Someone already took it."}
	set_state({"state": "inventory"})
	authority.give_item(eb_path, item_id, player_id)
	return {"ok": true}


func _apply_state(state: Dictionary) -> void:
	var in_world: bool = state.get("state", "world") == "world"
	visible = in_world
	EBNode.set_collisions_enabled(self, in_world)


## True for items that switch on UV layers while selected.
func is_uv_source() -> bool:
	return false
