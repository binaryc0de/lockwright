@icon("res://addons/escapebox_sdk/icons/eb_node.svg")
class_name UVTorch
extends Item
## An Item that reveals UV-only content (UVReveal nodes, Document.uv_text,
## Item.uv_text) while it is the local player's selected item.


func is_uv_source() -> bool:
	return true
