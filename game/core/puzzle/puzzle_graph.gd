class_name PuzzleGraph
extends RefCounted
## Server-side puzzle dependency chart (PLAN.md 8.3). Evaluates `solved_when`
## conditions against the world state. A puzzle is solved when its condition
## holds and all of its prerequisites are solved; solves are sticky.

var _puzzles: Array = []          # manifest puzzle dicts, in declaration order
var _by_id: Dictionary = {}
var exit_puzzle: String = ""


func _init(manifest_puzzles: Array, exit_id: String) -> void:
	_puzzles = manifest_puzzles
	for p: Dictionary in manifest_puzzles:
		_by_id[p["id"]] = p
	exit_puzzle = exit_id


func ids() -> Array[String]:
	var out: Array[String] = []
	for p: Dictionary in _puzzles:
		out.append(p["id"])
	return out


func get_puzzle(id: String) -> Dictionary:
	return _by_id.get(id, {})


func requires(id: String) -> Array:
	return _by_id.get(id, {}).get("requires", [])


## Unsolved puzzles whose prerequisites are all solved.
func open_puzzles(state: WorldState) -> Array[String]:
	var out: Array[String] = []
	for p: Dictionary in _puzzles:
		var id: String = p["id"]
		if state.is_solved(id):
			continue
		if requires(id).all(func(r: String) -> bool: return state.is_solved(r)):
			out.append(id)
	return out


## Marks every puzzle whose condition now holds as solved (repeating until
## nothing changes, so chains resolve in one call). Returns the newly solved
## ids in solve order.
func evaluate(state: WorldState, now: float) -> Array[String]:
	var newly: Array[String] = []
	var changed := true
	while changed:
		changed = false
		for id in open_puzzles(state):
			if condition_holds(_by_id[id].get("solved_when", {}), state):
				var p := state.puzzle(id)
				p["solved"] = true
				p["solved_at"] = now
				newly.append(id)
				changed = true
	return newly


## The closed solved_when vocabulary (ADR-0005).
static func condition_holds(c: Dictionary, state: WorldState) -> bool:
	if c.has("item_picked_up"):
		return state.picked_up.has(c["item_picked_up"])
	if c.has("node_state"):
		var ns: Dictionary = c["node_state"]
		return state.node_state(ns["path"]).get("state", "") == ns["state"]
	if c.has("flag_accepted"):
		return state.flags_accepted.has(c["flag_accepted"]["challenge"])
	if c.has("all_of"):
		return (c["all_of"] as Array).all(func(s: Dictionary) -> bool: return condition_holds(s, state))
	if c.has("any_of"):
		return (c["any_of"] as Array).any(func(s: Dictionary) -> bool: return condition_holds(s, state))
	push_error("unknown solved_when condition: %s" % c)
	return false


## Number of puzzles that (transitively) depend on `id`. Used to pick the
## most blocking open puzzle for the automatic hint nudge.
func dependents(id: String) -> int:
	var seen := {}
	var frontier: Array = [id]
	while not frontier.is_empty():
		var cur: String = frontier.pop_back()
		for p: Dictionary in _puzzles:
			if cur in p.get("requires", []) and not seen.has(p["id"]):
				seen[p["id"]] = true
				frontier.append(p["id"])
	return seen.size()
