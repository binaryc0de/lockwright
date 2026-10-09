@icon("res://addons/escapebox_sdk/icons/eb_node.svg")
class_name OpticalNetwork
extends Lock
## Light through a building (ADR-0040): a beam leaves `source`, and each
## place it reaches sends it on by an authored edge. At a station (an
## IndexedMechanism: a mirror, a turning prism) the edge depends on the
## station's position. Screens (IndexedMechanisms in `masks`) shade lanes of
## the beam. The lock opens when the beam ends at `goal` with exactly
## `goal_lanes` lit. All of it is computed on the server from the current
## positions; there is no ray tracing and no free angles, so every result is
## one of a finite, checkable set.
## State: Lock's, plus {path: [places], end: place, shut: bool (stopped at a
## gated place), lit: [lanes]}.

## Where the beam starts.
@export var source: String = "Source"
## Stations: IndexedMechanisms that redirect the beam; a station's place name
## is its node name.
@export var stations: Array[NodePath] = []
## "From>To" always; "From@2>To" when station From is at position 2 (or at
## the position labelled 2). A station with no edge for its position caps the
## beam there.
@export var edges: Array[String] = []
## Lanes across the beam (0 = one plain beam).
@export var lanes: int = 0
## Screens shading lanes, and per screen the lanes shaded at each position:
## "1,5|1,3|3,4" (positions separated by "|", lanes by ","; "" = none).
@export var masks: Array[NodePath] = []
@export var mask_table: Array[String] = []
## Places the beam only passes while a node is in a state (a shutter that
## must be open); otherwise it stops there. Parallel arrays.
@export var gate_places: Array[String] = []
@export var gate_nodes: Array[NodePath] = []
@export var gate_states: Array[String] = []
## Where the beam must end, and the exact lanes that must be lit ("3,4");
## empty = any light at all.
@export var goal: String = ""
@export var goal_lanes: String = ""
## Activated when the light arrives (like a Lever's targets).
@export var targets: Array[NodePath] = []
## Presentation: Node3Ds named like places, joined by beams in path order.
@export var points: Array[NodePath] = []
## Presentation: one mesh per lane, glowing while that lane is lit.
@export var lane_cells: Array[NodePath] = []
## Hide a cell while no light reaches it (the art behind shows the dark
## aperture) instead of painting it near-black.
@export var hide_dark_cells: bool = false
@export var beam_width: float = 0.05
@export var beam_color: Color = Color(1.0, 0.86, 0.5)
## Presentation, per lane: with a source point, each lane is drawn as its own
## beam from `lane_source` towards its `lane_ends` entry, and stops where the
## first mask that shades it stands (on the plane through the mask's origin,
## square to the line from the source to it), so a player sees light pass
## through a hole or end on stone. Masks are taken nearest the source first.
@export var lane_source: NodePath
@export var lane_ends: Array[NodePath] = []

const MAX_HOPS := 64

var _beams: Array[MeshInstance3D] = []
var _lane_beams: Array[MeshInstance3D] = []
static var _lane_mat: StandardMaterial3D
static var _lit_mat: StandardMaterial3D
static var _dark_mat: StandardMaterial3D


func _init() -> void:
	verbs = ["examine"]


func _ready() -> void:
	super()
	for p in stations + masks + gate_nodes:
		var n := get_node_or_null(p) as EBNode
		if n:
			n.state_applied.connect(func(_s: Dictionary) -> void: _server_recompute())
		else:
			push_error("%s: no SDK node at %s" % [name, p])
	# Which mask stops a shaded lane can change without the lit set changing.
	if not lane_source.is_empty():
		for p in masks:
			var m := get_node_or_null(p) as EBNode
			if m:
				m.state_applied.connect(func(_s: Dictionary) -> void: _draw_lanes(current_state))


func _initial_state() -> Dictionary:
	var s := super()
	s.merge({"path": [], "end": "", "shut": false, "lit": []})
	return s


## Index of a station or mask from its state, safe after a JSON round trip.
func _index(p: NodePath) -> int:
	var n := get_node_or_null(p) as EBNode
	return int(state_of(n).get("index", 0)) if n else 0


func _station_named(place: String) -> IndexedMechanism:
	for p in stations:
		var n := get_node_or_null(p) as IndexedMechanism
		if n and str(n.name) == place:
			return n
	return null


