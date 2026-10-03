@icon("res://addons/escapebox_sdk/icons/eb_node.svg")
class_name SequencePlayer
extends Interactable
## Plays a sequence of notes when wound or pressed (a music box, a songbird,
## a bell tower) so players can copy it onto a SequenceLock. Each note also
## turns `pointer` to that symbol's position, so the sequence can be read
## without sound. Replays as often as players like. Starts dead unless
## `starts_powered`; activation (AllOfGate, Lever, ...) brings it to life.
## State: {state: "dead" | "ready", plays: int}

signal played

## The sequence, one character per note; may use {{vars}}.
@export var sequence: String = ""
## All symbols in pointer order; symbol i sits at pointer_step * (i + 1).
@export var symbols: String = "12345"
## Pitch per symbol, same order as `symbols`.
@export var tones_hz: Array[float] = [523.3, 587.3, 659.3, 784.0, 880.0]
@export var tone_kind: String = "whistle"
@export var note_seconds: float = 0.7
@export var starts_powered: bool = false
@export var dead_message: String = "It won't budge."
## Optional part (a tail, a needle) that points at each note's symbol.
@export var pointer: NodePath
@export var pointer_step: Vector3 = Vector3(0, 0, -25)

var _rest: Variant = null
var _tween: Tween


func _init() -> void:
	verbs = ["wind"]


func _initial_state() -> Dictionary:
	return {"state": "ready" if starts_powered else "dead", "plays": 0}


func is_ready() -> bool:
	return my_state().get("state") == "ready"


func _server_activate() -> void:
	if not is_ready():
		set_state({"state": "ready"})


func _server_intent(_player_id: String, verb: String, _payload: Dictionary) -> Dictionary:
	if verb != "wind":
		return {"ok": false, "error": "unsupported_verb"}
	if not is_ready():
		return {"ok": false, "error": "no_power", "message": dead_message}
	set_state({"plays": int(my_state().get("plays", 0)) + 1})
	return {"ok": true}


func _state_sound(old: Dictionary, new: Dictionary) -> Variant:
	if new.get("state") == "ready" and old.get("state") != "ready":
		return "relay"
	if int(new.get("plays", 0)) > int(old.get("plays", 0)):
		_play()
	return ""


## Presentation on every client: notes and pointer, one per note_seconds.
func _play() -> void:
	var seq := EBTemplate.render(sequence, Game.vars())
	var p := get_node_or_null(pointer) as Node3D
	if p and _rest == null:
		_rest = p.rotation_degrees
	if _tween and _tween.is_valid():
		_tween.kill()
	_tween = create_tween()
	_tween.tween_interval(note_seconds * 0.5)
	for c in seq:
		var i := symbols.find(c)
		if i < 0:
			continue
		_tween.tween_callback(_note.bind(i))
		_tween.tween_interval(note_seconds)
	_tween.tween_callback(_note.bind(-1))
	played.emit()


func _note(i: int) -> void:
	var p := get_node_or_null(pointer) as Node3D
	if p and _rest != null:
		p.rotation_degrees = (_rest as Vector3) + (pointer_step * (i + 1) if i >= 0 else Vector3.ZERO)
	if i >= 0 and i < tones_hz.size():
		EBSound.play_at(self, EBSound.tone(tones_hz[i], tone_kind), 0.0, 0.0)


func prompt(item_name: String = "") -> String:
	if not current_state.is_empty() and current_state.get("state") != "ready":
		return "%s (%s)" % [display_name, "silent"]
	return super(item_name)
