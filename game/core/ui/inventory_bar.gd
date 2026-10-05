class_name InventoryBar
extends HBoxContainer
## Team inventory strip (PLAN.md 6.4): everything the team holds, visible to
## all, as thumbnails of the items themselves (ADR-0038). Keys 1-9 or the
## wheel select an item to use on things; Q deselects; F inspects the
## selected item. With the mouse free (point-and-tap), click or tap a slot to
## select it, or drag it onto something in the room to use it there.

## Emitted while an item is dragged over the room, and when it is let go
## (`released`; `pos` is (-1, -1) if it was let go over the bar itself).
## Positions are in viewport coordinates.
signal item_dragged(path: String, pos: Vector2, released: bool)
## The selected item's "Look closer" button.
signal inspect_requested

const SLOT := Vector2(104, 104)
const DRAG_SLOP := 14.0

## Shows the "Look closer" button (when the mouse is free).
var show_inspect_button := false

var _ghost: TextureRect
var _drag_path := ""
var _press_path := ""
var _press_pos := Vector2.ZERO


func _ready() -> void:
	add_theme_constant_override("separation", 8)
	mouse_filter = Control.MOUSE_FILTER_IGNORE
	Game.inventory_changed.connect(func(_i: Array[String]) -> void: rebuild())
	Game.selected_item_changed.connect(func(_p: String) -> void: rebuild())
	rebuild()


func rebuild() -> void:
	if not _drag_path.is_empty():
		_end_drag(Vector2(-1, -1))
	_press_path = ""
	for c in get_children():
		c.queue_free()
	var inv := Game.inventory()
	for i in inv.size():
		var item := Game.node_at(inv[i]) as Item
		add_child(_slot(i, inv[i], item))
	if show_inspect_button and not Game.selected_item.is_empty():
		var look := Button.new()
		look.name = "LookCloser"
		look.text = "Look\ncloser"
		look.focus_mode = Control.FOCUS_NONE
		look.custom_minimum_size = Vector2(SLOT.x * 0.8, SLOT.y)
		look.pressed.connect(func() -> void: inspect_requested.emit())
		add_child(look)


func _slot(i: int, path: String, item: Item) -> Button:
	var b := Button.new()
	b.name = "Slot%d" % (i + 1)
	b.focus_mode = Control.FOCUS_NONE
	b.toggle_mode = true
	b.button_pressed = path == Game.selected_item
	if b.button_pressed:
		# The held item: an amber frame, not just the darker pressed shade.
		var held := StyleBoxFlat.new()
		held.bg_color = Color(0.22, 0.17, 0.08, 0.85)
		held.border_color = Color(1.0, 0.75, 0.3)
		held.set_border_width_all(4)
		held.set_corner_radius_all(6)
		for st in ["normal", "pressed", "hover", "hover_pressed"]:
			b.add_theme_stylebox_override(st, held)
	b.custom_minimum_size = SLOT
	b.tooltip_text = item.display_name if item else path
	if item:
		b.icon = ItemIcons.icon(item, self)
	b.expand_icon = true
	b.icon_alignment = HORIZONTAL_ALIGNMENT_CENTER
	b.vertical_icon_alignment = VERTICAL_ALIGNMENT_CENTER
	# The number key (top left) and the name (bottom) sit over the thumbnail.
	var num := _caption(str(i + 1), 15)
	num.position = Vector2(6, 2)
	b.add_child(num)
	var label := _caption(item.display_name if item else path.get_file(), 13)
	label.set_anchors_and_offsets_preset(Control.PRESET_BOTTOM_WIDE)
	label.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	label.text_overrun_behavior = TextServer.OVERRUN_TRIM_ELLIPSIS
	label.offset_top = -22
	label.offset_bottom = -3
	b.add_child(label)
	b.gui_input.connect(_on_slot_input.bind(path))
	return b


func _caption(text: String, size: int) -> Label:
	var l := Label.new()
	l.text = text
	l.mouse_filter = Control.MOUSE_FILTER_IGNORE
	l.add_theme_font_size_override("font_size", size)
	l.add_theme_color_override("font_outline_color", Color.BLACK)
	l.add_theme_constant_override("outline_size", 5)
	return l


## A press on a slot selects it on release, unless the pointer moves away
## first: then the item follows the pointer and is used where it is let go.
## The pressed slot keeps receiving the pointer's events until release.
func _on_slot_input(event: InputEvent, path: String) -> void:
	if event is InputEventMouseButton and (event as InputEventMouseButton).button_index == MOUSE_BUTTON_LEFT:
		var b := event as InputEventMouseButton
		if b.pressed:
			_press_path = path
			_press_pos = b.global_position
		elif _drag_path == path:
			_end_drag(b.global_position)
		elif _press_path == path:
			_press_path = ""
			select(path)
		accept_event()
	elif event is InputEventMouseMotion and _press_path == path:
		var m := event as InputEventMouseMotion
		if _drag_path.is_empty() and m.global_position.distance_to(_press_pos) > DRAG_SLOP:
			_start_drag(path)
		if not _drag_path.is_empty():
			_ghost.global_position = m.global_position - _ghost.size / 2.0
			item_dragged.emit(_drag_path, m.global_position, false)
		accept_event()


func _start_drag(path: String) -> void:
	_drag_path = path
	_ghost = TextureRect.new()
	var item := Game.node_at(path) as Item
	_ghost.texture = ItemIcons.icon(item, self) if item else null
	_ghost.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
	_ghost.stretch_mode = TextureRect.STRETCH_KEEP_ASPECT_CENTERED
	_ghost.size = SLOT
	_ghost.modulate.a = 0.85
	_ghost.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_ghost.top_level = true
	add_child(_ghost)


func _end_drag(pos: Vector2) -> void:
	var path := _drag_path
	_drag_path = ""
	_press_path = ""
	if is_instance_valid(_ghost):
		_ghost.queue_free()
	_ghost = null
	var on_bar := pos.x < 0.0 or get_global_rect().grow(8).has_point(pos)
	item_dragged.emit(path, Vector2(-1, -1) if on_bar else pos, true)


func is_dragging() -> bool:
	return not _drag_path.is_empty()


func select(path: String) -> void:
	Game.selected_item = "" if Game.selected_item == path else path


func cycle(step: int) -> void:
	var inv := Game.inventory()
	if inv.is_empty():
		return
	var i := inv.find(Game.selected_item)
	i = posmod(i + step, inv.size()) if i >= 0 else (0 if step > 0 else inv.size() - 1)
	Game.selected_item = inv[i]
