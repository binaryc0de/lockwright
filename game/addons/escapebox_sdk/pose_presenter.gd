@icon("res://addons/escapebox_sdk/icons/eb_node.svg")
class_name PosePresenter
extends Node3D
## Presentation only (ADR-0040): moves parts into a second, stable pose while
## a watched SDK node's state[watch_key], as text, equals watch_value (stone
## leaves folding open, sand draining, a carriage rising). The first state a
## client sees snaps straight to the pose, so late joiners and restored games
## never replay the move. Collision and doors belong to SDK nodes, not this.

@export var watch: NodePath
@export var watch_key: String = "state"
@export var watch_value: String = "unlocked"
## Parts and, per part, the turn (degrees) and move (metres) into the pose.
@export var parts: Array[NodePath] = []
@export var pose_rotation: Array[Vector3] = []
@export var pose_offset: Array[Vector3] = []
## Nodes shown only in the pose, and nodes hidden in it.
@export var show_in_pose: Array[NodePath] = []
@export var hide_in_pose: Array[NodePath] = []
@export var duration_s: float = 4.0

var posed := false
var _seen := false
var _base := {}
var _tween: Tween


func _ready() -> void:
	for p in parts:
		var n := get_node_or_null(p) as Node3D
		if n:
			_base[n] = [n.rotation_degrees, n.position]
	var w := get_node_or_null(watch) as EBNode
	if w:
		w.state_applied.connect(_on_state)
		if not w.current_state.is_empty():
			_on_state(w.current_state)
	else:
		push_error("%s: no SDK node at %s" % [name, watch])


func _on_state(state: Dictionary) -> void:
	var want := str(state.get(watch_key, "")) == watch_value
	var instant := not _seen
	_seen = true
	if want == posed and not instant:
		return
	posed = want
	_go(want, instant or duration_s <= 0.0 or not is_inside_tree())


func _go(to_pose: bool, instant: bool) -> void:
	if _tween:
		_tween.kill()
	_tween = null if instant else create_tween().set_parallel(true).set_trans(Tween.TRANS_SINE).set_ease(Tween.EASE_IN_OUT)
	for k in parts.size():
		var n := get_node_or_null(parts[k]) as Node3D
		if n == null or not _base.has(n):
			continue
		var rot: Vector3 = (_base[n][0] as Vector3) + ((pose_rotation[k] if k < pose_rotation.size() else Vector3.ZERO) if to_pose else Vector3.ZERO)
		var pos: Vector3 = (_base[n][1] as Vector3) + ((pose_offset[k] if k < pose_offset.size() else Vector3.ZERO) if to_pose else Vector3.ZERO)
		if instant:
			n.rotation_degrees = rot
			n.position = pos
		else:
			_tween.tween_property(n, "rotation_degrees", rot, duration_s)
			_tween.tween_property(n, "position", pos, duration_s)
	for p in show_in_pose:
		var n := get_node_or_null(p) as Node3D
		if n:
			n.visible = to_pose
	for p in hide_in_pose:
		var n := get_node_or_null(p) as Node3D
		if n:
			n.visible = not to_pose
