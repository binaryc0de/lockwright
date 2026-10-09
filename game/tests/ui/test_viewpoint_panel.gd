extends GdUnitTestSuite
## Looking through a Viewpoint (physical rethink, 2026-10-08): the camera goes
## to the sight's eye with its narrow view, a round mask lies over the screen,
## the strip's buttons work the controls through the server, and Back puts
## everything back.

var room: RoomRoot
var hud: Hud
var player: FirstPersonPlayer


static func manifest() -> RoomManifest:
	return RoomManifest.from_dict({
		"id": "sight_test",
		"title": "Sight Test",
		"mode": {"duration_minutes": 60, "players": {"min": 1, "max": 4}, "auto_nudge_minutes": 0},
		"entry_scene": "res://rooms/sight_test/room.tscn",
		"puzzles": [{"id": "p", "title": "P", "requires": [],
			"solved_when": {"node_state": {"path": "Plate", "state": "never"}}, "hints": ["a", "b", "c"]}],
		"exit": {"puzzle": "p"},
	})


static func _add(parent: Node, child: Node, n: String) -> Node:
	child.name = n
	parent.add_child(child)
	child.owner = parent.owner if parent.owner else parent
	return child


func before_test() -> void:
	room = auto_free(RoomRoot.new())
	room.name = "SightRoom"
	var plate := _add(room, IndexedMechanism.new(), "Plate") as IndexedMechanism
	plate.detents = ["0", "1", "2"] as Array[String]
	var sight := _add(room, Viewpoint.new(), "Sight") as Viewpoint
	sight.display_name = "Bronze sight"
	sight.controls = [NodePath("../Plate")] as Array[NodePath]
	sight.control_names = ["Slide the plate"] as Array[String]
	sight.fov = 20.0
	var eye := _add(sight, Node3D.new(), "Eye") as Node3D
	eye.position = Vector3(0, 1.5, -2)
	sight.eye = NodePath("Eye")
	var fitted := _add(room, Viewpoint.new(), "Fitted") as Viewpoint
	fitted.key_item_id = "eyepiece"
	add_child(room)
	Game.start_local_session(manifest(), room, "sight-ui-test")
	Game.authority.allow_unpositioned = true
	player = auto_free(FirstPersonPlayer.new())
	add_child(player)
	player.set_physics_process(false)  # no floor here: keep it from falling
	hud = auto_free(Hud.new())
	add_child(hud)
	hud.setup(player)


func after_test() -> void:
	Game.end_session()
	Game.hud = null


func test_looking_moves_the_eye_and_masks_the_view() -> void:
	(room.get_node("Sight") as Viewpoint).client_interact()
	assert_bool(hud._modal is ViewpointPanel).is_true()
	assert_object(hud.get_node_or_null("SightRing")).is_not_null()
	assert_float(player.camera.fov).is_equal(20.0)
	await get_tree().create_timer(FirstPersonPlayer.FOCUS_TIME + 0.1).timeout
	assert_vector(player.camera.global_position).is_equal_approx(Vector3(0, 1.5, -2), Vector3.ONE * 0.01)


func test_buttons_work_the_controls_and_back_restores_the_view() -> void:
	(room.get_node("Sight") as Viewpoint).client_interact()
	var panel := hud._modal as ViewpointPanel
	(panel.find_child("Control0", true, false) as Button).pressed.emit()
	assert_int(int(Game.authority.state.node_state("Plate")["index"])).is_equal(1)
	panel.close()
	await get_tree().process_frame
	assert_bool(hud.is_modal_open()).is_false()
	assert_object(hud.get_node_or_null("SightRing")).is_null()
	assert_float(player.camera.fov).is_equal(Settings.fov)


func test_an_unfitted_sight_does_not_open() -> void:
	(room.get_node("Fitted") as Viewpoint).client_interact()
	assert_bool(hud.is_modal_open()).is_false()


## A fitted sight is a solved lock, but players must still be able to aim at
## it and use it (other solved locks drop out of the crosshair).
func test_a_fitted_sight_can_still_be_aimed_at() -> void:
	var fitted := room.get_node("Fitted") as Viewpoint
	Game.authority.set_node_state("Fitted", {"state": "unlocked"})
	assert_bool(fitted.is_open()).is_true()
	assert_bool(fitted.is_available()).is_true()
