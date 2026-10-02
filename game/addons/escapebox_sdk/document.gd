@icon("res://addons/escapebox_sdk/icons/eb_node.svg")
class_name Document
extends Interactable
## Readable paper, card, photo or poster (PLAN.md 6.3). Reading opens the
## inspect view locally (co-inspection is never exclusive) and pins the
## document to the shared evidence board on first read.
## State: {state: "unread" | "read"}

@export var title: String = "Document"
## Front side, Markdown subset (headings, bold, italic, lists).
@export_multiline var text_md: String = ""
## Back side; empty means single-sided. The inspect view offers "Flip".
@export_multiline var back_text_md: String = ""
## Hidden text, readable only with a UV torch selected.
@export_multiline var uv_text: String = ""
## Optional image instead of / above the text (printed document texture).
@export var texture: Texture2D


func _init() -> void:
	verbs = ["read"]


func _initial_state() -> Dictionary:
	return {"state": "unread"}


func _server_intent(player_id: String, verb: String, _payload: Dictionary) -> Dictionary:
	if verb != "read":
		return {"ok": false, "error": "unsupported_verb"}
	if authority.state.node_state(eb_path).get("state") != "read":
		set_state({"state": "read"})
	authority.pin_document(eb_path, title, player_id)
	return {"ok": true}


func client_interact(_item_path: String = "") -> void:
	Game.ui_inspect_document(self)
	Game.request(self, "read", {})
