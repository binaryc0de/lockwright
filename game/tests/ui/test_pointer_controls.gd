extends GdUnitTestSuite
## Point-and-tap controls, inventory thumbnails and drag-to-use, the walk
## mesh, and panels fitting small screens (ADR-0038). Headless, against a
## live in-process session of the code-built test room with a floor added.

const TestRoom := preload("res://tests/helpers/test_room.gd")

var room: RoomRoot
var hud: Hud
var player: FirstPersonPlayer
var results: Array[String] = []
var _saved_controls: String


func before_test() -> void:
	_saved_controls = Settings.controls
	Settings.controls = "point"
	room = auto_free(TestRoom.build())
	_box(room, "Floor", Vector3(0, -0.1, 0), Vector3(30, 0.2, 30))
	add_child(room)
	Game.start_local_session(TestRoom.manifest(), room, "pointer-test")
	Game.authority.allow_unpositioned = true
	player = auto_free(FirstPersonPlayer.new())
	player.room_root = room
	add_child(player)
	player.place_at(Transform3D.IDENTITY)
	hud = auto_free(Hud.new())
	add_child(hud)
	hud.setup(player)
	results.clear()
	Game.intent_result.connect(_on_result)


func after_test() -> void:
	Game.intent_result.disconnect(_on_result)
	Game.end_session()
	Game.hud = null
	ItemIcons.clear()
	Settings.controls = _saved_controls


func _on_result(path: String, verb: String, result: Dictionary) -> void:
	results.append("%s %s %s" % [path, verb, result.get("ok")])


## A solid box under `parent` (on the interaction layer if it is an
## Interactable, since those claim their bodies when they enter the tree).
func _box(parent: Node3D, n: String, pos: Vector3, extent: Vector3) -> StaticBody3D:
	var body := StaticBody3D.new()
	body.name = n
	var shape := CollisionShape3D.new()
	shape.shape = BoxShape3D.new()
	(shape.shape as BoxShape3D).size = extent
	body.add_child(shape)
	body.position = pos
	if parent is Interactable:
		body.collision_layer = 1 | (1 << (Interactable.INTERACT_LAYER - 1))
	parent.add_child(body)
	return body


## Puts an interactable `distance` metres straight ahead at eye height with
## a 0.4 m collider, and returns where it shows on screen.
func _place_ahead(n: Interactable, distance: float) -> Vector2:
	n.position = Vector3(0, FirstPersonPlayer.EYE_HEIGHT, -distance)
	_box(n, "Body", Vector3.ZERO, Vector3(0.4, 0.4, 0.4))
	return player.camera.unproject_position(n.global_position)


func _frames(n: int) -> void:
	for i in n:
		await get_tree().physics_frame


func test_pointer_mode_frees_the_mouse_and_shows_the_toolbar() -> void:
	assert_object(player.pointer).is_not_null()
	assert_bool(hud._toolbar.visible).is_true()
	assert_bool(hud._cross.visible).is_false()
	Settings.controls = "classic"
	hud.apply_controls()
	assert_object(player.pointer).is_null()
	assert_bool(hud._toolbar.visible).is_false()


func test_auto_controls_follow_the_device() -> void:
	Settings.controls = "auto"
	Device.force_touch(true)
	assert_bool(Settings.pointer_controls()).is_true()
	assert_float(Device.ui_factor(Vector2(863, 360))).is_greater(1.5)  # phone, landscape
	assert_float(Device.ui_factor(Vector2(1180, 820))).is_equal_approx(1.0, 0.05)  # tablet
	Device.force_touch(false)
	assert_bool(Settings.pointer_controls()).is_false()
	assert_float(Device.ui_factor(Vector2(863, 360))).is_equal(1.0)


func test_tap_uses_a_thing_within_reach() -> void:
	var lever := room.get_node("Lever") as Interactable
	var at := _place_ahead(lever, 2.0)
	await _frames(2)
	player.pointer.tap(at)
	await get_tree().create_timer(PointerControls.TURN_TIME + 0.2).timeout
	assert_array(results).contains(["Lever toggle true"])


func test_cancel_drops_a_use_still_to_come() -> void:
	var lever := room.get_node("Lever") as Interactable
	var at := _place_ahead(lever, 2.0)
	await _frames(2)
	player.pointer.tap(at)
	player.pointer.cancel()  # e.g. the Menu opened during the turn
	await get_tree().create_timer(PointerControls.TURN_TIME + 0.2).timeout
	assert_array(results).is_empty()


