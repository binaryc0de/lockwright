extends GdUnitTestSuite
## SocketLock + Socket and Spinner (ADR-0037), through the authority as
## players would. Room: a two-arbor train taking wheels 20/24/30, right with
## 20 and 30 in either order, unpowered until Power (a Lever) is thrown, and
## only after the "start" puzzle (a KeyLock) is solved.

var room: RoomRoot
var auth: RoomAuthority


static func manifest() -> RoomManifest:
	return RoomManifest.from_dict({
		"id": "socket_test",
		"title": "Socket Test",
		"mode": {"duration_minutes": 60, "players": {"min": 1, "max": 4}, "auto_nudge_minutes": 0},
		"entry_scene": "res://rooms/socket_test/room.tscn",
		"puzzles": [
			{"id": "start", "title": "Start", "requires": [],
				"solved_when": {"node_state": {"path": "Start", "state": "unlocked"}}, "hints": ["a", "b", "c"]},
			{"id": "train", "title": "Train", "requires": ["start"],
				"solved_when": {"node_state": {"path": "Train", "state": "unlocked"}}, "hints": ["a", "b", "c"]},
		],
		"exit": {"puzzle": "train"},
	})


static func build() -> RoomRoot:
	var root := RoomRoot.new()
	root.name = "SocketRoom"
	var start := _add(root, KeyLock.new(), "Start") as KeyLock
	start.key_item_id = "start_key"
	var key := _add(root, Item.new(), "StartKey") as Item
	key.item_id = "start_key"
	var train := _add(root, SocketLock.new(), "Train") as SocketLock
	train.accepts = ["wheel_20", "wheel_24", "wheel_30"]
	train.solutions = "A:wheel_20,B:wheel_30|A:wheel_30,B:wheel_20"
	train.wrong_message = "Wrong pace."
	train.starts_powered = false
	for id in ["A", "B"]:
		var s := _add(train, Socket.new(), "Arbor" + id) as Socket
		s.socket_id = id
		for w in train.accepts:
			_add(s, Node3D.new(), w)
	for t in [20, 24, 30]:
		var w := _add(root, Item.new(), "Wheel%d" % t) as Item
		w.item_id = "wheel_%d" % t
		w.display_name = "%d-tooth wheel" % t
	var other := _add(root, Item.new(), "Spoon") as Item
	other.item_id = "spoon"
	var power := _add(root, Lever.new(), "Power") as Lever
	power.targets = [NodePath("../Train")]
	var spin := _add(root, Spinner.new(), "Spin") as Spinner
	spin.only_when = NodePath("../Train")
	spin.only_when_value = "unlocked"
	spin.degrees_per_s = Vector3(0, 0, 90)
	return root


static func _add(parent: Node, child: Node, n: String) -> Node:
	child.name = n
	parent.add_child(child)
	child.owner = parent.owner if parent.owner else parent
	return child


func before_test() -> void:
	room = auto_free(build())
	add_child(room)
	auth = _authority(room, {})


func _authority(r: RoomRoot, snapshot: Dictionary) -> RoomAuthority:
	var a: RoomAuthority = auto_free(RoomAuthority.new())
	a.clock = func() -> float: return 1000.0
	a.allow_unpositioned = true
	a.setup(manifest(), r, "socket-1", snapshot)
	a.start_clock("p1")
	return a


func act(path: String, verb: String, payload: Dictionary = {}) -> Dictionary:
	return auth.handle_intent("p1", path, verb, payload)


func seat(wheel: String, socket: String) -> Dictionary:
	act(wheel, "pick_up")
	return act("Train/Arbor" + socket, "use_item", {"item": wheel})


func open_start() -> void:
	act("StartKey", "pick_up")
	act("Start", "use_item", {"item": "StartKey"})


func ready_to_solve() -> void:
	open_start()
	act("Power", "toggle")


func test_parse_solutions() -> void:
	var s := SocketLock.parse_solutions("A:w1, B:w2 | A:w2,B:w1|broken|A:")
	assert_int(s.size()).is_equal(2)
	assert_dict(s[0]).is_equal({"A": "w1", "B": "w2"})
	assert_dict(s[1]).is_equal({"A": "w2", "B": "w1"})


func test_only_accepted_held_items_are_seated() -> void:
	open_start()
	act("Spoon", "pick_up")
	assert_dict(act("Train/ArborA", "use_item", {"item": "Spoon"})).contains_key_value("error", "wrong_item")
	assert_dict(act("Train/ArborA", "use_item", {"item": "Wheel20"})).contains_key_value("error", "item_not_held")
	assert_dict(seat("Wheel20", "A")).contains_key_value("ok", true)
	assert_str(auth.state.node_state("Wheel20")["state"]).is_equal("placed")
	assert_bool("Wheel20" in auth.state.inventory).is_false()
	assert_dict(seat("Wheel24", "A")).contains_key_value("error", "occupied")


