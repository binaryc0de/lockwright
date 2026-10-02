class_name WorldState
extends RefCounted
## The authoritative state of one session (PLAN.md 7.2). This table is the
## snapshot: everything a rejoining client or a restarted server needs.
## Only RoomAuthority mutates it.

const SNAPSHOT_VERSION := 1

## node path (relative to the room root) -> state Dictionary. Every SDK node
## state has a string "state" key used by node_state conditions.
var nodes: Dictionary = {}
## Team inventory: ordered node paths of Item nodes currently held.
var inventory: Array[String] = []
## item_id -> true once any Item with that id has been picked up (sticky).
var picked_up: Dictionary = {}
## Evidence board entries: {kind: "doc", path, title} | {kind: "note", id, text, author}.
var evidence: Array[Dictionary] = []
## puzzle id -> {solved: bool, solved_at: float, hints_revealed: int}
var puzzles: Dictionary = {}
## challenge id -> unix time accepted
var flags_accepted: Dictionary = {}
## Per-session room variables (room.yaml `variables`), resolved at session start.
var vars: Dictionary = {}
var started_at: float = 0.0
var duration_s: int = 3600
var finished: bool = false
var won: bool = false
var finished_at: float = 0.0
var auto_nudge: bool = true
var timed_out: bool = false
var next_note_id: int = 1
## challenge id -> connection handle shown on Terminal props, e.g.
## {url, host, port, note}. Filled by the platform in M3; a dev stub in M1.
var challenges: Dictionary = {}


func node_state(path: String) -> Dictionary:
	return nodes.get(path, {})


func puzzle(id: String) -> Dictionary:
	if not puzzles.has(id):
		puzzles[id] = {"solved": false, "solved_at": 0.0, "hints_revealed": 0}
	return puzzles[id]


func is_solved(id: String) -> bool:
	return puzzles.has(id) and puzzles[id]["solved"]


func hints_used() -> int:
	var n := 0
	for id: String in puzzles:
		n += int(puzzles[id]["hints_revealed"])
	return n


func remaining_s(now: float) -> float:
	return maxf(0.0, started_at + duration_s - now)


func to_dict() -> Dictionary:
	return {
		"version": SNAPSHOT_VERSION,
		"nodes": nodes.duplicate(true),
		"inventory": inventory.duplicate(),
		"picked_up": picked_up.duplicate(),
		"evidence": evidence.duplicate(true),
		"puzzles": puzzles.duplicate(true),
		"flags_accepted": flags_accepted.duplicate(),
		"vars": vars.duplicate(),
		"started_at": started_at,
		"duration_s": duration_s,
		"finished": finished,
		"won": won,
		"finished_at": finished_at,
		"auto_nudge": auto_nudge,
		"timed_out": timed_out,
		"next_note_id": next_note_id,
		"challenges": challenges.duplicate(true),
	}


## Builds a WorldState from a snapshot. Survives a JSON round-trip (numbers
## come back as floats).
static func from_dict(d: Dictionary) -> WorldState:
	var s := WorldState.new()
	if int(d.get("version", 0)) != SNAPSHOT_VERSION:
		push_error("snapshot version %s not supported" % d.get("version"))
		return s
	s.nodes = d.get("nodes", {}).duplicate(true)
	s.inventory.assign(d.get("inventory", []))
	s.picked_up = d.get("picked_up", {}).duplicate()
	s.evidence.assign(d.get("evidence", []).duplicate(true))
	s.puzzles = d.get("puzzles", {}).duplicate(true)
	for id: String in s.puzzles:
		s.puzzles[id]["hints_revealed"] = int(s.puzzles[id]["hints_revealed"])
	s.flags_accepted = d.get("flags_accepted", {}).duplicate()
	s.vars = d.get("vars", {}).duplicate()
	s.started_at = float(d.get("started_at", 0.0))
	s.duration_s = int(d.get("duration_s", 3600))
	s.finished = bool(d.get("finished", false))
	s.won = bool(d.get("won", false))
	s.finished_at = float(d.get("finished_at", 0.0))
	s.auto_nudge = bool(d.get("auto_nudge", true))
	s.timed_out = bool(d.get("timed_out", false))
	s.next_note_id = int(d.get("next_note_id", 1))
	s.challenges = d.get("challenges", {}).duplicate(true)
	return s
