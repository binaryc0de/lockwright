@icon("res://addons/escapebox_sdk/icons/eb_node.svg")
class_name Intercom
extends EBNode
## In-fiction hint and narration surface (PLAN.md 6.6): shows the latest hint
## or narration on a Label3D and plays a chime if `chime` is set.

@export var label: NodePath
@export var chime: AudioStream
@export var speaker_name: String = "INTERCOM"


func _ready() -> void:
	Game.hint_revealed.connect(func(_p: String, _t: int, text: String, _a: bool) -> void: _show(text))
	Game.narrated.connect(_show)


func _show(text: String) -> void:
	var l := get_node_or_null(label) as Label3D
	if l:
		l.text = "%s:\n%s" % [speaker_name, text]
	EBSound.play_at(self, chime if chime else "chime", 0.0, 0.0)
