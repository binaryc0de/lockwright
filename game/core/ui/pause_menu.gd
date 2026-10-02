class_name PauseMenu
extends ModalPanel
## Esc menu: resume, accessibility settings (PLAN.md 6.9), leave.

signal quit_requested


func setup() -> void:
	add_title("Paused")
	var grid := GridContainer.new()
	grid.columns = 2
	_slider(grid, "Mouse sensitivity", 0.0005, 0.01, 0.0005, Settings.mouse_sensitivity,
		func(v: float) -> void: Settings.mouse_sensitivity = v)
	_slider(grid, "Field of view", 75, 90, 1, Settings.fov, func(v: float) -> void:
		Settings.fov = v
		var cam := get_viewport().get_camera_3d()
		if cam:
			cam.fov = v)
	_slider(grid, "Text size", 0.75, 2.0, 0.05, Settings.text_scale, func(v: float) -> void:
		Settings.text_scale = v
		get_tree().root.content_scale_factor = v)
	var inv_label := Label.new()
	inv_label.text = "Invert mouse Y"
	grid.add_child(inv_label)
	var inv := CheckBox.new()
	inv.button_pressed = Settings.invert_y
	inv.toggled.connect(func(on: bool) -> void: Settings.invert_y = on)
	grid.add_child(inv)
	body().add_child(grid)
	add_close_button("Resume (Esc)")
	var quit := Button.new()
	quit.text = "Leave room"
	quit.pressed.connect(func() -> void: quit_requested.emit())
	body().add_child(quit)
	closed.connect(Settings.save_settings)


func _slider(grid: GridContainer, label: String, lo: float, hi: float, step: float, value: float, on_change: Callable) -> void:
	var l := Label.new()
	l.text = label
	grid.add_child(l)
	var s := HSlider.new()
	s.min_value = lo
	s.max_value = hi
	s.step = step
	s.value = value
	s.custom_minimum_size = Vector2(260, 0)
	s.value_changed.connect(on_change)
	grid.add_child(s)
