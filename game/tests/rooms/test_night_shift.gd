extends GdUnitTestSuite
## M1 acceptance for Night Shift: loads the room exactly as the game does
## (RoomLoader; from a .pck when EB_TEST_PACK is set, see tools/packroom
## -verify), replays room.yaml's `solution` through RoomAuthority intents only,
## and checks the scene is wired and built sanely.

const ROOM_ID := "night_shift"
const EXIT_KEYPAD := "Office/ExitDoor/Keypad"
const CAGE_DOOR := "Cage/Door"
const CAGE_LOCK := "Cage/Door/Maglock"
## Walkable floor: office + cage interior, plus the exit corridor stub.
const ROOM_MIN := Vector3(0.0, 0.0, 0.0)
const ROOM_MAX := Vector3(8.5, 2.8, 5.0)
const MAX_INTERACT_HEIGHT := 2.15
const PLAYER_RADIUS := 0.3
const PLAYER_HEIGHT := 1.75

var loader: RoomLoader
var manifest: RoomManifest
var room: RoomRoot
var auth: RoomAuthority
var now: float = 1000.0
var solve_order: Array[String] = []


func before_test() -> void:
	now = 1000.0
	solve_order = []
	loader = RoomLoader.new()
	var ok := loader.load_room(ROOM_ID, OS.get_environment("EB_TEST_PACK"))
	assert_bool(ok).override_failure_message("load_room failed: %s" % loader.error).is_true()
	manifest = loader.manifest
	room = auto_free(loader.instantiate())
	assert_object(room).override_failure_message(loader.error).is_not_null()
	add_child(room)
	auth = auto_free(RoomAuthority.new())
	auth.allow_unpositioned = true  # trusted replay: no player positions
	auth.clock = func() -> float: return now
	auth.puzzle_solved.connect(func(id: String) -> void: solve_order.append(id))
	auth.setup(manifest, room, "replay-1")


func act(path: String, verb: String, payload: Dictionary = {}) -> Dictionary:
	return auth.handle_intent("p1", path, verb, payload)


## Thread A up to an open filing cabinet (find_uv + open_cabinet).
func solve_cabinet_thread() -> void:
	assert_dict(act("Office/Desk/Drawer", "open")).contains_key_value("ok", true)
	assert_dict(act(item_path("uv_torch"), "pick_up")).contains_key_value("ok", true)
	assert_dict(act("Office/FilingCabinet/Keypad", "submit_code", {"value": auth.state.vars["cabinet_code"]})).contains_key_value("ok", true)
	assert_dict(act("Office/FilingCabinet", "open")).contains_key_value("ok", true)


func accept_flag() -> void:
	assert_dict(act(terminal_path("intranet"), "submit_flag", {"value": "replay-dev-flag"})).contains_key_value("ok", true)


func item_path(item_id: String) -> String:
	for n: EBNode in auth.nodes():
		if n is Item and (n as Item).item_id == item_id:
			return n.eb_path
	return ""


func terminal_path(challenge_id: String) -> String:
	for n: EBNode in auth.nodes():
		if n is Terminal and (n as Terminal).challenge_id == challenge_id:
			return n.eb_path
	return ""


## Turns one `solution` step into an intent. Returns {} for steps that are
## observation only (examine/use on non-Documents) and have nothing to assert.
func replay_step(step: Dictionary) -> Dictionary:
	match step.get("act"):
		"interact":
			var payload := {}
			if step.has("value"):
				payload["value"] = step["value"]
			return act(step["node"], step["verb"], payload)
		"pick_up":
			var p := item_path(step["item"])
			assert_str(p).override_failure_message("no Item with item_id %s" % step["item"]).is_not_empty()
			return act(p, "pick_up")
		"input_code":
			return act(step["lock"], "submit_code", {"value": EBTemplate.render(step["value"], auth.state.vars)})
		"submit_flag":
			var t := terminal_path(step["challenge"])
			assert_str(t).override_failure_message("no Terminal for challenge %s" % step["challenge"]).is_not_empty()
			# Offline DevFlagValidator accepts any non-empty value.
			return act(t, "submit_flag", {"value": "replay-dev-flag"})
		"examine", "use":
			var target: String = step.get("node", step.get("target", ""))
			if auth.node(target) is Document:
				return act(target, "read")
			return {}
		"use_on":
			return act(step["target"], "use_item", {"item": item_path(step["item"])})
	fail("unknown solution act %s" % step)
	return {"ok": false}


