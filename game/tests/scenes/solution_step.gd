extends Node
## Prints the index of the solution step after which a puzzle is solved:
##   godot --headless --path game res://tests/scenes/solution_step.tscn -- --room clockmaker --puzzle strike_true
## Used by tools/play_from.sh. Replays room.yaml's solution through intents,
## like the room tests.


func _ready() -> void:
	var args := OS.get_cmdline_user_args()
	var room_id := _arg(args, "--room", "")
	var puzzle := _arg(args, "--puzzle", "")
	var loader := RoomLoader.new()
	if room_id.is_empty() or puzzle.is_empty() or not loader.load_room(room_id, ""):
		printerr("usage: --room ID --puzzle PUZZLE (%s)" % loader.error)
		get_tree().quit(1)
		return
	var room := loader.instantiate()
	add_child(room)
	var auth := RoomAuthority.new()
	auth.allow_unpositioned = true
	add_child(auth)
	auth.setup(loader.manifest, room, "solution-step")
	var nodes := {}
	for n: EBNode in auth.nodes():
		nodes[n.eb_path] = n
	var steps := loader.manifest.solution
	for i in steps.size():
		var intent := SolutionPlayer.intent_for(steps[i], nodes, auth.state.vars)
		if not intent.is_empty() and not intent.has("error"):
			auth.handle_intent("p1", intent["path"], intent["verb"], intent["payload"])
		if auth.state.is_solved(puzzle):
			print("solved_at_step %d" % i)
			get_tree().quit(0)
			return
	printerr("%s is never solved by the solution" % puzzle)
	get_tree().quit(1)


static func _arg(args: PackedStringArray, key: String, def: String) -> String:
	var i := args.find(key)
	return args[i + 1] if i >= 0 and i + 1 < args.size() else def
