@icon("res://addons/escapebox_sdk/icons/eb_node.svg")
class_name KeyLock
extends Lock
## Opened by using an inventory Item whose item_id matches `key_item_id`.

@export var key_item_id: String = ""
@export var consume_key: bool = false


func _init() -> void:
	verbs = ["use"]
	accepts_items = true


func _server_intent(_player_id: String, verb: String, payload: Dictionary) -> Dictionary:
	if not is_powered():
		return {"ok": false, "error": "no_power", "message": dead_message}
	if verb != "use_item":
		return {"ok": false, "error": "needs_item", "message": "It needs a key."}
	var item := authority.node(payload.get("item", "")) as Item
	if item == null or item.item_id != key_item_id:
		return {"ok": false, "error": "wrong_item", "message": "That doesn't fit."}
	set_state({"state": "unlocked", "last_ok": true})
	if consume_key:
		authority.consume_item(item.eb_path)
	return {"ok": true}


func client_interact(item_path: String = "") -> void:
	if not is_powered():
		Game.toast(dead_message)
		return
	if item_path.is_empty():
		Game.toast("It needs a key.")
		return
	super(item_path)
