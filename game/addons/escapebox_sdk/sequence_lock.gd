@icon("res://addons/escapebox_sdk/icons/eb_node.svg")
class_name SequenceLock
extends Lock
## Opens when its SequencePad children are struck in the order of `code`
## (chime bars, piano keys, a row of buttons). The last strikes are compared,
## so players can start over at any time; pads ring whether or not they are
## right, and keep ringing after the lock opens. One character per symbol.
## State: Lock's, plus {entered: the most recent symbols}.

## How many recent strikes the lock keeps (at least the code's length).
const KEEP := 16


func _init() -> void:
	verbs = ["strike"]


func _initial_state() -> Dictionary:
	var s := super()
	s["entered"] = ""
	return s


func client_interact(_item_path: String = "") -> void:
	Game.toast("Strike them one at a time.")


## Server: a pad was struck. Unlocks when the tail of the strikes matches the
## code and the puzzles before this one are solved.
func _server_strike(symbol: String) -> void:
	if is_unlocked() or not is_powered():
		return
	var entered: String = (str(my_state().get("entered", "")) + symbol).right(KEEP)
	var want := authority.resolve(code).strip_edges().to_upper()
	if not want.is_empty() and entered.to_upper().ends_with(want) and authority.prerequisites_met(self):
		set_state({"entered": entered, "state": "unlocked", "last_ok": true})
	else:
		set_state({"entered": entered})


func _server_intent(_player_id: String, verb: String, payload: Dictionary) -> Dictionary:
	if verb != "submit_code":
		return {"ok": false, "error": "unsupported_verb"}
	# Strikes a whole sequence at once (solution replay); same rules as pads.
	for c in str(payload.get("value", "")).strip_edges():
		var pad := pad_for(c)
		if pad == null:
			return {"ok": false, "error": "wrong_code", "message": "There is no %s to strike." % c}
		pad._server_intent(_player_id, "strike", {})
	if is_unlocked():
		return {"ok": true}
	return {"ok": false, "error": "wrong_code", "message": "Nothing happens."}


## The pad that plays `symbol`, or null.
func pad_for(symbol: String) -> SequencePad:
	for p: SequencePad in find_children("*", "SequencePad", true, false):
		if p.symbol.to_upper() == symbol.to_upper():
			return p
	return null


func _state_sound(old: Dictionary, new: Dictionary) -> Variant:
	# Pads make the sound; the lock only clicks when it opens.
	return "relay" if new.get("state") == "unlocked" and old.get("state") != "unlocked" else ""
