extends Node
## Boot: parse arguments and pick client or server mode (PLAN.md 6.1, 7.1).
##   client: godot --path game [-- --room <id> [--pack <file.pck>]]
##   join:   godot --path game -- --connect <host[:port]> --name <name> [--token <invite>]
##   server: godot --headless --path game -- --server --session <id> --room <id>
##           [--pack <path>] [--port 7777] [--transport enet|ws] [--token <invite>]
##           [--snapshot <file.json>]

var _menu: MainMenu
var _touchbot := false
var _touchbot_from := 0
## Phone browsers double up touches for Godot (ADR-0038):
## - Godot's web build reads mouse motion from `pointermove`, which browsers
##   also fire for fingers, on top of the touch events Godot turns into mouse
##   motion: every finger drag would count twice.
## - After a tap, a browser may also send its own "compatibility" mouse
##   click, which would press a button a second time (a toggle flips back).
## Both are dropped before Godot sees them; real mice and pens still pass.
const WEB_TOUCH_FIX := """(function () {
	var lastTouch = 0;
	window.addEventListener('pointermove', function (e) { if (e.pointerType === 'touch') e.stopImmediatePropagation(); }, true);
	['touchstart', 'touchend'].forEach(function (t) { window.addEventListener(t, function () { lastTouch = Date.now(); }, true); });
	['mousedown', 'mouseup', 'click'].forEach(function (t) { window.addEventListener(t, function (e) {
		if ((e.sourceCapabilities && e.sourceCapabilities.firesTouchEvents) || Date.now() - lastTouch < 800) {
			e.stopImmediatePropagation();
			e.preventDefault();
		}
	}, true); });
})();"""


func _ready() -> void:
	var argv := OS.get_cmdline_user_args() + OS.get_cmdline_args()
	if OS.has_feature("web"):
		JavaScriptBridge.eval(WEB_TOUCH_FIX, true)
		argv.append_array(AppArgs.web_query_args(str(JavaScriptBridge.eval("location.origin")), str(JavaScriptBridge.eval("location.search"))))
	var args := AppArgs.parse(argv, OS.has_feature("dedicated_server"))
	for e in args.errors:
		push_error(e)
	print("escapebox %s mode, sdk %s, godot %s" % [
		"server" if args.is_server() else "client",
		EscapeboxSDK.VERSION,
		Engine.get_version_info().string,
	])
	if args.stats:
		var t := Timer.new()
		t.wait_time = 5.0
		t.autostart = true
		t.timeout.connect(func() -> void:
			print("stats: %d fps, %.1f ms process, %d draw calls" % [Engine.get_frames_per_second(),
				Performance.get_monitor(Performance.TIME_PROCESS) * 1000.0,
				Performance.get_monitor(Performance.RENDER_TOTAL_DRAW_CALLS_IN_FRAME)]))
		add_child(t)
	if args.smoke_test or not args.errors.is_empty():
		get_tree().quit(0 if args.errors.is_empty() else 1)
		return
	if args.is_server():
		_run_server(args)
		return
	Settings.load_settings()
	Device.apply_ui_scale(get_tree().root)
	get_tree().root.size_changed.connect(func() -> void: Device.apply_ui_scale(get_tree().root))
	if args.is_remote_client():
		_join(args)
	elif not args.room_id.is_empty():
		_touchbot = args.touchbot
		_touchbot_from = args.touchbot_from
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
	if pack_path.is_empty() and OS.has_feature("web") and not RoomLoader.has_local(room_id):
		# The browser build carries no rooms: fetch the pack from the platform
		# that serves this page (ADR-0025).
		var fetcher := RoomPackFetcher.new()
		add_child(fetcher)
		pack_path = await fetcher.fetch(str(JavaScriptBridge.eval("location.origin")), room_id)
		fetcher.queue_free()
		if pack_path.is_empty():
			_show_menu("Could not get the room: %s" % fetcher.error)
			return
	var session := PlaySession.new()
	add_child(session)
	if not session.start(room_id, pack_path, "", difficulty):
		var err := session.error
		session.queue_free()
		push_error(err)
		_show_menu(err)
		return
	session.left.connect(func() -> void:
		if not _back_to_site(""):
			_show_menu())
	if _touchbot:
		var bot := TouchBot.new()
		bot.session = session
		bot.first_step = _touchbot_from
		session.add_child(bot)


func _join(args: AppArgs) -> void:
	if _menu:
		_menu.queue_free()
		_menu = null
	var session := PlaySession.new()
	add_child(session)
	var code := args.join_code
	session.left.connect(func() -> void:
		if not _back_to_site(code):
			_show_menu(session.error))
	session.start_remote(args)


## Browser build: leaving the room returns to the website (that game's page,
## or the lobby) instead of the in-engine menu. False on desktop.
func _back_to_site(code: String) -> bool:
	if not OS.has_feature("web"):
		return false
	var dest := "/g/%s" % code.uri_encode() if not code.is_empty() else "/"
	JavaScriptBridge.eval("window.location.assign(%s)" % JSON.stringify(dest))
	return true


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
