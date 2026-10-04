@icon("res://addons/escapebox_sdk/icons/eb_node.svg")
class_name Spinner
extends Node3D
## Turns a part continuously (a waterwheel, a clock train, a fan), optionally
## only while a watched SDK node's state[only_when_key], as text, equals
## only_when_value (like AmbientZone). Presentation only.

## The part to turn; defaults to this node.
@export var part: NodePath
## Degrees per second about each local axis.
@export var degrees_per_s: Vector3 = Vector3(0, 0, 30)
@export var only_when: NodePath
@export var only_when_key: String = "state"
@export var only_when_value: String = ""

var running := true
var _part: Node3D


func _ready() -> void:
	_part = get_node_or_null(part) as Node3D if not part.is_empty() else self
	var watched := get_node_or_null(only_when) as EBNode
	if watched:
		watched.state_applied.connect(_on_watched_state)
		_on_watched_state(watched.current_state)


func condition_met(state: Dictionary) -> bool:
	return str(state.get(only_when_key, "")) == only_when_value


func _on_watched_state(state: Dictionary) -> void:
	running = condition_met(state)


func _process(delta: float) -> void:
	if running and _part:
		_part.rotation_degrees += degrees_per_s * delta
