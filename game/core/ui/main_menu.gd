class_name MainMenu
extends Control
## Player name; play a room offline (rooms found in res://rooms or a .pck);
## or join a game server on the LAN (M2). The lobby/session browser arrives
## with the platform in M3.

signal play_requested(room_id: String, pack_path: String, difficulty: String)
## `args` is a parsed client command line (AppArgs) so menu and CLI share
## validation.
signal join_requested(args: AppArgs)

var _name: LineEdit
var _rooms: ItemList
var _difficulty: OptionButton
var _difficulty_note: Label
var _pack: LineEdit
var _pack_room: LineEdit
var _status: Label
var _server: LineEdit
var _code: LineEdit
var _token: LineEdit
var _ws: CheckBox
var _host_btn: Button
var _platform: PlatformClient


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

	var drow := HBoxContainer.new()
	var dlabel := Label.new()
	dlabel.text = "Difficulty"
	drow.add_child(dlabel)
	_difficulty = OptionButton.new()
	_difficulty.custom_minimum_size = Vector2(180, 0)
	drow.add_child(_difficulty)
	_difficulty_note = Label.new()
	_difficulty_note.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	_difficulty_note.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	drow.add_child(_difficulty_note)
	box.add_child(drow)
	_rooms.item_selected.connect(func(_i: int) -> void: _refresh_difficulties())
	_difficulty.item_selected.connect(func(_i: int) -> void: _refresh_difficulty_note())
	_refresh_difficulties()

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

	box.add_child(_caption("Online: platform or game server address"))
	var jrow := HBoxContainer.new()
	_server = LineEdit.new()
	_server.placeholder_text = "address, e.g. 192.168.1.20"
	_server.text = Settings.last_server
	_server.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	_server.text_submitted.connect(func(_t: String) -> void: _join())
	jrow.add_child(_server)
	_code = LineEdit.new()
	_code.placeholder_text = "join code"
	_code.max_length = 6
	_code.custom_minimum_size = Vector2(120, 0)
	_code.text_submitted.connect(func(_t: String) -> void: _join())
	jrow.add_child(_code)
	_token = LineEdit.new()
	_token.placeholder_text = "server password"
	_token.secret = true
	_token.custom_minimum_size = Vector2(170, 0)
	_token.text_submitted.connect(func(_t: String) -> void: _join())
	jrow.add_child(_token)
	box.add_child(jrow)
	_ws = CheckBox.new()
	_ws.text = "WebSocket (for servers behind a tunnel)"
	_ws.button_pressed = Settings.last_ws
	box.add_child(_ws)
	var brow := HBoxContainer.new()
	var join := Button.new()
	join.text = "Join"
	join.custom_minimum_size = Vector2(0, 48)
	join.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	join.pressed.connect(_join)
	brow.add_child(join)
	_host_btn = Button.new()
	_host_btn.text = "Host the selected room on the platform"
	_host_btn.custom_minimum_size = Vector2(0, 48)
	_host_btn.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	_host_btn.pressed.connect(_host)
	brow.add_child(_host_btn)
	box.add_child(brow)

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
		play_requested.emit(_pack_room.text.strip_edges(), _pack.text.strip_edges(), "")
		return
	var sel := _rooms.get_selected_items()
	if sel.is_empty():
		show_error("Pick a room.")
		return
	play_requested.emit(_rooms.get_item_metadata(sel[0]), "", selected_difficulty())


## The difficulty id picked for the selected room ("" = the room's default).
func selected_difficulty() -> String:
	if _difficulty == null or _difficulty.selected < 0:
		return ""
	return str(_difficulty.get_item_metadata(_difficulty.selected))


func _refresh_difficulties() -> void:
	_difficulty.clear()
	var sel := _rooms.get_selected_items()
	var m := RoomManifest.load_room(_rooms.get_item_metadata(sel[0])) if not sel.is_empty() else null
	if m:
		for d: Dictionary in m.difficulties:
			_difficulty.add_item(str(d.get("title", d.get("id"))))
			_difficulty.set_item_metadata(_difficulty.item_count - 1, str(d.get("id")))
		_difficulty.select(0)
	_refresh_difficulty_note()


func _refresh_difficulty_note() -> void:
	var sel := _rooms.get_selected_items()
	var m := RoomManifest.load_room(_rooms.get_item_metadata(sel[0])) if not sel.is_empty() else null
	_difficulty_note.text = ""
	if m and _difficulty.selected >= 0:
		_difficulty_note.text = str(m.difficulties[_difficulty.selected].get("description", ""))


func _join() -> void:
	_save_name()
	var server := _server.text.strip_edges()
	if server.is_empty():
		show_error("Type the server's address.")
		return
	var argv: PackedStringArray
	var code := _code.text.strip_edges()
	if not code.is_empty():
		argv = ["--join", server, "--code", code, "--name", Settings.display_name]
	else:
		argv = ["--connect", server, "--name", Settings.display_name]
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


## Creates a game for the selected room on the platform, then joins it; the
## join code shows in-game (toast and pause menu) to read out to friends.
func _host() -> void:
	_save_name()
	var server := _server.text.strip_edges()
	if server.is_empty():
		show_error("Type the platform's address.")
		return
	var sel := _rooms.get_selected_items()
	if sel.is_empty():
		show_error("Pick a room to host.")
		return
	var room_id: String = _rooms.get_item_metadata(sel[0])
	if _platform == null:
		_platform = PlatformClient.new(AppArgs.platform_http_url(server))
		add_child(_platform)
	else:
		_platform.base_url = AppArgs.platform_http_url(server)
	_host_btn.disabled = true
	show_error("Creating a game on %s ..." % _platform.base_url)
	_platform.request_async(HTTPClient.METHOD_POST, "/api/sessions", {"room_id": room_id, "difficulty": selected_difficulty()}, func(code: int, data: Variant) -> void:
		if not is_instance_valid(self):
			return
		_host_btn.disabled = false
		if code == 201 and data is Dictionary:
			Settings.last_server = server
			Settings.save_settings()
			_code.text = str(data["invite_code"])
			join_requested.emit(AppArgs.parse(["--join", server, "--code", _code.text, "--name", Settings.display_name]))
		elif code == 0:
			show_error("No platform answered at %s." % _platform.base_url)
		else:
			show_error("The platform refused: %s" % (data.get("message", "HTTP %d" % code) if data is Dictionary else "HTTP %d" % code)), 10.0)
