extends GdUnitTestSuite
## The authority model end to end on an in-code room: every change is an
## intent, validated and applied by RoomAuthority.

const TestRoom := preload("res://tests/helpers/test_room.gd")

var room: RoomRoot
var auth: RoomAuthority
var now: float = 1000.0
var events: Array = []


func before_test() -> void:
	now = 1000.0
	events = []
	room = auto_free(TestRoom.build())
	add_child(room)
	auth = auto_free(RoomAuthority.new())
	auth.clock = func() -> float: return now
	auth.allow_unpositioned = true
	auth.event_logged.connect(func(k: String, d: Dictionary) -> void: events.append([k, d]))
	auth.setup(TestRoom.manifest(), room, "session-1")
	auth.start_clock("p1")


func act(path: String, verb: String, payload: Dictionary = {}, player: String = "p1") -> Dictionary:
	return auth.handle_intent(player, path, verb, payload)


func code() -> String:
	return auth.state.vars["cabinet_code"]


func test_initial_state_and_variables() -> void:
	assert_str(code()).has_length(4)
	assert_bool(code().is_valid_int()).is_true()
	# Same session id -> same variables (restart safety); different id -> independent draw.
	assert_dict(RoomAuthority.generate_vars({"c": {"type": "digits", "length": 4}}, "session-1")).is_equal({"c": code()})
	assert_str(auth.state.node_state("Cabinet").get("state")).is_equal("closed")
	assert_dict(auth.state.node_state("ExitKeypad")).contains_key_value("powered", false)
	assert_float(auth.state.remaining_s(now)).is_equal(3600.0)
	assert_bool(auth.state.challenges.has("intranet")).is_true()


func test_contents_hidden_until_container_opens() -> void:
	var torch := room.get_node("Desk/Contents/Torch") as Item
	assert_bool(torch.is_available()).is_false()
	assert_dict(act("Desk/Contents/Torch", "pick_up")).contains_key_value("error", "unavailable")
	assert_dict(act("Desk", "open")).contains_key_value("ok", true)
	assert_bool(torch.is_available()).is_true()


func test_pickup_first_intent_wins_and_solves_puzzle() -> void:
	act("Desk", "open")
	assert_dict(act("Desk/Contents/Torch", "pick_up", {}, "p1")).contains_key_value("ok", true)
	var second := act("Desk/Contents/Torch", "pick_up", {}, "p2")
	assert_bool(second["ok"]).is_false()  # gone from the world for everyone
	assert_array(auth.state.inventory).contains_exactly(["Desk/Contents/Torch"])
	assert_bool(auth.state.is_solved("find_uv")).is_true()
	assert_bool((room.get_node("Desk/Contents/Torch") as Node3D).visible).is_false()


func test_keypad_checks_code_on_server() -> void:
	act("Desk", "open")
	act("Desk/Contents/Torch", "pick_up")
	assert_dict(act("Cabinet", "open")).contains_key_value("error", "locked")
	var wrong := "0000" if code() != "0000" else "1111"
	assert_dict(act("Cabinet/Keypad", "submit_code", {"value": wrong})).contains_key_value("error", "wrong_code")
	assert_dict(auth.state.node_state("Cabinet/Keypad")).contains_key_value("attempts", 1)
	assert_dict(act("Cabinet/Keypad", "submit_code", {"value": " %s " % code()})).contains_key_value("ok", true)
	assert_dict(act("Cabinet", "open")).contains_key_value("ok", true)
	assert_bool(auth.state.is_solved("open_cabinet")).is_true()


func test_reading_pins_documents_once() -> void:
	act("Note", "read", {}, "p1")
	act("Note", "read", {}, "p2")
	assert_int(auth.state.evidence.size()).is_equal(1)
	assert_dict(auth.state.evidence[0]).contains_key_value("title", "Sticky note")
	assert_dict(auth.add_note("p1", "Sam", "  site 417?  ")).contains_key_value("ok", true)
	assert_dict(auth.state.evidence[1]).contains_key_value("text", "site 417?")
	assert_dict(auth.remove_note("p1", 1)).contains_key_value("ok", true)
	assert_int(auth.state.evidence.size()).is_equal(1)


