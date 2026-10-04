extends GdUnitTestSuite
## DialLock, SequenceLock/SequencePad, SequencePlayer, AllOfGate and the
## wall-time SessionClock (ADR-0033), through the authority as players would.

const ClockworkRoom := preload("res://tests/helpers/clockwork_room.gd")

var room: RoomRoot
var auth: RoomAuthority


func before_test() -> void:
	room = auto_free(ClockworkRoom.build())
	add_child(room)
	auth = _authority(room, {})


func _authority(r: RoomRoot, snapshot: Dictionary) -> RoomAuthority:
	var a: RoomAuthority = auto_free(RoomAuthority.new())
	a.clock = func() -> float: return 1000.0
	a.allow_unpositioned = true
	a.setup(ClockworkRoom.manifest(), r, "clockwork-1", snapshot)
	a.start_clock("p1")
	return a


func act(path: String, verb: String, payload: Dictionary = {}) -> Dictionary:
	return auth.handle_intent("p1", path, verb, payload)


func melody() -> String:
	return auth.state.vars["melody"]


func fit_gears() -> void:
	for id in ["A", "B"]:
		act("GearItem" + id, "pick_up")
		act("Gear" + id, "use_item", {"item": "GearItem" + id})


func strike(seq: String) -> void:
	for c in seq:
		act("Bars/Bar" + c, "strike")


func test_dial_turns_wrap_and_open_on_the_right_combination() -> void:
	var rings := room.get_node("Rings") as DialLock
	assert_array(DialLock.dials_of(auth.state.node_state("Rings"))).contains_exactly([0, 0, 0])
	assert_dict(act("Rings", "turn", {"wheel": 0, "step": -1})).contains_key_value("ok", true)
	assert_str(rings.code_for(DialLock.dials_of(auth.state.node_state("Rings")))).is_equal("CAA")
	assert_dict(act("Rings", "turn", {"wheel": 3, "step": 1})).contains_key_value("error", "bad_wheel")
	assert_bool(rings.is_unlocked()).is_false()
	# Turning the last ring to B completes CAB: the lock opens by itself.
	assert_dict(act("Rings", "turn", {"wheel": 2, "step": 1})).contains_key_value("opened", true)
	assert_bool(rings.is_unlocked()).is_true()
	assert_bool(auth.state.is_solved("rings")).is_true()
	# Frozen once open.
	assert_dict(act("Rings", "turn", {"wheel": 0, "step": 1})).contains_key_value("already", true)
	assert_str(rings.code_for(DialLock.dials_of(auth.state.node_state("Rings")))).is_equal("CAB")


func test_activation_springs_an_openable_once_its_lock_allows() -> void:
	var box := room.get_node("Box") as ContainerProp
	box._server_activate()  # still locked: stays shut
	assert_bool(box.is_open()).is_false()
	act("Rings", "submit_code", {"value": "CAB"})  # RingSpring fires
	assert_bool(box.is_open()).is_true()


func test_locks_show_and_hide_parts_when_opened() -> void:
	var slot := room.get_node("GearA") as KeyLock
	var fitted := Node3D.new()
	var empty := Node3D.new()
	slot.add_child(fitted)
	slot.add_child(empty)
	slot.show_when_unlocked = [slot.get_path_to(fitted)]
	slot.hide_when_unlocked = [slot.get_path_to(empty)]
	slot._apply_state(auth.state.node_state("GearA"))
	assert_bool(fitted.visible).is_false()
	assert_bool(empty.visible).is_true()
	act("GearItemA", "pick_up")
	act("GearA", "use_item", {"item": "GearItemA"})
	assert_bool(fitted.visible).is_true()
	assert_bool(empty.visible).is_false()


func test_dial_submit_code_sets_every_wheel() -> void:
	assert_dict(act("Rings", "submit_code", {"value": "ABA"})).contains_key_value("error", "wrong_code")
	assert_dict(act("Rings", "submit_code", {"value": "XYZ"})).contains_key_value("error", "wrong_code")
	assert_int(int(auth.state.node_state("Rings")["attempts"])).is_equal(2)
	assert_dict(act("Rings", "submit_code", {"value": " cab "})).contains_key_value("ok", true)


