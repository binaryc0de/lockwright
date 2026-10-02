@icon("res://addons/escapebox_sdk/icons/eb_node.svg")
class_name Interactable
extends EBNode
## Something a player can aim at and act on (PLAN.md 6.2). Needs a
## CollisionObject3D (usually a StaticBody3D) somewhere below it so the
## interaction ray can hit it; the SDK puts that body on the interaction
## physics layer automatically.

## Physics layer (1-based) the interaction ray tests, in addition to walls.
const INTERACT_LAYER := 2

const VERB_LABELS := {
	"use": "Use", "pick_up": "Pick up", "read": "Read", "examine": "Examine",
	"open": "Open", "close": "Close", "toggle": "Switch", "enter_code": "Enter code",
	"patch": "Patch cables", "terminal": "Use terminal", "use_item": "Use",
}

## Name shown in prompts, e.g. "Open Filing cabinet".
@export var display_name: String = "Thing"
## Verbs this node supports; the first is the default action.
@export var verbs: PackedStringArray = ["use"]
## True if players can use an inventory item on this node ("Use UV torch on ...").
@export var accepts_items: bool = false

static var _highlight: StandardMaterial3D


func _ready() -> void:
	for body in _bodies(self):
		body.collision_layer |= 1 << (INTERACT_LAYER - 1)


## True while players can currently act on this node.
func is_available() -> bool:
	return is_visible_in_tree()


## The verb the interact key performs now (state-dependent for some nodes).
func current_verb() -> String:
	return verbs[0] if not verbs.is_empty() else "use"


## Prompt text for the HUD. `item_name` is the selected inventory item, if any.
func prompt(item_name: String = "") -> String:
	if accepts_items and not item_name.is_empty():
		return "Use %s on %s" % [item_name, display_name]
	return "%s %s" % [VERB_LABELS.get(current_verb(), current_verb().capitalize()), display_name]


## Client side: the local player pressed interact. Default sends the intent;
## nodes with a focused UI (locks, terminals) open it instead.
func client_interact(item_path: String = "") -> void:
	if accepts_items and not item_path.is_empty():
		Game.request(self, "use_item", {"item": item_path})
	else:
		Game.request(self, current_verb(), {})


func set_highlighted(on: bool) -> void:
	if _highlight == null:
		_highlight = StandardMaterial3D.new()
		_highlight.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
		_highlight.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
		_highlight.blend_mode = BaseMaterial3D.BLEND_MODE_ADD
		_highlight.albedo_color = Color(1.0, 0.8, 0.35, 0.22)
	for m in _meshes(self):
		m.material_overlay = _highlight if on else null


static func _bodies(n: Node) -> Array[CollisionObject3D]:
	var out: Array[CollisionObject3D] = []
	for c in n.get_children():
		if c is Interactable:
			continue  # nested interactables own their own bodies
		if c is CollisionObject3D:
			out.append(c)
		out.append_array(_bodies(c))
	return out


static func _meshes(n: Node) -> Array[MeshInstance3D]:
	var out: Array[MeshInstance3D] = []
	for c in n.get_children():
		if c is Interactable:
			continue
		if c is MeshInstance3D:
			out.append(c)
		out.append_array(_meshes(c))
	return out


## The Interactable that owns a collider hit by the interaction ray, if any.
static func owner_of(collider: Object) -> Interactable:
	var n := collider as Node
	while n != null:
		if n is Interactable:
			return n
		n = n.get_parent()
	return null
