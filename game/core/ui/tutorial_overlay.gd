class_name TutorialOverlay
extends PanelContainer
## Controls tutorial shown while a room's AirlockGate is waiting (ADR-0020):
## a short sequence of prompts that advance when the player does the thing.
## Generic: it knows controls, not rooms.

signal finished

const STEPS := [
	["move", "Walk with W A S D and look around with the mouse."],
	["read", "Read the notice on the wall: aim at it and press E (or click)."],
	["board", "Press Tab: everything anyone reads lands on the team's shared evidence board."],
	["enter", "Stuck later? Press H for a hint from security. Step through the door when your team is ready."],
]
## The same steps for point-and-tap controls (ADR-0038).
const STEPS_POINTER := [
	["move", "Drag to look around. Tap the floor to walk there."],
	["read", "Read the notice on the wall: tap it."],
	["board", "Tap Evidence: everything anyone reads lands on the team's shared evidence board."],
	["enter", "Stuck later? Tap Hints. Items you find go in the bar at the bottom: tap one to pick it, or drag it onto something. Step through the door when your team is ready."],
]

var _step := 0
var _label: Label
var _counter: Label
var _player: Node3D
var _start_pos := Vector3.ZERO
var _gate: AirlockGate


func setup(player: Node3D, gate: AirlockGate) -> void:
	_player = player
	_gate = gate
	_start_pos = player.global_position if player else Vector3.ZERO
	Game.evidence_changed.connect(_on_evidence)
	Game.node_state_changed.connect(_on_node_state)


func _ready() -> void:
	set_anchors_and_offsets_preset(Control.PRESET_CENTER_BOTTOM)
	grow_horizontal = Control.GROW_DIRECTION_BOTH
	grow_vertical = Control.GROW_DIRECTION_BEGIN
	offset_bottom = -120
	custom_minimum_size = Vector2(620, 0)
	mouse_filter = Control.MOUSE_FILTER_IGNORE
	var box := VBoxContainer.new()
	box.mouse_filter = Control.MOUSE_FILTER_IGNORE  # taps go through to the room
	add_child(box)
	_counter = Label.new()
	_counter.modulate.a = 0.7
	box.add_child(_counter)
	_label = Label.new()
	_label.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	_label.add_theme_font_size_override("font_size", 22)
	box.add_child(_label)
	_show()


func _steps() -> Array:
	return STEPS_POINTER if Settings.pointer_controls() else STEPS


func current_step() -> String:
	return _steps()[_step][0] if _step < _steps().size() else ""


func _show() -> void:
	if _step >= _steps().size():
		finished.emit()
		queue_free()
		return
	_counter.text = "Getting started  %d / %d" % [_step + 1, _steps().size()]
	_label.text = _steps()[_step][1]


## Moves on if the current step is `id` (and skips steps already satisfied).
func complete(id: String) -> void:
	if current_step() == id:
		_step += 1
		_show()


func _physics_process(_d: float) -> void:
	if current_step() == "move" and _player and _player.global_position.distance_to(_start_pos) > 1.5:
		complete("move")


func _on_evidence(entries: Array[Dictionary]) -> void:
	for e in entries:
		if e.get("kind") == "doc":
			complete("read")
			return


func _on_node_state(path: String, state: Dictionary) -> void:
	if _gate and path == _gate.eb_path and state.get("state") == "sealed":
		_step = _steps().size()
		_show()


## The HUD calls this when the evidence board opens.
func on_evidence_board_opened() -> void:
	complete("board")
