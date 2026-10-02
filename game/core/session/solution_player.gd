class_name SolutionPlayer
extends RefCounted
## Turns room.yaml `solution` steps (PLAN.md 8.3) into intents, using only
## SDK knowledge so it works for any room: the network bot (ADR-0015) and the
## future auto-solver both build on it.

## Flag used for `submit_flag` steps while flags are validated by the offline
## dev validator (M1/M2). M3 bots will fetch the real per-session flag.
const DEV_FLAG := "solution-player-dev-flag"


## Returns {path, verb, payload} for a step, {} for observation-only steps
## (examining something that is not a Document), or {error} if the step names
## something the room does not have. `nodes` maps eb_path -> EBNode.
static func intent_for(step: Dictionary, nodes: Dictionary, vars: Dictionary) -> Dictionary:
	match step.get("act"):
		"interact":
			var payload := {}
			if step.has("value"):
				payload["value"] = EBTemplate.render(str(step["value"]), vars)
			return _intent(nodes, str(step["node"]), str(step["verb"]), payload)
		"pick_up":
			var p := item_path(nodes, str(step["item"]))
			if p.is_empty():
				return {"error": "no Item with item_id %s" % step["item"]}
			return {"path": p, "verb": "pick_up", "payload": {}}
		"input_code":
			return _intent(nodes, str(step["lock"]), "submit_code", {"value": EBTemplate.render(str(step["value"]), vars)})
		"submit_flag":
			var t := terminal_path(nodes, str(step["challenge"]))
			if t.is_empty():
				return {"error": "no Terminal for challenge %s" % step["challenge"]}
			return {"path": t, "verb": "submit_flag", "payload": {"value": DEV_FLAG}}
		"examine", "use":
			var target := str(step.get("node", step.get("target", "")))
			if nodes.get(target) is Document:
				return {"path": target, "verb": "read", "payload": {}}
			return {}
		"use_on":
			var item := item_path(nodes, str(step["item"]))
			if item.is_empty():
				return {"error": "no Item with item_id %s" % step["item"]}
			return _intent(nodes, str(step["target"]), "use_item", {"item": item})
	return {"error": "unknown solution act %s" % step.get("act")}


static func _intent(nodes: Dictionary, path: String, verb: String, payload: Dictionary) -> Dictionary:
	if not nodes.has(path):
		return {"error": "no SDK node at %s" % path}
	return {"path": path, "verb": verb, "payload": payload}


static func item_path(nodes: Dictionary, item_id: String) -> String:
	for path: String in nodes:
		if nodes[path] is Item and (nodes[path] as Item).item_id == item_id:
			return path
	return ""


static func terminal_path(nodes: Dictionary, challenge_id: String) -> String:
	for path: String in nodes:
		if nodes[path] is Terminal and (nodes[path] as Terminal).challenge_id == challenge_id:
			return path
	return ""
