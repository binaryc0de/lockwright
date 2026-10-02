class_name PlatformSnapshotStore
extends SnapshotStore
## M3 snapshot persistence (PLAN.md 7.3): the platform keeps the latest
## snapshot. Saves are asynchronous and coalesced (one PUT in flight, then
## the newest pending one); the final save before an idle exit blocks.

var client: PlatformClient
var _in_flight := false
var _pending: Variant = null


func _init(p_client: PlatformClient) -> void:
	super("")
	client = p_client


func exists() -> bool:
	return true


## Blocking: the server needs the world before it accepts players. Returns
## {} for a fresh session; {"_error": text} if the platform did not answer.
func load_snapshot() -> Dictionary:
	var r := client.request_blocking(HTTPClient.METHOD_GET, client.internal_path("snapshot"), null, 10.0)
	if r["code"] == 200 and r["data"] is Dictionary:
		return r["data"]
	if r["code"] == 404:
		return {}
	return {"_error": "platform did not return the snapshot (HTTP %d)" % r["code"]}


func save(snapshot: Dictionary) -> bool:
	if _in_flight:
		_pending = snapshot
		return true
	_in_flight = true
	client.request_async(HTTPClient.METHOD_PUT, client.internal_path("snapshot"), snapshot, func(code: int, _d: Variant) -> void:
		_in_flight = false
		if code != 204:
			push_warning("snapshot PUT failed (HTTP %d); will retry with the next save" % code)
		if _pending != null:
			var next: Dictionary = _pending
			_pending = null
			save(next))
	return true


func save_blocking(snapshot: Dictionary) -> bool:
	return client.request_blocking(HTTPClient.METHOD_PUT, client.internal_path("snapshot"), snapshot, 5.0)["code"] == 204
