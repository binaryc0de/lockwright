class_name PlaySession
extends Node3D
## One room being played on this client: the room scene, the local player,
## teammates, and the HUD. Offline (start) hosts the authority in-process;
## networked (start_remote) joins a dedicated server (ADR-0015).

signal left

var room: RoomRoot
var player: FirstPersonPlayer
var hud: Hud
var remote_players: RemotePlayers
var error: String = ""

var _pack_path: String = ""
var _loading := false
## The platform this client joined through ("" for a direct --connect); room
## packs the game lacks are downloaded from it.
var _platform_url: String = ""
var _late_welcome: Dictionary = {}
var _bot: SolutionBot = null
var _remote := false
## Shown while joining, until the server's welcome (players only, not bots).
var _overlay: CanvasLayer = null
var _overlay_label: Label = null


## Loads and starts a room offline. Returns false (with `error`) on failure.
func start(room_id: String, pack_path: String = "", session_id: String = "", difficulty: String = "") -> bool:
	var loader := _load(room_id, pack_path)
	if loader == null:
		return false
	if session_id.is_empty():
		session_id = "local-%d" % int(Time.get_unix_time_from_system())
	Game.display_name = Settings.display_name
	Game.start_local_session(loader.manifest, room, session_id, {}, null, difficulty)
	_spawn_player_and_hud()
	return true


## Joins a server; the room loads when the server's welcome names it.
## `bot` makes this a headless test client instead of a player.
func start_remote(args: AppArgs) -> bool:
	_pack_path = args.pack_path
	_platform_url = args.join_url
	_remote = true
	Game.display_name = args.display_name if not args.display_name.is_empty() else Settings.display_name
	Game.net.welcomed.connect(_on_welcomed)
	Game.net.rejected.connect(_on_rejected)
	var client := SessionClient.new()
	client.name = "SessionClient"
	Game.net.add_child(client)
	Game.net.client = client
	client.status_changed.connect(_on_status)
	if not args.bot:
		_show_overlay("Joining game %s ..." % args.join_code if args.via_platform() else "Connecting to %s:%d ..." % [args.connect_host, args.port])
	if args.bot:
		_bot = SolutionBot.new()
		_bot.first_step = args.bot_first_step
		_bot.last_step = args.bot_last_step
		_bot.wait_for_win = args.bot_wait_win
		_bot.flag_value = args.bot_flag
		_bot.wait_for_card = args.bot_wait_card
		add_child(_bot)
	var err: Error
	if args.via_platform():
		Game.join_code = args.join_code
		err = client.open_platform(args.join_url, args.join_code, Game.display_name)
	else:
		Game.join_code = ""
		err = client.open(args.connect_host, args.port, args.transport, args.server_token, Game.display_name)
	if err != OK:
		error = "Cannot connect to %s:%d (%s)." % [args.connect_host, args.port, error_string(err)]
	return true


func _on_welcomed(info: Dictionary) -> void:
	if _loading:
		_late_welcome = info  # a rejoin while the room loads: use the newest
		return
	var snap = JSON.parse_string(str(info["snapshot_json"]))
	if not snap is Dictionary:
		push_error("server sent an unreadable snapshot")
		return
	if room != null:
		Game.rejoin_client(info["player_id"], snap, float(info["server_now"]))
		_place_from_welcome(info)
		if hud:
			hud.sync_end_state()
		return
	# Load on a worker thread: a multi-second freeze here outlasts ENet's
	# timeouts on slower PCs and drops the link we just joined on.
	_loading = true
	var room_id := str(info["room_id"])
	if _pack_path.is_empty() and not _platform_url.is_empty() and not RoomLoader.has_local(room_id):
		var fetched := await _fetch_pack(room_id)
		if fetched.is_empty():
			_loading = false
			error = "Joined, but could not get the room: %s" % error
			push_error(error)
			Game.net.disconnect_client()
			if _bot:
				_bot._finish(2, error)
			else:
				leave()
			return
		_pack_path = fetched
	var loader := RoomLoader.new()
	var ok: bool = await loader.load_room_async(str(info["room_id"]), _pack_path, get_tree())
	_loading = false
	if not is_inside_tree():
		return  # left while loading
	if ok:
		room = loader.instantiate()
		if room == null:
			ok = false
		else:
			add_child(room)
			GraphicsQuality.apply(room, Settings.graphics)
	if not ok:
		error = loader.error
		loader = null
	if not _late_welcome.is_empty():
		info = _late_welcome
		_late_welcome = {}
		snap = JSON.parse_string(str(info["snapshot_json"]))
	if loader == null:
		error = "Joined, but this game cannot load the server's room: %s" % error
		push_error(error)
		Game.net.disconnect_client()
		if _bot:
			_bot._finish(2, error)
		else:
			leave()
		return
	_hide_overlay()
	Game.start_client_session(loader.manifest, room, info["player_id"], snap, float(info["server_now"]))
	remote_players = RemotePlayers.new()
	remote_players.name = "RemotePlayers"
	add_child(remote_players)
	if _bot == null:
		_spawn_player_and_hud()
		_place_from_welcome(info)
		hud.sync_end_state()
		if not Game.join_code.is_empty():
			hud.toast("Join code for friends: %s" % Game.join_code)


