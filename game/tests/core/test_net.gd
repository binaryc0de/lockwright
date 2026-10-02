extends GdUnitTestSuite
## M2 networking pieces that can be tested in one process (ADR-0015). The
## end-to-end path (server process, bots, crash and restore, WebSocket) is
## tools/m2_smoke.sh.

const TestRoom := preload("res://tests/helpers/test_room.gd")


func after_test() -> void:
	Game.end_session()


func test_client_args() -> void:
	var a := AppArgs.parse(["--connect", "10.0.0.5:7790", "--name", "Alex", "--token", "inv", "--transport", "ws"])
	assert_array(a.errors).is_empty()
	assert_bool(a.is_remote_client()).is_true()
	assert_str(a.connect_host).is_equal("10.0.0.5")
	assert_int(a.port).is_equal(7790)
	assert_str(a.display_name).is_equal("Alex")
	assert_str(a.server_token).is_equal("inv")
	assert_str(a.transport).is_equal("ws")
	var b := AppArgs.parse(["--connect", "host", "--bot", "--bot-steps", "3-end", "--bot-wait-win"])
	assert_array(b.errors).is_empty()
	assert_int(b.port).is_equal(7777)
	assert_bool(b.bot).is_true()
	assert_int(b.bot_first_step).is_equal(3)
	assert_int(b.bot_last_step).is_equal(-1)
	assert_bool(b.bot_wait_win).is_true()
	assert_array(AppArgs.parse(["--connect", "h:99999"]).errors).is_not_empty()
	assert_array(AppArgs.parse(["--bot"]).errors).contains(["--bot needs --connect or --join"])
	var j := AppArgs.parse(["--join", "192.168.1.20", "--code", " ab3k9z ", "--name", "Sam"])
	assert_array(j.errors).is_empty()
	assert_bool(j.is_remote_client()).is_true()
	assert_bool(j.via_platform()).is_true()
	assert_str(j.join_url).is_equal("http://192.168.1.20:8080")
	assert_str(j.join_code).is_equal("AB3K9Z")
	assert_array(AppArgs.parse(["--join", "h"]).errors).contains(["--join needs --code"])
	assert_str(AppArgs.platform_http_url("http://h:9000/")).is_equal("http://h:9000")
	assert_str(AppArgs.platform_http_url("h:9000")).is_equal("http://h:9000")
	var p := AppArgs.parse(["--server", "--session", "s", "--room", "r", "--platform", "http://127.0.0.1:8080", "--token", "t"])
	assert_bool(p.platform_set).is_true()
	assert_bool(AppArgs.parse(["--server", "--session", "s", "--room", "r"]).platform_set).is_false()
	assert_array(AppArgs.parse(["--connect", "h", "--bot-steps", "x"]).errors).is_not_empty()
	var s := AppArgs.parse(["--server", "--session", "s1", "--room", "r", "--snapshot", "/tmp/x.json"])
	assert_array(s.errors).is_empty()
	assert_str(s.snapshot_path).is_equal("/tmp/x.json")


func test_snapshot_store_round_trip_and_bad_file() -> void:
	var dir := ProjectSettings.globalize_path("user://test_snapshots")
	var store := SnapshotStore.new(dir + "/s1.json")
	var st := WorldState.new()
	st.inventory.assign(["A/Item"])
	st.vars = {"code": "1234"}
	st.started_at = 1000.0
	assert_bool(store.save(st.to_dict())).is_true()
	assert_bool(FileAccess.file_exists(store.path + ".tmp")).is_false()
	var back := WorldState.from_dict(store.load_snapshot())
	assert_array(back.inventory).contains_exactly(["A/Item"])
	assert_str(back.vars["code"]).is_equal("1234")
	assert_float(back.started_at).is_equal(1000.0)
	var f := FileAccess.open(store.path, FileAccess.WRITE)
	f.store_string("{not json")
	f.close()
	assert_dict(store.load_snapshot()).is_empty()
	assert_dict(SnapshotStore.new(dir + "/missing.json").load_snapshot()).is_empty()
	DirAccess.remove_absolute(store.path)


func test_join_verifier() -> void:
	assert_bool(JoinVerifier.new("").verify("anything")["ok"]).is_true()
	assert_bool(JoinVerifier.new("inv").verify("inv")["ok"]).is_true()
	assert_dict(JoinVerifier.new("inv").verify("other")).contains_key_value("reason", "bad_token")


func test_player_ids_are_unique_and_stable() -> void:
	var srv := auto_free(SessionServer.new()) as SessionServer
	assert_str(srv._unique_player_id("  Alex Smith ")).is_equal("alex_smith")
	assert_str(srv._unique_player_id("")).is_equal("player")
	srv.players = {10: {"id": "alex", "name": "Alex"}}
	assert_str(srv._unique_player_id("Alex")).is_equal("alex_2")
	srv.players = {}
	assert_str(srv._unique_player_id("Alex")).is_equal("alex")