func _gate_open(place: String) -> bool:
	for i in gate_places.size():
		if gate_places[i] == place:
			var n := get_node_or_null(gate_nodes[i]) as EBNode if i < gate_nodes.size() else null
			var want := gate_states[i] if i < gate_states.size() else "unlocked"
			if n == null or str(state_of(n).get("state", "")) != want:
				return false
	return true


## Where the beam goes from `place`, or "" if it stops there.
func next_place(place: String) -> String:
	var st := _station_named(place)
	var pos := -1
	var label := ""
	if st:
		pos = int(state_of(st).get("index", 0))
		label = st.detents[pos] if pos < st.detents.size() else ""
	for e in edges:
		var lr := e.split(">")
		if lr.size() != 2:
			continue
		var from := lr[0].strip_edges()
		var to := lr[1].strip_edges()
		if from.contains("@"):
			var fa := from.split("@")
			if st == null or fa[0] != place:
				continue
			if fa[1] == str(pos) or (not label.is_empty() and fa[1] == label):
				return to
		elif from == place and st == null:
			return to
	return ""


## Follows the beam: {path, end, shut, lit}.
func trace() -> Dictionary:
	var path: Array[String] = [source]
	var cur := source
	if not _gate_open(cur):
		return {"path": path, "end": cur, "shut": true, "lit": lit_lanes()}
	for _hop in MAX_HOPS:
		var nxt := next_place(cur)
		if nxt.is_empty() or nxt in path:
			break
		path.append(nxt)
		cur = nxt
		if not _gate_open(cur):
			return {"path": path, "end": cur, "shut": true, "lit": lit_lanes()}
	return {"path": path, "end": cur, "shut": false, "lit": lit_lanes()}


func lit_lanes() -> Array[int]:
	var out: Array[int] = []
	if lanes <= 0:
		return [0] as Array[int]
	var shaded := {}
	for k in mini(masks.size(), mask_table.size()):
		var rows := mask_table[k].split("|")
		var i := _index(masks[k])
		if i < rows.size():
			for v in rows[i].split(",", false):
				shaded[int(v)] = true
	for l in lanes:
		if not shaded.has(l):
			out.append(l)
	return out


func _goal_met(t: Dictionary) -> bool:
	if goal.is_empty() or t["end"] != goal or t["shut"]:
		return false
	var lit: Array = t["lit"]
	if lit.is_empty():
		return false
	if goal_lanes.strip_edges().is_empty():
		return true
	var want: Array[int] = []
	for v in authority.resolve(goal_lanes).split(",", false):
		want.append(int(v))
	want.sort()
	var have: Array[int] = []
	for v in lit:
		have.append(int(v))
	have.sort()
	return want == have


func _server_recompute() -> void:
	if authority == null or authority.state == null or not authority.state.nodes.has(eb_path):
		return
	var t := trace()
	var cur := my_state()
	if cur.get("path") != t["path"] or cur.get("end") != t["end"] or cur.get("lit") != t["lit"] or cur.get("shut") != t["shut"]:
		set_state({"path": t["path"], "end": t["end"], "shut": t["shut"], "lit": t["lit"]})
	if not is_unlocked() and is_powered() and authority.prerequisites_met(self) and _goal_met(t):
		set_state({"state": "unlocked", "last_ok": true})
		for p in targets:
			authority.activate(room_path_of(p))


func _server_activate() -> void:
	if not is_powered():
		set_state({"powered": true})
	_server_recompute()


func _server_intent(_player_id: String, _verb: String, _payload: Dictionary) -> Dictionary:
	_server_recompute()
	return {"ok": true}


func client_interact(_item_path: String = "") -> void:
	var lit: Array = current_state.get("lit", [])
	Game.toast("The light ends at %s." % str(current_state.get("end", source)) if not lit.is_empty() else "No light gets through.")


func _apply_state(state: Dictionary) -> void:
	super(state)
	_draw_beam(state)
	_draw_lanes(state)
	var lit: Array = []
	for v in state.get("lit", []):
		lit.append(int(v))
	if _lit_mat == null:
		_lit_mat = StandardMaterial3D.new()
		_lit_mat.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
		_lit_mat.albedo_color = Color(1.0, 0.9, 0.6)
		_dark_mat = StandardMaterial3D.new()
		_dark_mat.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
		_dark_mat.albedo_color = Color(0.06, 0.05, 0.04)
	var arrived: bool = (str(state.get("end", "")) == goal or goal.is_empty()) and not state.get("shut", false)
	for i in lane_cells.size():
		var m := get_node_or_null(lane_cells[i]) as GeometryInstance3D
		if m:
			var on: bool = arrived and i in lit
			m.material_override = _lit_mat if on else _dark_mat
			if hide_dark_cells:
				m.visible = on


