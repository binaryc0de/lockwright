extends GdUnitTestSuite
## Headless smoke test of the HUD and every focused panel, driven through
## their UI code against a live in-process session.

const TestRoom := preload("res://tests/helpers/test_room.gd")

var room: RoomRoot
var hud: Hud
var player: FirstPersonPlayer


func before_test() -> void:
	room = auto_free(TestRoom.build())
	add_child(room)
	Game.start_local_session(TestRoom.manifest(), room, "ui-test")
	Game.authority.allow_unpositioned = true
	player = auto_free(FirstPersonPlayer.new())
	add_child(player)
	hud = auto_free(Hud.new())
	add_child(hud)
	hud.setup(player)


func after_test() -> void:
	Game.end_session()
	Game.hud = null


func test_keypad_panel_submits_through_authority() -> void:
	Game.request(room.get_node("Desk") as EBNode, "open")
	Game.request(room.get_node("Desk/Contents/Torch") as EBNode, "pick_up")
	var lock := room.get_node("Cabinet/Keypad") as KeypadLock
	hud.open_keypad(lock)
	assert_bool(hud.is_modal_open()).is_true()
	assert_bool(player.input_enabled).is_false()
	var panel := hud._modal as KeypadPanel
	for d in "9999" if Game.vars()["cabinet_code"] != "9999" else "1111":
		panel._press(d)
	panel._press("ENT")
	assert_bool(lock.is_unlocked()).is_false()
	assert_str(panel._display.text).is_equal("ERROR")
	for d: String in Game.vars()["cabinet_code"]:
		panel._press(d)
	panel._press("ENT")
	assert_bool(lock.is_unlocked()).is_true()
	assert_str(panel._display.text).is_equal("OPEN")


func test_patch_panel_ui_maps_cables() -> void:
	Game.request(room.get_node("Desk") as EBNode, "open")
	Game.request(room.get_node("Desk/Contents/Torch") as EBNode, "pick_up")
	Game.request(room.get_node("Cabinet/Keypad") as EBNode, "submit_code", {"value": Game.vars()["cabinet_code"]})
	Game.request(room.get_node("Laptop") as EBNode, "submit_flag", {"value": "dev"})
	var pp := room.get_node("Panel") as PatchPanel
	hud.open_patch_panel(pp)
	var ui := hud._modal as PatchPanelUI
	(ui._pickers["A"] as OptionButton).select(2)  # Port 2
	(ui._pickers["B"] as OptionButton).select(1)  # Port 1
	ui._connect()
	assert_bool(pp.is_solved()).is_true()
	assert_dict(Game.world().node_state("ExitKeypad")).contains_key_value("powered", true)


func test_terminal_flag_and_simulated_shell() -> void:
	var t := room.get_node("Laptop") as Terminal
	hud.open_terminal(t)
	var ui := hud._modal as TerminalPanel
	# A blank Enter is not a guess: nothing reaches the authority.
	ui._on_submit("   ")
	assert_bool(Game.world().flags_accepted.has("intranet")).is_false()
	assert_str(ui._status.text).is_equal("Type or paste a flag first.")
	ui._on_submit("anything")
	assert_bool(Game.world().flags_accepted.has("intranet")).is_true()
	assert_str(ui._status.text).is_equal("ACCESS GRANTED")
	t.mode = "simulated"
	t.commands = {"whoami": "user {{cabinet_code}}"}
	assert_str(t.run_command("whoami")).is_equal("user " + Game.vars()["cabinet_code"])
	assert_str(t.run_command("rm -rf /")).is_equal("rm: command not found")


func test_document_inspect_pins_evidence_and_board_lists_it() -> void:
	var note := room.get_node("Note") as Document
	note.text_md = "# mreyes\n**bold** and *it*"
	note.back_text_md = "back side"
	note.client_interact()
	assert_object(hud._modal).is_instanceof(InspectPanel)
	assert_str((hud._modal as InspectPanel)._text.text).contains("[b]bold[/b]")
	hud._modal.close()
	assert_int(Game.world().evidence.size()).is_equal(1)
	var board := EvidenceBoard.new()
	hud._open(board)
	board.setup()
	assert_int(board._list.item_count).is_equal(1)
	board._note.text = "site 417"
	board._add()
	assert_int(board._list.item_count).is_equal(2)


func test_hints_end_screen_pause_and_inventory() -> void:
	var hp := HintsPanel.new()
	hud._open(hp)
	hp.setup()
	Game.request_hint("find_uv")
	assert_int(Game.world().hints_used()).is_equal(1)
	var desk := room.get_node("Desk") as ContainerProp
	Game.request(desk, "open")
	Game.request(room.get_node("Desk/Contents/Torch") as Item, "pick_up")
	assert_array(Game.inventory()).has_size(1)
	hud._inventory.cycle(1)
	assert_bool(Game.uv_active()).is_true()
	hud.open_item(room.get_node("Desk/Contents/Torch") as Item)
	hud.show_end(true)
	assert_object(hud._modal).is_instanceof(EndScreen)
	var pm := PauseMenu.new()
	hud._open(pm)
	pm.setup()
	pm.close()
	await get_tree().process_frame
	assert_bool(hud.is_modal_open()).is_false()
	assert_bool(player.input_enabled).is_true()


func test_markdown_subset() -> void:
	assert_str(EBMarkdown.to_bbcode("# T\n- a **b** *c* `d` [x]")).is_equal(
		"[font_size=28][b]T[/b][/font_size]\n  •  a [b]b[/b] [i]c[/i] [code]d[/code] [lb]x]")
	assert_str(EBMarkdown.to_bbcode("2 * 3 = 6")).is_equal("2 * 3 = 6")


func test_briefing_start_button_starts_the_clock() -> void:
	assert_bool(Game.world().clock_started()).is_false()
	hud.open_briefing()
	hud._modal.close()
	assert_bool(Game.world().clock_started()).is_true()


func test_evidence_board_shows_image_backed_documents() -> void:
	var note := room.get_node("Note") as Document
	note.text_md = ""
	var img := Image.create(8, 8, false, Image.FORMAT_RGB8)
	note.texture = ImageTexture.create_from_image(img)
	Game.request(note, "read")
	var board := EvidenceBoard.new()
	hud._open(board)
	board.setup()
	board._show(0)
	assert_str(board._detail.get_parsed_text()).contains(note.title)
	assert_int(board._detail.get_paragraph_count()).is_greater(1)
