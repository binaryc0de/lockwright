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
## Difficulty levels the room offers ([{id, title, description, ...}]); the
## first is the default. Rooms without the section have one, "standard".
var difficulties: Array:
	get:
		var d: Array = data.get("difficulties", [])
		return d if not d.is_empty() else [{"id": "standard", "title": "Standard"}]
var default_difficulty: String:
	get: return str(difficulties[0].get("id", "standard"))
## The difficulty this manifest has been specialised to (for_difficulty).
var difficulty: String:
	get: return str(data.get("_difficulty", default_difficulty))


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


func has_difficulty(id: String) -> bool:
	return difficulties.any(func(d: Dictionary) -> bool: return d.get("id") == id)


## A copy specialised to difficulty `id` ("" or unknown: the default): that
## level's `puzzles` and `challenges` entries replace fields of the puzzles and
## challenges with the same id, and its `solution` replaces the solution.
func for_difficulty(id: String) -> RoomManifest:
	if not has_difficulty(id):
		if not id.is_empty():
			push_warning("room %s has no difficulty %s; using %s" % [self.id, id, default_difficulty])
		id = default_difficulty
	var d: Dictionary = data.duplicate(true)
	d["_difficulty"] = id
	for level: Dictionary in difficulties:
		if level.get("id") != id:
			continue
		for section: String in ["puzzles", "challenges"]:
			var overrides: Dictionary = level.get(section, {})
			var list: Array = d.get("puzzles", []) if section == "puzzles" else d.get("ctf", {}).get("challenges", [])
			for entry: Dictionary in list:
				for field: String in overrides.get(entry.get("id"), {}):
					var v: Variant = overrides[entry.get("id")][field]
					entry[field] = v.duplicate(true) if (v is Array or v is Dictionary) else v
		if level.has("solution"):
			d["solution"] = level["solution"].duplicate(true)
	return RoomManifest.from_dict(d)


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
