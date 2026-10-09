@icon("res://addons/escapebox_sdk/icons/eb_node.svg")
class_name ComboPresenter
extends Node3D
## Presentation only: poses one part from the positions of several stepped
## controls together (a rocker bar between two teeth tilts one way when one
## tooth is up and the other down, the other way when reversed, and lies
## jammed level when they match). `poses` maps the controls' indices joined by
## commas ("0,1") to the part's turn in degrees; anything unlisted is the
## part's own scene pose.

@export var inputs: Array[NodePath] = []
@export var part: NodePath
@export var poses: Dictionary = {}
@export var duration_s: float = 0.5

var _base: Variant = null
var _tween: Tween


func _ready() -> void:
	for p in inputs:
		var n := get_node_or_null(p) as EBNode
		if n:
			n.state_applied.connect(func(_s: Dictionary) -> void: _pose())
		else:
			push_error("%s: no SDK node at %s" % [name, p])
	_pose.call_deferred()


func key() -> String:
	var idx: Array[String] = []
	for p in inputs:
		var n := get_node_or_null(p) as EBNode
		idx.append(str(int(n.current_state.get("index", 0))) if n else "?")
	return ",".join(idx)


func _pose() -> void:
	var n := get_node_or_null(part) as Node3D
	if n == null:
		return
	if _base == null:
		_base = n.rotation_degrees
	var to: Vector3 = (_base as Vector3) + (poses.get(key(), Vector3.ZERO) as Vector3)
	if _tween:
		_tween.kill()
	if is_inside_tree() and DisplayServer.get_name() != "headless" and n.rotation_degrees != to:
		_tween = create_tween()
		_tween.tween_property(n, "rotation_degrees", to, duration_s).set_trans(Tween.TRANS_SINE)
	else:
		n.rotation_degrees = to