func test_a_new_tap_replaces_a_walk_under_way() -> void:
	var lever := room.get_node("Lever") as Interactable
	_place_ahead(lever, 7.0)
	var key := room.get_node("Key") as Interactable
	key.position = Vector3(0.8, FirstPersonPlayer.EYE_HEIGHT, -1.5)
	_box(key, "Body", Vector3.ZERO, Vector3(0.3, 0.3, 0.3))
	await _frames(2)
	player.pointer.tap(player.camera.unproject_position(lever.global_position))
	assert_bool(player.pointer.is_walking()).is_true()
	player.pointer.tap(player.camera.unproject_position(key.global_position))
	assert_bool(player.pointer.is_walking()).is_false()
	await _frames(150)
	assert_array(results).contains_exactly(["Key pick_up true"])  # never the lever


func test_tap_on_a_far_thing_walks_up_to_it_first() -> void:
	var lever := room.get_node("Lever") as Interactable
	var at := _place_ahead(lever, 7.0)
	await _frames(2)
	player.pointer.tap(at)
	assert_bool(player.pointer.is_walking()).is_true()
	await _frames(150)
	assert_float(player.global_position.z).is_less(-3.0)
	await get_tree().create_timer(PointerControls.TURN_TIME + 0.2).timeout
	assert_array(results).contains(["Lever toggle true"])


func test_tap_on_the_floor_walks_there() -> void:
	await _frames(2)
	var at := player.camera.unproject_position(Vector3(0, 0, -4))
	player.pointer.tap(at)
	await _frames(120)
	assert_float(player.global_position.distance_to(Vector3(0, 0, -4))).is_less(0.6)
	assert_array(results).is_empty()


func test_dropping_an_item_on_a_thing_uses_it_there() -> void:
	Game.request(room.get_node("Key") as EBNode, "pick_up")
	var key_path := (room.get_node("Key") as Item).eb_path
	var box := room.get_node("Box") as KeyLock
	var at := _place_ahead(box, 1.5)
	await _frames(2)
	assert_object(player.pointer.thing_at(at)).is_same(box)
	player.pointer.drop(key_path, at)
	assert_str(Game.selected_item).is_equal(key_path)
	await get_tree().create_timer(PointerControls.TURN_TIME + 0.2).timeout
	assert_bool(box.is_unlocked()).is_true()


func test_inventory_shows_thumbnails_and_drags_items_out() -> void:
	Game.request(room.get_node("Key") as EBNode, "pick_up")
	var key_path := (room.get_node("Key") as Item).eb_path
	await get_tree().process_frame
	var slot := hud._inventory.get_node("Slot1") as Button
	assert_object(slot.icon).is_not_null()
	var seen: Array = []
	hud._inventory.item_dragged.connect(func(p: String, pos: Vector2, released: bool) -> void: seen.append([p, released]))
	var start := slot.get_global_rect().get_center()
	var press := InputEventMouseButton.new()
	press.button_index = MOUSE_BUTTON_LEFT
	press.pressed = true
	press.global_position = start
	hud._inventory._on_slot_input(press, key_path)
	var move := InputEventMouseMotion.new()
	move.global_position = start + Vector2(0, -300)
	hud._inventory._on_slot_input(move, key_path)
	assert_bool(hud._inventory.is_dragging()).is_true()
	var release := InputEventMouseButton.new()
	release.button_index = MOUSE_BUTTON_LEFT
	release.global_position = move.global_position
	hud._inventory._on_slot_input(release, key_path)
	assert_array(seen).contains_exactly([[key_path, false], [key_path, true]])
	assert_str(Game.selected_item).is_equal(key_path)  # let go over nothing: held up
	assert_array(results).contains_exactly(["Key pick_up true"])  # nothing used
	# A plain click (no movement) toggles the selection.
	await get_tree().process_frame
	hud._inventory._on_slot_input(press, key_path)
	hud._inventory._on_slot_input(release, key_path)
	assert_str(Game.selected_item).is_equal("")


func test_a_tap_just_beside_a_small_thing_still_takes_it() -> void:
	var key := room.get_node("Key") as Item
	key.position = Vector3(0, FirstPersonPlayer.EYE_HEIGHT - 0.3, -1.5)
	_box(key, "Body", Vector3.ZERO, Vector3(0.02, 0.01, 0.02))  # a small key
	Device.force_touch(true)
	await _frames(2)
	var at := player.camera.unproject_position(key.global_position)
	var beside := at + Vector2(player.pointer.finger_radius() * 0.9, 0)
	assert_object(player.pick(beside).get("interactable")).is_null()  # the ray alone misses
	player.pointer.tap(beside)
	Device.force_touch(false)
	await get_tree().create_timer(PointerControls.TURN_TIME + 0.2).timeout
	assert_array(results).contains(["Key pick_up true"])