func _point(place: String) -> Node3D:
	for p in points:
		var n := get_node_or_null(p) as Node3D
		if n and str(n.name) == place:
			return n
	return null


func _draw_beam(state: Dictionary) -> void:
	for b in _beams:
		b.queue_free()
	_beams.clear()
	if (state.get("lit", []) as Array).is_empty() or not is_inside_tree():
		return
	var mat := StandardMaterial3D.new()
	mat.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	mat.albedo_color = beam_color
	var prev: Node3D = null
	for place in state.get("path", []):
		var p := _point(str(place))
		if p == null:
			continue
		if prev != null:
			var a := prev.global_position
			var b := p.global_position
			var dist := a.distance_to(b)
			if dist > 0.01:
				var mi := MeshInstance3D.new()
				var box := BoxMesh.new()
				box.size = Vector3(beam_width, beam_width, dist)
				mi.mesh = box
				mi.material_override = mat
				mi.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
				add_child(mi)
				mi.global_position = (a + b) * 0.5
				mi.look_at(b, Vector3.UP if absf((b - a).normalized().y) < 0.99 else Vector3.RIGHT)
				_beams.append(mi)
		prev = p


## The mask nearest the source that shades `lane` in its present position, as
## [distance along the lane, mask index], or [] when none does.
func blocker(lane: int) -> Array:
	var src := get_node_or_null(lane_source) as Node3D
	var end := get_node_or_null(lane_ends[lane]) as Node3D if lane < lane_ends.size() else null
	if src == null or end == null:
		return []
	var a := src.global_position
	var dir := end.global_position - a
	var best: Array = []
	for k in mini(masks.size(), mask_table.size()):
		var m := get_node_or_null(masks[k]) as EBNode
		if m == null:
			continue
		var rows := mask_table[k].split("|")
		var i := int(m.current_state.get("index", 0))
		if i >= rows.size() or not (str(lane) in rows[i].split(",", false)):
			continue
		var c := (m as Node3D).global_position
		var n := (c - a).normalized()
		var denom := dir.dot(n)
		if absf(denom) < 1e-6:
			continue
		var t := (c - a).dot(n) / denom
		if t > 0.0 and t < 1.0 and (best.is_empty() or t < best[0]):
			best = [t, k]
	return best


func _draw_lanes(state: Dictionary) -> void:
	for b in _lane_beams:
		if is_instance_valid(b):
			b.queue_free()
	_lane_beams.clear()
	var src := get_node_or_null(lane_source) as Node3D
	if src == null or not is_inside_tree():
		return
	# No light at all while the source's own gate is shut (an unlit fire).
	if bool(state.get("shut", false)) and str(state.get("end", source)) == source:
		return
	if _lane_mat == null:
		_lane_mat = StandardMaterial3D.new()
		_lane_mat.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
		_lane_mat.blend_mode = BaseMaterial3D.BLEND_MODE_ADD
		_lane_mat.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
		_lane_mat.cull_mode = BaseMaterial3D.CULL_DISABLED
		_lane_mat.no_depth_test = false
		_lane_mat.albedo_color = Color(beam_color.r, beam_color.g, beam_color.b, 0.22)
	var a := src.global_position
	for l in mini(lanes, lane_ends.size()):
		var end := get_node_or_null(lane_ends[l]) as Node3D
		if end == null:
			continue
		var b := end.global_position
		var stop := blocker(l)
		if not stop.is_empty():
			b = a.lerp(b, float(stop[0]))
		var dist := a.distance_to(b)
		if dist < 0.02:
			continue
		var mi := MeshInstance3D.new()
		mi.name = "Lane%d" % l
		var cyl := CylinderMesh.new()
		cyl.top_radius = beam_width * 0.5
		cyl.bottom_radius = beam_width * 0.35
		cyl.height = dist
		cyl.radial_segments = 6
		cyl.rings = 1
		mi.mesh = cyl
		mi.material_override = _lane_mat
		mi.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
		add_child(mi)
		mi.global_position = (a + b) * 0.5
		# A cylinder runs along its Y axis: point it from a to b.
		var y := (b - a).normalized()
		var x := y.cross(Vector3.FORWARD if absf(y.z) < 0.99 else Vector3.RIGHT).normalized()
		mi.global_basis = Basis(x, y, x.cross(y))
		_lane_beams.append(mi)
