@icon("res://addons/escapebox_sdk/icons/eb_node.svg")
class_name UVReveal
extends EBNode
## UV-ink text on a surface (whiteboard, wall, desk). Its Label3D child is
## shown only while the local player's selected item is a UV source and the
## camera is within `reveal_range` metres. Text may use {{vars}}.

@export var label: NodePath
@export var text: String = ""
@export var reveal_range: float = 2.5


func _process(_delta: float) -> void:
	var l := get_node_or_null(label) as Label3D
	if l == null:
		return
	var cam := get_viewport().get_camera_3d()
	var show := Game.uv_active() and cam != null \
		and cam.global_position.distance_to(global_position) <= reveal_range
	l.visible = show
	if show:
		l.text = EBTemplate.render(text, Game.vars())
