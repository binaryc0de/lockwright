extends Node
## Boot: parse arguments and pick client or server mode (PLAN.md 6.1, 7.1).
##   client: godot --path game [-- --room <id> [--pack <file.pck>]]
##   server: escapebox-server --session <id> --room <id> --pack <path> ... (M2)

var _menu: MainMenu


func _ready() -> void:
	var args := AppArgs.parse(OS.get_cmdline_user_args() + OS.get_cmdline_args(),
		OS.has_feature("dedicated_server"))
	for e in args.errors:
		push_error(e)
	print("escapebox %s mode, sdk %s, godot %s" % [
		"server" if args.is_server() else "client",
		EscapeboxSDK.VERSION,
		Engine.get_version_info().string,
	])
	if args.smoke_test or not args.errors.is_empty():
		get_tree().quit(0 if args.errors.is_empty() else 1)
		return
	if args.is_server():
		push_error("dedicated server mode arrives in M2")
		get_tree().quit(1)
		return
	Settings.load_settings()
	get_tree().root.content_scale_factor = Settings.text_scale
	if not args.room_id.is_empty():
		_play(args.room_id, args.pack_path)
	else:
		_show_menu()


func _show_menu(error: String = "") -> void:
	Input.mouse_mode = Input.MOUSE_MODE_VISIBLE
	_menu = MainMenu.new()
	add_child(_menu)
	_menu.play_requested.connect(_play)
	if not error.is_empty():
		_menu.show_error(error)


func _play(room_id: String, pack_path: String) -> void:
	if _menu:
		_menu.queue_free()
		_menu = null
	var session := PlaySession.new()
	add_child(session)
	if not session.start(room_id, pack_path):
		var err := session.error
		session.queue_free()
		push_error(err)
		_show_menu(err)
		return
	session.left.connect(func() -> void: _show_menu())
