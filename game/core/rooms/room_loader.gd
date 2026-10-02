class_name RoomLoader
extends RefCounted
## Loads a room (PLAN.md 8.1). From a pack: mounts the .pck without
## replacing existing files, then reads the manifest. Dev mode: the room is
## already under res://rooms/<room_id>/.

var error: String = ""
var manifest: RoomManifest
var scene: PackedScene


## Loads `room_id`, mounting `pack_path` first when given. On failure returns
## false and sets `error`.
func load_room(room_id: String, pack_path: String = "") -> bool:
	error = ""
	if not RoomLoader.valid_id(room_id):
		error = "invalid room id %s" % room_id
		return false
	if not pack_path.is_empty():
		if not FileAccess.file_exists(pack_path):
			error = "pack not found: %s" % pack_path
			return false
		# Never replace_files=true: a pack must not override engine or core files.
		if not ProjectSettings.load_resource_pack(pack_path, false):
			error = "could not mount pack %s" % pack_path
			return false
	manifest = RoomManifest.load_room(room_id)
	if manifest == null:
		error = "room %s has no valid manifest%s" % [room_id, " in pack" if pack_path else ""]
		return false
	if not manifest.entry_scene.begins_with("res://rooms/%s/" % room_id):
		error = "entry scene %s is outside the room" % manifest.entry_scene
		return false
	scene = load(manifest.entry_scene) as PackedScene
	if scene == null:
		error = "cannot load entry scene %s" % manifest.entry_scene
		return false
	return true


## Instantiates the entry scene; null (with `error`) if its root is not a RoomRoot.
func instantiate() -> RoomRoot:
	var inst := scene.instantiate()
	if not inst is RoomRoot:
		error = "entry scene root must use the RoomRoot script"
		inst.free()
		return null
	return inst


static func valid_id(id: String) -> bool:
	return RegEx.create_from_string("^[a-z0-9_]+$").search(id) != null


## Room ids available in res://rooms (dev mode and mounted packs).
static func available_rooms() -> PackedStringArray:
	var out := PackedStringArray()
	for d in DirAccess.get_directories_at("res://rooms"):
		if FileAccess.file_exists("res://rooms/%s/room.json" % d):
			out.append(d)
	return out
