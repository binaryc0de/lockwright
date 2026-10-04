extends GdUnitTestSuite
## The focused DialLock view against a live in-process session (ADR-0033).

const ClockworkRoom := preload("res://tests/helpers/clockwork_room.gd")

var room: RoomRoot
var hud: Hud
var player: FirstPersonPlayer


func before_test() -> void:
	room = auto_free(ClockworkRoom.build())
	add_child(room)
	Game.start_local_session(ClockworkRoom.manifest(), room, "dial-ui-test")
	Game.authority.allow_unpositioned = true
	player = auto_free(FirstPersonPlayer.new())
	add_child(player)
	hud = auto_free(Hud.new())
	add_child(hud)
	hud.setup(player)


func after_test() -> void:
	Game.end_session()
	Game.hud = null


func test_turning_wheels_shows_live_state_and_opens() -> void:
	var rings := room.get_node("Rings") as DialLock
	rings.client_interact()
	assert_bool(hud.is_modal_open()).is_true()
	var panel := hud._modal as DialLockPanel
	assert_int(panel._shown.size()).is_equal(3)
	assert_str(panel._shown[0].text).is_equal("A")
	panel.turn(0, -1)
	assert_str(panel._shown[0].text).is_equal("C")
	# A teammate's turn (straight to the authority) shows up in this view.
	Game.authority.handle_intent("p2", "Rings", "turn", {"wheel": 2, "step": 1})
	assert_str(panel._shown[2].text).is_equal("B")
	assert_bool(rings.is_unlocked()).is_true()
	assert_str(panel._status.text).is_equal("It gives.")


func test_unpowered_dial_does_not_open_a_panel() -> void:
	(room.get_node("Clock") as DialLock).client_interact()
	assert_bool(hud.is_modal_open()).is_false()


## The web build's font has no arrow glyphs ("▲" showed as an empty box):
## turn buttons carry a drawn icon and no text.
func test_turn_buttons_use_drawn_arrows_not_glyphs() -> void:
	(room.get_node("Rings") as DialLock).client_interact()
	var panel := hud._modal as DialLockPanel
	var buttons := panel.find_children("*", "Button", true, false)
	var arrows := 0
	for b: Button in buttons:
		if b.icon != null:
			arrows += 1
			assert_str(b.text).is_empty()
		for c in b.text:
			assert_int(c.unicode_at(0)).override_failure_message("non-ASCII button text %s" % b.text).is_less(128)
	assert_int(arrows).is_equal(6)  # three wheels, up and down
	var up := DialLockPanel.arrow_icon(true).get_image()
	assert_float(up.get_pixel(2, 1).a).is_less(0.1)     # tip at the top: corners empty
	assert_float(up.get_pixel(14, 16).a).is_greater(0.9)
	assert_float(up.get_pixel(1, 16).a).is_greater(0.3)


func test_crosshair_hides_while_a_panel_is_open() -> void:
	assert_bool(hud._cross.visible).is_true()
	(room.get_node("Rings") as DialLock).client_interact()
	assert_bool(hud._cross.visible).is_false()
	hud._modal.close()
	assert_bool(hud._cross.visible).is_true()
