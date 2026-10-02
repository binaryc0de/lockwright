class_name PlaySession
extends Node3D
## One room being played on this client: the room scene, the local player,
## and the HUD. M1 also hosts the authority in-process (offline).

signal left

var room: RoomRoot
var player: FirstPersonPlayer
var hud: Hud
var error: String = ""


## Loads and starts a room. Returns false (with `error`) on failure.
func start(room_id: String, pack_path: String = "", session_id: String = "") -> bool:
	var loader := RoomLoader.new()
	if not loader.load_room(room_id, pack_path):
		error = loader.error
		return false
	room = loader.instantiate()
	if room == null:
		error = loader.error
		return false
	add_child(room)
	if session_id.is_empty():
		session_id = "local-%d" % int(Time.get_unix_time_from_system())
	Game.display_name = Settings.display_name
	Game.start_local_session(loader.manifest, room, session_id)

	player = FirstPersonPlayer.new()
	player.name = "LocalPlayer"
	add_child(player)
	player.place_at(room.spawn_transform())

	hud = Hud.new()
	add_child(hud)
	hud.setup(player)
	hud.leave_requested.connect(leave)
	hud.open_briefing()
	return true


func leave() -> void:
	Game.end_session()
	Game.hud = null
	Input.mouse_mode = Input.MOUSE_MODE_VISIBLE
	left.emit()
	queue_free()