func test_pinch_zooms_and_does_not_tap() -> void:
	var lever := room.get_node("Lever") as Interactable
	var at := _place_ahead(lever, 2.0)
	await _frames(2)
	var fov := player.camera.fov
	for ev: InputEvent in [_touch(0, at, true), _touch(1, at + Vector2(100, 0), true),
			_drag(1, at + Vector2(250, 0)), _touch(1, at + Vector2(250, 0), false), _touch(0, at, false)]:
		player.pointer.handle(ev)
		var m := _as_mouse(ev)
		if m:
			player.pointer.handle(m)
	assert_float(player.zoom).is_greater(2.0)
	assert_float(player.camera.fov).is_less(fov / 2.0)
	await get_tree().create_timer(PointerControls.TURN_TIME + 0.2).timeout
	assert_array(results).is_empty()  # lifting the fingers did not tap the lever


func test_things_in_reach_glint_on_touch_screens() -> void:
	Device.force_touch(true)
	var key := room.get_node("Key") as Item
	key.position = Vector3(0, FirstPersonPlayer.EYE_HEIGHT - 0.3, -1.5)
	var mesh := MeshInstance3D.new()
	mesh.mesh = BoxMesh.new()
	key.add_child(mesh)
	await _frames(30)
	assert_object(mesh.material_overlay).is_not_null()
	Settings.glint_items = false
	await _frames(30)
	assert_object(mesh.material_overlay).is_null()
	Settings.glint_items = true
	Device.force_touch(false)


func test_pause_menu_checkboxes_are_finger_sized() -> void:
	var pm := PauseMenu.new()
	hud._open(pm)
	pm.setup()
	await _frames(2)
	for name: String in ["DragGrabs", "InvertY"]:
		var c := pm.find_child(name, true, false) as CheckBox
		assert_object(c).is_not_null()
		assert_float(c.size.y).is_greater_equal(52.0)
		assert_float(c.size.x).is_greater_equal(160.0)
	pm.close()


func _touch(i: int, at: Vector2, down: bool) -> InputEventScreenTouch:
	var e := InputEventScreenTouch.new()
	e.index = i
	e.position = at
	e.pressed = down
	return e


func _drag(i: int, at: Vector2) -> InputEventScreenDrag:
	var e := InputEventScreenDrag.new()
	e.index = i
	e.position = at
	return e


## What Godot's touch-to-mouse emulation makes of finger 0.
func _as_mouse(ev: InputEvent) -> InputEvent:
	if ev is InputEventScreenTouch and (ev as InputEventScreenTouch).index == 0:
		var b := InputEventMouseButton.new()
		b.button_index = MOUSE_BUTTON_LEFT
		b.pressed = (ev as InputEventScreenTouch).pressed
		b.position = (ev as InputEventScreenTouch).position
		b.device = InputEvent.DEVICE_ID_EMULATION
		return b
	return null


func test_walk_mesh_routes_around_a_wall() -> void:
	_box(room, "Wall", Vector3(0, 1, -3), Vector3(4, 2, 0.3))
	await _frames(2)
	player.pointer.walk.bake()
	await _frames(20)  # the navigation map takes the new region over a few iterations
	assert_int(player.pointer.walk.baked_polygons).is_greater(0)
	var path := player.pointer.walk.route(Vector3.ZERO, Vector3(0, 0, -6))
	var widest := 0.0
	for p in path:
		widest = maxf(widest, absf(p.x))
	assert_float(widest).is_greater(1.9)  # went round the 4 m wall's end


func test_panels_fit_a_small_screen() -> void:
	var vp := SubViewport.new()
	vp.size = Vector2i(900, 400)
	add_child(vp)
	var p := ModalPanel.new()
	p.add_title("Tall")
	var tall := Control.new()
	tall.custom_minimum_size = Vector2(1200, 1500)
	p.body().add_child(tall)
	vp.add_child(p)
	for i in 4:
		await get_tree().process_frame
	var r := Rect2(p.position, p.size * p.scale)
	assert_bool(Rect2(Vector2.ZERO, Vector2(900, 400)).grow(1).encloses(r)) \
		.override_failure_message("panel %s outside the screen" % r).is_true()
	vp.queue_free()
