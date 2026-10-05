class_name WalkMesh
extends Node
## Where the local player can walk, for tap-to-walk (ADR-0038). Baked on the
## client from the room's static colliders when the room loads, so room
## authors do nothing. Re-baked shortly after any world state change, since
## doors and hidden passages open.

const AGENT_RADIUS := 0.3
const AGENT_HEIGHT := 1.75
const CELL := 0.1
const CELL_H := 0.05
## Waits for door animations to finish before re-baking.
const REBAKE_DELAY := 1.5

var _room: Node3D
var _map: RID
var _region: RID
var _rebake_timer: SceneTreeTimer
var baked_polygons: int = 0


func setup(room: Node3D) -> void:
	_room = room
	_map = room.get_world_3d().navigation_map
	NavigationServer3D.map_set_cell_size(_map, CELL)
	NavigationServer3D.map_set_cell_height(_map, CELL_H)
	bake()
	Game.node_state_changed.connect(func(_p: String, _s: Dictionary) -> void: _schedule_rebake())


func _exit_tree() -> void:
	if _region.is_valid():
		NavigationServer3D.free_rid(_region)


func bake() -> void:
	if _room == null or not is_instance_valid(_room):
		return
	var t := Time.get_ticks_msec()
	var nm := NavigationMesh.new()
	nm.agent_radius = AGENT_RADIUS
	nm.agent_height = AGENT_HEIGHT
	nm.agent_max_climb = 0.3
	nm.agent_max_slope = 50.0
	nm.cell_size = CELL
	nm.cell_height = CELL_H
	nm.geometry_parsed_geometry_type = NavigationMesh.PARSED_GEOMETRY_STATIC_COLLIDERS
	nm.geometry_collision_mask = 1
	var src := NavigationMeshSourceGeometryData3D.new()
	NavigationServer3D.parse_source_geometry_data(nm, src, _room)
	NavigationServer3D.bake_from_source_geometry_data(nm, src)
	# A fresh region each time: swapping the mesh on a live region did not
	# always reach the map's paths (seen in the gdUnit run on Godot 4.7.2).
	var region := NavigationServer3D.region_create()
	NavigationServer3D.region_set_navigation_mesh(region, nm)
	NavigationServer3D.region_set_map(region, _map)
	if _region.is_valid():
		NavigationServer3D.free_rid(_region)
	_region = region
	baked_polygons = nm.get_polygon_count()
	print("walk mesh: %d polygons in %d ms" % [baked_polygons, Time.get_ticks_msec() - t])


func _schedule_rebake() -> void:
	if not is_inside_tree():
		return
	var timer := get_tree().create_timer(REBAKE_DELAY)
	_rebake_timer = timer
	timer.timeout.connect(func() -> void:
		if _rebake_timer == timer:
			bake())


## A walking route from `from` to the walkable point nearest `to`. Falls back
## to a straight line when nothing is baked (the player slides along walls).
func route(from: Vector3, to: Vector3) -> PackedVector3Array:
	if baked_polygons == 0 or NavigationServer3D.map_get_iteration_id(_map) == 0:
		return PackedVector3Array([to])
	var goal := NavigationServer3D.map_get_closest_point(_map, to)
	var path := NavigationServer3D.map_get_path(_map, from, goal, true)
	if path.is_empty():
		return PackedVector3Array([to])
	return path
