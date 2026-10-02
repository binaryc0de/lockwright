class_name RoomManifest
extends RefCounted
## Runtime view of a room manifest. Reads room.json, which roomcheck
## generates from room.yaml (ADR-0006).

var data: Dictionary = {}
var id: String:
	get: return data.get("id", "")
var title: String:
	get: return data.get("title", "")
var version: String:
	get: return data.get("version", "")
var entry_scene: String:
	get: return data.get("entry_scene", "")
var duration_minutes: int:
	get: return int(data.get("mode", {}).get("duration_minutes", 60))
var auto_nudge_minutes: int:
	get: return int(data.get("mode", {}).get("auto_nudge_minutes", 6))
var puzzles: Array:
	get: return data.get("puzzles", [])
var exit_puzzle: String:
	get: return data.get("exit", {}).get("puzzle", "")
var challenges: Array:
	get: return data.get("ctf", {}).get("challenges", [])
var solution: Array:
	get: return data.get("solution", [])


static func from_dict(d: Dictionary) -> RoomManifest:
	var m := RoomManifest.new()
	m.data = d
	return m


## Loads res://rooms/<room_id>/room.json. Returns null and pushes an error
## if it is missing, unparseable, or its id does not match.
static func load_room(room_id: String) -> RoomManifest:
	var path := "res://rooms/%s/room.json" % room_id
	if not FileAccess.file_exists(path):
		push_error("room manifest not found: %s" % path)
		return null
	var parsed: Variant = JSON.parse_string(FileAccess.get_file_as_string(path))
	if not parsed is Dictionary:
		push_error("room manifest is not a JSON object: %s" % path)
		return null
	var m := from_dict(parsed)
	if m.id != room_id:
		push_error("room manifest id %s does not match %s" % [m.id, room_id])
		return null
	return m


func puzzle(id: String) -> Dictionary:
	for p: Dictionary in puzzles:
		if p.get("id") == id:
			return p
	return {}


func challenge(id: String) -> Dictionary:
	for c: Dictionary in challenges:
		if c.get("id") == id:
			return c
	return {}


## Reads a briefing markdown file (relative to the room directory).
func briefing(key: String) -> String:
	var rel: String = data.get("briefing", {}).get(key, "")
	if rel.is_empty():
		return ""
	var path := "res://rooms/%s/%s" % [id, rel]
	return FileAccess.get_file_as_string(path) if FileAccess.file_exists(path) else ""
