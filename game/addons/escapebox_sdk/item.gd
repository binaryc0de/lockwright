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
## Optional file "on" the item (a USB stick's backup, a photo's EXIF dump):
## the inspect view shows it and lets players copy it or save it to their own
## computer for real tools. `file_text` may use {{vars}}.
@export var file_name: String = ""
@export_multiline var file_text: String = ""
## Optional guard: the item can only be picked up while this SDK node's
## `state` is `pick_up_requires_state` (an idol that stays put until its
## counterweight is set). Players are told `pick_up_refused_message`.
@export var pick_up_requires: NodePath
@export var pick_up_requires_state: String = "unlocked"
@export var pick_up_refused_message: String = "It won't come free."
## With a LoadPlate guard: its loads must be right at the moment of lifting
## (a balance must be level now), not merely have been right once.
@export var pick_up_requires_balance: bool = false


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
	var guard := get_node_or_null(pick_up_requires) as EBNode if not pick_up_requires.is_empty() else null
	if guard != null and state_of(guard).get("state") != pick_up_requires_state:
		return {"ok": false, "error": "held", "message": pick_up_refused_message}
	if guard is LoadPlate and pick_up_requires_balance and not (guard as LoadPlate).loads_right():
		return {"ok": false, "error": "held", "message": pick_up_refused_message}
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


func _state_sound(old: Dictionary, new: Dictionary) -> Variant:
	return "pick_up" if old.get("state") == "world" and new.get("state") == "inventory" else ""
