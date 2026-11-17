extends Node3D
## Records a room's intro trailer from a shot list (docs/research/06-intro-videos.md).
## Run through tools/trailer/build.sh, or directly:
##   godot --path game --write-movie out.avi --fixed-fps 30 \
##     res://tests/scenes/room_trailer.tscn -- --room night_shift --shots /abs/media/rooms/night_shift/trailer.json
## Shot list: {"quality": "high", "shots": [{"duration": s, "from": [x,y,z,yaw,pitch],
## "to": [...], "caption": "...", "title": "...", "set": {"node/path": {state}}}]}.
## A shot without "to" holds still; "title" draws a centred title card over it.

var _cam: Camera3D
var _shots: Array = []
var _i := -1
var _t := 0.0
var _caption: Label
var _title: Label
var _dim: ColorRect


func _ready() -> void:
	var args := OS.get_cmdline_user_args()
	var spec: Variant = JSON.parse_string(FileAccess.get_file_as_string(_arg(args, "--shots", "")))
	if not spec is Dictionary or not (spec as Dictionary).get("shots") is Array:
		push_error("room_trailer: no shot list (--shots)")
		get_tree().quit(1)
		return
	_shots = spec["shots"]
	var loader := RoomLoader.new()
	if not loader.load_room(_arg(args, "--room", ""), ""):
		push_error(loader.error)
		get_tree().quit(1)
		return
	var room := loader.instantiate()
	add_child(room)
	GraphicsQuality.apply(room, str(spec.get("quality", "high")))
	Game.start_local_session(loader.manifest, room, "trailer")
	_cam = Camera3D.new()
	_cam.fov = float(spec.get("fov", 70.0))
	add_child(_cam)
	_cam.make_current()
	_build_overlay()
	_next_shot()


func _build_overlay() -> void:
	var layer := CanvasLayer.new()
	add_child(layer)
	# A plain Label with its own background: inside a container an autowrapping
	# label asks for its height before it has a width and grows off-screen.
	_caption = Label.new()
	var bg := StyleBoxFlat.new()
	bg.bg_color = Color(0, 0, 0, 0.55)
	bg.set_content_margin_all(14)
	bg.set_corner_radius_all(6)
	_caption.add_theme_stylebox_override("normal", bg)
	_caption.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	_caption.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
	_caption.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	_caption.add_theme_font_size_override("font_size", 34)
	_caption.add_theme_color_override("font_color", Color(0.96, 0.92, 0.84))
	layer.add_child(_caption)
	_place_caption()
	# Title cards darken the shot so the title reads (it is also the poster).
	_dim = ColorRect.new()
	_dim.color = Color(0, 0, 0, 0.45)
	_dim.set_anchors_preset(Control.PRESET_FULL_RECT)
	_dim.mouse_filter = Control.MOUSE_FILTER_IGNORE
	layer.add_child(_dim)
	_title = Label.new()
	_title.set_anchors_preset(Control.PRESET_FULL_RECT)
	_title.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	_title.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
	_title.add_theme_font_size_override("font_size", 112)
	_title.add_theme_constant_override("outline_size", 12)
	_title.add_theme_color_override("font_outline_color", Color(0.08, 0.05, 0.02, 0.9))
	_title.add_theme_color_override("font_color", Color(0.98, 0.9, 0.7))
	_title.add_theme_color_override("font_shadow_color", Color(0, 0, 0, 0.85))
	_title.add_theme_constant_override("shadow_offset_x", 3)
	_title.add_theme_constant_override("shadow_offset_y", 3)
	layer.add_child(_title)


## The caption box: 76 % of the width, near the bottom. Set from the visible
## rect each frame (anchors under the project's stretch settings misplaced it).
func _place_caption() -> void:
	var vs := get_viewport().get_visible_rect().size
	_caption.position = Vector2(vs.x * 0.12, vs.y * 0.79)
	_caption.size = Vector2(vs.x * 0.76, vs.y * 0.14)


func _next_shot() -> void:
	_i += 1
	_t = 0.0
	if _i >= _shots.size():
		get_tree().quit(0)
		return
	var s: Dictionary = _shots[_i]
	var states: Dictionary = s.get("set", {})
	if not states.is_empty():
		# Staging, not gameplay: silence the one-shot sounds (door, lock) the
		# state changes trigger, or they land loudly on the cut.
		var before := find_children("*", "AudioStreamPlayer3D", true, false)
		for path: String in states:
			Game.authority.set_node_state(path, states[path])
		for p in find_children("*", "AudioStreamPlayer3D", true, false):
			if not p in before and not p.get_parent() is AmbientZone:
				p.queue_free()
	_caption.text = str(s.get("caption", ""))
	_caption.visible = not _caption.text.is_empty()
	_title.text = str(s.get("title", ""))
	_dim.visible = not _title.text.is_empty()
	_apply(s, 0.0)


## Camera pose for shot `s` at progress u (0..1), eased.
func _apply(s: Dictionary, u: float) -> void:
	var a: Array = s["from"]
	var b: Array = s.get("to", a)
	var e := smoothstep(0.0, 1.0, u)
	var pa := Vector3(a[0], a[1], a[2])
	var pb := Vector3(b[0], b[1], b[2])
	_cam.position = pa.lerp(pb, e)
	_cam.rotation_degrees = Vector3(lerpf(a[4], b[4], e), lerpf(a[3], b[3], e), 0)
	# Captions and titles fade in and out over the shot's first/last half second.
	var d := float(s["duration"])
	var fade := clampf(minf(_t, d - _t) / 0.5, 0.0, 1.0)
	_caption.modulate.a = fade
	_title.modulate.a = fade
	_dim.modulate.a = fade


func _process(delta: float) -> void:
	if _i < 0 or _i >= _shots.size():
		return
	var s: Dictionary = _shots[_i]
	_place_caption()
	_t += delta
	var d := float(s["duration"])
	if _t >= d:
		_next_shot()
		return
	_apply(s, _t / d)


static func _arg(args: PackedStringArray, key: String, def: String) -> String:
	var i := args.find(key)
	return args[i + 1] if i >= 0 and i + 1 < args.size() else def
