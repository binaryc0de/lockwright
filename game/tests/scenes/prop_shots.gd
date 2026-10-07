extends Node3D
## Renders every top-level part of a prop GLB as Godot imports it: one close
## view per part (front, three-quarter) under a warm key light and a dim
## ambient, like a room. Catches import problems Blender previews cannot
## (texture coordinate sets, alpha modes, normal-map detection).
##   godot --path game res://tests/scenes/prop_shots.tscn -- --glb res://.../x.glb --out DIR
## tools/shots/prop_views.sh wraps it with the web (Compatibility) renderer.

var _glb := ""
var _out := ""
var _only := ""


func _ready() -> void:
	var args := OS.get_cmdline_user_args()
	for i in args.size():
		match args[i]:
			"--glb": _glb = args[i + 1]
			"--out": _out = args[i + 1]
			"--part": _only = args[i + 1]
	if _glb.is_empty() or _out.is_empty():
		push_error("usage: -- --glb res://path.glb --out DIR [--part name]")
		get_tree().quit(2)
		return
	DirAccess.make_dir_recursive_absolute(_out)
	var env := WorldEnvironment.new()
	var e := Environment.new()
	e.background_mode = Environment.BG_COLOR
	e.background_color = Color(0.16, 0.16, 0.17)
	e.ambient_light_source = Environment.AMBIENT_SOURCE_COLOR
	e.ambient_light_color = Color(0.78, 0.80, 0.72)
	e.ambient_light_energy = 0.35
	e.tonemap_mode = Environment.TONE_MAPPER_FILMIC
	env.environment = e
	add_child(env)
	var key := DirectionalLight3D.new()
	key.light_color = Color(1.0, 0.88, 0.7)
	key.light_energy = 1.4
	key.shadow_enabled = true
	key.rotation_degrees = Vector3(-40, 35, 0)
	add_child(key)
	var fill := DirectionalLight3D.new()
	fill.light_color = Color(0.6, 0.7, 0.85)
	fill.light_energy = 0.35
	fill.rotation_degrees = Vector3(-20, -140, 0)
	add_child(fill)
	var cam := Camera3D.new()
	cam.fov = 40.0
	add_child(cam)
	cam.make_current()
	var ps := load(_glb) as PackedScene
	if ps == null:
		push_error("cannot load %s" % _glb)
		get_tree().quit(1)
		return
	var inst := ps.instantiate() as Node3D
	add_child(inst)
	var parts: Array[Node3D] = []
	for c in inst.get_children():
		if c is Node3D and (_only.is_empty() or str(c.name) == _only):
			parts.append(c)
	for p in parts:
		for q in parts:
			q.visible = q == p
		var box := _bounds(p)
		var centre := box.get_center()
		var r := maxf(box.size.length() * 0.5, 0.05)
		var dist := r / tan(deg_to_rad(cam.fov * 0.5)) * 1.15
		for view in [["front", Vector3(0, 0.15, -1)], ["three_quarter", Vector3(-0.7, 0.45, -0.7)]]:
			var dir: Vector3 = (view[1] as Vector3).normalized()
			cam.global_position = centre + dir * dist
			cam.look_at(centre, Vector3.UP)
			for _f in 3:
				await RenderingServer.frame_post_draw
			var img := get_viewport().get_texture().get_image()
			img.save_png("%s/%s__%s.png" % [_out, p.name, view[0]])
	print("prop_shots: %d parts -> %s" % [parts.size(), _out])
	get_tree().quit(0)


func _bounds(n: Node3D) -> AABB:
	var out := AABB()
	var first := true
	for mi: MeshInstance3D in ([n] if n is MeshInstance3D else []) + n.find_children("*", "MeshInstance3D", true, false):
		var a: AABB = mi.global_transform * mi.get_aabb()
		out = a if first else out.merge(a)
		first = false
	return out
