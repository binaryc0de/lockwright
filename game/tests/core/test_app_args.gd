extends GdUnitTestSuite


func test_defaults_to_client() -> void:
	var a := AppArgs.parse(PackedStringArray())
	assert_bool(a.is_server()).is_false()
	assert_int(a.port).is_equal(7777)
	assert_str(a.transport).is_equal("enet")
	assert_array(a.errors).is_empty()


func test_parses_server_command_line() -> void:
	var a := AppArgs.parse(PackedStringArray([
		"--headless", "--server", "--session", "s1", "--room", "night_shift",
		"--pack", "/srv/packs/night_shift-0.1.0.pck", "--port=7781",
		"--platform", "http://10.0.0.2:8080", "--token", "tok", "--transport", "ws",
	]))
	assert_bool(a.is_server()).is_true()
	assert_str(a.session_id).is_equal("s1")
	assert_str(a.room_id).is_equal("night_shift")
	assert_str(a.pack_path).is_equal("/srv/packs/night_shift-0.1.0.pck")
	assert_int(a.port).is_equal(7781)
	assert_str(a.platform_url).is_equal("http://10.0.0.2:8080")
	assert_str(a.server_token).is_equal("tok")
	assert_str(a.transport).is_equal("ws")
	assert_array(a.errors).is_empty()


func test_dedicated_server_feature_forces_server_mode() -> void:
	var a := AppArgs.parse(PackedStringArray(["--session", "s", "--room", "r"]), true)
	assert_bool(a.is_server()).is_true()
	assert_array(a.errors).is_empty()


func test_server_mode_requires_session_and_room() -> void:
	var a := AppArgs.parse(PackedStringArray(["--server"]))
	assert_array(a.errors).contains(["server mode requires --session", "server mode requires --room"])


func test_rejects_bad_port_transport_and_missing_value() -> void:
	var a := AppArgs.parse(PackedStringArray(["--port", "99999", "--transport", "udp", "--token"]))
	assert_int(a.errors.size()).is_equal(3)
	assert_int(a.port).is_equal(7777)
	assert_str(a.transport).is_equal("enet")


func test_local_pack_lookup_picks_the_newest_version() -> void:
	var dir := create_temp_dir("packs")
	for f in ["night_shift-0.1.0.pck", "night_shift-0.10.0.pck", "night_shift-0.9.3.pck", "other-9.9.9.pck", "night_shift-x.pck", "notes.txt"]:
		FileAccess.open(dir.path_join(f), FileAccess.WRITE).store_string("x")
	assert_str(RoomLoader.find_local_pack("night_shift", [dir])).is_equal(dir.path_join("night_shift-0.10.0.pck"))
	assert_str(RoomLoader.find_local_pack("missing", [dir])).is_empty()
	assert_str(RoomLoader.find_local_pack("night_shift", [dir.path_join("nope")])).is_empty()


func test_web_page_url_becomes_join_args() -> void:
	var a := AppArgs.parse(AppArgs.web_query_args("https://play.example.org", "?code=ab3k9z&name=Riley+K&bot=1"))
	assert_bool(a.via_platform()).is_true()
	assert_str(a.join_url).is_equal("https://play.example.org")
	assert_str(a.join_code).is_equal("AB3K9Z")
	assert_str(a.display_name).is_equal("Riley K")
	assert_bool(a.bot).is_true()
	var offline := AppArgs.parse(AppArgs.web_query_args("http://h:8090", "?room=night_shift&difficulty=hard"))
	assert_str(offline.room_id).is_equal("night_shift")
	assert_str(offline.difficulty).is_equal("hard")
	assert_array(Array(AppArgs.web_query_args("http://h", ""))).is_empty()


func test_platform_urls_keep_explicit_ports() -> void:
	assert_str(AppArgs.platform_http_url("192.168.1.20")).is_equal("http://192.168.1.20:8080")
	assert_str(AppArgs.platform_http_url("192.168.1.20:8090")).is_equal("http://192.168.1.20:8090")
	assert_str(AppArgs.platform_http_url("https://play.example.org/")).is_equal("https://play.example.org")
	assert_str(AppArgs.platform_http_url("http://h:9000")).is_equal("http://h:9000")
