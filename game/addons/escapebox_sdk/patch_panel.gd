@icon("res://addons/escapebox_sdk/icons/eb_node.svg")
class_name PatchPanel
extends Interactable
## Loose cables to plug into numbered ports. Players set every cable in the
## focused patch UI; when the mapping matches `solution` the panel is solved
## and activates `targets` once.
## State: {state: "idle" | "solved", connections: {cable_id: port}}

## Cable ids, e.g. ["A", "B", "C", "D"].
@export var cable_ids: PackedStringArray = ["A", "B", "C", "D"]
## Player-facing cable labels; never colour alone, e.g. "A - red, striped".
@export var cable_labels: PackedStringArray = []
@export var port_count: int = 8
## Correct mapping, "A:3,B:1,C:4,D:2". Server-only.
@export var solution: String = ""
@export var targets: Array[NodePath] = []


func _init() -> void:
	verbs = ["patch"]


func _initial_state() -> Dictionary:
	return {"state": "idle", "connections": {}}


func is_solved() -> bool:
	return my_state().get("state") == "solved"


func is_available() -> bool:
	return super() and not is_solved()


func label_of(cable_id: String) -> String:
	var i := cable_ids.find(cable_id)
	return cable_labels[i] if i >= 0 and i < cable_labels.size() else cable_id


## Parses "A:3,B:1" into {"A": 3, "B": 1}; {} if malformed or out of range.
func parse_mapping(text: String) -> Dictionary:
	var out := {}
	for pair in text.split(",", false):
		var kv := pair.strip_edges().split(":")
		if kv.size() != 2 or not kv[1].is_valid_int():
			return {}
		var cable := kv[0].strip_edges().to_upper()
		var port := int(kv[1])
		if not cable in cable_ids or port < 1 or port > port_count:
			return {}
		out[cable] = port
	return out


static func format_mapping(m: Dictionary) -> String:
	var keys := m.keys()
	keys.sort()
	return ",".join(keys.map(func(k: String) -> String: return "%s:%d" % [k, m[k]]))


func _server_intent(_player_id: String, verb: String, payload: Dictionary) -> Dictionary:
	if verb != "patch":
		return {"ok": false, "error": "unsupported_verb"}
	if is_solved():
		return {"ok": true, "already": true}
	var m := parse_mapping(str(payload.get("value", "")))
	if m.is_empty():
		return {"ok": false, "error": "bad_mapping", "message": "That doesn't fit the ports."}
	var want := parse_mapping(solution)
	var solved := not want.is_empty() and m == want
	set_state({"state": "solved" if solved else "idle", "connections": m})
	if solved:
		for t in targets:
			authority.activate(room_path_of(t))
		return {"ok": true}
	return {"ok": false, "error": "no_effect", "message": "Nothing happens."}


func client_interact(_item_path: String = "") -> void:
	Game.ui_open_patch_panel(self)


func _state_sound(old: Dictionary, new: Dictionary) -> Variant:
	return "relay" if new.get("state") == "solved" and old.get("state") != "solved" else ""
