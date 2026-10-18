extends Node3D
## Physical audit of a room's visuals, for any room (owner, 2026-10-11: things
## rendered into thin air, sunk into other things, or hidden behind them).
## Plays the room's solution through intents and, as it goes, checks the
## meshes players see against each other's real triangles:
##   FLOAT   a group of meshes touching nothing anchored (walls, floors...)
##   EMBED   much of one object inside another, unrelated one
##   HIDDEN  a solution step's target barely visible from anywhere a player
##           can stand within reach, just before that step
##   CLUE    a pigmented (clue) face barely visible from where players stand
##   godot --headless --path game res://tests/scenes/room_audit.tscn -- \
##     --room quiet_sun --out /tmp/audit.txt [--checkpoints 0,20,40,end|every:5]
## Findings looked at and accepted (a pawl pivoting in its jamb slot, a fern
## growing out of rubble) are listed in the room's `audit_accepted.txt`, one
## per line: the finding's key (or a * pattern), a tab, and why it is right. Exit code 1 while
## any finding is neither fixed nor accepted.
## Each finding carries a room_shots view (`--steps N --views ...`) to look at it.

const LAYER := 1 << 19
const TOUCH := 0.02
const EYE := 1.6
const REACH := 3.2
const CLUE_RANGE := 4.5

var room: RoomRoot
var manifest: RoomManifest
var _now := 1000.0
var _bodies := {}  # StaticBody3D -> MeshInstance3D
var _mesh_body := {}  # MeshInstance3D -> StaticBody3D
var _findings: Array[Dictionary] = []
var _seen := {}
var _anim_until := 0.0
var _accepted := {}


func _ready() -> void:
	var args := OS.get_cmdline_user_args()
	var loader := RoomLoader.new()
	if not loader.load_room(_arg(args, "--room", "quiet_sun"), _arg(args, "--pack", "")):
		push_error(loader.error)
		get_tree().quit(1)
		return
	manifest = loader.manifest
	var acc := "res://rooms/%s/audit_accepted.txt" % _arg(args, "--room", "quiet_sun")
	if FileAccess.file_exists(acc):
		for line in FileAccess.get_file_as_string(acc).split("\n"):
			if line.strip_edges().is_empty() or line.begins_with("#"):
				continue
			var parts := line.split("\t")
			_accepted[parts[0].strip_edges()] = parts[1].strip_edges() if parts.size() > 1 else ""
	room = loader.instantiate()
	add_child(room)
	Game.start_local_session(manifest, room, "audit", {}, null, "")
	Game.authority.allow_unpositioned = true
	Game.authority.clock = func() -> float: return _now
	Game.node_state_changed.connect(func(path: String, _s: Dictionary) -> void:
		var n := Game.node_at(path)
		var anim: float = n.get("anim_time") if n and n.get("anim_time") is float else 0.0
		_anim_until = maxf(_anim_until, Time.get_ticks_msec() / 1000.0 + anim + 0.4))
	await _frames(10)
	_attach_bodies()
	var steps := manifest.solution
	var cps := _checkpoints(_arg(args, "--checkpoints", "0,end"), steps.size())
	var nodes := {}
	for n: EBNode in Game.authority.nodes():
		nodes[n.eb_path] = n
	for i in steps.size() + 1:
		await _settle()
		if i in cps:
			print("audit: checkpoint at step %d" % i)
			_refresh_bodies()
			await _frames(3)
			var stand := _stand_points()
			_check_float(i)
			_check_embed(i)
			_check_clues(i, stand + _sight_eyes())
		if i == steps.size():
			break
		_now += 30.0
		var intent := SolutionPlayer.intent_for(steps[i], nodes, Game.authority.state.vars)
		if intent.is_empty() or intent.has("error"):
			continue
		_refresh_bodies()
		await _frames(2)
		_check_target(i, str(intent["path"]), steps[i])
		var r := Game.authority.handle_intent("p1", intent["path"], intent["verb"], intent["payload"])
		if not r.get("ok", false):
			_add({"kind": "STEP", "step": i, "what": "%s failed: %s" % [steps[i], r]})
	_write(_arg(args, "--out", "user://audit.txt"))
	var open := _findings.filter(func(f: Dictionary) -> bool: return not f.get("accepted", false))
	print("audit: %d open, %d accepted" % [open.size(), _findings.size() - open.size()])
	get_tree().quit(1 if not open.is_empty() else 0)


