@icon("res://addons/escapebox_sdk/icons/eb_node.svg")
class_name KeypadLock
extends Lock
## Number pad: opens the focused keypad UI; the code is checked on the server.

## Number of digits the display shows (the UI does not reveal the code length
## beyond this).
@export var display_length: int = 4


func _init() -> void:
	verbs = ["enter_code"]


func _server_intent(_player_id: String, verb: String, payload: Dictionary) -> Dictionary:
	if verb != "submit_code":
		return {"ok": false, "error": "unsupported_verb"}
	return _server_try_code(str(payload.get("value", "")))


func client_interact(_item_path: String = "") -> void:
	if not is_powered():
		Game.toast("The panel is dead.")
		return
	Game.ui_open_keypad(self)
