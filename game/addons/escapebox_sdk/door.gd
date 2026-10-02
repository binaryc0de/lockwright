@icon("res://addons/escapebox_sdk/icons/eb_node.svg")
class_name Door
extends Openable
## Walk-through door, cage gate, or exit. The session ends when room.yaml's
## exit puzzle is solved; `is_exit` only changes the prompt wording.

@export var is_exit: bool = false


func prompt(item_name: String = "") -> String:
	if is_exit and is_locked() and item_name.is_empty():
		return "%s (sealed)" % display_name
	return super(item_name)


func _default_sound(opening: bool) -> String:
	return "door_open" if opening else "door_close"
