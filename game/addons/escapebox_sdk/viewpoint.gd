@icon("res://addons/escapebox_sdk/icons/eb_node.svg")
class_name Viewpoint
extends KeyLock
## A sight to look through (a telescope, a sighting tube, a spy hole). With
## `key_item_id` set it first needs that part fitted, as a KeyLock; once open,
## using it moves the player's camera to `eye` (a Node3D looking along its -Z)
## with a narrow, round view, and the player can work `controls`
## (IndexedMechanisms seen through it) from there. Reach is checked to the
## sight; the sight relays each control to its mechanism on the server.

## Where the eye goes: a Node3D whose -Z looks along the sight.
@export var eye: NodePath
## Field of view through the sight, degrees.
@export var fov: float = 20.0
## Controls that can be worked while looking, and their button labels.
@export var controls: Array[NodePath] = []
@export var control_names: Array[String] = []
## Said when it is used before its part is fitted.
@export var unfitted_message: String = "There's nothing to look through."


func _init() -> void:
	super()
	verbs = ["look"]


func is_open() -> bool:
	return key_item_id.is_empty() or is_unlocked()


func current_verb() -> String:
	return "look"


## Unlike other locks, a sight stays usable once its part is fitted: that is
## when it is for looking through.
func is_available() -> bool:
	return is_visible_in_tree()


func _server_intent(player_id: String, verb: String, payload: Dictionary) -> Dictionary:
	match verb:
		"use_item":
			return super(player_id, verb, payload)
		"look":
			return {"ok": true} if is_open() else {"ok": false, "error": "unfitted", "message": unfitted_message}
		"work":
			if not is_open():
				return {"ok": false, "error": "unfitted", "message": unfitted_message}
			var i := int(payload.get("control", -1))
			if i < 0 or i >= controls.size():
				return {"ok": false, "error": "bad_control"}
			var target := authority.node(room_path_of(controls[i]))
			if target == null or not authority.is_available(target) or not authority.prerequisites_met(target):
				return {"ok": false, "error": "unavailable"}
			return target._server_intent(player_id, str(payload.get("verb", "turn")), {})
	return {"ok": false, "error": "bad_verb"}


func client_interact(item_path: String = "") -> void:
	if not item_path.is_empty():
		super(item_path)
	elif not is_open():
		Game.toast(unfitted_message)
	else:
		Game.ui_open_viewpoint(self)


## Asks the server to work control `i` (as if turned by hand).
func work(i: int) -> void:
	Game.request(self, "work", {"control": i, "verb": "turn"})