# --- Bodies: one concave collider per visible mesh, on its own layer -------

func _attach_bodies() -> void:
	for n in room.find_children("*", "MeshInstance3D", true, false):
		var mi := n as MeshInstance3D
		if mi.mesh == null or not _solid_look(mi):
			continue
		var faces := mi.mesh.get_faces()
		if faces.size() < 3:
			continue
		var shape := ConcavePolygonShape3D.new()
		shape.backface_collision = true
		shape.set_faces(faces)
		var body := StaticBody3D.new()
		body.collision_layer = LAYER
		body.collision_mask = 0
		var cs := CollisionShape3D.new()
		cs.shape = shape
		body.add_child(cs)
		mi.add_child(body)
		_bodies[body] = mi
		_mesh_body[mi] = body
	print("audit: %d meshes" % _bodies.size())


## Glows, beams, dust and sky are light, not things.
func _solid_look(mi: MeshInstance3D) -> bool:
	if mi.cast_shadow == GeometryInstance3D.SHADOW_CASTING_SETTING_SHADOWS_ONLY:
		return false
	for i in mi.mesh.get_surface_count():
		var m := mi.get_active_material(i)
		var bm := m as BaseMaterial3D
		if bm and (bm.shading_mode == BaseMaterial3D.SHADING_MODE_UNSHADED or bm.blend_mode == BaseMaterial3D.BLEND_MODE_ADD):
			return false
		var sm := m as ShaderMaterial
		if sm and sm.shader:
			var code := sm.shader.code
			if "blend_add" in code or "unshaded" in code:
				return false
	return true


func _refresh_bodies() -> void:
	for body: StaticBody3D in _bodies:
		var mi := _bodies[body] as MeshInstance3D
		body.collision_layer = LAYER if mi.is_visible_in_tree() else 0


func _space() -> PhysicsDirectSpaceState3D:
	return get_world_3d().direct_space_state


func _live_meshes() -> Array[MeshInstance3D]:
	var out: Array[MeshInstance3D] = []
	for body: StaticBody3D in _bodies:
		if body.collision_layer != 0:
			out.append(_bodies[body])
	return out


func _samples(mi: MeshInstance3D, count: int) -> PackedVector3Array:
	var faces := mi.mesh.get_faces()
	var out := PackedVector3Array()
	var stride := maxi(1, faces.size() / count)
	for k in range(0, faces.size(), stride):
		out.append(mi.global_transform * faces[k])
	# Always the lowest points (what it stands on).
	var low := mi.global_transform * Vector3(0, 0, 0)
	var lo_y := INF
	for f in faces:
		var g := mi.global_transform * f
		if g.y < lo_y:
			lo_y = g.y
			low = g
	out.append(low)
	return out


## A mesh's whole underside, for contact: a flat block resting in a bowl
## touches only by its outer edge, not at one lowest point.
func _underside(mi: MeshInstance3D) -> PackedVector3Array:
	var lo_y := INF
	var world := PackedVector3Array()
	for f in mi.mesh.get_faces():
		var g := mi.global_transform * f
		world.append(g)
		lo_y = minf(lo_y, g.y)
	var low := PackedVector3Array()
	for g in world:
		if g.y < lo_y + 0.004:
			low.append(g)
	var out := PackedVector3Array()
	for k in range(0, low.size(), maxi(1, low.size() / 24)):
		out.append(low[k])
	return out


## The object a mesh belongs to: the nearest ancestor that is an interactable,
## or else the node the builder placed (a part wrapper's parent).
func _owner_of(mi: Node) -> Node:
	var n := mi
	while n and n != room:
		if n is Interactable:
			return n
		n = n.get_parent()
	return mi.get_parent()


