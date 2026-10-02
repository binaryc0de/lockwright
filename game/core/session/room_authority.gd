class_name RoomAuthority
extends Node
## Server-side owner of one session (PLAN.md 7.2): receives intents,
## validates them, mutates the WorldState, and announces every change through
## signals. In M1 the client listens in-process; from M2 the network layer
## turns these signals into RPCs. Nothing else may mutate the WorldState.

signal node_state_changed(path: String, state: Dictionary)
signal inventory_changed(inventory: Array[String])
signal evidence_changed(evidence: Array[Dictionary])
signal puzzles_changed(puzzles: Dictionary)
signal puzzle_solved(puzzle_id: String)
signal hint_revealed(puzzle_id: String, tier: int, text: String, automatic: bool)
signal narrated(text: String)
signal flag_accepted(challenge_id: String)
signal time_up
signal session_finished(won: bool)
## Coarse session log for the platform (M3 posts these to /internal/.../events).
## Never contains flag values.
signal event_logged(kind: String, data: Dictionary)

## Max distance between a player and the node they act on (3 m reach + slack).
const MAX_REACH_M := 4.5

var session_id: String = ""
var manifest: RoomManifest
var room: Node
var state: WorldState
var graph: PuzzleGraph
var hints: HintService
var flags: FlagValidator = DevFlagValidator.new()
## Injectable clock (unix seconds) so tests can control time.
var clock: Callable = Time.get_unix_time_from_system
## player id -> last known world position (sanity checks only).
var player_positions: Dictionary = {}
## Trusted callers only (tests, solution replay): skip the reach check for
## players that never reported a position. Never set on a networked server.
var allow_unpositioned: bool = false

var _nodes: Dictionary = {}   # path -> EBNode
## node path -> puzzle ids whose solved_when watches that node; item_id and
## challenge id -> puzzle ids likewise. Intents on a watched node are refused
## until those puzzles' prerequisites are solved (PLAN.md 7.2).
var _gates_by_path: Dictionary = {}
var _gates_by_item: Dictionary = {}
var _gates_by_challenge: Dictionary = {}
var _last_progress: float = 0.0


## Prepares the session. `room_instance` must already be in the scene tree
## (or at least have its children) so node paths resolve. A non-empty
## `snapshot` restores a previous session instead of starting fresh.
func setup(p_manifest: RoomManifest, room_instance: Node, p_session_id: String, snapshot: Dictionary = {}) -> void:
	manifest = p_manifest
	room = room_instance
	session_id = p_session_id
	graph = PuzzleGraph.new(manifest.puzzles, manifest.exit_puzzle)
	hints = HintService.new(graph)
	var now: float = clock.call()
	if snapshot.is_empty():
		state = WorldState.new()
		state.started_at = now
		state.duration_s = manifest.duration_minutes * 60
		state.auto_nudge = manifest.auto_nudge_minutes > 0
		state.vars = generate_vars(manifest.data.get("variables", {}), session_id)
		state.challenges = flags.start_challenges(session_id, manifest.challenges)
	else:
		state = WorldState.from_dict(snapshot)
	for id in graph.ids():
		state.puzzle(id)
	_nodes = EBNode.register_all(room, self)
	for path: String in _nodes:
		if not state.nodes.has(path):
			state.nodes[path] = (_nodes[path] as EBNode)._initial_state()
	# The authority's own scene always mirrors the state it owns (as copies:
	# nothing outside the authority may hold a writable reference into it).
	for path: String in _nodes:
		(_nodes[path] as EBNode).receive_state(state.nodes[path].duplicate(true))
	_build_gates()
	_last_progress = now
	graph.evaluate(state, now)
	event_logged.emit("session_started", {"room": manifest.id, "restored": not snapshot.is_empty()})


## Per-session randomisation of room.yaml `variables`, deterministic per session id.
static func generate_vars(spec: Dictionary, seed_text: String) -> Dictionary:
	var rng := RandomNumberGenerator.new()
	rng.seed = hash(seed_text)
	var out := {}
	var names := spec.keys()
	names.sort()
	for name: String in names:
		var v: Dictionary = spec[name]
		match v.get("type"):
			"digits":
				var s := ""
				for i in int(v.get("length", 4)):
					s += str(rng.randi_range(0, 9))
				out[name] = s
			"letters":
				var s := ""
				for i in int(v.get("length", 4)):
					s += char(65 + rng.randi_range(0, 25))
				out[name] = s
			"choice":
				var choices: Array = v.get("choices", [])
				out[name] = choices[rng.randi_range(0, choices.size() - 1)] if not choices.is_empty() else ""
	return out


func node(path: String) -> EBNode:
	return _nodes.get(path)


