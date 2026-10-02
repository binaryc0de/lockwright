@icon("res://addons/escapebox_sdk/icons/eb_node.svg")
class_name MaglockGate
extends Lock
## Electromagnetic lock with no player input: released only by activation
## (FlagGate, PatchPanel, Lever targets).


func _init() -> void:
	verbs = ["examine"]


func is_available() -> bool:
	return false  # Not a direct interaction target.


func _server_available() -> bool:
	return false


func _server_intent(_player_id: String, _verb: String, _payload: Dictionary) -> Dictionary:
	return {"ok": false, "error": "no_input", "message": "The maglock is holding."}


func _state_sound(old: Dictionary, new: Dictionary) -> Variant:
	if new.get("state") == "unlocked" and old.get("state") != "unlocked":
		return "maglock_release"
	return ""
