@icon("res://addons/escapebox_sdk/icons/eb_node.svg")
class_name SequencePad
extends Interactable
## One bar, key or button of a SequenceLock (its nearest SequenceLock
## ancestor). Striking it rings a synthesised note on every client and feeds
## its symbol to the lock. State: {state: "idle", strikes: int}

## The character this pad adds to the sequence ("1", "C", ...).
@export var symbol: String = "1"
## Pitch of its note; 0 for silence.
@export var tone_hz: float = 440.0
## "bell" (tubes, chimes) or "whistle" (see EBSound.tone).
@export var tone_kind: String = "bell"
## Optional part that swings by `strike_rotation_deg` and back when struck.
@export var moving_part: NodePath
@export var strike_rotation_deg: Vector3 = Vector3(0, 0, 8)


func _init() -> void:
	verbs = ["strike"]


func _initial_state() -> Dictionary:
	return {"state": "idle", "strikes": 0}


func lock() -> SequenceLock:
	var p := get_parent()
	while p != null and not p is SequenceLock:
		p = p.get_parent()
	return p as SequenceLock


func _server_intent(_player_id: String, verb: String, _payload: Dictionary) -> Dictionary:
	if verb != "strike":
		return {"ok": false, "error": "unsupported_verb"}
	set_state({"strikes": int(my_state().get("strikes", 0)) + 1})
	var l := lock()
	if l and l.authority:
		l._server_strike(symbol)
	return {"ok": true}


func _state_sound(old: Dictionary, new: Dictionary) -> Variant:
	if int(new.get("strikes", 0)) <= int(old.get("strikes", 0)) or tone_hz <= 0.0:
		return ""
	_swing()
	# Played here rather than returned: notes must stay in tune (no jitter).
	EBSound.play_at(self, EBSound.tone(tone_hz, tone_kind), 0.0, 0.0)
	return ""


var _rest: Variant = null  # the moving part's scene rotation


func _swing() -> void:
	var p := get_node_or_null(moving_part) as Node3D
	if p == null or not p.is_inside_tree():
		return
	if _rest == null:
		_rest = p.rotation_degrees
	var base: Vector3 = _rest
	var tw := p.create_tween()
	tw.tween_property(p, "rotation_degrees", base + strike_rotation_deg, 0.08)
	tw.tween_property(p, "rotation_degrees", base, 0.5).set_trans(Tween.TRANS_SINE)