func replay_all() -> void:
	var steps := manifest.solution
	assert_array(steps).is_not_empty()
	for i in steps.size():
		now += 30.0
		var step: Dictionary = steps[i]
		var r := replay_step(step)
		if r.is_empty():
			continue
		assert_bool(r.get("ok", false)) \
			.override_failure_message("solution[%d] %s failed: %s" % [i, step, r]).is_true()


# --- Manifest -------------------------------------------------------------

func test_room_json_matches_file_and_id() -> void:
	var path := "res://rooms/%s/room.json" % ROOM_ID
	assert_bool(FileAccess.file_exists(path)).is_true()
	var parsed: Variant = JSON.parse_string(FileAccess.get_file_as_string(path))
	assert_bool(parsed is Dictionary).is_true()
	assert_dict(manifest.data).is_equal(parsed)
	assert_str(manifest.id).is_equal(ROOM_ID)
	assert_str((parsed as Dictionary).get("id")).is_equal(ROOM_ID)
	assert_str(manifest.exit_puzzle).is_equal("override_door")


func test_every_puzzle_and_challenge_has_three_hints() -> void:
	assert_array(manifest.puzzles).is_not_empty()
	for p: Dictionary in manifest.puzzles:
		assert_int((p.get("hints", []) as Array).size()) \
			.override_failure_message("puzzle %s has < 3 hints" % p["id"]).is_greater_equal(3)
	for c: Dictionary in manifest.challenges:
		assert_int((c.get("hints", []) as Array).size()) \
			.override_failure_message("challenge %s has < 3 hints" % c["id"]).is_greater_equal(3)


# --- Replay ---------------------------------------------------------------

func test_solution_replay_wins() -> void:
	var finished: Array = []
	auth.session_finished.connect(func(w: bool) -> void: finished.append(w))
	replay_all()
	assert_bool(auth.state.won).is_true()
	assert_array(finished).contains_exactly([true])
	for p: Dictionary in manifest.puzzles:
		assert_bool(auth.state.is_solved(p["id"])) \
			.override_failure_message("puzzle %s not solved" % p["id"]).is_true()
	# Solve order respects every `requires` edge.
	assert_int(solve_order.size()).is_equal(manifest.puzzles.size())
	for p: Dictionary in manifest.puzzles:
		var at := solve_order.find(p["id"])
		for r: String in p.get("requires", []):
			assert_int(solve_order.find(r)) \
				.override_failure_message("%s solved before its prerequisite %s" % [p["id"], r]) \
				.is_less(at)
	# The exit door really opened, and it no longer blocks the doorway.
	assert_str(auth.state.node_state("Office/ExitDoor").get("state")).is_equal("open")


# --- Wiring -----------------------------------------------------------------

func test_exit_keypad_is_unpowered_until_patch_panel_solved() -> void:
	# The authority refuses intents on the exit keypad with "not_yet" while
	# override_door's prerequisite (restore_power) is unsolved; the lock itself
	# would answer "no_power". Either way the panel must stay dead and locked.
	assert_dict(auth.state.node_state(EXIT_KEYPAD)).contains_key_value("powered", false)
	var r := act(EXIT_KEYPAD, "submit_code", {"value": "417062"})
	assert_bool(r.get("ok", false)).is_false()
	assert_array(["no_power", "not_yet"]).contains([r.get("error")])
	assert_dict(act("Office/ExitDoor", "open")).contains_key_value("error", "locked")
	# The patch panel itself waits for the cabinet thread and the flag.
	assert_dict(act("Cage/PatchPanel", "patch", {"value": "A:3,B:7,C:1,D:5"})).contains_key_value("error", "not_yet")
	solve_cabinet_thread()
	accept_flag()
	assert_dict(act("Cage/PatchPanel", "patch", {"value": "A:1,B:2,C:3,D:4"})).contains_key_value("error", "no_effect")
	assert_dict(auth.state.node_state(EXIT_KEYPAD)).contains_key_value("powered", false)
	r = act(EXIT_KEYPAD, "submit_code", {"value": "417062"})
	assert_array(["no_power", "not_yet"]).contains([r.get("error")])
	assert_str(auth.state.node_state(EXIT_KEYPAD).get("state")).is_equal("locked")
	assert_dict(act("Cage/PatchPanel", "patch", {"value": "A:3,B:7,C:1,D:5"})).contains_key_value("ok", true)
	assert_dict(auth.state.node_state(EXIT_KEYPAD)).contains_key_value("powered", true)
	assert_dict(act(EXIT_KEYPAD, "submit_code", {"value": "123456"})).contains_key_value("error", "wrong_code")
	assert_bool(auth.state.won).is_false()


