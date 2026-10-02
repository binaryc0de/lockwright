class_name KeypadPanel
extends ModalPanel
## Focused keypad (PLAN.md 6.5): digits, CLR, ENT, an LED, and a display.
## The code is checked by the authority; this panel only sends the attempt.

var lock: KeypadLock
var _entry: String = ""
var _display: Label
var _led: ColorRect


func setup(p_lock: KeypadLock) -> void:
	lock = p_lock
	add_title(lock.display_name)
	var row := HBoxContainer.new()
	_display = Label.new()
	_display.custom_minimum_size = Vector2(220, 0)
	_display.add_theme_font_size_override("font_size", 40)
	_display.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	row.add_child(_display)
	_led = ColorRect.new()
	_led.custom_minimum_size = Vector2(24, 24)
	_led.size_flags_vertical = Control.SIZE_SHRINK_CENTER
	row.add_child(_led)
	body().add_child(row)
	var grid := GridContainer.new()
	grid.columns = 3
	for key in ["1", "2", "3", "4", "5", "6", "7", "8", "9", "CLR", "0", "ENT"]:
		var b := Button.new()
		b.text = key
		b.custom_minimum_size = Vector2(76, 60)
		b.add_theme_font_size_override("font_size", 24)
		b.focus_mode = Control.FOCUS_NONE
		b.pressed.connect(_press.bind(key))
		grid.add_child(b)
	body().add_child(grid)
	var hint := Label.new()
	hint.text = "Type digits, Enter to submit, Backspace to clear."
	body().add_child(hint)
	add_close_button()
	lock.state_applied.connect(_on_lock_state)
	_set_led(Lock.COLOR_OFF)
	_refresh()


func _press(key: String) -> void:
	match key:
		"CLR":
			_entry = ""
		"ENT":
			_submit()
			return  # keep OPEN/ERROR on the display until the next key
		_:
			if _entry.length() < maxi(lock.display_length, 1) + 4:
				_entry += key
	_refresh()


func _submit() -> void:
	if _entry.is_empty():
		return
	var code := _entry
	_entry = ""
	_refresh()
	Game.request(lock, "submit_code", {"value": code}, _on_result)


func _on_result(r: Dictionary) -> void:
	if not is_instance_valid(self) or not is_inside_tree():
		return
	if r.get("ok", false):
		_set_led(Lock.COLOR_OPEN)
		_display.text = "OPEN"
		get_tree().create_timer(0.8).timeout.connect(close)
	else:
		_set_led(Lock.COLOR_LOCKED)
		_display.text = "ERROR"


func _refresh() -> void:
	_display.text = _entry if not _entry.is_empty() else "-".repeat(maxi(lock.display_length, 1))


func _set_led(c: Color) -> void:
	_led.color = c


func _on_lock_state(state: Dictionary) -> void:
	if state.get("state") == "unlocked":
		_set_led(Lock.COLOR_OPEN)


func _unhandled_input(event: InputEvent) -> void:
	super(event)
	if not is_inside_tree() or not event is InputEventKey or not event.pressed:
		return
	var k := event as InputEventKey
	if k.keycode >= KEY_0 and k.keycode <= KEY_9:
		_press(str(k.keycode - KEY_0))
	elif k.keycode >= KEY_KP_0 and k.keycode <= KEY_KP_9:
		_press(str(k.keycode - KEY_KP_0))
	elif k.keycode in [KEY_ENTER, KEY_KP_ENTER]:
		_press("ENT")
	elif k.keycode == KEY_BACKSPACE:
		_press("CLR")
	else:
		return
	get_viewport().set_input_as_handled()
