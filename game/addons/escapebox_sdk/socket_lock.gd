@icon("res://addons/escapebox_sdk/icons/eb_node.svg")
class_name SocketLock
extends Lock
## Opens when its Socket children hold one of the right arrangements (wheels
## on a clock's arbors, statues on plinths, books in a shelf). Any accepted
## item can be seated anywhere and taken back, so choosing is the puzzle.
## A full but wrong arrangement counts as a failed attempt.
## State: Lock's.

## item_ids the sockets take (the right ones and the spare ones).
@export var accepts: Array[String] = []
## Right arrangements, "|"-separated, each "socket:item_id,..." over every
## socket, e.g. "A:wheel_20,B:wheel_30|A:wheel_30,B:wheel_20". May use {{vars}}.
## Server-only.
@export var solutions: String = ""
## Told to players when every socket is full but the arrangement is wrong.
@export var wrong_message: String = "Nothing happens."
## Told to players who use the lock itself rather than a socket.
@export var empty_message: String = "Something has to be fitted here."


func _init() -> void:
	verbs = ["use"]


func client_interact(_item_path: String = "") -> void:
	Game.toast(empty_message)


func sockets() -> Array[Socket]:
	var out: Array[Socket] = []
	for s: Socket in find_children("*", "Socket", true, false):
		if s.lock() == self:
			out.append(s)
	return out


## Parses solutions into [{socket: item_id}, ...]; malformed entries are skipped.
static func parse_solutions(text: String) -> Array[Dictionary]:
	var out: Array[Dictionary] = []
	for alt in text.split("|", false):
		var m := {}
		var ok := true
		for pair in alt.split(",", false):
			var kv := pair.split(":")
			if kv.size() != 2 or kv[0].strip_edges().is_empty() or kv[1].strip_edges().is_empty():
				ok = false
				break
			m[kv[0].strip_edges()] = kv[1].strip_edges()
		if ok and not m.is_empty():
			out.append(m)
	return out


## The current arrangement {socket_id: item_id} of seated sockets.
func arrangement() -> Dictionary:
	var m := {}
	for s in sockets():
		if not s.seated_id().is_empty():
			m[s.id()] = s.seated_id()
	return m


## Server: a socket was filled. Returns the result for the player who did it.
func _server_socket_changed() -> Dictionary:
	if is_unlocked():
		return {"ok": true, "already": true}
	var now := arrangement()
	if now.size() < sockets().size():
		return {"ok": true}
	var attempts: int = int(my_state().get("attempts", 0)) + 1
	if is_powered() and authority.prerequisites_met(self):
		for want in parse_solutions(authority.resolve(solutions)):
			if want == now:
				set_state({"state": "unlocked", "attempts": attempts, "last_ok": true})
				return {"ok": true, "opened": true}
	set_state({"attempts": attempts, "last_ok": false})
	return {"ok": true, "message": wrong_message if is_powered() else dead_message}


func _server_intent(_player_id: String, _verb: String, _payload: Dictionary) -> Dictionary:
	return {"ok": false, "error": "needs_item", "message": empty_message}


func _server_activate() -> void:
	# Power arriving later re-checks a train that is already complete.
	var was_powered := is_powered()
	super()
	if not was_powered and is_powered() and not is_unlocked() and arrangement().size() == sockets().size():
		for want in parse_solutions(authority.resolve(solutions)):
			if want == arrangement():
				set_state({"state": "unlocked", "last_ok": true})
