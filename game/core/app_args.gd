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
##   touch:  godot --path game -- --room <id> --touchbot   (plays the solution
##           through the touch controls, ADR-0038; tests only)
## Server extras: [--snapshot <file.json>] (default user://snapshots/<session>.json)
## Godot passes user arguments after `--`; dedicated-server exports also
## receive them directly, so both forms are accepted.

enum Mode { CLIENT, SERVER }

const VALUE_FLAGS: PackedStringArray = [
	"session", "room", "pack", "port", "platform", "token", "transport",
	"connect", "name", "snapshot", "bot-steps", "touchbot-from", "play-from", "join", "code", "bot-flag", "difficulty",
]
## Environment variable the platform uses to hand the game server its token
## without exposing it on the process command line.
const SERVER_TOKEN_ENV := "ESCAPEBOX_SERVER_TOKEN"

var mode: Mode = Mode.CLIENT
var session_id: String = ""
var room_id: String = ""
var pack_path: String = ""
## Room difficulty id (room.yaml `difficulties`; "" = the room's default).
var difficulty: String = ""
var port: int = 7777
var platform_url: String = "http://127.0.0.1:8080"
## True when --platform was given: the server reports to the platform (M3)
## and --token is its server token, not a shared invite.
var platform_set: bool = false
var server_token: String = ""
## Browsers cannot use ENet (UDP); web builds default to WebSocket.
var transport: String = "ws" if OS.has_feature("web") else "enet"
var smoke_test: bool = false
## Client: server to join ("" = play offline).
var connect_host: String = ""
## Client via the platform (M3): platform URL and the host's join code.
var join_url: String = ""
var join_code: String = ""
var display_name: String = ""
var snapshot_path: String = ""
var bot: bool = false
var bot_first_step: int = 0
var bot_last_step: int = -1
var bot_wait_win: bool = false
## Flag the bot submits for submit_flag steps (M3 tests; "" = dev flag).
var bot_flag: String = ""
## Bot stays until a challenge's connection card shows an address (M3 tests).
var bot_wait_card: bool = false
## Tests only: play the room's solution offline through the touch controls.
var touchbot: bool = false
## With touchbot: do the steps before this one by intent, then touch.
var touchbot_from: int = 0
## Dev play from part-way (--play-from N, ?play_from=N): the first N solution
## steps are done by intent, then the player takes over. Offline play only.
var play_from: int = -1
## Tests only: the same play-through with classic keyboard and mouse.
var deskbot: bool = false
var deskbot_drag: bool = false
## Tests only: the play bot at a watching pace, to record a play-through.
var bot_tour: bool = false
## Print frames per second every few seconds (performance checks).
var stats: bool = false
## Server, tests only: accept teleporting positions (bots).
var trust_positions: bool = false
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
	if a.mode == Mode.SERVER and a.server_token.is_empty():
		a.server_token = OS.get_environment(SERVER_TOKEN_ENV)
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
		"difficulty":
			difficulty = value.strip_edges().to_lower()
		"port":
			if value.is_valid_int() and int(value) > 0 and int(value) < 65536:
				port = int(value)
			else:
				errors.append("--port must be 1-65535, got %s" % value)
		"platform":
			platform_url = value
			platform_set = true
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
		"join":
			join_url = AppArgs.platform_http_url(value)
		"code":
			join_code = value.strip_edges().to_upper()
		"snapshot":
			snapshot_path = value
		"bot":
			bot = true
		"bot-wait-win":
			bot_wait_win = true
		"bot-flag":
			bot_flag = value
		"bot-wait-card":
			bot_wait_card = true
		"touchbot":
			touchbot = true
		"deskbot":
			touchbot = true
			deskbot = true
		"deskbot-drag":
			touchbot = true
			deskbot = true
			deskbot_drag = true
		"bot-tour":
			bot_tour = true
		"touchbot-from":
			touchbot_from = int(value)
		"play-from":
			touchbot = true
			touchbot_from = int(value)
			play_from = int(value)
		"trust-positions":
			trust_positions = true
		"stats":
			stats = true
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
	if bot and connect_host.is_empty() and join_url.is_empty():
		errors.append("--bot needs --connect or --join")
	if not join_url.is_empty() and join_code.is_empty():
		errors.append("--join needs --code")


func is_remote_client() -> bool:
	return mode == Mode.CLIENT and (not connect_host.is_empty() or not join_url.is_empty())


func via_platform() -> bool:
	return not join_url.is_empty()


## "192.168.1.20" -> "http://192.168.1.20:8080"; keeps an explicit scheme/port.
static func platform_http_url(addr: String) -> String:
	var a := addr.strip_edges().trim_suffix("/")
	if a.begins_with("http://") or a.begins_with("https://"):
		return a  # a full URL keeps its own (or the scheme's default) port
	if not ":" in a:
		a += ":8080"
	return "http://" + a


## Browser builds (ADR-0023): the page URL carries the join details, e.g.
## /play/?code=AB3K9Z&name=Riley (bot=1 for automated tests,
## difficulty/room for offline play). `origin` is the page's origin, which
## serves the platform API too. Returns command-line style arguments.
static func web_query_args(origin: String, query: String) -> PackedStringArray:
	var q := {}
	for pair in query.trim_prefix("?").split("&", false):
		var kv := pair.split("=", true, 1)
		q[kv[0].uri_decode()] = kv[1].uri_decode().replace("+", " ") if kv.size() > 1 else ""
	var out := PackedStringArray()
	if q.has("code"):
		out.append_array(["--join", origin, "--code", str(q["code"])])
	elif q.has("room"):
		out.append_array(["--room", str(q["room"])])
	if q.has("name"):
		out.append_array(["--name", str(q["name"])])
	if q.has("difficulty"):
		out.append_array(["--difficulty", str(q["difficulty"])])
	if q.get("stats", "") == "1":
		out.append("--stats")
	if q.get("deskbot", "") == "1" and q.has("room"):
		out.append("--deskbot-drag" if q.get("deskdrag", "") == "1" else "--deskbot")  # tests only
		if q.get("tour", "") == "1":
			out.append("--bot-tour")  # recording a play-through
	elif q.get("touchbot", "") == "1" and q.has("room"):
		out.append("--touchbot")  # tests only
		if q.has("touchbot_from"):
			out.append_array(["--touchbot-from", str(q["touchbot_from"])])
	elif q.has("play_from") and q.has("room"):
		out.append_array(["--play-from", str(q["play_from"])])  # dev play part-way
	if q.get("bot", "") == "1":
		out.append_array(["--bot", "--bot-wait-win"])
		if q.has("flag"):
			out.append_array(["--bot-flag", str(q["flag"])])  # tests only
	return out


func is_server() -> bool:
	return mode == Mode.SERVER
