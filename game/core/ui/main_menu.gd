class_name MainMenu
extends Control
## M1 menu: player name, rooms found in res://rooms (dev mode and mounted
## packs), or a .pck path. The lobby/session browser arrives with the
## platform in M3.

signal play_requested(room_id: String, pack_path: String)

var _name: LineEdit
var _rooms: ItemList
var _pack: LineEdit
var _pack_room: LineEdit
var _status: Label


func _ready() -> void:
	set_anchors_preset(Control.PRESET_FULL_RECT)
	var bg := ColorRect.new()
	bg.color = Color(0.07, 0.07, 0.09)
	bg.set_anchors_preset(Control.PRESET_FULL_RECT)
	add_child(bg)
	var box := VBoxContainer.new()
	box.set_anchors_preset(Control.PRESET_CENTER)
	box.grow_horizontal = Control.GROW_DIRECTION_BOTH
	box.grow_vertical = Control.GROW_DIRECTION_BOTH
	box.custom_minimum_size = Vector2(520, 0)
	box.add_theme_constant_override("separation", 10)
	add_child(box)

	var title := Label.new()
	title.text = "ESCAPEBOX"
	title.add_theme_font_size_override("font_size", 48)
	title.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	box.add_child(title)

	box.add_child(_caption("Your name"))
	_name = LineEdit.new()
	_name.text = Settings.display_name
	_name.max_length = 24
	box.add_child(_name)

	box.add_child(_caption("Rooms"))
	_rooms = ItemList.new()
	_rooms.custom_minimum_size = Vector2(0, 160)
	for id in RoomLoader.available_rooms():
		var m := RoomManifest.load_room(id)
		_rooms.add_item("%s  (%s, %d min)" % [m.title, m.version, m.duration_minutes] if m else id)
		_rooms.set_item_metadata(_rooms.item_count - 1, id)
	if _rooms.item_count > 0:
		_rooms.select(0)
	_rooms.item_activated.connect(func(_i: int) -> void: _play())
	box.add_child(_rooms)

	box.add_child(_caption("...or a room pack (.pck) and its room id"))
	var row := HBoxContainer.new()
	_pack = LineEdit.new()
	_pack.placeholder_text = "/path/to/room-0.1.0.pck"
	_pack.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	row.add_child(_pack)
	_pack_room = LineEdit.new()
	_pack_room.placeholder_text = "room_id"
	_pack_room.custom_minimum_size = Vector2(150, 0)
	row.add_child(_pack_room)
	box.add_child(row)

	var play := Button.new()
	play.text = "Play"
	play.custom_minimum_size = Vector2(0, 48)
	play.pressed.connect(_play)
	box.add_child(play)
	var quit := Button.new()
	quit.text = "Quit"
	quit.pressed.connect(func() -> void: get_tree().quit())
	box.add_child(quit)
	_status = Label.new()
	_status.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	box.add_child(_status)


func show_error(text: String) -> void:
	_status.text = text


func _caption(text: String) -> Label:
	var l := Label.new()
	l.text = text
	l.modulate.a = 0.75
	return l


func _play() -> void:
	Settings.display_name = _name.text.strip_edges() if not _name.text.strip_edges().is_empty() else "Player"
	Settings.save_settings()
	if not _pack.text.strip_edges().is_empty():
		play_requested.emit(_pack_room.text.strip_edges(), _pack.text.strip_edges())
		return
	var sel := _rooms.get_selected_items()
	if sel.is_empty():
		show_error("Pick a room.")
		return
	play_requested.emit(_rooms.get_item_metadata(sel[0]), "")
