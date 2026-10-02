class_name InputActions
extends RefCounted
## Default key bindings, registered at startup so they live in one readable
## place. Rebinding (settings menu) is M4.

const BINDINGS := {
	"move_forward": [KEY_W, KEY_UP],
	"move_back": [KEY_S, KEY_DOWN],
	"move_left": [KEY_A, KEY_LEFT],
	"move_right": [KEY_D, KEY_RIGHT],
	"interact": [KEY_E],
	"inspect_item": [KEY_F],
	"evidence_board": [KEY_TAB],
	"hints": [KEY_H],
	"deselect_item": [KEY_Q],
	"pause": [KEY_ESCAPE],
}
const MOUSE_BINDINGS := {
	"interact": [MOUSE_BUTTON_LEFT],
	"next_item": [MOUSE_BUTTON_WHEEL_DOWN],
	"prev_item": [MOUSE_BUTTON_WHEEL_UP],
}


static func register() -> void:
	for action: String in BINDINGS:
		_ensure(action)
		for key: Key in BINDINGS[action]:
			var ev := InputEventKey.new()
			ev.physical_keycode = key
			InputMap.action_add_event(action, ev)
	for action: String in MOUSE_BINDINGS:
		_ensure(action)
		for b: MouseButton in MOUSE_BINDINGS[action]:
			var ev := InputEventMouseButton.new()
			ev.button_index = b
			InputMap.action_add_event(action, ev)
	for i in 9:
		var action := "select_item_%d" % (i + 1)
		_ensure(action)
		var ev := InputEventKey.new()
		ev.physical_keycode = KEY_1 + i
		InputMap.action_add_event(action, ev)


static func _ensure(action: String) -> void:
	if not InputMap.has_action(action):
		InputMap.add_action(action)