func test_solution_player_maps_every_night_shift_step() -> void:
	var loader := RoomLoader.new()
	assert_bool(loader.load_room("night_shift", "")).is_true()
	var room := auto_free(loader.instantiate()) as RoomRoot
	add_child(room)
	var nodes := EBNode.register_all(room, null)
	var vars := {"cabinet_code": "1234"}
	var acting := 0
	for step: Dictionary in loader.manifest.solution:
		var intent := SolutionPlayer.intent_for(step, nodes, vars)
		assert_bool(intent.has("error")).override_failure_message("%s -> %s" % [step, intent]).is_false()
		if not intent.is_empty():
			acting += 1
			assert_bool(nodes.has(intent["path"])).is_true()
	assert_int(acting).is_greater(10)
	assert_dict(SolutionPlayer.intent_for({"act": "pick_up", "item": "nope"}, nodes, vars)).contains_keys(["error"])
	var code := SolutionPlayer.intent_for({"act": "input_code", "lock": "Office/FilingCabinet/Keypad", "value": "{{cabinet_code}}"}, nodes, vars)
	assert_str(code["payload"]["value"]).is_equal("1234")


## A server-side authority on one copy of the room feeds snapshots to Game in
## CLIENT mode on another copy; only what changed is re-applied and announced.
func test_client_mirror_applies_and_announces_only_changes() -> void:
	var manifest := TestRoom.manifest()
	var server_room := auto_free(TestRoom.build()) as RoomRoot
	add_child(server_room)
	var auth := auto_free(RoomAuthority.new()) as RoomAuthority
	add_child(auth)
	auth.allow_unpositioned = true
	auth.setup(manifest, server_room, "mirror-test")
	var client_room := auto_free(TestRoom.build()) as RoomRoot
	add_child(client_room)
	var now := Time.get_unix_time_from_system()
	Game.start_client_session(manifest, client_room, "p1", auth.snapshot(), now + 100.0)
	assert_bool(Game.is_client()).is_true()
	assert_object(Game.authority).is_null()
	assert_float(Game.server_now() - Time.get_unix_time_from_system()).is_equal_approx(100.0, 1.0)
	assert_str(Game.vars()["cabinet_code"]).is_equal(auth.state.vars["cabinet_code"])

	var changed: Array[String] = []
	var inventories: Array = []
	Game.node_state_changed.connect(func(p: String, _s: Dictionary) -> void: changed.append(p))
	Game.inventory_changed.connect(func(inv: Array[String]) -> void: inventories.append(inv.duplicate()))
	assert_dict(auth.handle_intent("p1", "Desk", "open", {})).contains_key_value("ok", true)
	Game.apply_server_state(auth.snapshot(), now)
	assert_array(changed).contains_exactly(["Desk"])
	assert_str((client_room.get_node("Desk") as EBNode).current_state["state"]).is_equal("open")
	assert_array(inventories).is_empty()

	changed.clear()
	assert_dict(auth.handle_intent("p1", "Desk/Contents/Torch", "pick_up", {})).contains_key_value("ok", true)
	Game.apply_server_state(JSON.parse_string(JSON.stringify(auth.snapshot())), now)
	assert_array(Game.inventory()).contains_exactly(["Desk/Contents/Torch"])
	assert_array(inventories).has_size(1)
	assert_bool(Game.world().is_solved("find_uv")).is_true()

	# Re-sending the same world changes nothing.
	changed.clear()
	Game.apply_server_state(JSON.parse_string(JSON.stringify(auth.snapshot())), now)
	assert_array(changed).is_empty()

	var solved: Array[String] = []
	Game.puzzle_solved.connect(func(id: String) -> void: solved.append(id))
	Game.apply_server_event("puzzle_solved", {"puzzle": "find_uv"})
	assert_array(solved).contains_exactly(["find_uv"])


func test_offline_intents_still_answer_synchronously() -> void:
	var room := auto_free(TestRoom.build()) as RoomRoot
	add_child(room)
	Game.start_local_session(TestRoom.manifest(), room, "sync-test")
	Game.authority.allow_unpositioned = true
	var got: Array = []
	Game.request(room.get_node("Desk") as EBNode, "open", {}, func(r: Dictionary) -> void: got.append(r))
	assert_array(got).has_size(1)
	assert_bool(got[0]["ok"]).is_true()