func test_clock_dial_starts_set_turns_its_hands_and_needs_power() -> void:
	var clock := room.get_node("Clock") as DialLock
	var hour := clock.get_node("HourHand") as Node3D
	var minute := clock.get_node("MinuteHand") as Node3D
	assert_str(clock.code_for(DialLock.dials_of(auth.state.node_state("Clock")))).is_equal("11:05")
	assert_float(hour.rotation_degrees.z).is_equal_approx(-330.0, 0.01)
	assert_float(minute.rotation_degrees.z).is_equal_approx(-30.0, 0.01)
	# The puzzle graph holds it back first; the lock's own rule is power.
	assert_dict(act("Clock", "turn", {"wheel": 0, "step": 1})).contains_key_value("error", "not_yet")
	assert_dict(clock._server_intent("p1", "turn", {"wheel": 0, "step": 1})).contains_key_value("error", "no_power")
	clock._server_activate()  # what ClockGate does once the song is played
	assert_dict(clock._server_intent("p1", "submit_code", {"value": "4:40"})).contains_key_value("error", "wrong_code")
	assert_float(hour.rotation_degrees.z).is_equal_approx(-120.0, 0.01)
	assert_float(minute.rotation_degrees.z).is_equal_approx(-240.0, 0.01)
	assert_array(clock.parse_code("13:00")).is_empty()
	assert_array(clock.parse_code("4:40")).contains_exactly([4, 8])


func test_gate_fires_once_when_every_input_is_ready() -> void:
	var bird := room.get_node("Bird") as SequencePlayer
	assert_dict(act("Bird", "wind")).contains_key_value("error", "no_power")
	act("GearItemA", "pick_up")
	act("GearA", "use_item", {"item": "GearItemA"})
	assert_str(auth.state.node_state("Gears")["state"]).is_equal("waiting")
	assert_bool(bird.is_ready()).is_false()
	act("GearItemB", "pick_up")
	assert_dict(act("GearB", "use_item", {"item": "GearItemA"})).contains_key_value("error", "item_not_held")
	act("GearB", "use_item", {"item": "GearItemB"})
	assert_str(auth.state.node_state("Gears")["state"]).is_equal("fired")
	assert_bool(bird.is_ready()).is_true()
	assert_bool(auth.state.is_solved("fit")).is_true()
	assert_dict(act("Bird", "wind")).contains_key_value("ok", true)
	act("Bird", "wind")
	assert_int(int(auth.state.node_state("Bird")["plays"])).is_equal(2)


func test_sequence_needs_its_prerequisites_and_matches_the_tail() -> void:
	var bars := room.get_node("Bars") as SequenceLock
	# Right tune before the bird sings: the bars ring, the lock stays shut.
	strike(melody())
	assert_bool(bars.is_unlocked()).is_false()
	assert_int(int(auth.state.node_state("Bars/Bar1")["strikes"])).is_equal(1)
	assert_dict(act("Bars", "submit_code", {"value": melody()})).contains_key_value("error", "not_yet")
	fit_gears()
	# Wrong notes first, then the tune: the tail matches.
	strike("55" + melody())
	assert_bool(bars.is_unlocked()).is_true()
	assert_bool(auth.state.is_solved("song")).is_true()
	# The gate then powers the clock; the bars still ring afterwards.
	assert_bool((room.get_node("Clock") as DialLock).is_powered()).is_true()
	assert_dict(act("Bars/Bar2", "strike")).contains_key_value("ok", true)


func test_sequence_submit_code_strikes_the_pads() -> void:
	fit_gears()
	assert_dict(act("Bars", "submit_code", {"value": "9"})).contains_key_value("error", "wrong_code")
	assert_dict(act("Bars", "submit_code", {"value": melody()})).contains_key_value("ok", true)
	assert_int(int(auth.state.node_state("Bars/Bar" + melody()[0])["strikes"])).is_greater_equal(1)


