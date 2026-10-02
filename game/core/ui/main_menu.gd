class_name MainMenu
extends Control
## Player name; play a room offline (rooms found in res://rooms or a .pck);
## or join a game server on the LAN (M2). The lobby/session browser arrives
## with the platform in M3.

signal play_requested(room_id: String, pack_path: String)
## `args` is a parsed client command line (AppArgs) so menu and CLI share
## validation.
signal join_requested(args: AppArgs)

var _name: LineEdit
var _rooms: ItemList
var _pack: LineEdit
var _pack_room: LineEdit
var _status: Label
var _server: LineEdit
var _token: LineEdit
var _ws: CheckBox


func _ready() -> void:
	set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	var bg := ColorRect.new()
	bg.color = Color(0.07, 0.07, 0.09)
	bg.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	add_child(bg)
	var center := CenterContainer.new()
	center.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	add_child(center)
	var box := VBoxContainer.new()
	box.custom_minimum_size = Vector2(520, 0)
	box.add_theme_constant_override("separation", 10)
	center.add_child(box)

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
	play.text = "Play offline"
	play.custom_minimum_size = Vector2(0, 48)
	play.pressed.connect(_play)
	box.add_child(play)

	box.add_child(_caption("Join a game server"))
	var jrow := HBoxContainer.new()
	_server = LineEdit.new()
	_server.placeholder_text = "192.168.1.20  or  host:7777"
	_server.text = Settings.last_server
	_server.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	_server.text_submitted.connect(func(_t: String) -> void: _join())
	jrow.add_child(_server)
	_token = LineEdit.new()
	_token.placeholder_text = "invite password"
	_token.secret = true
	_token.custom_minimum_size = Vector2(170, 0)
	_token.text_submitted.connect(func(_t: String) -> void: _join())
	jrow.add_child(_token)
	box.add_child(jrow)
	_ws = CheckBox.new()
	_ws.text = "WebSocket (for servers behind a tunnel)"
	_ws.button_pressed = Settings.last_ws
	box.add_child(_ws)
	var join := Button.new()
	join.text = "Join"
	join.custom_minimum_size = Vector2(0, 48)
	join.pressed.connect(_join)
	box.add_child(join)

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
	_save_name()
	if not _pack.text.strip_edges().is_empty():
		play_requested.emit(_pack_room.text.strip_edges(), _pack.text.strip_edges())
		return
	var sel := _rooms.get_selected_items()
	if sel.is_empty():
		show_error("Pick a room.")
		return
	play_requested.emit(_rooms.get_item_metadata(sel[0]), "")


func _join() -> void:
	_save_name()
	var server := _server.text.strip_edges()
	if server.is_empty():
		show_error("Type the server's address.")
		return
	var argv: PackedStringArray = ["--connect", server, "--name", Settings.display_name]
	if not _token.text.is_empty():
		argv.append_array(["--token", _token.text])
	if _ws.button_pressed:
		argv.append_array(["--transport", "ws"])
	var args := AppArgs.parse(argv)
	if not args.errors.is_empty():
		show_error("\n".join(args.errors))
		return
	Settings.last_server = server
	Settings.last_ws = _ws.button_pressed
	Settings.save_settings()
	join_requested.emit(args)


func _save_name() -> void:
	Settings.display_name = _name.text.strip_edges() if not _name.text.strip_edges().is_empty() else "Player"
	Settings.save_settings()
