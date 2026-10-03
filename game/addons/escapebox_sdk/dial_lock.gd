@icon("res://addons/escapebox_sdk/icons/eb_node.svg")
class_name DialLock
extends Lock
## Wheels, rings or clock hands that open the lock when every one shows the
## right symbol (ADR-0033; covers the planned LetterLock). Players turn wheels
## in a focused view; every turn is an intent, so teammates see the wheels
## move, and the lock opens the moment the combination is right.
## State: Lock's, plus {dials: [index per wheel]}.

## One entry per wheel: its symbols in order, comma-separated ("12,1,2,...")
## or, with no comma, one symbol per character ("ABCDEFGHIJKLMNOPQRSTUVWXYZ").
@export var wheels: Array[String] = ["ABCDEFGHIJKLMNOPQRSTUVWXYZ"]
## Joins the wheels' symbols into the code ("4:40" with ":"). Empty means
## symbols are single characters joined directly ("MAREN").
@export var separator: String = ""
## Captions for the wheels in the focused view, e.g. ["Hour", "Minute"].
@export var wheel_labels: Array[String] = []
## Where the wheels start, written like a code ("11:05"); empty = first symbols.
@export var start_code: String = ""
## Optional parts (rings, clock hands) turned by each wheel: symbol i of n
## rotates its part by hand_turn * i / n from where the scene puts it.
@export var hand_parts: Array[NodePath] = []
## Rotation in degrees for one full turn of a wheel (sign sets the direction).
@export var hand_turn: Vector3 = Vector3(0, 0, -360)

var _hand_base := {}  # part -> its scene rotation


func _init() -> void:
	verbs = ["dial"]


func _initial_state() -> Dictionary:
	var s := super()
	var start: Array[int] = []
	if not start_code.is_empty():
		start = parse_code(start_code)
	if start.is_empty():
		for i in wheels.size():
			start.append(0)
	s["dials"] = start
	return s


## Symbols of wheel `i`.
func symbols(i: int) -> PackedStringArray:
	var w := wheels[i]
	if w.contains(","):
		var out := PackedStringArray()
		for s in w.split(","):
			out.append(s.strip_edges())
		return out
	var chars := PackedStringArray()
	for c in w:
		chars.append(c)
	return chars


## Wheel indices (ints) of a state, safe after a JSON round trip.
static func dials_of(state: Dictionary) -> Array[int]:
	var out: Array[int] = []
	for v in state.get("dials", []):
		out.append(int(v))
	return out


## The code the wheels show for `dials`.
func code_for(dials: Array[int]) -> String:
	var parts := PackedStringArray()
	for i in wheels.size():
		var syms := symbols(i)
		parts.append(syms[posmod(dials[i] if i < dials.size() else 0, syms.size())])
	return separator.join(parts)


## Wheel indices for a written code, or [] if it does not fit the wheels.
func parse_code(text: String) -> Array[int]:
	var parts := PackedStringArray()
	text = text.strip_edges().to_upper()
	if separator.is_empty():
		for c in text:
			parts.append(c)
	else:
		for p in text.split(separator):
			parts.append(p.strip_edges())
	var out: Array[int] = []
	if parts.size() != wheels.size():
		return out
	for i in wheels.size():
		var syms := symbols(i)
		var idx := -1
		for j in syms.size():
			if syms[j].to_upper() == parts[i]:
				idx = j
				break
		if idx < 0:
			return [] as Array[int]
		out.append(idx)
	return out


func _server_intent(_player_id: String, verb: String, payload: Dictionary) -> Dictionary:
	if not is_powered():
		return {"ok": false, "error": "no_power", "message": dead_message}
	if is_unlocked():
		return {"ok": true, "already": true}
	var dials := dials_of(my_state())
	match verb:
		"turn":
			var i := int(payload.get("wheel", -1))
			var step := signi(int(payload.get("step", 1)))
			if i < 0 or i >= wheels.size() or step == 0:
				return {"ok": false, "error": "bad_wheel"}
			dials[i] = posmod(dials[i] + step, symbols(i).size())
		"submit_code":
			# Setting every wheel at once (solution replay, keyboard entry).
			var want := parse_code(str(payload.get("value", "")))
			if want.is_empty():
				set_state({"attempts": int(my_state().get("attempts", 0)) + 1, "last_ok": false})
				return {"ok": false, "error": "wrong_code", "message": "The wheels don't have those symbols."}
			dials = want
		_:
			return {"ok": false, "error": "unsupported_verb"}
	set_state({"dials": dials})
	if code_for(dials).to_upper() == authority.resolve(code).strip_edges().to_upper():
		set_state({"state": "unlocked", "last_ok": true})
		return {"ok": true, "opened": true}
	if verb == "submit_code":
		set_state({"attempts": int(my_state().get("attempts", 0)) + 1, "last_ok": false})
		return {"ok": false, "error": "wrong_code", "message": "Nothing gives."}
	return {"ok": true}


func _apply_state(state: Dictionary) -> void:
	super(state)
	var dials := dials_of(state)
	for i in mini(hand_parts.size(), wheels.size()):
		var part := get_node_or_null(hand_parts[i]) as Node3D
		if part == null:
			continue
		if not _hand_base.has(part):
			_hand_base[part] = part.rotation_degrees
		var n := symbols(i).size()
		var idx := dials[i] if i < dials.size() else 0
		part.rotation_degrees = (_hand_base[part] as Vector3) + hand_turn * (float(idx) / n)


func client_interact(_item_path: String = "") -> void:
	if not is_powered():
		Game.toast(dead_message)
		return
	Game.ui_open_dial_lock(self)


func _state_sound(old: Dictionary, new: Dictionary) -> Variant:
	var s: Variant = super(old, new)
	if s is String and not (s as String).is_empty():
		return s
	return "key" if old.get("dials") != new.get("dials") else ""