func test_whole_chain_wins_and_survives_a_json_snapshot() -> void:
	act("Rings", "submit_code", {"value": "CAB"})
	fit_gears()
	act("Bars", "submit_code", {"value": melody()})
	var snap: Dictionary = JSON.parse_string(JSON.stringify(auth.snapshot()))
	# Restore into a fresh scene: gates stay fired, dials come back as ints.
	var room2: RoomRoot = auto_free(ClockworkRoom.build())
	add_child(room2)
	var auth2 := _authority(room2, snap)
	assert_str(auth2.state.node_state("ClockGate")["state"]).is_equal("fired")
	assert_bool((room2.get_node("Clock") as DialLock).is_powered()).is_true()
	assert_dict(auth2.handle_intent("p1", "Clock", "turn", {"wheel": 1, "step": 1})).contains_key_value("ok", true)
	assert_str((room2.get_node("Clock") as DialLock).code_for(DialLock.dials_of(auth2.state.node_state("Clock")))).is_equal("11:10")
	var r := auth2.handle_intent("p1", "Clock", "submit_code", {"value": auth2.state.vars["true_time"]})
	assert_dict(r).contains_key_value("ok", true)
	assert_bool(auth2.state.won).is_true()


func test_solution_steps_map_to_intents() -> void:
	var nodes := {}
	for n: EBNode in auth.nodes():
		nodes[n.eb_path] = n
	var steps := [
		{"act": "input_code", "lock": "Rings", "value": "CAB"},
		{"act": "pick_up", "item": "gear_a"}, {"act": "use_on", "item": "gear_a", "target": "GearA"},
		{"act": "pick_up", "item": "gear_b"}, {"act": "use_on", "item": "gear_b", "target": "GearB"},
		{"act": "interact", "node": "Bird", "verb": "wind"},
		{"act": "input_code", "lock": "Bars", "value": "{{melody}}"},
		{"act": "input_code", "lock": "Clock", "value": "{{true_time}}"},
	]
	for s: Dictionary in steps:
		var i := SolutionPlayer.intent_for(s, nodes, auth.state.vars)
		assert_bool(i.has("error")).override_failure_message(str(i)).is_false()
		assert_dict(act(i["path"], i["verb"], i["payload"])).contains_key_value("ok", true)
	assert_bool(auth.state.won).is_true()


func test_wall_clock_runs_from_its_start_time() -> void:
	assert_float(SessionClock.wall_minutes("23:00", 0.0)).is_equal(1380.0)
	assert_str(SessionClock.format_wall(SessionClock.wall_minutes("23:00", 59.0 * 60.0))).is_equal("11:59")
	assert_str(SessionClock.format_wall(SessionClock.wall_minutes("23:00", 3600.0))).is_equal("12:00")
	assert_str(SessionClock.format_wall(SessionClock.wall_minutes("bad", 90.0))).is_equal("12:01")
	assert_str(SessionClock.format_wall(SessionClock.wall_minutes("09:30", 0.0))).is_equal("9:30")


func test_tones_are_synthesised_and_cached() -> void:
	var bell := EBSound.tone(440.0)
	assert_object(bell).is_not_null()
	assert_bool(bell.data.size() > 22050).is_true()
	assert_object(EBSound.tone(440.0)).is_same(bell)
	assert_object(EBSound.tone(440.0, "whistle")).is_not_same(bell)


func test_ambient_tick_and_condition() -> void:
	var z: AmbientZone = auto_free(AmbientZone.new())
	z.tick_per_s = 1.0
	z.only_when_key = "powered"
	z.only_when_value = "true"
	assert_bool(z.condition_met({"powered": true})).is_true()
	assert_bool(z.condition_met({"powered": false})).is_false()
	assert_bool(z.condition_met({})).is_false()
	# A click right after each beat, silence in between.
	assert_float(absf(z.tick_sample(0.0005)) + absf(z.tick_sample(1.0004))).is_greater(0.01)
	assert_float(z.tick_sample(0.5)).is_equal(0.0)
	z.hum_level = 0.0
	var loop := z.make_loop()
	assert_int(loop.data.size()).is_equal(int(AmbientZone.RATE * AmbientZone.SECONDS) * 2)


func test_unlock_strike_count() -> void:
	var lock := room.get_node("Clock") as DialLock
	for case in [["1", 1], ["7", 7], ["20", 12], ["0", 1], ["x", 1]]:
		lock.unlock_tone_count = case[0]
		assert_int(lock.unlock_strikes()).override_failure_message(str(case)).is_equal(case[1])

