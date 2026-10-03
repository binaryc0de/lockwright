class_name DialLockPanel
extends ModalPanel
## Focused view of a DialLock: one column per wheel with up/down buttons. Each
## click is a "turn" intent; the shown symbols come from the lock's replicated
## state, so a teammate turning the same lock is seen live.

var lock: DialLock
var _shown: Array[Label] = []
var _status: Label


func setup(p_lock: DialLock) -> void:
	lock = p_lock
	add_title(lock.display_name)
	var row := HBoxContainer.new()
	row.alignment = BoxContainer.ALIGNMENT_CENTER
	row.add_theme_constant_override("separation", 14)
	for i in lock.wheels.size():
		if i > 0 and not lock.separator.is_empty():
			var sep := Label.new()
			sep.text = lock.separator
			sep.add_theme_font_size_override("font_size", 40)
			row.add_child(sep)
		var col := VBoxContainer.new()
		col.alignment = BoxContainer.ALIGNMENT_CENTER
		if i < lock.wheel_labels.size():
			var cap := Label.new()
			cap.text = lock.wheel_labels[i]
			cap.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
			col.add_child(cap)
		col.add_child(_button("▲", i, -1))
		var l := Label.new()
		l.custom_minimum_size = Vector2(64, 56)
		l.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
		l.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
		l.add_theme_font_size_override("font_size", 40)
		col.add_child(l)
		_shown.append(l)
		col.add_child(_button("▼", i, 1))
		row.add_child(col)
	body().add_child(row)
	_status = Label.new()
	_status.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	body().add_child(_status)
	add_close_button()
	lock.state_applied.connect(_on_state)
	_on_state(lock.current_state)


func _button(text: String, wheel: int, step: int) -> Button:
	var b := Button.new()
	b.text = text
	b.custom_minimum_size = Vector2(64, 44)
	b.focus_mode = Control.FOCUS_NONE
	b.pressed.connect(turn.bind(wheel, step))
	return b


## Turns wheel `wheel` by `step` (+1 forward, -1 back).
func turn(wheel: int, step: int) -> void:
	Game.request(lock, "turn", {"wheel": wheel, "step": step})


func _on_state(state: Dictionary) -> void:
	if not is_instance_valid(self):
		return
	var dials := DialLock.dials_of(state)
	for i in _shown.size():
		var syms := lock.symbols(i)
		_shown[i].text = syms[posmod(dials[i] if i < dials.size() else 0, syms.size())]
	if state.get("state") == "unlocked":
		_status.text = "It gives."
		if is_inside_tree():
			get_tree().create_timer(0.9).timeout.connect(close)