func _related(a: Node, b: Node) -> bool:
	var oa := _owner_of(a)
	var ob := _owner_of(b)
	return oa == ob or oa.is_ancestor_of(b) or ob.is_ancestor_of(a) or a.get_parent() == b.get_parent()


func _anchor(mi: MeshInstance3D) -> bool:
	var b := mi.global_transform * mi.get_aabb()
	if maxf(b.size.x, maxf(b.size.y, b.size.z)) > 2.6:
		return true  # walls, floors, ceilings, terrain
	var p := str(room.get_path_to(mi))
	for k in ["Floor", "Wall", "Ceil", "Roof", "Landing", "Slope", "Lintel", "Jamb", "Terrain", "Cliff", "Sky"]:
		if k in p:
			return true
	return false


# --- FLOAT --------------------------------------------------------------

func _check_float(step: int) -> void:
	var live := _live_meshes()
	var parent := {}
	for mi in live:
		parent[mi] = mi
	var sphere := SphereShape3D.new()
	sphere.radius = TOUCH
	var q := PhysicsShapeQueryParameters3D.new()
	q.shape = sphere
	q.collision_mask = LAYER
	var ray := PhysicsRayQueryParameters3D.new()
	ray.collision_mask = LAYER
	ray.hit_back_faces = true
	for mi in live:
		q.exclude = [(_mesh_body[mi] as StaticBody3D).get_rid()]
		ray.exclude = q.exclude
		for p in _samples(mi, 48) + _underside(mi):
			q.transform = Transform3D(Basis(), p)
			for hit in _space().intersect_shape(q, 8):
				var other := _bodies.get(hit["collider"]) as MeshInstance3D
				if other:
					_union(parent, mi, other)
		# Edges that pass through another surface touch it too (a bar run
		# into a wall has no corner near the wall's face).
		var faces := mi.mesh.get_faces()
		var stride := maxi(3, (faces.size() / 3 / 64) * 3)
		for k in range(0, faces.size() - 2, stride):
			for e in 3:
				ray.from = mi.global_transform * faces[k + e]
				ray.to = mi.global_transform * faces[k + (e + 1) % 3]
				var hit := _space().intersect_ray(ray)
				var other := _bodies.get(hit.get("collider")) as MeshInstance3D if not hit.is_empty() else null
				if other:
					_union(parent, mi, other)
	var groups := {}
	for mi in live:
		var r: Variant = _find(parent, mi)
		if not groups.has(r):
			groups[r] = []
		groups[r].append(mi)
	for r in groups:
		var g: Array = groups[r]
		if g.any(func(m: MeshInstance3D) -> bool: return _anchor(m)):
			continue
		var box := AABB()
		for k in g.size():
			var b := (g[k] as MeshInstance3D).global_transform * (g[k] as MeshInstance3D).get_aabb()
			box = b if k == 0 else box.merge(b)
		var names := g.map(func(m: Node) -> String: return str(room.get_path_to(m)))
		names.sort()
		_add({"kind": "FLOAT", "step": step, "what": "%d mesh(es) touching nothing anchored: %s" % [g.size(), ", ".join(names.slice(0, 4))],
				"key": "FLOAT " + names[0], "at": box.get_center(), "size": box.size})


func _find(parent: Dictionary, x: Variant) -> Variant:
	while parent[x] != x:
		parent[x] = parent[parent[x]]
		x = parent[x]
	return x


func _union(parent: Dictionary, a: Variant, b: Variant) -> void:
	if not parent.has(b):
		return
	parent[_find(parent, a)] = _find(parent, b)


# --- EMBED --------------------------------------------------------------

func _check_embed(step: int) -> void:
	for mi in _live_meshes():
		if _anchor(mi):
			continue
		var pts := _samples(mi, 40)
		var inside := {}
		for p in pts:
			var up := _crossings(p, Vector3.UP, mi)
			var down := _crossings(p, Vector3.DOWN, mi)
			for other in up:
				if up[other] % 2 == 1 and down.get(other, 0) % 2 == 1:
					inside[other] = inside.get(other, 0) + 1
		for other: MeshInstance3D in inside:
			var frac := float(inside[other]) / pts.size()
			if frac < 0.15 or _related(mi, other) or mi.mesh == other.mesh:
				continue  # (the same kit piece repeated along a run overlaps at its joints)
			var a := str(room.get_path_to(mi))
			var b := str(room.get_path_to(other))
			_add({"kind": "EMBED", "step": step, "what": "%d%% of %s is inside %s" % [int(frac * 100), a, b],
					"key": "EMBED %s in %s" % [a, b], "at": (mi.global_transform * mi.get_aabb()).get_center(),
					"size": (mi.global_transform * mi.get_aabb()).size})


