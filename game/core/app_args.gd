class_name AppArgs
extends RefCounted
## Parsed command line for client and dedicated-server modes (PLAN.md 7.1).
##
## Server: escapebox-server --session <id> --room <room_id> --pack <path.pck>
##         --port 7777 --platform http://127.0.0.1:8080 --token <server_token>
##         [--transport enet|ws]
## Client: godot --path game -- [--room <id> [--pack <file.pck>]]
##         | --connect <host[:port]> --name <display name> [--token <invite>]
##           [--transport enet|ws] [--pack <file.pck>]
##           [--bot [--bot-steps A-B] [--bot-wait-win]]   (headless test client)
## Server extras: [--snapshot <file.json>] (default user://snapshots/<session>.json)
## Godot passes user arguments after `--`; dedicated-server exports also
## receive them directly, so both forms are accepted.

enum Mode { CLIENT, SERVER }

const VALUE_FLAGS: PackedStringArray = [
	"session", "room", "pack", "port", "platform", "token", "transport",
	"connect", "name", "snapshot", "bot-steps",
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
## Client: server to join ("" = play offline).
var connect_host: String = ""
var display_name: String = ""
var snapshot_path: String = ""
var bot: bool = false
var bot_first_step: int = 0
var bot_last_step: int = -1
var bot_wait_win: bool = false
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
		"connect":
			var parts := value.rsplit(":", true, 1)
			connect_host = parts[0]
			if parts.size() == 2:
				if parts[1].is_valid_int() and int(parts[1]) > 0 and int(parts[1]) < 65536:
					port = int(parts[1])
				else:
					errors.append("--connect port must be 1-65535, got %s" % parts[1])
			if connect_host.is_empty():
				errors.append("--connect needs a host")
		"name":
			display_name = value
		"snapshot":
			snapshot_path = value
		"bot":
			bot = true
		"bot-wait-win":
			bot_wait_win = true
		"bot-steps":
			var r := value.split("-")
			if r.size() == 2 and r[0].is_valid_int() and (r[1].is_valid_int() or r[1] == "end"):
				bot_first_step = int(r[0])
				bot_last_step = -1 if r[1] == "end" else int(r[1])
			else:
				errors.append("--bot-steps must look like 3-7 or 3-end, got %s" % value)
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
	if bot and connect_host.is_empty():
		errors.append("--bot needs --connect")


func is_remote_client() -> bool:
	return mode == Mode.CLIENT and not connect_host.is_empty()


func is_server() -> bool:
	return mode == Mode.SERVER
