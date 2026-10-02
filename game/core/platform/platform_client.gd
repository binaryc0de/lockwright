class_name PlatformClient
extends Node
## HTTP client for the platform (docs/API.md, ADR-0018). Game servers use the
## /internal endpoints with their session's server token; clients use the
## public /api endpoints. Asynchronous calls use HTTPRequest; the few calls
## that must answer inside one frame (start-up snapshot, flag checks) use a
## short blocking HTTPClient exchange. Never log request bodies: flags travel
## through here.

## Default request timeout for async calls.
const TIMEOUT_S := 15.0

var base_url: String = "http://127.0.0.1:8080"
var session_id: String = ""
var server_token: String = ""


func _init(p_base_url: String = "", p_session_id: String = "", p_server_token: String = "") -> void:
	if not p_base_url.is_empty():
		base_url = p_base_url.trim_suffix("/")
	session_id = p_session_id
	server_token = p_server_token


func internal_path(rest: String) -> String:
	return "/internal/sessions/%s/%s" % [session_id.uri_encode(), rest]


## Calls back with (code: int, data: Variant). code 0 = no response.
func request_async(method: int, path: String, body: Variant, on_done: Callable, timeout_s: float = TIMEOUT_S) -> void:
	var req := HTTPRequest.new()
	req.timeout = timeout_s
	add_child(req)
	req.request_completed.connect(func(result: int, code: int, _headers: PackedStringArray, raw: PackedByteArray) -> void:
		req.queue_free()
		var data: Variant = null
		if result == HTTPRequest.RESULT_SUCCESS and raw.size() > 0:
			data = JSON.parse_string(raw.get_string_from_utf8())
		if on_done.is_valid():
			on_done.call(code if result == HTTPRequest.RESULT_SUCCESS else 0, data))
	var err := req.request(base_url + path, _headers(body != null), method, _encode(body))
	if err != OK:
		req.queue_free()
		if on_done.is_valid():
			on_done.call(0, null)


## Blocking request; returns {code, data}. Keep to localhost and short timeouts.
func request_blocking(method: int, path: String, body: Variant, timeout_s: float = 3.0) -> Dictionary:
	var parts := _split_url(base_url)
	var http := HTTPClient.new()
	var deadline := Time.get_ticks_msec() + int(timeout_s * 1000.0)
	if http.connect_to_host(parts["host"], parts["port"]) != OK:
		return {"code": 0, "data": null}
	while http.get_status() in [HTTPClient.STATUS_CONNECTING, HTTPClient.STATUS_RESOLVING]:
		http.poll()
		if Time.get_ticks_msec() > deadline:
			return {"code": 0, "data": null}
		OS.delay_usec(1000)
	if http.get_status() != HTTPClient.STATUS_CONNECTED:
		return {"code": 0, "data": null}
	if http.request(method, path, _headers(body != null), _encode(body)) != OK:
		return {"code": 0, "data": null}
	while http.get_status() == HTTPClient.STATUS_REQUESTING:
		http.poll()
		if Time.get_ticks_msec() > deadline:
			return {"code": 0, "data": null}
		OS.delay_usec(1000)
	var code := http.get_response_code()
	var raw := PackedByteArray()
	while http.get_status() == HTTPClient.STATUS_BODY:
		http.poll()
		raw.append_array(http.read_response_body_chunk())
		if Time.get_ticks_msec() > deadline:
			return {"code": 0, "data": null}
		OS.delay_usec(500)
	http.close()
	var data: Variant = JSON.parse_string(raw.get_string_from_utf8()) if raw.size() > 0 else null
	return {"code": code, "data": data}


func _headers(has_body: bool) -> PackedStringArray:
	var h := PackedStringArray()
	if has_body:
		h.append("Content-Type: application/json")
	if not server_token.is_empty():
		h.append("Authorization: Bearer " + server_token)
	return h


func _encode(body: Variant) -> String:
	if body == null:
		return ""
	if body is String:
		return body
	return JSON.stringify(body)


static func _split_url(url: String) -> Dictionary:
	var rest := url.trim_prefix("http://")
	var slash := rest.find("/")
	if slash >= 0:
		rest = rest.substr(0, slash)
	var host := rest
	var port := 80
	var colon := rest.rfind(":")
	if colon > 0:
		host = rest.substr(0, colon)
		port = int(rest.substr(colon + 1))
	return {"host": host, "port": port}