func nodes() -> Array:
	return _nodes.values()


# --- Intents (PLAN.md 7.2: clients send intents, the server decides) ------

## Entry point for every player action on an SDK node. Returns a result for
## the requesting player: {ok: bool, error?: String, message?: String, ...}.
func handle_intent(player_id: String, path: String, verb: String, payload: Dictionary) -> Dictionary:
	var n: EBNode = _nodes.get(path)
	if n == null:
		return {"ok": false, "error": "unknown_node"}
	if not _in_reach(player_id, n):
		return {"ok": false, "error": "out_of_reach"}
	if not is_available(n):
		return {"ok": false, "error": "unavailable"}
	if not _prerequisites_met(n):
		return {"ok": false, "error": "not_yet", "message": "Nothing happens. Something else must come first."}
	var item_path: String = payload.get("item", "")
	if not item_path.is_empty() and not item_path in state.inventory:
		return {"ok": false, "error": "item_not_held"}
	var result: Dictionary = n._server_intent(player_id, verb, payload)
	_after_change()
	return result


func request_hint(player_id: String, puzzle_id: String) -> Dictionary:
	var r := hints.reveal_next(state, puzzle_id)
	if r["ok"]:
		event_logged.emit("hint_revealed", {"player": player_id, "puzzle": puzzle_id, "tier": r["tier"]})
		hint_revealed.emit(puzzle_id, r["tier"], r["text"], false)
		puzzles_changed.emit(state.puzzles)
	return r


func set_auto_nudge(player_id: String, enabled: bool) -> void:
	state.auto_nudge = enabled
	event_logged.emit("auto_nudge", {"player": player_id, "enabled": enabled})


func add_note(player_id: String, author: String, text: String) -> Dictionary:
	text = text.strip_edges().left(500)
	if text.is_empty():
		return {"ok": false, "error": "empty"}
	state.evidence.append({"kind": "note", "id": state.next_note_id, "text": text, "author": author})
	state.next_note_id += 1
	evidence_changed.emit(state.evidence)
	return {"ok": true}


func remove_note(_player_id: String, note_id: int) -> Dictionary:
	for i in state.evidence.size():
		var e := state.evidence[i]
		if e["kind"] == "note" and int(e["id"]) == note_id:
			state.evidence.remove_at(i)
			evidence_changed.emit(state.evidence)
			return {"ok": true}
	return {"ok": false, "error": "unknown_note"}


func update_player_position(player_id: String, pos: Vector3) -> void:
	player_positions[player_id] = pos


func _in_reach(player_id: String, n: EBNode) -> bool:
	if not n.is_inside_tree():
		return false
	if not player_positions.has(player_id):
		return allow_unpositioned
	return (player_positions[player_id] as Vector3).distance_to(n.global_position) <= MAX_REACH_M


## Server-side availability, decided from the WorldState only (never from
## scene visibility, which is presentation): the node's own rule, and no
## closed ContainerProp holding it in its `contents`.
func is_available(n: EBNode) -> bool:
	if not n._server_available():
		return false
	var p := n.get_parent()
	while p != null and p != room:
		if p is ContainerProp:
			var c := p as ContainerProp
			var contents := c.get_node_or_null(c.contents)
			if contents and (contents == n or contents.is_ancestor_of(n)) \
					and state.node_state(c.eb_path).get("state") != "open":
				return false
		p = p.get_parent()
	return true


func _prerequisites_met(n: EBNode) -> bool:
	var gates: Array = _gates_by_path.get(n.eb_path, [])
	if n is Item:
		gates = gates + _gates_by_item.get((n as Item).item_id, [])
	if n is Terminal:
		gates = gates + _gates_by_challenge.get((n as Terminal).challenge_id, [])
	for pid: String in gates:
		if state.is_solved(pid):
			continue
		for r: String in graph.requires(pid):
			if not state.is_solved(r):
				return false
	return true


func _build_gates() -> void:
	_gates_by_path = {}
	_gates_by_item = {}
	_gates_by_challenge = {}
	for p: Dictionary in manifest.puzzles:
		_index_condition(p.get("solved_when", {}), p["id"])


func _index_condition(c: Dictionary, pid: String) -> void:
	if c.has("node_state"):
		_gates_by_path.get_or_add(c["node_state"]["path"], []).append(pid)
	elif c.has("item_picked_up"):
		_gates_by_item.get_or_add(c["item_picked_up"], []).append(pid)
	elif c.has("flag_accepted"):
		_gates_by_challenge.get_or_add(c["flag_accepted"]["challenge"], []).append(pid)
	for sub: Dictionary in c.get("all_of", []) + c.get("any_of", []):
		_index_condition(sub, pid)


