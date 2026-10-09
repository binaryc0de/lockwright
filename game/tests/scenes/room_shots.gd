extends Node3D
## Renders screenshots of a room from fixed viewpoints, for art review on a
## machine with a real GPU (ADR-0003 forbids this on the iGPU dev box).
##   godot --path game res://tests/scenes/room_shots.tscn -- \
##     --room night_shift --out /tmp/shots [--fov 80] [--quality low|medium|high] [--difficulty <id>] [--set path={json} ...] [--views name:x,y,z:yaw_deg:pitch_deg ...]
## Without --views it uses the room spawn plus any Marker3D named Shot* in the room.

const SETTLE_FRAMES := 45

var _out := "user://shots"
var _views: Array = []
var _cam: Camera3D
var _i := 0
var _frames := 0


func _ready() -> void:
	var args := OS.get_cmdline_user_args()
	var room_id := _arg(args, "--room", "night_shift")
	_out = _arg(args, "--out", _out)
	DirAccess.make_dir_recursive_absolute(_out)
	var loader := RoomLoader.new()
	if not loader.load_room(room_id, _arg(args, "--pack", "")):
		push_error(loader.error)
		get_tree().quit(1)
		return
	var room := loader.instantiate()
	add_child(room)
	GraphicsQuality.apply(room, _arg(args, "--quality", "high"))
	Game.start_local_session(loader.manifest, room, "shots", {}, null, _arg(args, "--difficulty", ""))
	# --set path={json state} (repeatable): put nodes into a state for the shot
	# (review only; bypasses the puzzle rules).
	for j in args.size():
		if args[j] == "--set" and j + 1 < args.size():
			var kv := args[j + 1].split("=", true, 1)
			Game.authority.set_node_state(kv[0], JSON.parse_string(kv[1]))
			print("set %s" % args[j + 1])
	# --show path (repeatable): make a hidden node visible for the shot (review
	# only; e.g. heat-ink text that needs the lamp in hand).
	for j in args.size():
		if args[j] == "--show" and j + 1 < args.size():
			var n := room.get_node_or_null(args[j + 1]) as Node3D
			if n:
				n.visible = true
				var rev := n.get_parent() as UVReveal
				if rev and n is Label3D:
					rev.set_process(false)
					(n as Label3D).text = EBTemplate.render(rev.text, Game.vars())
	_cam = Camera3D.new()
	_cam.fov = float(_arg(args, "--fov", "80"))
	add_child(_cam)
	_cam.make_current()
	var s := room.spawn_transform()
	_views.append({"name": "spawn", "pos": s.origin + Vector3.UP * 1.6, "yaw": rad_to_deg(s.basis.get_euler().y), "pitch": -5.0})
	for m in room.find_children("Shot*", "Marker3D", true, false):
		var mk := m as Marker3D
		_views.append({"name": mk.name.to_snake_case(), "pos": mk.global_position, "yaw": mk.global_rotation_degrees.y, "pitch": mk.global_rotation_degrees.x})
	var i := args.find("--views")
	if i >= 0:
		_views.clear()
		for v in args.slice(i + 1):
			var p := v.split(":")
			if p.size() != 4 or v.begins_with("--"):
				break
			var xyz := p[1].split_floats(",")
			_views.append({"name": p[0], "pos": Vector3(xyz[0], xyz[1], xyz[2]), "yaw": float(p[2]), "pitch": float(p[3])})
	print("renderer: %s on %s" % [RenderingServer.get_current_rendering_method(), RenderingServer.get_video_adapter_name()])
	_apply_view()


func _apply_view() -> void:
	var v: Dictionary = _views[_i]
	_cam.global_position = v["pos"]
	_cam.rotation_degrees = Vector3(v["pitch"], v["yaw"], 0)
	_frames = 0


var _settled_ms := -1


func _process(_delta: float) -> void:
	_frames += 1
	# The first shot also waits for --set moves to finish (parts glide).
	if _settled_ms < 0:
		_settled_ms = Time.get_ticks_msec() + 2500
	if _frames < SETTLE_FRAMES or Time.get_ticks_msec() < _settled_ms:
		return
	var path := "%s/%02d_%s.png" % [_out, _i, _views[_i]["name"]]
	get_viewport().get_texture().get_image().save_png(path)
	print("shot ", path)
	_i += 1
	if _i >= _views.size():
		get_tree().quit(0)
	else:
		_apply_view()


static func _arg(args: PackedStringArray, key: String, def: String) -> String:
	var i := args.find(key)
	return args[i + 1] if i >= 0 and i + 1 < args.size() else def
