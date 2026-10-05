class_name ModalPanel
extends PanelContainer
## Base for focused UI panels (locks, documents, terminal, boards). While one
## is open the HUD frees the mouse and the player stops moving. Esc closes.
## Panels fit the screen (ADR-0038): content taller than the screen scrolls,
## and a panel wider than the screen is scaled down. A scrolling panel also
## gets a Close button in a bar above the scroll area, which never scrolls
## out of reach (a long letter on a phone held sideways).

signal closed

const SCREEN_MARGIN := 16.0

var _vbox: VBoxContainer
var _scroll: ScrollContainer
var _bar: HBoxContainer


func _init() -> void:
	set_anchors_preset(Control.PRESET_TOP_LEFT)
	mouse_filter = Control.MOUSE_FILTER_STOP
	# Nearly opaque, so the room behind does not compete with text on small
	# screens.
	var bg := StyleBoxFlat.new()
	bg.bg_color = Color(0.09, 0.09, 0.11, 0.95)
	bg.set_corner_radius_all(6)
	add_theme_stylebox_override("panel", bg)
	var margin := MarginContainer.new()
	for side in ["left", "right", "top", "bottom"]:
		margin.add_theme_constant_override("margin_" + side, 18)
	add_child(margin)
	var frame := VBoxContainer.new()
	margin.add_child(frame)
	_bar = HBoxContainer.new()
	_bar.alignment = BoxContainer.ALIGNMENT_END
	_bar.visible = false
	var top_close := Button.new()
	top_close.name = "TopClose"
	top_close.text = "Close"
	top_close.custom_minimum_size = Vector2(120, 48)
	top_close.focus_mode = Control.FOCUS_NONE
	top_close.pressed.connect(close)
	_bar.add_child(top_close)
	frame.add_child(_bar)
	_scroll = ScrollContainer.new()
	_scroll.horizontal_scroll_mode = ScrollContainer.SCROLL_MODE_DISABLED
	frame.add_child(_scroll)
	_vbox = VBoxContainer.new()
	_vbox.add_theme_constant_override("separation", 10)
	_vbox.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	_scroll.add_child(_vbox)
	_vbox.minimum_size_changed.connect(_fit)


func _ready() -> void:
	get_viewport().size_changed.connect(_fit)
	_fit()


## Scales the panel down to the screen's width if needed, caps the scroll
## area at the screen's height, then centres the panel.
func _fit() -> void:
	if not is_inside_tree():
		return
	var screen := get_viewport().get_visible_rect().size
	var content := _vbox.get_combined_minimum_size()
	var chrome := get_combined_minimum_size() - _scroll.get_combined_minimum_size()
	var s := minf(1.0, (screen.x - 2.0 * SCREEN_MARGIN) / maxf(content.x + chrome.x, 1.0))
	scale = Vector2(s, s)
	var max_h := (screen.y - 2.0 * SCREEN_MARGIN) / s - chrome.y
	var scrolls := content.y > max_h
	if scrolls and not _bar.visible:
		max_h -= _bar.get_combined_minimum_size().y + 4.0
	_bar.visible = scrolls
	_scroll.custom_minimum_size = Vector2(content.x, maxf(minf(content.y, max_h), 60.0))
	_place.call_deferred()


func _place() -> void:
	if not is_inside_tree():
		return
	reset_size()
	position = ((get_viewport().get_visible_rect().size - size * scale) / 2.0).floor()


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