## How many times a ray from p crosses each other mesh's surface.
func _crossings(p: Vector3, dir: Vector3, own: MeshInstance3D) -> Dictionary:
	var out := {}
	var q := PhysicsRayQueryParameters3D.new()
	q.collision_mask = LAYER
	q.hit_back_faces = true
	q.hit_from_inside = false
	q.exclude = [(_mesh_body[own] as StaticBody3D).get_rid()]
	var from := p
	for _k in 48:
		q.from = from
		q.to = p + dir * 30.0
		var hit := _space().intersect_ray(q)
		if hit.is_empty():
			break
		var m: Variant = _bodies.get(hit["collider"])
		if m:
			out[m] = out.get(m, 0) + 1
		from = (hit["position"] as Vector3) + dir * 0.0015
	return out


# --- HIDDEN and CLUE ----------------------------------------------------

func _stand_points() -> PackedVector3Array:
	var nm := NavigationMesh.new()
	nm.agent_radius = 0.2
	nm.agent_height = 1.75
	nm.agent_max_climb = 0.3
	nm.cell_size = 0.05
	nm.cell_height = 0.05
	nm.geometry_parsed_geometry_type = NavigationMesh.PARSED_GEOMETRY_STATIC_COLLIDERS
	nm.geometry_collision_mask = 1
	var src := NavigationMeshSourceGeometryData3D.new()
	NavigationServer3D.parse_source_geometry_data(nm, src, room)
	NavigationServer3D.bake_from_source_geometry_data(nm, src)
	# Reachable from the spawn: flood over polygons sharing vertices.
	var verts := nm.get_vertices()
	var by_vert := {}
	for pi in nm.get_polygon_count():
		for v in nm.get_polygon(pi):
			if not by_vert.has(v):
				by_vert[v] = []
			by_vert[v].append(pi)
	var spawn := room.get_node_or_null("Spawns")
	var start := Vector3.ZERO
	if spawn and spawn.get_child_count() > 0:
		start = (spawn.get_child(0) as Node3D).global_position
	var best := -1
	var best_d := INF
	for pi in nm.get_polygon_count():
		var d := verts[nm.get_polygon(pi)[0]].distance_to(start)
		if d < best_d:
			best_d = d
			best = pi
	var seen := {best: true}
	var todo := [best]
	while not todo.is_empty():
		var pi: int = todo.pop_back()
		for v in nm.get_polygon(pi):
			for o in by_vert[v]:
				if not seen.has(o):
					seen[o] = true
					todo.append(o)
	var out := PackedVector3Array()
	var grid := {}
	for pi in seen:
		var poly := nm.get_polygon(pi)
		var c := Vector3.ZERO
		for v in poly:
			c += verts[v]
		c /= poly.size()
		for p in [c] + Array(poly).map(func(v: int) -> Vector3: return verts[v].lerp(c, 0.3)):
			var key := Vector3i((p as Vector3) / 0.35)
			if not grid.has(key):
				grid[key] = true
				out.append((p as Vector3) + Vector3.UP * EYE)
	return out


