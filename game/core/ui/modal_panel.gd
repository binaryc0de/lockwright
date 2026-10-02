class_name ModalPanel
extends PanelContainer
## Base for focused UI panels (locks, documents, terminal, boards). While one
## is open the HUD frees the mouse and the player stops moving. Esc closes.

signal closed

var _vbox: VBoxContainer


func _init() -> void:
	set_anchors_preset(Control.PRESET_CENTER)
	grow_horizontal = Control.GROW_DIRECTION_BOTH
	grow_vertical = Control.GROW_DIRECTION_BOTH
	mouse_filter = Control.MOUSE_FILTER_STOP
	var margin := MarginContainer.new()
	for side in ["left", "right", "top", "bottom"]:
		margin.add_theme_constant_override("margin_" + side, 18)
	add_child(margin)
	_vbox = VBoxContainer.new()
	_vbox.add_theme_constant_override("separation", 10)
	margin.add_child(_vbox)


## Content container for subclasses.
func body() -> VBoxContainer:
	return _vbox


func add_title(text: String) -> Label:
	var l := Label.new()
	l.text = text
	l.add_theme_font_size_override("font_size", 26)
	_vbox.add_child(l)
	return l


func add_close_button(text: String = "Close (Esc)") -> Button:
	var b := Button.new()
	b.text = text
	b.pressed.connect(close)
	_vbox.add_child(b)
	return b


func close() -> void:
	closed.emit()
	queue_free()


func _unhandled_input(event: InputEvent) -> void:
	if event.is_action_pressed("pause"):
		close()
		get_viewport().set_input_as_handled()