func test_flag_opens_cage_through_flag_gate_without_logging_value() -> void:
	assert_dict(act("CageDoor", "open")).contains_key_value("error", "locked")
	assert_dict(act("Laptop", "submit_flag", {"value": ""})).contains_key_value("error", "wrong_flag")
	assert_dict(act("Laptop", "submit_flag", {"value": "s3cr3t-value"})).contains_key_value("ok", true)
	assert_bool(auth.state.is_solved("hack")).is_true()
	assert_str(auth.state.node_state("CageLock").get("state")).is_equal("unlocked")
	assert_str(auth.state.node_state("Laptop").get("state")).is_equal("solved")
	assert_dict(act("CageDoor", "open")).contains_key_value("ok", true)
	assert_str(JSON.stringify(events) + JSON.stringify(auth.snapshot())).not_contains("s3cr3t-value")


func test_full_solution_finishes_session() -> void:
	var finished: Array = []
	auth.session_finished.connect(func(w: bool) -> void: finished.append(w))
	act("Desk", "open")
	act("Desk/Contents/Torch", "pick_up")
	act("Cabinet/Keypad", "submit_code", {"value": code()})
	act("Laptop", "submit_flag", {"value": "dev"})
	assert_dict(act("ExitKeypad", "submit_code", {"value": "417062"})).contains_key_value("error", "not_yet")
	assert_dict(act("Panel", "patch", {"value": "A:1,B:2"})).contains_key_value("error", "no_effect")
	assert_dict(act("Panel", "patch", {"value": "A:9,B:1"})).contains_key_value("error", "bad_mapping")
	assert_dict(act("Panel", "patch", {"value": "a:2, B:1"})).contains_key_value("ok", true)
	assert_bool(auth.state.is_solved("power")).is_true()
	assert_dict(act("ExitKeypad", "submit_code", {"value": "417062"})).contains_key_value("ok", true)
	assert_bool(auth.state.won).is_true()
	assert_array(finished).contains_exactly([true])


func test_key_lock_consumes_key_and_rejects_items_not_held() -> void:
	assert_dict(act("Box", "use_item", {"item": "Key"})).contains_key_value("error", "item_not_held")
	act("Key", "pick_up")
	assert_dict(act("Box", "use_item", {"item": "Key"})).contains_key_value("ok", true)
	assert_array(auth.state.inventory).is_empty()
	assert_str(auth.state.node_state("Key").get("state")).is_equal("consumed")


func test_out_of_reach_intents_are_rejected() -> void:
	auth.update_player_position("p1", Vector3(50, 0, 0))
	assert_dict(act("Desk", "open")).contains_key_value("error", "out_of_reach")
	auth.update_player_position("p1", Vector3(1, 0, 0))
	assert_dict(act("Desk", "open")).contains_key_value("ok", true)


func test_auto_nudge_and_timeout_follow_the_clock() -> void:
	var revealed: Array = []
	auth.hint_revealed.connect(func(p: String, t: int, _x: String, a: bool) -> void: revealed.append([p, t, a]))
	now += 5 * 60
	auth.tick()
	assert_array(revealed).is_empty()
	now += 60
	auth.tick()
	assert_array(revealed).contains_exactly([["find_uv", 1, true]])
	auth.set_auto_nudge("p1", false)
	now += 6 * 60
	auth.tick()
	assert_int(revealed.size()).is_equal(1)
	now = 1000.0 + 3600.0
	auth.tick()
	assert_bool(auth.state.timed_out).is_true()