func test_cage_door_locked_until_flag_accepted() -> void:
	assert_dict(act(CAGE_DOOR, "open")).contains_key_value("error", "locked")
	assert_str(auth.state.node_state(CAGE_LOCK).get("state")).is_equal("locked")
	# Opening the cabinet does not touch the cage.
	solve_cabinet_thread()
	assert_dict(act(CAGE_DOOR, "open")).contains_key_value("error", "locked")
	assert_dict(act(terminal_path("intranet"), "submit_flag", {"value": ""})).contains_key_value("error", "wrong_flag")
	assert_dict(act(CAGE_DOOR, "open")).contains_key_value("error", "locked")
	accept_flag()
	assert_str(auth.state.node_state(CAGE_LOCK).get("state")).is_equal("unlocked")
	assert_dict(act(CAGE_DOOR, "open")).contains_key_value("ok", true)


func test_cabinet_contents_hidden_until_unlocked_and_opened() -> void:
	var diagram := "Office/FilingCabinet/Drawer/Contents/NetworkDiagram"
	assert_dict(act(diagram, "read")).contains_key_value("error", "unavailable")
	assert_dict(act("Office/FilingCabinet", "open")).contains_key_value("error", "locked")
	# The torch is inside the closed desk drawer, and the keypad waits for find_uv.
	assert_dict(act(item_path("uv_torch"), "pick_up")).contains_key_value("error", "unavailable")
	assert_dict(act("Office/FilingCabinet/Keypad", "submit_code", {"value": auth.state.vars["cabinet_code"]})).contains_key_value("error", "not_yet")
	assert_dict(act("Office/Desk/Drawer", "open")).contains_key_value("ok", true)
	assert_dict(act(item_path("uv_torch"), "pick_up")).contains_key_value("ok", true)
	assert_bool(auth.state.is_solved("find_uv")).is_true()
	assert_dict(act("Office/FilingCabinet/Keypad", "submit_code", {"value": auth.state.vars["cabinet_code"]})).contains_key_value("ok", true)
	assert_dict(act("Office/FilingCabinet", "open")).contains_key_value("ok", true)
	assert_dict(act(diagram, "read")).contains_key_value("ok", true)


## The hero GLB drawers are visual children that follow the SDK's moving part
## through a RemoteTransform3D (ADR-0012); opening must carry them 0.4 m out.
func test_drawer_models_follow_their_containers() -> void:
	var desk_model := room.get_node("Office/Desk/Model/drawer_top") as Node3D
	var cab_model := room.get_node("Office/FilingCabinet/Model/drawer_top") as Node3D
	await get_tree().process_frame
	var desk_closed := desk_model.global_position
	var cab_closed := cab_model.global_position
	solve_cabinet_thread()
	await get_tree().process_frame
	assert_vector(desk_model.global_position - desk_closed).is_equal_approx(Vector3(0, 0, 0.4), Vector3.ONE * 0.001)
	assert_vector(cab_model.global_position - cab_closed).is_equal_approx(Vector3(0, 0, -0.4), Vector3.ONE * 0.001)


func test_cabinet_keypad_status_light_is_the_model_led() -> void:
	var lock := room.get_node("Office/FilingCabinet/Keypad") as Lock
	assert_object(lock.get_node_or_null(lock.status_light)).is_instanceof(GeometryInstance3D)


# --- Scene sanity -----------------------------------------------------------

## CollisionShape3Ds owned by `n` (not by a nested Interactable).
static func own_shapes(n: Node) -> Array[CollisionShape3D]:
	var out: Array[CollisionShape3D] = []
	for c in n.get_children():
		if c is Interactable:
			continue
		if c is CollisionShape3D:
			out.append(c)
		out.append_array(own_shapes(c))
	return out


static func shape_aabb(cs: CollisionShape3D) -> AABB:
	var box := cs.shape as BoxShape3D
	if box == null:
		return AABB(cs.global_position, Vector3.ZERO)
	return cs.global_transform * AABB(-box.size / 2.0, box.size)