func test_seated_items_can_be_taken_back() -> void:
	open_start()
	seat("Wheel20", "A")
	var a := room.get_node("Train/ArborA") as Socket
	assert_str(a.current_verb()).is_equal("take")
	assert_str(a.prompt()).contains("20-tooth wheel")
	assert_dict(act("Train/ArborA", "take")).contains_key_value("ok", true)
	assert_bool("Wheel20" in auth.state.inventory).is_true()
	assert_str(auth.state.node_state("Wheel20")["state"]).is_equal("inventory")
	assert_str(a.current_verb()).is_equal("use")
	assert_dict(act("Train/ArborA", "take")).contains_key_value("error", "empty")


func test_socket_shows_the_seated_item() -> void:
	open_start()
	seat("Wheel24", "B")
	var b := room.get_node("Train/ArborB")
	assert_bool((b.get_node("wheel_24") as Node3D).visible).is_true()
	assert_bool((b.get_node("wheel_20") as Node3D).visible).is_false()
	act("Train/ArborB", "take")
	assert_bool((b.get_node("wheel_24") as Node3D).visible).is_false()


func test_wrong_full_train_fails_and_the_right_one_opens_in_either_order() -> void:
	ready_to_solve()
	var train := room.get_node("Train") as SocketLock
	seat("Wheel20", "A")
	var r := seat("Wheel24", "B")
	assert_dict(r).contains_key_value("message", "Wrong pace.")
	assert_int(int(auth.state.node_state("Train")["attempts"])).is_equal(1)
	assert_bool(train.is_unlocked()).is_false()
	act("Train/ArborA", "take")
	act("Train/ArborB", "take")
	seat("Wheel30", "A")
	assert_dict(seat("Wheel20", "B")).contains_key_value("opened", true)
	assert_bool(train.is_unlocked()).is_true()
	assert_bool(auth.state.won).is_true()
	# Frozen once open: the wheels stay in.
	assert_dict(act("Train/ArborA", "take")).contains_key_value("error", "unavailable")


func test_needs_its_prerequisites_and_power() -> void:
	var train := room.get_node("Train") as SocketLock
	# Before "start": the sockets themselves are gated by the puzzle graph.
	act("Wheel20", "pick_up")
	assert_dict(act("Train/ArborA", "use_item", {"item": "Wheel20"})).contains_key_value("error", "not_yet")
	open_start()
	# Unpowered: the right train sits there.
	seat("Wheel20", "A")
	seat("Wheel30", "B")
	assert_bool(train.is_unlocked()).is_false()
	# Power arrives: it re-checks and opens.
	act("Power", "toggle")
	assert_bool(train.is_unlocked()).is_true()


func test_survives_a_json_snapshot() -> void:
	ready_to_solve()
	seat("Wheel30", "B")
	var snap: Dictionary = JSON.parse_string(JSON.stringify(auth.snapshot()))
	var room2: RoomRoot = auto_free(build())
	add_child(room2)
	var auth2 := _authority(room2, snap)
	assert_str((room2.get_node("Train/ArborB") as Socket).seated_id()).is_equal("wheel_30")
	assert_bool((room2.get_node("Train/ArborB/wheel_30") as Node3D).visible).is_true()
	auth2.handle_intent("p1", "Wheel20", "pick_up", {})
	assert_dict(auth2.handle_intent("p1", "Train/ArborA", "use_item", {"item": "Wheel20"})).contains_key_value("opened", true)


func test_solution_steps_map_to_intents() -> void:
	var nodes := {}
	for n: EBNode in auth.nodes():
		nodes[n.eb_path] = n
	var steps := [
		{"act": "pick_up", "item": "start_key"}, {"act": "use_on", "item": "start_key", "target": "Start"},
		{"act": "interact", "node": "Power", "verb": "toggle"},
		{"act": "pick_up", "item": "wheel_20"}, {"act": "use_on", "item": "wheel_20", "target": "Train/ArborA"},
		{"act": "pick_up", "item": "wheel_30"}, {"act": "use_on", "item": "wheel_30", "target": "Train/ArborB"},
	]
	for s: Dictionary in steps:
		var i := SolutionPlayer.intent_for(s, nodes, auth.state.vars)
		assert_bool(i.has("error")).override_failure_message(str(i)).is_false()
		assert_dict(act(i["path"], i["verb"], i["payload"])).contains_key_value("ok", true)
	assert_bool(auth.state.won).is_true()


func test_spinner_turns_only_while_its_condition_holds() -> void:
	var spin := room.get_node("Spin") as Spinner
	assert_bool(spin.running).is_false()
	spin._process(1.0)
	assert_float(spin.rotation_degrees.z).is_equal(0.0)
	ready_to_solve()
	seat("Wheel20", "A")
	seat("Wheel30", "B")
	assert_bool(spin.running).is_true()
	spin._process(0.5)
	assert_float(spin.rotation_degrees.z).is_equal_approx(45.0, 0.01)