## Of the given points, the most any one eye sees, and that eye.
func _best_view(pts: PackedVector3Array, own: Array, stand: PackedVector3Array, reach: float) -> Dictionary:
	var c := Vector3.ZERO
	for p in pts:
		c += p
	c /= maxf(1.0, pts.size())
	var q := PhysicsRayQueryParameters3D.new()
	q.collision_mask = LAYER
	q.hit_back_faces = true
	q.exclude = own.map(func(b: StaticBody3D) -> RID: return b.get_rid())
	var best := {"frac": 0.0, "eye": Vector3.ZERO, "blocker": "", "eyes": 0}
	var eyes := 0
	var blockers := {}
	for eye in stand:
		if eye.distance_to(c) > reach:
			continue
		eyes += 1
		var seen := 0
		for p in pts:
			q.from = eye
			q.to = p + (eye - p).normalized() * 0.01
			var hit := _space().intersect_ray(q)
			if hit.is_empty():
				seen += 1
			else:
				var m: Variant = _bodies.get(hit["collider"])
				if m:
					var k := str(room.get_path_to(m))
					blockers[k] = blockers.get(k, 0) + 1
		var frac := float(seen) / maxf(1.0, pts.size())
		if frac > best["frac"]:
			best["frac"] = frac
			best["eye"] = eye
	var top := ""
	var top_n := 0
	for k in blockers:
		if blockers[k] > top_n:
			top_n = blockers[k]
			top = k
	best["blocker"] = top
	best["eyes"] = eyes
	return best


func _check_target(step: int, path: String, act: Dictionary) -> void:
	var n: Node = Game.node_at(path)
	if n == null:
		return
	var meshes: Array = n.find_children("*", "MeshInstance3D", true, false).filter(
		func(m: MeshInstance3D) -> bool: return _mesh_body.has(m) and m.is_visible_in_tree())
	if meshes.is_empty():
		return  # logic only, or seen through something else
	var pts := PackedVector3Array()
	for m in meshes:
		pts.append_array(_samples(m, maxi(4, 24 / meshes.size())))
	var own := meshes.map(func(m: MeshInstance3D) -> StaticBody3D: return _mesh_body[m])
	var v := _best_view(pts, own, _stand_points_cached(), REACH)
	if v["frac"] < 0.5:
		_add({"kind": "HIDDEN", "step": step, "what": "step %d (%s %s): at best %d%% of it can be seen from within reach; most blocked by %s" % [
				step, act.get("act"), path, int(v["frac"] * 100), v["blocker"]], "key": "HIDDEN " + path,
				"at": _centre(pts), "eye": v["eye"]})


var _stand_cache: PackedVector3Array
var _stand_gen := -1


func _stand_points_cached() -> PackedVector3Array:
	# Rebaked when something moved (a door opened) since the last bake.
	var gen := int(_anim_until * 10.0)
	if gen != _stand_gen:
		_stand_cache = _stand_points()
		_stand_gen = gen
	return _stand_cache


## Where a player's eye goes when looking through a sight: a clue meant to be
## read only through one (the skyline frame in its sealed well) is seen there.
func _sight_eyes() -> PackedVector3Array:
	var out := PackedVector3Array()
	for n in room.find_children("*", "", true, false):
		var vp := n as Viewpoint
		var eye := vp.get_node_or_null(vp.eye) as Node3D if vp else null
		if eye:
			out.append(eye.global_position)
	return out


func _check_clues(step: int, stand: PackedVector3Array) -> void:
	# Documents (carved or printed clue faces) are checked whole.
	for n in room.find_children("*", "", true, false):
		var d := n as Document
		if d == null or not d.is_visible_in_tree():
			continue
		var meshes: Array = d.find_children("*", "MeshInstance3D", true, false).filter(
			func(m: MeshInstance3D) -> bool: return _mesh_body.has(m) and m.is_visible_in_tree())
		if meshes.is_empty():
			continue
		var pts := PackedVector3Array()
		for m in meshes:
			pts.append_array(_samples(m, maxi(4, 24 / meshes.size())))
		var v := _best_view(pts, meshes.map(func(m: MeshInstance3D) -> StaticBody3D: return _mesh_body[m]), stand, CLUE_RANGE)
		if v["eyes"] > 0 and v["frac"] < 0.5:
			_add({"kind": "CLUE", "step": step, "what": "%s: at best %d%% of it can be seen from within %.1f m; most blocked by %s" % [
					room.get_path_to(d), int(v["frac"] * 100), CLUE_RANGE, v["blocker"]], "key": "CLUE %s" % room.get_path_to(d),
					"at": _centre(pts), "eye": v["eye"]})
	for mi in _live_meshes():
		var pts := PackedVector3Array()
		for i in mi.mesh.get_surface_count():
			var m := mi.mesh.surface_get_material(i)
			if m == null or not "pigment" in m.resource_name.to_lower():
				continue
			var arr := mi.mesh.surface_get_arrays(i)
			var vs: PackedVector3Array = arr[Mesh.ARRAY_VERTEX]
			var stride := maxi(1, vs.size() / 16)
			for k in range(0, vs.size(), stride):
				pts.append(mi.global_transform * vs[k])
		if pts.is_empty():
			continue
		var v := _best_view(pts, [_mesh_body[mi]], stand, CLUE_RANGE)
		if v["eyes"] > 0 and v["frac"] < 0.6:
			_add({"kind": "CLUE", "step": step, "what": "%s: at best %d%% of its painted face can be seen from within %.1f m; most blocked by %s" % [
					room.get_path_to(mi), int(v["frac"] * 100), CLUE_RANGE, v["blocker"]], "key": "CLUE %s" % room.get_path_to(mi),
					"at": _centre(pts), "eye": v["eye"]})