func _on_placed(eye: Vector3) -> void:
	if player:
		_place_from_welcome({"position": eye})


## Stand where the server says (rejoin keeps your place; the server rejects
## positions that jump, so the client must start from the server's view).
func _place_from_welcome(info: Dictionary) -> void:
	if player == null or not info.has("position"):
		return
	var eye: Vector3 = info["position"]
	var t := player.global_transform
	t.origin = eye - Vector3.UP * FirstPersonPlayer.EYE_HEIGHT
	player.global_transform = t


func _on_rejected(reason: String) -> void:
	error = "The server refused to let you in (%s)." % ("wrong invite password or expired join ticket" if reason == "bad_token" else reason)
	if hud:
		hud.toast(error)
	elif _bot == null:
		leave()


func _on_status(status: String, detail: String) -> void:
	print("connection: %s %s" % [status, detail])
	if status == "rejected" and room == null:
		# Refused before the room loaded (e.g. a bad join code): back out.
		error = "Could not join: %s" % detail
		if _bot:
			_bot._finish(3, error)
		else:
			leave()
		return
	if _overlay_label:
		match status:
			"connecting":
				_overlay_label.text = "Connecting to %s ..." % detail
			"lost":
				_overlay_label.text = "Can't reach the server (%s). Retrying ..." % detail
	if hud == null:
		return
	match status:
		"lost":
			hud.toast("Connection lost (%s). Reconnecting..." % detail)
		"connected":
			hud.toast("Connected.")
		"rejected":
			hud.toast("The server refused the connection (%s)." % detail)


func _load(room_id: String, pack_path: String) -> RoomLoader:
	var loader := RoomLoader.new()
	if not loader.load_room(room_id, pack_path):
		error = loader.error
		return null
	room = loader.instantiate()
	if room == null:
		error = loader.error
		return null
	add_child(room)
	GraphicsQuality.apply(room, Settings.graphics)
	return loader


func _spawn_player_and_hud() -> void:
	player = FirstPersonPlayer.new()
	player.name = "LocalPlayer"
	player.room_root = room
	add_child(player)
	player.place_at(room.join_spawn_transform())
	if not Game.local_player_placed.is_connected(_on_placed):
		Game.local_player_placed.connect(_on_placed)
	hud = Hud.new()
	add_child(hud)
	hud.setup(player)
	hud.leave_requested.connect(leave)
	hud.open_briefing()


## Downloads the room's pack from the platform, showing progress.
func _fetch_pack(room_id: String) -> String:
	var fetcher := RoomPackFetcher.new()
	add_child(fetcher)
	fetcher.progressed.connect(func(f: float) -> void:
		if _overlay_label:
			_overlay_label.text = "Downloading the room ... %d%%" % int(f * 100))
	var path := await fetcher.fetch(_platform_url, room_id)
	error = fetcher.error
	fetcher.queue_free()
	if not path.is_empty():
		print("room pack: %s" % path)
	return path


func _show_overlay(text: String) -> void:
	_overlay = CanvasLayer.new()
	add_child(_overlay)
	var bg := ColorRect.new()
	bg.color = Color(0.07, 0.07, 0.09)
	bg.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	_overlay.add_child(bg)
	var center := CenterContainer.new()
	center.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	_overlay.add_child(center)
	var box := VBoxContainer.new()
	box.custom_minimum_size = Vector2(520, 0)
	box.add_theme_constant_override("separation", 14)
	center.add_child(box)
	_overlay_label = Label.new()
	_overlay_label.text = text
	_overlay_label.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	_overlay_label.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	box.add_child(_overlay_label)
	var cancel := Button.new()
	cancel.text = "Cancel"
	cancel.custom_minimum_size = Vector2(0, 44)
	cancel.pressed.connect(leave)
	box.add_child(cancel)
	Input.mouse_mode = Input.MOUSE_MODE_VISIBLE


func _hide_overlay() -> void:
	if _overlay:
		_overlay.queue_free()
	_overlay = null
	_overlay_label = null


func _exit_tree() -> void:
	if Game.local_player_placed.is_connected(_on_placed):
		Game.local_player_placed.disconnect(_on_placed)


func leave() -> void:
	if Game.net.welcomed.is_connected(_on_welcomed):
		Game.net.welcomed.disconnect(_on_welcomed)
		Game.net.rejected.disconnect(_on_rejected)
	Game.end_session()
	if _remote:
		# Covers leaving before the welcome, when Game is not in CLIENT mode yet.
		Game.net.disconnect_client()
	Game.hud = null
	ItemIcons.clear()
	Input.mouse_mode = Input.MOUSE_MODE_VISIBLE
	left.emit()
	queue_free()
