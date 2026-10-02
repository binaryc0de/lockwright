class_name SnapshotStore
extends RefCounted
## Session snapshot persistence for the dedicated server (PLAN.md 7.3,
## ADR-0015): a JSON file per session in M2; M3 posts to the platform instead.
## Writes go to a temp file then rename, so a crash never leaves half a file.

var path: String = ""


func _init(p_path: String) -> void:
	path = p_path


func exists() -> bool:
	return not path.is_empty() and FileAccess.file_exists(path)


## Returns the stored snapshot, or {} if there is none or it is unreadable.
func load_snapshot() -> Dictionary:
	if not exists():
		return {}
	var parsed = JSON.parse_string(FileAccess.get_file_as_string(path))
	if parsed is Dictionary:
		return parsed
	push_error("snapshot %s is not valid JSON; starting fresh" % path)
	return {}


func save(snapshot: Dictionary) -> bool:
	if path.is_empty():
		return false
	DirAccess.make_dir_recursive_absolute(path.get_base_dir())
	var tmp := path + ".tmp"
	var f := FileAccess.open(tmp, FileAccess.WRITE)
	if f == null:
		push_error("cannot write snapshot %s: %s" % [tmp, error_string(FileAccess.get_open_error())])
		return false
	f.store_string(JSON.stringify(snapshot))
	f.close()
	return DirAccess.rename_absolute(tmp, path) == OK
