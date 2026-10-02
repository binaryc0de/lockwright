@icon("res://addons/escapebox_sdk/icons/eb_node.svg")
class_name ContainerProp
extends Openable
## Drawer, cabinet, safe or hatch (PLAN.md 8.2 "Container"; renamed because
## Godot already has a Container class, ADR-0008). Things under `contents`
## are hidden and cannot be targeted while it is closed.

## Node holding the items/documents inside; hidden while closed.
@export var contents: NodePath


func _apply_state(state: Dictionary) -> void:
	super(state)
	var c := get_node_or_null(contents) as Node3D
	if c:
		var open: bool = state.get("state", "closed") == "open"
		c.visible = open
		EBNode.set_collisions_enabled(c, open)
		if open:
			# Items already taken stay hidden even though the container opened.
			for n in EBNode.find_all(c):
				if not n.current_state.is_empty():
					n._apply_state(n.current_state)
