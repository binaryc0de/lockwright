@icon("res://addons/escapebox_sdk/icons/eb_node.svg")
class_name SessionClock
extends EBNode
## Countdown display bound to the server-owned timer (PLAN.md 6.7). Writes
## MM:SS (or H:MM:SS) into a Label3D child named by `label`.

@export var label: NodePath


func _process(_delta: float) -> void:
	var l := get_node_or_null(label) as Label3D
	if l:
		l.text = format_remaining(Game.remaining_s())


static func format_remaining(s: float) -> String:
	var t := int(ceil(s))
	if t >= 3600:
		return "%d:%02d:%02d" % [t / 3600, (t / 60) % 60, t % 60]
	return "%02d:%02d" % [t / 60, t % 60]
