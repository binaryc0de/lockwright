extends GdUnitTestSuite
## Main-menu join form and the connecting overlay (M2). The network itself is
## covered by tools/m2_smoke.sh.

var _saved_name := ""
var _saved_server := ""
var _saved_ws := false


func before_test() -> void:
	_saved_name = Settings.display_name
	_saved_server = Settings.last_server
	_saved_ws = Settings.last_ws


func after_test() -> void:
	Settings.display_name = _saved_name
	Settings.last_server = _saved_server
	Settings.last_ws = _saved_ws
	Settings.save_settings()
	Game.end_session()


func test_join_form_builds_client_args() -> void:
	var menu := auto_free(MainMenu.new()) as MainMenu
	add_child(menu)
	var got: Array = []
	menu.join_requested.connect(func(a: AppArgs) -> void: got.append(a))
	menu._name.text = "Riley"
	menu._server.text = "10.1.2.3:7790"
	menu._token.text = "letmein"
	menu._ws.button_pressed = true
	menu._join()
	assert_array(got).has_size(1)
	var a: AppArgs = got[0]
	assert_str(a.connect_host).is_equal("10.1.2.3")
	assert_int(a.port).is_equal(7790)
	assert_str(a.display_name).is_equal("Riley")
	assert_str(a.server_token).is_equal("letmein")
	assert_str(a.transport).is_equal("ws")
	assert_str(Settings.last_server).is_equal("10.1.2.3:7790")


func test_join_form_reports_bad_input() -> void:
	var menu := auto_free(MainMenu.new()) as MainMenu
	add_child(menu)
	var got: Array = []
	menu.join_requested.connect(func(a: AppArgs) -> void: got.append(a))
	menu._server.text = ""
	menu._join()
	assert_str(menu._status.text).contains("address")
	menu._server.text = "host:99999"
	menu._join()
	assert_str(menu._status.text).contains("1-65535")
	assert_array(got).is_empty()


func test_connecting_overlay_and_cancel() -> void:
	var session := PlaySession.new()
	add_child(session)
	var left: Array = []
	session.left.connect(func() -> void: left.append(true))
	var args := AppArgs.parse(["--connect", "127.0.0.1:1", "--name", "Riley"])
	assert_bool(session.start_remote(args)).is_true()
	assert_object(session._overlay).is_not_null()
	assert_str(session._overlay_label.text).contains("Connecting")
	assert_object(Game.net.client).is_not_null()
	session.leave()
	assert_array(left).has_size(1)
	assert_object(Game.net.client).is_null()
	assert_bool(multiplayer.multiplayer_peer is ENetMultiplayerPeer).is_false()
