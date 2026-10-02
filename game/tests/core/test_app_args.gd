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