# --- Mutation API used by SDK nodes on the server ------------------------

func set_node_state(path: String, patch: Dictionary) -> void:
	var cur: Dictionary = state.nodes.get(path, {}).duplicate()
	cur.merge(patch, true)
	state.nodes[path] = cur
	var n: EBNode = _nodes.get(path)
	if n:
		n.receive_state(cur.duplicate(true))
	node_state_changed.emit(path, cur.duplicate(true))


## Moves an Item into the team inventory.
func give_item(item_path: String, item_id: String, player_id: String) -> void:
	if item_path in state.inventory:
		return
	state.inventory.append(item_path)
	state.picked_up[item_id] = true
	event_logged.emit("item_picked_up", {"player": player_id, "item": item_id})
	inventory_changed.emit(state.inventory)


## Removes an Item from the team inventory for good.
func consume_item(item_path: String) -> void:
	if not item_path in state.inventory:
		return
	state.inventory.erase(item_path)
	set_node_state(item_path, {"state": "consumed"})
	inventory_changed.emit(state.inventory)


func pin_document(path: String, title: String, player_id: String) -> void:
	for e in state.evidence:
		if e["kind"] == "doc" and e["path"] == path:
			return
	state.evidence.append({"kind": "doc", "path": path, "title": title, "found_by": player_id})
	evidence_changed.emit(state.evidence)


## Calls `_server_activate()` on the node at `target_path` (FlagGate,
## PatchPanel and Lever targets use this).
func activate(target_path: String) -> void:
	var t: EBNode = _nodes.get(target_path)
	if t == null:
		push_error("activate: no SDK node at %s" % target_path)
		return
	t._server_activate()


func narrate(text: String) -> void:
	narrated.emit(text)


func resolve(text: String) -> String:
	return EBTemplate.render(text, state.vars)


## Flag submission (PLAN.md 7.5). The value is passed to the validator and
## then dropped: it is never stored, logged, or emitted.
func submit_flag(player_id: String, challenge_id: String, value: String) -> Dictionary:
	if manifest.challenge(challenge_id).is_empty():
		return {"ok": false, "error": "unknown_challenge"}
	if state.flags_accepted.has(challenge_id):
		return {"ok": true, "already": true}
	for pid: String in _gates_by_challenge.get(challenge_id, []):
		for r: String in graph.requires(pid):
			if not state.is_solved(r):
				return {"ok": false, "error": "not_yet", "message": "The system isn't ready for that yet."}
	var r: Dictionary = flags.validate(session_id, challenge_id, value, player_id)
	event_logged.emit("flag_submitted", {"player": player_id, "challenge": challenge_id, "accepted": r.get("accepted", false)})
	if not r.get("accepted", false):
		var out := {"ok": false, "error": "wrong_flag"}
		if r.has("retry_after_s"):
			out["retry_after_s"] = r["retry_after_s"]
		return out
	state.flags_accepted[challenge_id] = clock.call()
	flag_accepted.emit(challenge_id)
	for n: EBNode in _nodes.values():
		n._server_flag_accepted(challenge_id)
	return {"ok": true}


# --- Progress, timer, end of session -------------------------------------

func _after_change() -> void:
	var now: float = clock.call()
	var newly := graph.evaluate(state, now)
	if newly.is_empty():
		return
	_last_progress = now
	for id in newly:
		event_logged.emit("puzzle_solved", {"puzzle": id})
		puzzle_solved.emit(id)
	puzzles_changed.emit(state.puzzles)
	if not state.finished and state.is_solved(graph.exit_puzzle):
		state.finished = true
		state.won = true
		state.finished_at = now
		event_logged.emit("session_finished", {"won": true})
		session_finished.emit(true)


## Advances timers. Called every frame by the node's _process; tests call it
## directly with a controlled clock.
func tick() -> void:
	if state == null or state.finished:
		return
	var now: float = clock.call()
	if not state.timed_out and state.remaining_s(now) <= 0.0:
		state.timed_out = true
		event_logged.emit("time_up", {})
		time_up.emit()
	var nudge_s := manifest.auto_nudge_minutes * 60
	if state.auto_nudge and nudge_s > 0 and now - _last_progress >= nudge_s:
		_last_progress = now
		var target := hints.nudge_target(state)
		if not target.is_empty():
			var r := hints.reveal_next(state, target)
			if r["ok"]:
				event_logged.emit("hint_revealed", {"puzzle": target, "tier": r["tier"], "automatic": true})
				hint_revealed.emit(target, r["tier"], r["text"], true)
				puzzles_changed.emit(state.puzzles)


func _process(_delta: float) -> void:
	tick()


func snapshot() -> Dictionary:
	return state.to_dict()
