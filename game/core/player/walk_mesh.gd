class_name WalkMesh
extends Node
## Where the local player can walk, for tap-to-walk (ADR-0038). Baked on the
## client from the room's static colliders when the room loads, so room
## authors do nothing. Re-baked shortly after any world state change, since
## doors and hidden passages open.

## Thinner than the player's 0.3 m capsule: the mesh only plans the route and
## the capsule slides along walls, but Recast's erosion and voxel rounding
## closed 0.7 m passages (beside a swung door, on a spiral stair) at
## the full radius.
const AGENT_RADIUS := 0.2
const AGENT_HEIGHT := 1.75
const CELL := 0.05
const CELL_H := 0.05
## Waits for door animations to finish before re-baking.
const REBAKE_DELAY := 1.5

var _room: Node3D
var _map: RID
var _region: RID
var _rebake_timer: SceneTreeTimer
var baked_polygons: int = 0
## Counts bakes, so a walk can tell its route came from an older mesh.
var generation: int = 0


func setup(room: Node3D) -> void:
	_room = room
	_map = room.get_world_3d().navigation_map
	NavigationServer3D.map_set_cell_size(_map, CELL)
	NavigationServer3D.map_set_cell_height(_map, CELL_H)
	bake()
	# Joining a game in progress: doors already open in the snapshot are still
	# animating open now, so bake again once they have finished.
	_schedule_rebake()
	Game.node_state_changed.connect(func(path: String, _s: Dictionary) -> void:
		# Wait for that door or lid to finish moving.
		var n := Game.node_at(path)
		var anim: float = n.get("anim_time") if n and n.get("anim_time") is float else 0.0
		_schedule_rebake(maxf(REBAKE_DELAY, anim + 0.3)))


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
	_add_flipped_backfaces(src, _room)
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
	generation += 1
	print("walk mesh: %d polygons in %d ms" % [baked_polygons, Time.get_ticks_msec() - t])


## Concave colliders with backface_collision are solid from both sides for the
## player, but the baker only walks on their front faces: a ramp built facing
## down (a stair seen from below) would be left out. Add their faces flipped too.
static func _add_flipped_backfaces(src: NavigationMeshSourceGeometryData3D, root: Node) -> void:
	for cs: CollisionShape3D in root.find_children("*", "CollisionShape3D", true, false):
		var shape := cs.shape as ConcavePolygonShape3D
		if shape == null or not shape.backface_collision or cs.disabled:
			continue
		var body := cs.get_parent() as StaticBody3D
		if body == null or body.collision_layer & 1 == 0:
			continue
		var faces := shape.get_faces()
		var flipped := PackedVector3Array()
		flipped.resize(faces.size())
		for i in range(0, faces.size(), 3):
			flipped[i] = faces[i]
			flipped[i + 1] = faces[i + 2]
			flipped[i + 2] = faces[i + 1]
		src.add_faces(flipped, cs.global_transform)


## True while a re-bake is waiting for doors to finish moving.
func pending() -> bool:
	return _rebake_timer != null and _rebake_timer.time_left > 0.0


func _schedule_rebake(delay: float = REBAKE_DELAY) -> void:
	if not is_inside_tree():
		return
	if pending() and _rebake_timer.time_left >= delay:
		return  # a later bake is already due
	var timer := get_tree().create_timer(delay)
	_rebake_timer = timer
	timer.timeout.connect(func() -> void:
		if _rebake_timer == timer:
			_rebake_timer = null
			bake())


## A walking route from `from` to the walkable point nearest `to`. Falls back
## to a straight line when nothing is baked (the player slides along walls).
## The walkable point nearest `to` can be an island nobody can reach (the top
## of a ledge); when the route ends far short, nearby goals a little lower or
## to the side are tried too and the route that gets closest wins.
func route(from: Vector3, to: Vector3, corners: bool = true) -> PackedVector3Array:
	if baked_polygons == 0 or NavigationServer3D.map_get_iteration_id(_map) == 0:
		return PackedVector3Array([to])
	var best := _path(from, to, corners)
	if best.is_empty():
		return PackedVector3Array([to])
	var best_d := best[best.size() - 1].distance_to(to)
	if best_d > 0.8:
		for off: Vector3 in [Vector3(0, -0.6, 0), Vector3(0, -1.2, 0), Vector3(0, -1.8, 0),
				Vector3(0.6, -1.0, 0), Vector3(-0.6, -1.0, 0), Vector3(0, -1.0, 0.6), Vector3(0, -1.0, -0.6)]:
			var p := _path(from, to + off, corners)
			if p.is_empty():
				continue
			var d := p[p.size() - 1].distance_to(to)
			if d < best_d - 0.2:
				best = p
				best_d = d
	return best


## `corners` false: an unoptimised path through the polygons' edge midpoints,
## which keeps clear of the corners a string-pulled path hugs.
func _path(from: Vector3, to: Vector3, corners: bool = true) -> PackedVector3Array:
	var goal := NavigationServer3D.map_get_closest_point(_map, to)
	return NavigationServer3D.map_get_path(_map, from, goal, corners)
