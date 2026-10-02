extends Node3D
## Frame-time benchmark (M4 performance pass, ADR-0021). Walks a camera
## through the room at walking speed, turning as it goes, once per graphics
## preset, with vsync off, and prints GPU and CPU frame times.
##   godot --path game res://tests/scenes/perf_bench.tscn -- --room night_shift \
##     [--resolution-note 1920x1080] [--quality low,medium,high] [--seconds 12] \
##     [--path x,z;x,z;...] [--json out.json]
## Without --path it walks between the spawn and every Shot* marker.

const WARMUP_S := 3.0  # SDFGI and fog settle; not measured
const EYE := 1.6
const SPEED := 1.2  # m/s
const TURN := 40.0  # deg/s

var _room: RoomRoot
var _cam: Camera3D
var _levels: PackedStringArray
var _seconds := 12.0
var _points: Array[Vector3] = []
var _level_i := 0
var _t := 0.0
var _dist := 0.0
var _gpu: PackedFloat32Array = []
var _cpu: PackedFloat32Array = []
var _results := {}
var _json := ""


func _ready() -> void:
	var args := OS.get_cmdline_user_args()
	var loader := RoomLoader.new()
	if not loader.load_room(_arg(args, "--room", "night_shift"), _arg(args, "--pack", "")):
		push_error(loader.error)
		get_tree().quit(1)
		return
	_room = loader.instantiate()
	add_child(_room)
	Game.start_local_session(loader.manifest, _room, "bench")
	_levels = _arg(args, "--quality", "low,medium,high").split(",", false)
	_seconds = float(_arg(args, "--seconds", "12"))
	_json = _arg(args, "--json", "")
	var path := _arg(args, "--path", "")
	if path.is_empty():
		_points.append(_room.spawn_transform().origin)
		for m: Marker3D in _room.find_children("Shot*", "Marker3D", true, false):
			_points.append(m.global_position)
	else:
		for xz in path.split(";", false):
			var f := xz.split_floats(",")
			_points.append(Vector3(f[0], 0, f[1]))
	for i in _points.size():
		_points[i].y = EYE
	_cam = Camera3D.new()
	_cam.fov = 80.0
	add_child(_cam)
	_cam.make_current()
	DisplayServer.window_set_vsync_mode(DisplayServer.VSYNC_DISABLED)
	Engine.max_fps = 0
	RenderingServer.viewport_set_measure_render_time(get_viewport().get_viewport_rid(), true)
	print("renderer: %s on %s, window %s" % [RenderingServer.get_current_rendering_method(), RenderingServer.get_video_adapter_name(), get_window().size])
	_start_level()


func _start_level() -> void:
	GraphicsQuality.apply(_room, _levels[_level_i])
	_t = 0.0
	_dist = 0.0
	_gpu.clear()
	_cpu.clear()


func _process(delta: float) -> void:
	_t += delta
	_dist += SPEED * delta
	_place_camera()
	if _t < WARMUP_S:
		return
	var vp := get_viewport().get_viewport_rid()
	_gpu.append(RenderingServer.viewport_get_measured_render_time_gpu(vp))
	_cpu.append(delta * 1000.0)
	if _t < WARMUP_S + _seconds:
		return
	var r := {"gpu_ms": _stats(_gpu), "frame_ms": _stats(_cpu), "frames": _gpu.size()}
	_results[_levels[_level_i]] = r
	print("%-6s gpu avg %.2f ms p95 %.2f max %.2f | frame avg %.2f ms p95 %.2f (%.0f fps) | %d frames" % [
		_levels[_level_i], r.gpu_ms.avg, r.gpu_ms.p95, r.gpu_ms.max, r.frame_ms.avg, r.frame_ms.p95, 1000.0 / r.frame_ms.avg, r.frames])
	_level_i += 1
	if _level_i < _levels.size():
		_start_level()
		return
	if not _json.is_empty():
		var f := FileAccess.open(_json, FileAccess.WRITE)
		f.store_string(JSON.stringify({"adapter": RenderingServer.get_video_adapter_name(), "window": str(get_window().size), "results": _results}, "  "))
	get_tree().quit(0)


## Ping-pong along the polyline at walking speed, turning steadily.
func _place_camera() -> void:
	var total := 0.0
	for i in _points.size() - 1:
		total += _points[i].distance_to(_points[i + 1])
	var d := fposmod(_dist, maxf(total * 2.0, 0.001))
	if d > total:
		d = total * 2.0 - d
	var pos := _points[0]
	for i in _points.size() - 1:
		var seg := _points[i].distance_to(_points[i + 1])
		if d <= seg:
			pos = _points[i].lerp(_points[i + 1], d / maxf(seg, 0.001))
			break
		d -= seg
		pos = _points[i + 1]
	_cam.global_position = pos
	_cam.rotation_degrees = Vector3(-8.0, fmod(_t * TURN, 360.0), 0)


static func _stats(a: PackedFloat32Array) -> Dictionary:
	var s := Array(a)
	s.sort()
	var sum := 0.0
	for v: float in s:
		sum += v
	return {"avg": sum / maxf(s.size(), 1), "p95": s[int(s.size() * 0.95)] if s.size() else 0.0, "max": s.back() if s.size() else 0.0}


static func _arg(args: PackedStringArray, key: String, def: String) -> String:
	var i := args.find(key)
	return args[i + 1] if i >= 0 and i + 1 < args.size() else def
