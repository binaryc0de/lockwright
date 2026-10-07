extends SceneTree
## Supplemental import review only. Lives outside the game and ships nowhere.
## -- --glb res://... --out ABS [--part NAME] [--canyon]

func _initialize() -> void:
	call_deferred("render_views")


func render_views() -> void:
	var args := OS.get_cmdline_user_args()
	var path := ""
	var out := ""
	var part := ""
	var canyon := args.has("--canyon")
	for i in args.size():
		match args[i]:
			"--glb": path = args[i + 1]
			"--out": out = args[i + 1]
			"--part": part = args[i + 1]
	DirAccess.make_dir_recursive_absolute(out)
	var stage := Node3D.new()
	root.add_child(stage)
	var env := WorldEnvironment.new()
	var e := Environment.new()
	e.background_mode = Environment.BG_COLOR
	e.background_color = Color(0.48, 0.60, 0.64) if canyon else Color(0.16, 0.16, 0.17)
	e.ambient_light_source = Environment.AMBIENT_SOURCE_COLOR
	e.ambient_light_color = Color(0.78, 0.80, 0.72)
	e.ambient_light_energy = 0.5 if canyon else 0.35
	e.tonemap_mode = Environment.TONE_MAPPER_FILMIC
	env.environment = e
	stage.add_child(env)
	var key := DirectionalLight3D.new()
	key.light_color = Color(1.0, 0.92, 0.8)
	key.light_energy = 1.2
	key.shadow_enabled = true
	key.rotation_degrees = Vector3(-40, 35, 0)
	stage.add_child(key)
	var camera := Camera3D.new()
	camera.fov = 65 if canyon else 40
	camera.far = 600
	stage.add_child(camera)
	camera.make_current()
	var scene := load(path) as PackedScene
	if scene == null:
		quit(1)
		return
	var asset := scene.instantiate() as Node3D
	stage.add_child(asset)
	for mi in asset.find_children("*", "MeshInstance3D", true, false):
		for si in mi.mesh.get_surface_count():
			var mat = mi.mesh.surface_get_material(si)
			if mat is StandardMaterial3D:
				print(mi.name," material=",mat.resource_name," vertex_as_albedo=",mat.vertex_color_use_as_albedo," albedo=",mat.albedo_color)
	if not part.is_empty():
		for child in asset.get_children():
			if child is Node3D: child.visible = str(child.name) == part
	var views: Array = []
	if canyon:
		views = [
			["gallery_left", Vector3(-7,6.1,-19), Vector3(0,-7,-48)],
			["gallery_centre", Vector3(0,6.1,-19), Vector3(0,-7,-48)],
			["gallery_right", Vector3(7,6.1,-19), Vector3(0,-7,-48)],
			["span", Vector3(7,6.1,-30), Vector3(8,5,-43.7)],
			["valley", Vector3(0,6.1,-19), Vector3(0,-20,-54)]
		]
	else:
		var bounds := AABB()
		var first := true
		for mi in asset.find_children("*", "MeshInstance3D", true, false):
			if not mi.is_visible_in_tree(): continue
			var box: AABB = mi.global_transform * mi.get_aabb()
			bounds = box if first else bounds.merge(box)
			first = false
		var centre := bounds.get_center()
		var dist := maxf(bounds.size.length()*0.5,0.05)/tan(deg_to_rad(camera.fov*0.5))*1.15
		views = [[part+"__right",centre+Vector3(1,0.10,-0.10).normalized()*dist,centre],
			[part+"__reverse",centre+Vector3(0,0.15,1).normalized()*dist,centre]]
	for view in views:
		camera.global_position = view[1]
		camera.look_at(view[2], Vector3.UP)
		for i in 4: await RenderingServer.frame_post_draw
		root.get_texture().get_image().save_png(out+"/"+view[0]+".png")
	print("Supplemental Godot views: ",out)
	quit(0)
