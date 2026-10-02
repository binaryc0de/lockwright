@icon("res://addons/escapebox_sdk/icons/eb_node.svg")
class_name RoomRoot
extends Node3D
## Root of every room's entry scene (PLAN.md 8.2).

signal room_ready
signal puzzle_solved(puzzle_id: String)
signal session_finished(won: bool)

## Where players spawn (a Marker3D or any Node3D).
@export var spawn_point: NodePath


func spawn_transform() -> Transform3D:
	var s := get_node_or_null(spawn_point) as Node3D
	return s.global_transform if s else global_transform


## Per-session room variables (room.yaml `variables`).
func vars() -> Dictionary:
	return Game.vars()
