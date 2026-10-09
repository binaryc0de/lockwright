@icon("res://addons/escapebox_sdk/icons/eb_node.svg")
class_name LoadPlate
extends Lock
## A set of weighing pans (ADR-0040): blocks of known weight go on its
## LoadPan children and the plate opens when the loads are right. Weights are
## fixed numbers per item, never physics or the players' own weight, so a
## "pressure plate" is solvable solo. Items stay free to take back after it
## opens (a pawl holds what they lifted).
## State: Lock's.

## item_ids the pans take, and their weights (parallel arrays).
@export var weight_items: Array[String] = []
@export var weight_values: Array[int] = []
## Total over every pan (each pan's load times its multiplier); -1 = no total
## (only the pans' own targets count).
@export var target_total: int = -1
## item_ids that must all be on the pans.
@export var require_items: Array[String] = []
## Activated when the plate opens (like a Lever's targets).
@export var targets: Array[NodePath] = []
@export var empty_message: String = "Something has to be weighed here."
## Presentation, a balance: `beam` tilts by beam_step degrees per unit of
## (pans' total, each times its multiplier) minus `counterweight`, up to
## beam_limit either way, and lies level while they match. The counterweight
## counts only while `counterweight_item` is still in the world (an idol on the
## far pan); once it is taken, the beam rests level (its pawl has caught it).
@export var beam: NodePath
@export var beam_step: Vector3 = Vector3(0, 0, -2.0)
@export var beam_limit: float = 8.0
@export var counterweight: int = 0
@export var counterweight_item: NodePath

var _beam_base: Variant = null
var _beam_tween: Tween


func _init() -> void:
	verbs = ["use"]


func _ready() -> void:
	super()
	if beam.is_empty():
		return
	for p in pans():
		p.state_applied.connect(func(_s: Dictionary) -> void: _tilt_beam())
	var cw := get_node_or_null(counterweight_item) as EBNode
	if cw:
		cw.state_applied.connect(func(_s: Dictionary) -> void: _tilt_beam())
	_tilt_beam.call_deferred()


## The pans' moment: each pan's load times its multiplier.
func moment() -> int:
	var total := 0
	for p in pans():
		total += int(p.current_state.get("load", 0)) * p.multiplier
	return total


func _tilt_beam() -> void:
	var b := get_node_or_null(beam) as Node3D
	if b == null:
		return
	if _beam_base == null:
		_beam_base = b.rotation_degrees
	var cw := get_node_or_null(counterweight_item) as EBNode
	var against := counterweight if cw == null or str(cw.current_state.get("state", "world")) == "world" else moment()
	var diff := float(moment() - against)
	var step_len := beam_step.length()
	var turn := beam_step * diff
	if step_len > 0.0 and turn.length() > beam_limit:
		turn = turn.normalized() * beam_limit
	var to: Vector3 = (_beam_base as Vector3) + turn
	if _beam_tween:
		_beam_tween.kill()
	if is_inside_tree() and DisplayServer.get_name() != "headless":
		_beam_tween = create_tween()
		_beam_tween.tween_property(b, "rotation_degrees", to, 0.8).set_trans(Tween.TRANS_SINE)
	else:
		b.rotation_degrees = to


func weight_of(item_id: String) -> int:
	var i := weight_items.find(item_id)
	return weight_values[i] if i >= 0 and i < weight_values.size() else -1


func pans() -> Array[LoadPan]:
	var out: Array[LoadPan] = []
	for p: LoadPan in find_children("*", "LoadPan", true, false):
		if p.plate() == self:
			out.append(p)
	return out


## Whether the pans show a right load.
func loads_right() -> bool:
	var total := 0
	var seated := {}
	for p in pans():
		var amount := p.current_load()
		total += amount * p.multiplier
		if p.target >= 0 and amount != p.target:
			return false
		for it in state_of(p).get("items", []):
			seated[str(it.get("item_id", ""))] = true
	if target_total >= 0 and total != target_total:
		return false
	for id in require_items:
		if not seated.has(id):
			return false
	return true


## Server: a pan changed. Returns the result for the player who did it.
func _server_pan_changed() -> Dictionary:
	if is_unlocked():
		return {"ok": true}
	if is_powered() and authority.prerequisites_met(self) and loads_right():
		set_state({"state": "unlocked", "last_ok": true})
		for t in targets:
			authority.activate(room_path_of(t))
		return {"ok": true, "opened": true}
	return {"ok": true}


func _server_intent(_player_id: String, _verb: String, _payload: Dictionary) -> Dictionary:
	return {"ok": false, "error": "needs_item", "message": empty_message}


func client_interact(_item_path: String = "") -> void:
	Game.toast(empty_message)


func _server_activate() -> void:
	if not is_powered():
		set_state({"powered": true})
		_server_pan_changed()
	elif not is_unlocked():
		set_state({"state": "unlocked", "last_ok": true})
