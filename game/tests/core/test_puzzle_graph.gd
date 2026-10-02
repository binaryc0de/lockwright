extends GdUnitTestSuite

const TestRoom := preload("res://tests/helpers/test_room.gd")

var graph: PuzzleGraph
var state: WorldState


func before_test() -> void:
	var m := TestRoom.manifest()
	graph = PuzzleGraph.new(m.puzzles, m.exit_puzzle)
	state = WorldState.new()


func test_roots_are_open_first() -> void:
	assert_array(graph.open_puzzles(state)).contains_exactly(["find_uv", "hack"])


func test_condition_needs_prerequisites() -> void:
	# Cabinet unlocked before the torch was found: open_cabinet must wait.
	state.nodes["Cabinet/Keypad"] = {"state": "unlocked"}
	assert_array(graph.evaluate(state, 10.0)).is_empty()
	state.picked_up["uv_torch"] = true
	assert_array(graph.evaluate(state, 11.0)).contains_exactly(["find_uv", "open_cabinet"])
	assert_float(state.puzzle("open_cabinet")["solved_at"]).is_equal(11.0)


func test_solves_are_sticky() -> void:
	state.picked_up["uv_torch"] = true
	graph.evaluate(state, 1.0)
	state.picked_up.clear()
	graph.evaluate(state, 2.0)
	assert_bool(state.is_solved("find_uv")).is_true()


func test_flag_and_compound_conditions() -> void:
	state.flags_accepted["intranet"] = 5.0
	assert_array(graph.evaluate(state, 5.0)).contains_exactly(["hack"])
	assert_bool(PuzzleGraph.condition_holds({"any_of": [{"item_picked_up": "nope"}, {"flag_accepted": {"challenge": "intranet"}}]}, state)).is_true()
	assert_bool(PuzzleGraph.condition_holds({"all_of": [{"item_picked_up": "nope"}, {"flag_accepted": {"challenge": "intranet"}}]}, state)).is_false()


func test_dependents_counts_transitive_children() -> void:
	assert_int(graph.dependents("find_uv")).is_equal(3)  # open_cabinet, power, escape
	assert_int(graph.dependents("escape")).is_equal(0)


func test_hints_reveal_in_order_only_for_open_puzzles() -> void:
	var hints := HintService.new(graph)
	assert_dict(hints.reveal_next(state, "power")).contains_key_value("error", "not_open")
	assert_dict(hints.reveal_next(state, "find_uv")).contains_key_value("text", "h1a")
	assert_dict(hints.reveal_next(state, "find_uv")).contains_key_value("tier", 2)
	hints.reveal_next(state, "find_uv")
	assert_dict(hints.reveal_next(state, "find_uv")).contains_key_value("error", "no_more_hints")
	assert_array(hints.revealed(state, "find_uv")).contains_exactly(["h1a", "h1b", "h1c"])
	# find_uv has a hint now, so the nudge goes to the other open puzzle.
	assert_str(hints.nudge_target(state)).is_equal("hack")
