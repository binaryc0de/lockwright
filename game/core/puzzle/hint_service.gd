class_name HintService
extends RefCounted
## Tiered hints (PLAN.md 6.6): three or more tiers per puzzle, revealed in
## order, last tier is the answer. Every reveal is recorded in the world state
## so it is counted on the end screen and survives restarts.

var _graph: PuzzleGraph


func _init(graph: PuzzleGraph) -> void:
	_graph = graph


func tiers(puzzle_id: String) -> Array:
	return _graph.get_puzzle(puzzle_id).get("hints", [])


func revealed(state: WorldState, puzzle_id: String) -> Array[String]:
	var out: Array[String] = []
	var n: int = state.puzzle(puzzle_id)["hints_revealed"]
	var t := tiers(puzzle_id)
	for i in mini(n, t.size()):
		out.append(t[i])
	return out


## Reveals the next tier for an open puzzle. Returns {ok, tier, text} or
## {ok: false, error}.
func reveal_next(state: WorldState, puzzle_id: String) -> Dictionary:
	if not puzzle_id in _graph.open_puzzles(state):
		return {"ok": false, "error": "not_open"}
	var p := state.puzzle(puzzle_id)
	var t := tiers(puzzle_id)
	if p["hints_revealed"] >= t.size():
		return {"ok": false, "error": "no_more_hints"}
	p["hints_revealed"] += 1
	return {"ok": true, "tier": p["hints_revealed"], "text": t[p["hints_revealed"] - 1]}


## Open puzzle the nudge should help with: the one blocking the most other
## puzzles, among those with no hint revealed yet. "" if none.
func nudge_target(state: WorldState) -> String:
	var best := ""
	var best_score := -1
	for id in _graph.open_puzzles(state):
		if state.puzzle(id)["hints_revealed"] > 0 or tiers(id).is_empty():
			continue
		var score := _graph.dependents(id)
		if score > best_score:
			best = id
			best_score = score
	return best
