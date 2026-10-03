class_name RoomPackFetcher
extends Node
## Downloads a room's pack from the platform into user://packs/ when the game
## does not have the room (ADR-0025): browsers always, desktop builds when no
## pack sits next to the executable. Verifies the platform's SHA-256 and
## reuses a cached copy whose hash still matches. Add it to the tree, then
## `await fetch(...)`.

signal progressed(fraction: float)

const DIR := "user://packs"

var error: String = ""


## The local path of `room_id`'s pack, or "" (with `error`) on failure.
func fetch(platform_url: String, room_id: String) -> String:
	error = ""
	var res := await _http_get(platform_url.trim_suffix("/") + "/api/catalog")
	if res.is_empty():
		return ""
	var catalog: Variant = JSON.parse_string((res["body"] as PackedByteArray).get_string_from_utf8())
	var pack: Dictionary = {}
	if catalog is Array:
		for r: Dictionary in catalog:
			if r.get("room_id") == room_id and r.get("pack") is Dictionary:
				pack = r["pack"]
	if pack.is_empty():
		error = "the platform has no pack for room %s" % room_id
		return ""
	var file := str(pack.get("file", "")).get_file()
	var want := str(pack.get("sha256", "")).to_lower()
	var path := DIR.path_join(file)
	if FileAccess.file_exists(path) and RoomPackFetcher.sha256_of(path) == want:
		return path
	DirAccess.make_dir_recursive_absolute(DIR)
	var part := path + ".part"
	res = await _http_get(platform_url.trim_suffix("/") + str(pack.get("url", "")), int(pack.get("size", 0)))
	if res.is_empty():
		return ""
	# Written here rather than with HTTPRequest.download_file, which the web
	# build ignores (the file stayed empty in Chrome).
	var out := FileAccess.open(part, FileAccess.WRITE)
	if out == null:
		error = "cannot write %s" % part
		return ""
	out.store_buffer(res["body"])
	out.close()
	var got := RoomPackFetcher.sha256_of(part)
	if got != want:
		var n := FileAccess.get_file_as_bytes(part).size()
		DirAccess.remove_absolute(part)
		error = "room pack %s failed its checksum (%d of %d bytes, sha256 %s)" % [file, n, int(pack.get("size", 0)), got.left(12)]
		return ""
	DirAccess.remove_absolute(path)
	if DirAccess.rename_absolute(part, path) != OK:
		error = "cannot store the room pack"
		return ""
	return path


static func sha256_of(path: String) -> String:
	var f := FileAccess.open(path, FileAccess.READ)
	if f == null:
		return ""
	var ctx := HashingContext.new()
	ctx.start(HashingContext.HASH_SHA256)
	while not f.eof_reached():
		ctx.update(f.get_buffer(1 << 20))
	return ctx.finish().hex_encode()


## GET url; {result, code, body} or {} with `error`. `size` (if known) drives
## the progress signal.
func _http_get(url: String, size: int = 0) -> Dictionary:
	var http := HTTPRequest.new()
	http.timeout = 300.0
	http.body_size_limit = 512 * 1024 * 1024
	add_child(http)
	var done := []
	http.request_completed.connect(func(result: int, code: int, _h: PackedStringArray, body: PackedByteArray) -> void:
		done.append({"result": result, "code": code, "body": body}))
	if http.request(url) != OK:
		http.queue_free()
		error = "cannot reach %s" % url
		return {}
	while done.is_empty():
		if size > 0:
			progressed.emit(clampf(float(http.get_downloaded_bytes()) / size, 0.0, 1.0))
		await get_tree().process_frame
	http.queue_free()
	var r: Dictionary = done[0]
	if r["result"] != HTTPRequest.RESULT_SUCCESS or int(r["code"]) != 200:
		error = "download of %s failed (result %d, HTTP %d)" % [url, r["result"], r["code"]]
		return {}
	return r
