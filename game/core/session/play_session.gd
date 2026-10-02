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
var _bot: SolutionBot = null


## Loads and starts a room offline. Returns false (with `error`) on failure.
func start(room_id: String, pack_path: String = "", session_id: String = "") -> bool:
	var loader := _load(room_id, pack_path)
	if loader == null:
		return false
	if session_id.is_empty():
		session_id = "local-%d" % int(Time.get_unix_time_from_system())
	Game.display_name = Settings.display_name
	Game.start_local_session(loader.manifest, room, session_id)
	_spawn_player_and_hud()
	return true


## Joins a server; the room loads when the server's welcome names it.
## `bot` makes this a headless test client instead of a player.
func start_remote(args: AppArgs) -> bool:
	_pack_path = args.pack_path
	Game.display_name = args.display_name if not args.display_name.is_empty() else Settings.display_name
	Game.net.welcomed.connect(_on_welcomed)
	Game.net.rejected.connect(_on_rejected)
	var client := SessionClient.new()
	client.name = "SessionClient"
	Game.net.add_child(client)
	Game.net.client = client
	client.status_changed.connect(_on_status)
	if args.bot:
		_bot = SolutionBot.new()
		_bot.first_step = args.bot_first_step
		_bot.last_step = args.bot_last_step
		_bot.wait_for_win = args.bot_wait_win
		add_child(_bot)
	var err := client.open(args.connect_host, args.port, args.transport, args.server_token, Game.display_name)
	if err != OK:
		error = "Cannot connect to %s:%d (%s)." % [args.connect_host, args.port, error_string(err)]
	return true


func _on_welcomed(info: Dictionary) -> void:
	var snap = JSON.parse_string(str(info["snapshot_json"]))
	if not snap is Dictionary:
		push_error("server sent an unreadable snapshot")
		return
	if room != null:
		Game.rejoin_client(info["player_id"], snap, float(info["server_now"]))
		return
	var loader := _load(str(info["room_id"]), _pack_path)
	if loader == null:
		push_error(error)
		if hud:
			hud.toast(error)
		return
	Game.start_client_session(loader.manifest, room, info["player_id"], snap, float(info["server_now"]))
	remote_players = RemotePlayers.new()
	remote_players.name = "RemotePlayers"
	add_child(remote_players)
	if _bot == null:
		_spawn_player_and_hud()


func _on_rejected(reason: String) -> void:
	error = "The server refused to let you in (%s)." % reason
	if hud:
		hud.toast(error)


func _on_status(status: String, detail: String) -> void:
	print("connection: %s %s" % [status, detail])
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
	return loader


func _spawn_player_and_hud() -> void:
	player = FirstPersonPlayer.new()
	player.name = "LocalPlayer"
	add_child(player)
	player.place_at(room.spawn_transform())
	hud = Hud.new()
	add_child(hud)
	hud.setup(player)
	hud.leave_requested.connect(leave)
	hud.open_briefing()


func leave() -> void:
	if Game.net.welcomed.is_connected(_on_welcomed):
		Game.net.welcomed.disconnect(_on_welcomed)
		Game.net.rejected.disconnect(_on_rejected)
	Game.end_session()
	Game.hud = null
	Input.mouse_mode = Input.MOUSE_MODE_VISIBLE
	left.emit()
	queue_free()
