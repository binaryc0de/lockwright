@icon("res://addons/escapebox_sdk/icons/eb_node.svg")
class_name Socket
extends Interactable
## One seat of a SocketLock (its nearest SocketLock ancestor): an arbor, a
## plinth, a shelf gap. Players seat any item the lock accepts and can take it
## back out until the lock opens. Children named after an item_id are shown
## while that item sits here (the seated wheel, the statue on its plinth).
## State: {state: "empty" | "seated", item: item path, item_id, item_name}

## Id used in the lock's `solutions` ("A", "B", ...); defaults to the node name.
@export var socket_id: String = ""


func _init() -> void:
	verbs = ["use", "take"]
	accepts_items = true


func _initial_state() -> Dictionary:
	return {"state": "empty", "item": "", "item_id": "", "item_name": ""}


func id() -> String:
	return socket_id if not socket_id.is_empty() else str(name)


func lock() -> SocketLock:
	var p := get_parent()
	while p != null and not p is SocketLock:
		p = p.get_parent()
	return p as SocketLock


func gate_owner() -> EBNode:
	return lock()


func seated_id() -> String:
	return str(my_state().get("item_id", "")) if my_state().get("state") == "seated" else ""


func current_verb() -> String:
	return "take" if not seated_id().is_empty() else "use"


func is_available() -> bool:
	var l := lock()
	return super() and (l == null or not l.is_unlocked())


func _server_available() -> bool:
	var l := lock()
	return l == null or not l.is_unlocked()


func prompt(item_name: String = "") -> String:
	if not seated_id().is_empty():
		return "Take %s from %s" % [_item_name(), display_name]
	return super(item_name)


func _item_name() -> String:
	return str(my_state().get("item_name", "it"))


func _server_intent(player_id: String, verb: String, payload: Dictionary) -> Dictionary:
	var l := lock()
	if l == null:
		return {"ok": false, "error": "no_lock"}
	if l.is_unlocked():
		return {"ok": false, "error": "unavailable"}
	if verb == "take":
		if seated_id().is_empty():
			return {"ok": false, "error": "empty", "message": "There is nothing here to take."}
		var path := str(my_state().get("item", ""))
		set_state({"state": "empty", "item": "", "item_id": "", "item_name": ""})
		authority.return_item(path, player_id)
		return {"ok": true}
	if verb != "use_item":
		return {"ok": false, "error": "needs_item", "message": l.empty_message}
	if not seated_id().is_empty():
		return {"ok": false, "error": "occupied", "message": "Something is already there. Take it out first."}
	var item := authority.node(payload.get("item", "")) as Item
	if item == null or not item.item_id in l.accepts:
		return {"ok": false, "error": "wrong_item", "message": "That doesn't fit."}
	authority.place_item(item.eb_path)
	set_state({"state": "seated", "item": item.eb_path, "item_id": item.item_id, "item_name": item.display_name})
	return l._server_socket_changed()


func _apply_state(state: Dictionary) -> void:
	var seated := str(state.get("item_id", "")) if state.get("state") == "seated" else ""
	var l := lock()
	if l == null:
		return
	for c in get_children():
		if c is Node3D and str(c.name) in l.accepts:
			(c as Node3D).visible = str(c.name) == seated


func _state_sound(old: Dictionary, new: Dictionary) -> Variant:
	if new.get("state") != old.get("state"):
		return "relay"
	return ""
