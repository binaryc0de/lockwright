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


## The room's AirlockGate, if it has one (onboarding, ADR-0020).
func airlock() -> AirlockGate:
	for n in EBNode.find_all(self):
		if n is AirlockGate:
			return n
	return null


## Where a player who joins now should appear: inside, once the airlock has
## sealed; the normal spawn otherwise.
func join_spawn_transform() -> Transform3D:
	var a := airlock()
	if a and a.is_sealed():
		return a.late_spawn_transform()
	return spawn_transform()


## Eye position for a rejoining player last seen at `known_eye`: keep it,
## unless they were left outside a sealed airlock (then the inside spawn).
func rejoin_eye(known_eye: Vector3) -> Vector3:
	var a := airlock()
	if a and a.is_sealed() and not a.is_inside(known_eye):
		return join_spawn_transform().origin + Vector3.UP * FirstPersonPlayer.EYE_HEIGHT
	return known_eye


## Per-session room variables (room.yaml `variables`).
func vars() -> Dictionary:
	return Game.vars()
