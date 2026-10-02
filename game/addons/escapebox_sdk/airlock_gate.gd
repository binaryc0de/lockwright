@icon("res://addons/escapebox_sdk/icons/eb_node.svg")
class_name AirlockGate
extends EBNode
## Onboarding airlock (PLAN.md 9.6, 10; ADR-0020). Players start outside the
## room (RoomRoot.spawn_point) and learn the controls; when every connected
## player is inside `inside_min`..`inside_max`, or `seal_after_s` after the
## first one walked in, the server closes `door`, starts the clock, narrates
## `seal_text` and moves stragglers to `late_spawn`. Players who join after
## that spawn at `late_spawn`.
## State: {state: "waiting" | "sealed"}

## The door players walk through; closed (and left to its lock) on sealing.
@export var door: NodePath
## The "inside" box, in room coordinates.
@export var inside_min: Vector3 = Vector3.ZERO
@export var inside_max: Vector3 = Vector3.ZERO
## Seal anyway this long after the first player is inside (0 = wait for all).
@export var seal_after_s: float = 60.0
## Narration when the room seals (may use {{vars}}).
@export_multiline var seal_text: String = ""
## Where late joiners and stragglers appear (a Marker3D or any Node3D).
@export var late_spawn: NodePath

var _first_inside_t := -1.0


func _initial_state() -> Dictionary:
	return {"state": "waiting"}


func is_sealed() -> bool:
	return my_state().get("state", "waiting") == "sealed"


func late_spawn_transform() -> Transform3D:
	var m := get_node_or_null(late_spawn) as Node3D
	return m.global_transform if m else global_transform


## Room-coordinates containment test for a world position.
func is_inside(world_pos: Vector3) -> bool:
	var p: Vector3 = (room_root as Node3D).to_local(world_pos) if room_root is Node3D else world_pos
	return p.x >= inside_min.x and p.x <= inside_max.x \
		and p.y >= inside_min.y and p.y <= inside_max.y \
		and p.z >= inside_min.z and p.z <= inside_max.z


func _physics_process(delta: float) -> void:
	if authority == null or is_sealed():
		return
	var positions: Dictionary = authority.player_positions
	if positions.is_empty():
		return
	var inside := 0
	for pid: String in positions:
		if is_inside(positions[pid]):
			inside += 1
	if inside == 0:
		_first_inside_t = -1.0
		return
	if _first_inside_t < 0.0:
		_first_inside_t = 0.0
	_first_inside_t += delta
	if inside == positions.size() or (seal_after_s > 0.0 and _first_inside_t >= seal_after_s):
		seal()


## Server: seals the room now (also used by tests and replays).
func seal() -> void:
	assert(authority != null, "seal() is server-only")
	if is_sealed():
		return
	var door_path := room_path_of(door)
	if not door_path.is_empty():
		authority.set_node_state(door_path, {"state": "closed"})
	set_state({"state": "sealed"})
	var spot := late_spawn_transform().origin
	for pid: String in authority.player_positions.keys():
		if not is_inside(authority.player_positions[pid]):
			authority.place_player(pid, spot)
	authority.start_clock("airlock")
	if not seal_text.is_empty():
		authority.narrate(authority.resolve(seal_text))