func test_every_interactable_has_a_body_and_a_name() -> void:
	var count := 0
	for n: EBNode in auth.nodes():
		if not n is Interactable:
			continue
		count += 1
		var i := n as Interactable
		assert_int(own_shapes(i).size()) \
			.override_failure_message("%s has no CollisionShape3D" % i.eb_path).is_greater(0)
		assert_str(i.display_name).override_failure_message("%s has no display_name" % i.eb_path).is_not_empty()
		assert_str(i.display_name).override_failure_message("%s keeps the default display_name" % i.eb_path).is_not_equal("Thing")
	assert_int(count).is_greater_equal(15)


func test_every_document_has_a_title_and_text() -> void:
	for n: EBNode in auth.nodes():
		if n is Document:
			var d := n as Document
			assert_str(d.title).override_failure_message("%s has no title" % d.eb_path).is_not_empty()
			assert_str(d.text_md).override_failure_message("%s has no text" % d.eb_path).is_not_empty()


func test_interactables_lie_inside_the_room_and_within_reach() -> void:
	# Open the containers so contents sit at their reachable (open) pose.
	solve_cabinet_thread()
	for n: EBNode in auth.nodes():
		if not n is Interactable:
			continue
		var p := n.global_position
		for cs in own_shapes(n):
			p = shape_aabb(cs).get_center()
			break
		var inside := p.x >= ROOM_MIN.x - 0.1 and p.x <= ROOM_MAX.x + 0.1 \
			and p.z >= ROOM_MIN.z - 0.1 and p.z <= ROOM_MAX.z + 0.1
		assert_bool(inside).override_failure_message("%s at %s is outside the room" % [n.eb_path, p]).is_true()
		assert_float(p.y).override_failure_message("%s at %s is too high" % [n.eb_path, p]) \
			.is_between(0.2, MAX_INTERACT_HEIGHT)


func test_spawn_point_is_on_the_office_floor_and_clear() -> void:
	var t := room.spawn_transform()
	var p := t.origin
	assert_float(p.y).is_equal_approx(0.0, 0.01)
	assert_bool(p.x > 0.5 and p.x < 5.5 and p.z > 0.5 and p.z < 4.5) \
		.override_failure_message("spawn %s not inside the office" % p).is_true()
	# The player's capsule (as a box) must not overlap any collider but the floor.
	var player := AABB(p + Vector3(-PLAYER_RADIUS, 0.05, -PLAYER_RADIUS), Vector3(PLAYER_RADIUS * 2, PLAYER_HEIGHT, PLAYER_RADIUS * 2))
	for cs in own_shapes(room):
		assert_bool(shape_aabb(cs).intersects(player)) \
			.override_failure_message("spawn overlaps %s" % room.get_path_to(cs)).is_false()
	for n: EBNode in auth.nodes():
		for cs in own_shapes(n):
			assert_bool(shape_aabb(cs).intersects(player)) \
				.override_failure_message("spawn overlaps %s" % room.get_path_to(cs)).is_false()


func test_open_doors_clear_their_doorways() -> void:
	# Doorway volumes (walkable gap the leaf fills when closed), slightly inset.
	var doorways := {
		"Office/ExitDoor": AABB(Vector3(-0.1, 0.1, 2.1), Vector3(0.1, 1.9, 0.8)),
		CAGE_DOOR: AABB(Vector3(5.95, 0.1, 3.7), Vector3(0.1, 1.9, 0.8)),
	}
	solve_cabinet_thread()
	accept_flag()
	assert_dict(act("Cage/PatchPanel", "patch", {"value": "A:3,B:7,C:1,D:5"})).contains_key_value("ok", true)
	for path: String in doorways:
		var door := auth.node(path) as Door
		var gap: AABB = doorways[path]
		var blocked := func() -> bool:
			for cs in own_shapes(door):
				if shape_aabb(cs).intersects(gap):
					return true
			return false
		assert_bool(blocked.call()).override_failure_message("%s does not fill its doorway when closed" % path).is_true()
	assert_dict(act(EXIT_KEYPAD, "submit_code", {"value": "417062"})).contains_key_value("ok", true)
	for path: String in doorways:
		assert_dict(act(path, "open")).contains_key_value("ok", true)
		var door := auth.node(path) as Door
		var gap: AABB = doorways[path]
		for cs in own_shapes(door):
			assert_bool(shape_aabb(cs).intersects(gap)) \
				.override_failure_message("%s still blocks its doorway when open" % path).is_false()
