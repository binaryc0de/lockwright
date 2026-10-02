extends Node
## Boot: parse arguments and pick client or server mode (PLAN.md 6.1, 7.1).
##   client: godot --path game [-- --room <id> [--pack <file.pck>]]
##   join:   godot --path game -- --connect <host[:port]> --name <name> [--token <invite>]
##   server: godot --headless --path game -- --server --session <id> --room <id>
##           [--pack <path>] [--port 7777] [--transport enet|ws] [--token <invite>]
##           [--snapshot <file.json>]

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
		_run_server(args)
		return
	Settings.load_settings()
	get_tree().root.content_scale_factor = Settings.text_scale
	if args.is_remote_client():
		var session := PlaySession.new()
		add_child(session)
		session.start_remote(args)
	elif not args.room_id.is_empty():
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


## Dedicated server (PLAN.md 7.1): loads the room, restores the snapshot if
## there is one, and serves clients until killed.
func _run_server(args: AppArgs) -> void:
	var loader := RoomLoader.new()
	if not loader.load_room(args.room_id, args.pack_path):
		push_error(loader.error)
		get_tree().quit(1)
		return
	var room := loader.instantiate()
	if room == null:
		push_error(loader.error)
		get_tree().quit(1)
		return
	var world := Node3D.new()
	world.name = "ServerWorld"
	add_child(world)
	world.add_child(room)
	var snap_path := args.snapshot_path
	if snap_path.is_empty():
		snap_path = "user://snapshots/%s.json" % args.session_id.validate_filename()
	var store := SnapshotStore.new(ProjectSettings.globalize_path(snap_path))
	var snapshot := store.load_snapshot()
	Game.start_server_session(loader.manifest, room, args.session_id, snapshot)
	print("escapebox server: %s snapshot %s" % ["restored" if not snapshot.is_empty() else "fresh", store.path])
	var server := SessionServer.new()
	server.name = "SessionServer"
	server.session_id = args.session_id
	server.room_id = loader.manifest.id
	server.room_version = str(loader.manifest.data.get("version", ""))
	add_child(server)
	var err := server.start(args.port, args.transport, JoinVerifier.new(args.server_token), store)
	if err != OK:
		push_error("cannot listen on port %d: %s" % [args.port, error_string(err)])
		get_tree().quit(1)
		return
	get_tree().set_auto_accept_quit(false)


func _notification(what: int) -> void:
	if what == NOTIFICATION_WM_CLOSE_REQUEST:
		var server := get_node_or_null("SessionServer") as SessionServer
		if server:
			server.stop()
		get_tree().quit(0)