func _centre(pts: PackedVector3Array) -> Vector3:
	var c := Vector3.ZERO
	for p in pts:
		c += p
	return c / maxf(1.0, pts.size())


# --- Bookkeeping ----------------------------------------------------------

func _add(f: Dictionary) -> void:
	var key: String = f.get("key", f["what"])
	if _seen.has(key):
		return
	_seen[key] = true
	f["key"] = key
	f["accepted"] = _is_accepted(key)
	_findings.append(f)
	print("audit: %s%s step %d: %s" % ["(accepted) " if f["accepted"] else "", f["kind"], f["step"], f["what"]])


## An exact key, or a pattern with * (for a family: every trim course where
## it runs into a pilaster).
func _is_accepted(key: String) -> bool:
	if _accepted.has(key):
		return true
	for k: String in _accepted:
		if "*" in k and key.match(k):
			return true
	return false


func _write(path: String) -> void:
	var lines: PackedStringArray = []
	for f in _findings:
		var line := "%s%s\tstep %d\t%s\tkey %s" % ["ok-" if f["accepted"] else "", f["kind"], f["step"], f["what"], f["key"]]
		if f.has("at"):
			var at: Vector3 = f["at"]
			var eye: Vector3 = f.get("eye", Vector3.ZERO)
			if eye == Vector3.ZERO:
				var size: Vector3 = f.get("size", Vector3.ONE)
				eye = at + Vector3(0.0, 0.6, 1.0).normalized() * clampf(size.length() * 2.0, 1.2, 4.0)
			var d := at - eye
			var yaw := rad_to_deg(atan2(-d.x, -d.z))
			var pitch := rad_to_deg(atan2(d.y, Vector2(d.x, d.z).length()))
			line += "\tat %.2f,%.2f,%.2f\tview --steps %d --views f:%.2f,%.2f,%.2f:%.0f:%.0f" % [at.x, at.y, at.z, f["step"], eye.x, eye.y, eye.z, yaw, pitch]
		lines.append(line)
	var fa := FileAccess.open(path, FileAccess.WRITE)
	fa.store_string("\n".join(lines) + "\n")
	print("audit: %d findings -> %s" % [_findings.size(), path])


func _checkpoints(spec: String, n: int) -> Array[int]:
	var out: Array[int] = []
	for s in spec.split(","):
		if s.begins_with("every:"):
			for i in range(0, n, int(s.substr(6))):
				out.append(i)
			out.append(n)
		elif s == "end":
			out.append(n)
		elif s == "all":
			for i in n + 1:
				out.append(i)
		elif s.is_valid_int():
			out.append(int(s))
	return out


func _settle() -> void:
	await _frames(2)
	while Time.get_ticks_msec() / 1000.0 < _anim_until:
		await _frames(5)


func _frames(n: int) -> void:
	for _k in n:
		await get_tree().physics_frame


static func _arg(args: PackedStringArray, key: String, def: String) -> String:
	var i := args.find(key)
	return args[i + 1] if i >= 0 and i + 1 < args.size() else def
