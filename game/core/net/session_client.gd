class_name SessionClient
extends Node
## Client side of the connection (PLAN.md 7.4): connects, sends the join
## token as the first RPC, and reconnects after a drop until close() is called.
## The server answers with a full snapshot, so a rejoin needs nothing special.

signal status_changed(status: String, detail: String)

const RETRY_S := 2.0

var host: String = "127.0.0.1"
var port: int = 7777
var transport: String = "enet"
var token: String = ""
var display_name: String = "Player"
## M3: when set, every connection attempt first asks the platform for a
## fresh single-use join token (and the game server's address) with the code.
var platform_url: String = ""
var join_code: String = ""
## Filled from the platform's answer.
var session_id: String = ""
var room_id: String = ""
var _platform: PlatformClient = null

var _joined := false
var _closing := false
var _retry_t := -1.0
var _wired := false


## Joins through the platform with the host's join code.
func open_platform(p_url: String, p_code: String, p_name: String) -> Error:
	platform_url = p_url
	join_code = p_code
	if _platform == null:
		_platform = PlatformClient.new(p_url)
		_platform.name = "Platform"
		add_child(_platform)
	return open("", 0, "enet", "", p_name)


func open(p_host: String, p_port: int, p_transport: String, p_token: String, p_name: String) -> Error:
	host = p_host
	port = p_port
	transport = p_transport
	token = p_token
	display_name = p_name
	_closing = false
	if not _wired:
		_wired = true
		multiplayer.connected_to_server.connect(_on_connected)
		multiplayer.connection_failed.connect(_on_lost.bind("connection failed"))
		multiplayer.server_disconnected.connect(_on_lost.bind("server disconnected"))
		Game.net.welcomed.connect(func(_i: Dictionary) -> void:
			_joined = true
			# After the room has loaded: the load itself can stall this process
			# for seconds, which a short timeout would mistake for a dead link.
			call_deferred("_tighten_timeouts")
			status_changed.emit("connected", ""))
		Game.net.rejected.connect(func(reason: String) -> void:
			_closing = true
			_joined = false
			status_changed.emit("rejected", reason))
	return _connect()


func is_joined() -> bool:
	return _joined


func close() -> void:
	_closing = true
	_joined = false
	_retry_t = -1.0
	if multiplayer.multiplayer_peer:
		multiplayer.multiplayer_peer.close()
	multiplayer.multiplayer_peer = null


func _connect() -> Error:
	if not platform_url.is_empty():
		_fetch_ticket()
		return OK
	return _connect_direct()


func _fetch_ticket() -> void:
	status_changed.emit("connecting", platform_url)
	_platform.request_async(HTTPClient.METHOD_POST, "/api/join", {"invite_code": join_code, "display_name": display_name},
		func(code: int, data: Variant) -> void:
			if _closing:
				return
			if code == 200 and data is Dictionary:
				host = str(data["host"])
				port = int(data["port"])
				transport = str(data.get("transport", "enet"))
				token = str(data["join_token"])
				session_id = str(data.get("session_id", ""))
				room_id = str(data.get("room_id", ""))
				_connect_direct()
			elif code in [400, 403, 404]:
				_closing = true
				var msg: String = data.get("message", "join refused") if data is Dictionary else "join refused"
				status_changed.emit("rejected", msg)
			else:
				_schedule_retry("platform not reachable at %s" % platform_url), 10.0)


func _connect_direct() -> Error:
	var err: Error
	var peer: MultiplayerPeer
	if transport == "ws":
		var ws := WebSocketMultiplayerPeer.new()
		err = ws.create_client("ws://%s:%d" % [host, port])
		peer = ws
	else:
		var enet := ENetMultiplayerPeer.new()
		err = enet.create_client(host, port)
		peer = enet
	if err != OK:
		_schedule_retry("cannot open %s:%d (%s)" % [host, port, error_string(err)])
		return err
	multiplayer.multiplayer_peer = peer
	status_changed.emit("connecting", "%s:%d" % [host, port])
	return OK


func _on_connected() -> void:
	Game.net.send_join(token, display_name)


func _tighten_timeouts() -> void:
	if multiplayer.multiplayer_peer:
		NetTimeouts.apply(multiplayer.multiplayer_peer, 1)


func _on_lost(reason: String) -> void:
	_joined = false
	Game.net._fail_pending()
	multiplayer.multiplayer_peer = null
	if _closing:
		return
	_schedule_retry(reason)


func _schedule_retry(reason: String) -> void:
	status_changed.emit("lost", reason)
	_retry_t = RETRY_S


func _process(delta: float) -> void:
	if _retry_t < 0.0 or _closing:
		return
	_retry_t -= delta
	if _retry_t < 0.0:
		_connect()