func test_client_without_connection_fails_fast() -> void:
	var room := auto_free(TestRoom.build()) as RoomRoot
	add_child(room)
	var server_room := auto_free(TestRoom.build()) as RoomRoot
	add_child(server_room)
	var auth := auto_free(RoomAuthority.new()) as RoomAuthority
	add_child(auth)
	auth.setup(TestRoom.manifest(), server_room, "nc")
	Game.start_client_session(TestRoom.manifest(), room, "p1", auth.snapshot(), Time.get_unix_time_from_system())
	var got: Array = []
	Game.request(room.get_node("Desk") as EBNode, "open", {}, func(r: Dictionary) -> void: got.append(r))
	assert_array(got).has_size(1)
	assert_str(got[0]["error"]).is_equal("not_connected")


# --- Codex M2 review regressions ------------------------------------------

func test_server_rejects_teleporting_positions() -> void:
	assert_bool(SessionServer.move_allowed(Vector3.ZERO, Vector3(0.9, 0, 0), 0.0)).is_true()
	assert_bool(SessionServer.move_allowed(Vector3.ZERO, Vector3(5, 0, 0), 0.1)).is_false()
	assert_bool(SessionServer.move_allowed(Vector3.ZERO, Vector3(5, 0, 0), 1.0)).is_true()
	var room := auto_free(TestRoom.build()) as RoomRoot
	add_child(room)
	Game.start_local_session(TestRoom.manifest(), room, "move-test")
	var srv := auto_free(SessionServer.new()) as SessionServer
	srv._auth = Game.authority
	srv.players = {5: {"id": "p", "name": "P"}}
	var start := Vector3(1, 1.6, 1)
	srv._last_move["p"] = {"pos": start, "t": srv._now()}
	Game.authority.update_player_position("p", start)
	srv.on_position(5, Vector3(40, 1.6, 40), 0.0)
	assert_vector(Game.authority.player_positions["p"]).is_equal(start)
	srv.on_position(5, start + Vector3(0.5, 0, 0), 0.0)
	assert_vector(Game.authority.player_positions["p"]).is_equal(start + Vector3(0.5, 0, 0))
	srv.trust_positions = true
	srv.on_position(5, Vector3(40, 1.6, 40), 0.0)
	assert_vector(Game.authority.player_positions["p"]).is_equal(Vector3(40, 1.6, 40))


func test_end_screen_shows_for_a_session_already_over() -> void:
	var room := auto_free(TestRoom.build()) as RoomRoot
	add_child(room)
	Game.start_local_session(TestRoom.manifest(), room, "end-test")
	var player := auto_free(FirstPersonPlayer.new()) as FirstPersonPlayer
	add_child(player)
	var hud := auto_free(Hud.new()) as Hud
	add_child(hud)
	hud.setup(player)
	hud.sync_end_state()
	assert_object(hud._modal).is_null()
	Game.world().started_at = Game.server_now() - 600.0
	Game.world().finished = true
	Game.world().won = true
	Game.world().finished_at = Game.server_now()
	hud.sync_end_state()
	assert_object(hud._modal).is_instanceof(EndScreen)
	var first: Node = hud._modal
	hud.sync_end_state()
	assert_object(hud._modal).is_same(first)
	Game.hud = null


func test_timeout_debrief_uses_server_time() -> void:
	var manifest := TestRoom.manifest()
	var server_room := auto_free(TestRoom.build()) as RoomRoot
	add_child(server_room)
	var auth := auto_free(RoomAuthority.new()) as RoomAuthority
	add_child(auth)
	auth.setup(manifest, server_room, "skew")
	var server_now := Time.get_unix_time_from_system() + 3600.0
	auth.state.started_at = server_now - 1200.0
	auth.state.timed_out = true
	var client_room := auto_free(TestRoom.build()) as RoomRoot
	add_child(client_room)
	Game.start_client_session(manifest, client_room, "p1", auth.snapshot(), server_now)
	var end := auto_free(EndScreen.new()) as EndScreen
	add_child(end)
	end.setup(false)
	var text := ""
	for c in end.find_children("*", "RichTextLabel", true, false):
		text += (c as RichTextLabel).text
	assert_str(text).contains("[b]Time:[/b] 20:00")


func test_room_load_failure_after_join_returns_to_menu() -> void:
	var session := PlaySession.new()
	add_child(session)
	var left: Array = []
	session.left.connect(func() -> void: left.append(true))
	session.start_remote(AppArgs.parse(["--connect", "127.0.0.1:1", "--name", "Riley", "--pack", "/nonexistent/x.pck"]))
	session._on_welcomed({"player_id": "riley", "room_id": "night_shift", "room_version": "0.1.0",
		"snapshot_json": "{}", "server_now": Time.get_unix_time_from_system(), "position": Vector3.ZERO})
	assert_array(left).has_size(1)
	assert_str(session.error).contains("cannot load")
	assert_object(Game.net.client).is_null()
