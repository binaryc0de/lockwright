class_name ItemIcons
extends RefCounted
## Inventory thumbnails (ADR-0038): each Item's own meshes rendered once into
## a small transparent viewport, so rooms need no icon art. The viewports are
## kept (rendered once, never again) under one holder node at the tree root,
## keyed by the item's path, until the room is left (clear).

const SIZE := 128

static var _cache: Dictionary = {}
static var _holder: Node = null


## The thumbnail for `item`. `near` is any node in the scene tree.
static func icon(item: Item, near: Node) -> Texture2D:
	var key := item.eb_path
	var cached: Variant = _cache.get(key)
	if cached != null and is_instance_valid(cached):
		return (cached as SubViewport).get_texture()
	if not is_instance_valid(_holder):
		_holder = Node.new()
		_holder.name = "ItemIcons"
		near.get_tree().root.add_child.call_deferred(_holder)
	var vp := SubViewport.new()
	vp.size = Vector2i(SIZE, SIZE)
	vp.own_world_3d = true
	vp.transparent_bg = true
	vp.render_target_update_mode = SubViewport.UPDATE_ONCE
	var env := WorldEnvironment.new()
	env.environment = Environment.new()
	env.environment.background_mode = Environment.BG_CLEAR_COLOR
	env.environment.ambient_light_source = Environment.AMBIENT_SOURCE_COLOR
	env.environment.ambient_light_color = Color(0.75, 0.75, 0.75)
	vp.add_child(env)
	var light := DirectionalLight3D.new()
	light.rotation_degrees = Vector3(-45, 35, 0)
	vp.add_child(light)
	var pivot := Node3D.new()
	vp.add_child(pivot)
	var aabb := copy_meshes(item, pivot)
	pivot.position = -aabb.get_center()
	var cam := Camera3D.new()
	var reach := maxf(aabb.get_longest_axis_size(), 0.05)
	# A three-quarter view from above, framed on the item's bounds.
	cam.transform = Transform3D(Basis.from_euler(Vector3(deg_to_rad(-30), deg_to_rad(30), 0)), Vector3.ZERO)
	cam.position = cam.transform.basis.z * reach * 1.9
	cam.fov = 40
	cam.near = 0.01
	vp.add_child(cam)
	_holder.add_child(vp)
	_cache[key] = vp
	return vp.get_texture()


## Copies the visible meshes under `src` into `dest`, in `src`'s local space.
## Returns their combined bounds.
static func copy_meshes(src: Node3D, dest: Node3D) -> AABB:
	var aabb := AABB()
	var first := true
	var inv := src.global_transform.affine_inverse()
	for m in Interactable._meshes(src):
		if not shown_under(m, src):
			continue  # e.g. a greybox mesh hidden under a hero model
		var copy := MeshInstance3D.new()
		copy.mesh = m.mesh
		copy.material_override = m.material_override
		copy.transform = inv * m.global_transform
		dest.add_child(copy)
		var box := copy.transform * m.get_aabb()
		aabb = box if first else aabb.merge(box)
		first = false
	return aabb


## Visible relative to `root`: neither the node nor any parent up to `root` is
## hidden (the item itself may be hidden, e.g. still in a closed drawer).
static func shown_under(n: Node, root: Node) -> bool:
	while n != null and n != root:
		if n is Node3D and not (n as Node3D).visible:
			return false
		n = n.get_parent()
	return true


## Forget rendered icons (the room was left).
static func clear() -> void:
	if is_instance_valid(_holder):
		_holder.queue_free()
	_holder = null
	_cache.clear()
