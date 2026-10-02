@icon("res://addons/escapebox_sdk/icons/eb_node.svg")
class_name Terminal
extends Interactable
## In-game terminal prop (PLAN.md 6.8). "remote": shows the challenge's
## connection card (where to point real tools) and a flag field.
## "simulated": a tiny offline shell driven by `commands`; it never gates a
## real flag on its own. State: {state: "open" | "solved"}

@export_enum("remote", "simulated") var mode: String = "remote"
## CTF challenge id from room.yaml (remote mode).
@export var challenge_id: String = ""
@export_multiline var banner: String = ""
## Simulated mode: command line -> output. Use {{var}} for session variables.
@export var commands: Dictionary = {}


func _init() -> void:
	verbs = ["terminal"]


func _initial_state() -> Dictionary:
	return {"state": "open"}


func _server_intent(player_id: String, verb: String, payload: Dictionary) -> Dictionary:
	if verb != "submit_flag" or challenge_id.is_empty():
		return {"ok": false, "error": "unsupported_verb"}
	return authority.submit_flag(player_id, challenge_id, str(payload.get("value", "")))


func _server_flag_accepted(id: String) -> void:
	if id == challenge_id:
		set_state({"state": "solved"})


func client_interact(_item_path: String = "") -> void:
	Game.ui_open_terminal(self)


## Simulated shell output for one command line (client side, offline).
func run_command(line: String) -> String:
	line = line.strip_edges()
	if line == "help":
		var names := commands.keys()
		names.sort()
		return "commands: " + ", ".join(PackedStringArray(names + ["help", "clear"]))
	if commands.has(line):
		return EBTemplate.render(str(commands[line]), Game.vars())
	return "%s: command not found" % line.get_slice(" ", 0)
