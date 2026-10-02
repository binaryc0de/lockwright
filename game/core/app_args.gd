class_name AppArgs
extends RefCounted
## Parsed command line for client and dedicated-server modes (PLAN.md 7.1).
##
## Server: escapebox-server --session <id> --room <room_id> --pack <path.pck>
##         --port 7777 --platform http://127.0.0.1:8080 --token <server_token>
##         [--transport enet|ws]
## Godot passes user arguments after `--`; dedicated-server exports also
## receive them directly, so both forms are accepted.

enum Mode { CLIENT, SERVER }

const VALUE_FLAGS: PackedStringArray = [
	"session", "room", "pack", "port", "platform", "token", "transport",
]

var mode: Mode = Mode.CLIENT
var session_id: String = ""
var room_id: String = ""
var pack_path: String = ""
var port: int = 7777
var platform_url: String = "http://127.0.0.1:8080"
var server_token: String = ""
var transport: String = "enet"
var smoke_test: bool = false
var errors: PackedStringArray = []


static func parse(args: PackedStringArray, is_dedicated_server: bool = false) -> AppArgs:
	var a := AppArgs.new()
	if is_dedicated_server:
		a.mode = Mode.SERVER
	var i := 0
	while i < args.size():
		var arg := args[i]
		if not arg.begins_with("--"):
			i += 1
			continue
		var key := arg.substr(2)
		var value := ""
		var eq := key.find("=")
		if eq >= 0:
			value = key.substr(eq + 1)
			key = key.substr(0, eq)
		elif key in VALUE_FLAGS:
			if i + 1 >= args.size():
				a.errors.append("--%s needs a value" % key)
				break
			i += 1
			value = args[i]
		a._apply(key, value)
		i += 1
	a._validate()
	return a


func _apply(key: String, value: String) -> void:
	match key:
		"server":
			mode = Mode.SERVER
		"smoke":
			smoke_test = true
		"session":
			session_id = value
		"room":
			room_id = value
		"pack":
			pack_path = value
		"port":
			if value.is_valid_int() and int(value) > 0 and int(value) < 65536:
				port = int(value)
			else:
				errors.append("--port must be 1-65535, got %s" % value)
		"platform":
			platform_url = value
		"token":
			server_token = value
		"transport":
			if value in ["enet", "ws"]:
				transport = value
			else:
				errors.append("--transport must be enet or ws, got %s" % value)
		_:
			pass  # Unknown flags belong to the engine (--headless, --verbose, ...).


func _validate() -> void:
	if mode == Mode.SERVER and not smoke_test:
		for required: String in ["session", "room"]:
			if get("%s_id" % required) == "":
				errors.append("server mode requires --%s" % required)


func is_server() -> bool:
	return mode == Mode.SERVER
