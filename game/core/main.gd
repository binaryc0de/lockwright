extends Node
## Boot: parse arguments and pick client or server mode (PLAN.md 6.1, 7.1).
##   client: godot --path game [-- --room <id> [--pack <file.pck>]]
##   join:   godot --path game -- --connect <host[:port]> --name <name> [--token <invite>]
##   server: godot --headless --path game -- --server --session <id> --room <id>
##           [--pack <path>] [--port 7777] [--transport enet|ws] [--token <invite>]
##           [--snapshot <file.json>]

var _menu: MainMenu


func _ready() -> void:
	var argv := OS.get_cmdline_user_args() + OS.get_cmdline_args()
	if OS.has_feature("web"):
		argv.append_array(AppArgs.web_query_args(str(JavaScriptBridge.eval("location.origin")), str(JavaScriptBridge.eval("location.search"))))
	var args := AppArgs.parse(argv, OS.has_feature("dedicated_server"))
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
		_join(args)
	elif not args.room_id.is_empty():
		_play(args.room_id, args.pack_path, args.difficulty)
	else:
		_show_menu()


func _show_menu(error: String = "") -> void:
	Input.mouse_mode = Input.MOUSE_MODE_VISIBLE
	_menu = MainMenu.new()
	add_child(_menu)
	_menu.play_requested.connect(_play)
	_menu.join_requested.connect(_join)
	if not error.is_empty():
		_menu.show_error(error)


func _play(room_id: String, pack_path: String, difficulty: String = "") -> void:
	if _menu:
		_menu.queue_free()
		_menu = null
	var session := PlaySession.new()
	add_child(session)
	if not session.start(room_id, pack_path, "", difficulty):
		var err := session.error
		session.queue_free()
		push_error(err)
		_show_menu(err)
		return
	session.left.connect(func() -> void: _show_menu())


func _join(args: AppArgs) -> void:
	if _menu:
		_menu.queue_free()
		_menu = null
	var session := PlaySession.new()
	add_child(session)
	session.left.connect(func() -> void: _show_menu(session.error))
	session.start_remote(args)


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
	var store: SnapshotStore
	var verifier: JoinVerifier
	var flags: FlagValidator = null
	var platform: PlatformClient = null
	if args.platform_set:
		# M3: the platform owns join tokens, snapshots and flags (ADR-0018).
		platform = PlatformClient.new(args.platform_url, args.session_id, args.server_token)
		platform.name = "Platform"
		add_child(platform)
		store = PlatformSnapshotStore.new(platform)
		verifier = PlatformJoinVerifier.new(platform)
		flags = PlatformFlagValidator.new(platform)
	else:
		var snap_path := args.snapshot_path
		if snap_path.is_empty():
			snap_path = "user://snapshots/%s.json" % args.session_id.validate_filename()
		store = SnapshotStore.new(ProjectSettings.globalize_path(snap_path))
		verifier = JoinVerifier.new(args.server_token)
	var snapshot := store.load_snapshot()
	if snapshot.has("_error"):
		push_error("cannot start: %s" % snapshot["_error"])
		get_tree().quit(1)
		return
	Game.start_server_session(loader.manifest, room, args.session_id, snapshot, flags, args.difficulty)
	print("escapebox server: %s snapshot %s, difficulty %s" % ["restored" if not snapshot.is_empty() else "fresh",
		args.platform_url if platform else store.path, Game.difficulty()])
	var server := SessionServer.new()
	server.name = "SessionServer"
	server.session_id = args.session_id
	server.room_id = loader.manifest.id
	server.room_version = str(loader.manifest.data.get("version", ""))
	server.trust_positions = args.trust_positions
	server.platform = platform
	server.idle_exit_s = 300.0 if platform else 0.0
	if args.trust_positions:
		print("escapebox server: WARNING --trust-positions (test mode): reach checks accept teleports")
	add_child(server)
	var err := server.start(args.port, args.transport, verifier, store)
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
