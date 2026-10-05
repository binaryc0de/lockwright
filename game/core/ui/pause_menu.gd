class_name PauseMenu
extends ModalPanel
## Esc menu: resume, accessibility settings (PLAN.md 6.9), leave.

signal quit_requested
## Settings.controls (or the drag direction) changed; the HUD re-applies it.
signal controls_changed

const CONTROL_LABELS := {
	"auto": "Automatic (tap on phones and tablets)",
	"classic": "Classic: W A S D and mouse look",
	"point": "Point and click: drag to look, click to walk",
}


func setup() -> void:
	add_title("Paused")
	if not Game.join_code.is_empty():
		var code := Label.new()
		code.text = "Join code for friends: %s" % Game.join_code
		code.add_theme_font_size_override("font_size", 22)
		body().add_child(code)
		var invite := PauseMenu.invite_text(Game.join_code)
		var row := HBoxContainer.new()
		var copied := Label.new()
		var copy := Button.new()
		copy.text = "Copy invite link" if invite.begins_with("http") else "Copy code"
		copy.pressed.connect(func() -> void:
			DisplayServer.clipboard_set(invite)
			copied.text = "Copied.")
		row.add_child(copy)
		row.add_child(copied)
		body().add_child(row)
	var grid := GridContainer.new()
	grid.columns = 2
	var ctl_label := Label.new()
	ctl_label.text = "Controls"
	grid.add_child(ctl_label)
	var ctl := OptionButton.new()
	ctl.name = "Controls"
	for c: String in Settings.CONTROLS:
		ctl.add_item(CONTROL_LABELS[c])
	ctl.selected = Settings.CONTROLS.find(Settings.controls)
	ctl.item_selected.connect(func(i: int) -> void:
		Settings.controls = Settings.CONTROLS[i]
		controls_changed.emit())
	grid.add_child(ctl)
	var grab_label := Label.new()
	grab_label.text = "Drag moves the room\n(like a map)"
	grid.add_child(grab_label)
	var grab := CheckBox.new()
	grab.button_pressed = Settings.drag_grabs_world
	grab.toggled.connect(func(on: bool) -> void: Settings.drag_grabs_world = on)
	grid.add_child(grab)
	_slider(grid, "Mouse sensitivity", 0.0005, 0.01, 0.0005, Settings.mouse_sensitivity,
		func(v: float) -> void: Settings.mouse_sensitivity = v)
	_slider(grid, "Field of view", 75, 90, 1, Settings.fov, func(v: float) -> void:
		Settings.fov = v
		var cam := get_viewport().get_camera_3d()
		if cam:
			cam.fov = v)
	_slider(grid, "Text size", 0.75, 2.0, 0.05, Settings.text_scale, func(v: float) -> void:
		Settings.text_scale = v
		Device.apply_ui_scale(get_tree().root))
	var gfx_label := Label.new()
	gfx_label.text = "Graphics"
	grid.add_child(gfx_label)
	var gfx := OptionButton.new()
	for level: String in GraphicsQuality.LEVELS:
		gfx.add_item(level.capitalize())
	gfx.selected = GraphicsQuality.LEVELS.find(Settings.graphics)
	gfx.item_selected.connect(func(i: int) -> void:
		Settings.graphics = GraphicsQuality.LEVELS[i]
		if Game.room:
			GraphicsQuality.apply(Game.room, Settings.graphics))
	grid.add_child(gfx)
	var inv_label := Label.new()
	inv_label.text = "Invert mouse Y"
	grid.add_child(inv_label)
	var inv := CheckBox.new()
	inv.button_pressed = Settings.invert_y
	inv.toggled.connect(func(on: bool) -> void: Settings.invert_y = on)
	grid.add_child(inv)
	body().add_child(grid)
	add_close_button("Resume" if Settings.pointer_controls() else "Resume (Esc)")
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


## What to share: in the browser, the game page's link on this site; on the
## desktop, the code itself.
static func invite_text(code: String) -> String:
	if OS.has_feature("web"):
		return "%s/g/%s" % [str(JavaScriptBridge.eval("location.origin")), code]
	return code