func test_restart_from_snapshot_restores_world() -> void:
	act("Desk", "open")
	act("Desk/Contents/Torch", "pick_up")
	act("Cabinet/Keypad", "submit_code", {"value": code()})
	auth.request_hint("p1", "hack")
	var snap: Dictionary = JSON.parse_string(JSON.stringify(auth.snapshot()))

	var room2: RoomRoot = auto_free(TestRoom.build())
	add_child(room2)
	var auth2: RoomAuthority = auto_free(RoomAuthority.new())
	auth2.clock = func() -> float: return now + 100.0
	auth2.setup(TestRoom.manifest(), room2, "session-1", snap)
	assert_array(auth2.state.inventory).contains_exactly(["Desk/Contents/Torch"])
	assert_bool(auth2.state.is_solved("open_cabinet")).is_true()
	assert_int(auth2.state.puzzle("hack")["hints_revealed"]).is_equal(1)
	# The restored scene matches the state: torch gone, cabinet keypad unlocked.
	assert_bool((room2.get_node("Desk/Contents/Torch") as Node3D).visible).is_false()
	assert_bool((room2.get_node("Cabinet/Keypad") as Lock).is_unlocked()).is_true()
	assert_float(auth2.state.started_at).is_equal(1000.0)


# --- Regression tests for the Codex adversarial review of M1 ---------------

func test_prerequisites_gate_mechanisms_before_any_mutation() -> void:
	# Panel belongs to "power", which requires hack + open_cabinet.
	assert_dict(act("Panel", "patch", {"value": "A:2,B:1"})).contains_key_value("error", "not_yet")
	assert_str(auth.state.node_state("Panel").get("state")).is_equal("idle")
	assert_dict(auth.state.node_state("ExitKeypad")).contains_key_value("powered", false)
	assert_dict(act("ExitKeypad", "submit_code", {"value": "417062"})).contains_key_value("error", "not_yet")
	# The cabinet keypad belongs to open_cabinet, which requires find_uv.
	assert_dict(act("Cabinet/Keypad", "submit_code", {"value": code()})).contains_key_value("error", "not_yet")
	assert_str(auth.state.node_state("Cabinet/Keypad").get("state")).is_equal("locked")


func test_client_side_state_writes_never_reach_the_authority() -> void:
	var cage_lock := room.get_node("CageLock") as Lock
	cage_lock.current_state["state"] = "unlocked"
	assert_dict(act("CageDoor", "open")).contains_key_value("error", "locked")
	assert_str(auth.state.node_state("CageLock").get("state")).is_equal("locked")
	var captured: Array = []
	auth.node_state_changed.connect(func(_p: String, s: Dictionary) -> void: captured.append(s))
	act("Desk", "open")
	(captured[0] as Dictionary)["state"] = "closed"
	assert_str(auth.state.node_state("Desk").get("state")).is_equal("open")


func test_scene_visibility_is_not_permission() -> void:
	(room.get_node("Desk/Contents") as Node3D).visible = true
	assert_dict(act("Desk/Contents/Torch", "pick_up")).contains_key_value("error", "unavailable")
	assert_array(auth.state.inventory).is_empty()
	# The keypad on the closed cabinet is not inside its contents: still usable.
	act("Desk", "open")
	act("Desk/Contents/Torch", "pick_up")
	assert_dict(act("Cabinet/Keypad", "submit_code", {"value": code()})).contains_key_value("ok", true)


func test_players_without_a_position_are_refused_on_a_real_server() -> void:
	auth.allow_unpositioned = false
	assert_dict(act("Note", "read", {}, "ghost")).contains_key_value("error", "out_of_reach")
	auth.update_player_position("ghost", Vector3.ZERO)
	assert_dict(act("Note", "read", {}, "ghost")).contains_key_value("ok", true)


func test_clock_waits_for_the_briefing() -> void:
	var room3: RoomRoot = auto_free(TestRoom.build())
	add_child(room3)
	var a: RoomAuthority = auto_free(RoomAuthority.new())
	a.clock = func() -> float: return now
	a.setup(TestRoom.manifest(), room3, "fresh")
	now += 7200
	a.tick()
	assert_bool(a.state.timed_out).is_false()
	assert_float(a.state.remaining_s(now)).is_equal(3600.0)
	assert_int(a.state.hints_used()).is_equal(0)  # no auto-nudge before the start
	a.start_clock("p1")
	a.start_clock("p2")  # idempotent
	assert_float(a.state.started_at).is_equal(now)
	now += 3600
	a.tick()
	assert_bool(a.state.timed_out).is_true()
