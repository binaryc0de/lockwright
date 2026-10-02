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
	if not _prepare(room_id, pack_path):
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


## Exported builds without --pack (ADR-0021): the newest
## `<room_id>.pck` or `<room_id>-<version>.pck` in a `packs/` directory next to
## the executable, or in user://packs/. "" if none. (Download from the platform
## comes with /download in M5.)
static func find_local_pack(room_id: String, dirs: PackedStringArray = []) -> String:
	if dirs.is_empty():
		dirs = [OS.get_executable_path().get_base_dir().path_join("packs"), ProjectSettings.globalize_path("user://packs")]
	var re := RegEx.create_from_string("^%s(-(\\d+)\\.(\\d+)\\.(\\d+))?\\.pck$" % room_id)
	var best := ""
	var best_ver := -1
	for d in dirs:
		if not DirAccess.dir_exists_absolute(d):
			continue
		for f in DirAccess.get_files_at(d):
			var m := re.search(f)
			if m == null:
				continue
			var ver := 0
			if not m.get_string(1).is_empty():
				ver = int(m.get_string(2)) * 1000000 + int(m.get_string(3)) * 1000 + int(m.get_string(4))
			if ver > best_ver:
				best_ver = ver
				best = d.path_join(f)
	return best


## Like load_room, but loads the entry scene on a worker thread while the
## main loop keeps running (await it), so a client keeps servicing its
## network link instead of freezing for seconds on a slow PC.
func load_room_async(room_id: String, pack_path: String, tree: SceneTree) -> bool:
	if not _prepare(room_id, pack_path):
		return false
	var path := manifest.entry_scene
	if ResourceLoader.load_threaded_request(path, "PackedScene", true) != OK:
		return load_room(room_id, "")  # pack already mounted; plain load
	while true:
		var st := ResourceLoader.load_threaded_get_status(path)
		if st == ResourceLoader.THREAD_LOAD_LOADED:
			break
		if st != ResourceLoader.THREAD_LOAD_IN_PROGRESS:
			error = "cannot load entry scene %s" % path
			return false
		await tree.process_frame
	scene = ResourceLoader.load_threaded_get(path) as PackedScene
	if scene == null:
		error = "cannot load entry scene %s" % path
		return false
	return true


## Validates the id, mounts the pack, reads the manifest.
func _prepare(room_id: String, pack_path: String = "") -> bool:
	error = ""
	if not RoomLoader.valid_id(room_id):
		error = "invalid room id %s" % room_id
		return false
	if pack_path.is_empty() and not FileAccess.file_exists("res://rooms/%s/room.json" % room_id):
		pack_path = RoomLoader.find_local_pack(room_id)
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
	return true


static func valid_id(id: String) -> bool:
	return RegEx.create_from_string("^[a-z0-9_]+$").search(id) != null


## Room ids available in res://rooms (dev mode and mounted packs).
static func available_rooms() -> PackedStringArray:
	var out := PackedStringArray()
	for d in DirAccess.get_directories_at("res://rooms"):
		if FileAccess.file_exists("res://rooms/%s/room.json" % d):
			out.append(d)
	return out
