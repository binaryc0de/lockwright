@icon("res://addons/escapebox_sdk/icons/eb_node.svg")
class_name LoadPan
extends Interactable
## One pan (or one arm of a lever) of a LoadPlate, its nearest LoadPlate
## ancestor. Use an item on it to set it down; Take lifts the last one off.
## Its load is the sum of its items' weights; the plate counts it times
## `multiplier` (a long arm counts double). Children named after an item_id
## are shown while that item sits here.
## State: {state: "empty" | "loaded", items: [{item, item_id, item_name}], load: int}

@export var multiplier: int = 1
@export var capacity: int = 4
## Load this pan must carry for the plate to open; -1 = any.
@export var target: int = -1
## Optional gauge: a needle turned by needle_step per unit of load, and a
## Label3D showing the load as text.
@export var gauge_needle: NodePath
@export var needle_step: Vector3 = Vector3(0, 0, -15)
@export var gauge_label: NodePath

var _needle_base: Variant = null


func _init() -> void:
	verbs = ["take"]
	accepts_items = true


func _initial_state() -> Dictionary:
	return {"state": "empty", "items": [], "load": 0}


func plate() -> LoadPlate:
	var p := get_parent()
	while p != null and not p is LoadPlate:
		p = p.get_parent()
	return p as LoadPlate


func gate_owner() -> EBNode:
	return plate()


func current_load() -> int:
	return int(my_state().get("load", 0))


func items() -> Array:
	return my_state().get("items", [])


func prompt(item_name: String = "") -> String:
	if item_name.is_empty() and not items().is_empty():
		var last: Dictionary = items()[-1]
		return "Take %s from %s" % [last.get("item_name", "it"), display_name]
	return super(item_name)


func client_interact(item_path: String = "") -> void:
	if item_path.is_empty() and items().is_empty():
		Game.toast("It's empty.")
		return
	super(item_path)


func _server_intent(player_id: String, verb: String, payload: Dictionary) -> Dictionary:
	var pl := plate()
	if pl == null:
		return {"ok": false, "error": "no_plate"}
	var list: Array = items().duplicate(true)
	if verb == "take":
		if list.is_empty():
			return {"ok": false, "error": "empty", "message": "There is nothing on it."}
		var last: Dictionary = list.pop_back()
		_store(pl, list)
		authority.return_item(str(last.get("item", "")), player_id)
		return pl._server_pan_changed()
	if verb != "use_item":
		return {"ok": false, "error": "unsupported_verb"}
	var item := authority.node(payload.get("item", "")) as Item
	if item == null or pl.weight_of(item.item_id) < 0:
		return {"ok": false, "error": "wrong_item", "message": "That isn't one of the weights."}
	if list.size() >= capacity:
		return {"ok": false, "error": "full", "message": "There's no room for more."}
	authority.place_item(item.eb_path)
	list.append({"item": item.eb_path, "item_id": item.item_id, "item_name": item.display_name})
	_store(pl, list)
	return pl._server_pan_changed()


func _store(pl: LoadPlate, list: Array) -> void:
	var total := 0
	for it: Dictionary in list:
		total += maxi(pl.weight_of(str(it.get("item_id", ""))), 0)
	set_state({"state": "loaded" if not list.is_empty() else "empty", "items": list, "load": total})


func _apply_state(state: Dictionary) -> void:
	var ids := {}
	for it in state.get("items", []):
		ids[str(it.get("item_id", ""))] = true
	var pl := plate()
	if pl:
		for c in get_children():
			if c is Node3D and str(c.name) in pl.weight_items:
				(c as Node3D).visible = ids.has(str(c.name))
	var amount := int(state.get("load", 0))
	var needle := get_node_or_null(gauge_needle) as Node3D
	if needle:
		if _needle_base == null:
			_needle_base = needle.rotation_degrees
		needle.rotation_degrees = (_needle_base as Vector3) + needle_step * amount
	var label := get_node_or_null(gauge_label) as Label3D
	if label:
		label.text = str(amount)


func _state_sound(old: Dictionary, new: Dictionary) -> Variant:
	return "relay" if old.get("load") != new.get("load") else ""
