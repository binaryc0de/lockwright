class_name PointerControls
extends Node
## Point-and-tap controls for the FirstPersonPlayer (ADR-0038), for phones,
## tablets and anyone who finds WASD + mouse look awkward. One finger or the
## left mouse button does everything:
##   drag            look around
##   tap the floor   walk there (routed around furniture by the WalkMesh)
##   tap a thing     walk up to it if needed, turn to it, and use it
## Items dragged out of the inventory and dropped on a thing are used on it.
## Only intents leave the client; the server still checks reach.

## A press that moves less than this (viewport px) is a tap, not a drag.
const TAP_SLOP := 16.0
const TAP_TIME_MS := 650
## Eye-to-point distance at which a walk towards a thing stops to use it.
const ARRIVE_M := 1.9
## A full-width drag turns the view this far (radians).
const DRAG_TURN := 2.8
const STUCK_TIME := 0.6
const TURN_TIME := 0.22

var player: FirstPersonPlayer
var walk: WalkMesh
## The thing under the mouse (mouse only; fingers do not hover), or under
## an inventory item being dragged.
var hover: Interactable = null
## Set by the HUD while an inventory item is dragged over the room.
var dragging_item := false
var drag_target: Interactable = null

var _down := false
var _down_pos := Vector2.ZERO
var _down_ms := 0
var _dragging := false
var _mouse_pos := Vector2.ZERO
var _mouse_inside := false

var _route := PackedVector3Array()
var _route_i := 0
var _pending: Interactable = null
var _pending_item := ""
var _pending_point := Vector3.ZERO
var _last_pos := Vector3.ZERO
var _stuck := 0.0
var _turn: Tween


func _init(p: FirstPersonPlayer) -> void:
	player = p


func is_walking() -> bool:
	return not _route.is_empty()


## Stops walking and drops any interaction still to come (a pending walk-up
## or the turn before a use).
func cancel() -> void:
	_route = PackedVector3Array()
	_pending = null
	if _turn:
		_turn.kill()
		_turn = null


## Returns true if the event was used.
func handle(event: InputEvent) -> bool:
	if event is InputEventMouseButton:
		var b := event as InputEventMouseButton
		if b.button_index != MOUSE_BUTTON_LEFT and b.button_index != MOUSE_BUTTON_RIGHT:
			return false
		if b.pressed:
			_down = true
			_dragging = false
			_down_pos = b.position
			_down_ms = Time.get_ticks_msec()
		elif _down:
			_down = false
			if not _dragging and b.button_index == MOUSE_BUTTON_LEFT and Time.get_ticks_msec() - _down_ms <= TAP_TIME_MS:
				tap(b.position)
		return true
	if event is InputEventMouseMotion:
		var m := event as InputEventMouseMotion
		if m.device != InputEvent.DEVICE_ID_EMULATION:
			_mouse_pos = m.position
			_mouse_inside = true
		if _down:
			if not _dragging and m.position.distance_to(_down_pos) > TAP_SLOP:
				_dragging = true
			if _dragging:
				_look(m.relative)
			return true
	return false


func _look(relative: Vector2) -> void:
	var width := player.get_viewport().get_visible_rect().size.x
	var k := DRAG_TURN / maxf(width, 1.0) * (-1.0 if Settings.drag_grabs_world else 1.0)
	player.turn(-relative.x * k, -relative.y * k * (-1.0 if Settings.invert_y else 1.0))


## A tap (or click) at a viewport position.
func tap(pos: Vector2) -> void:
	var hit := player.pick(pos)
	if hit.is_empty():
		return
	var thing: Interactable = hit.get("interactable")
	if thing:
		act_on(thing, hit.position, Game.selected_item)
		return
	var point: Vector3 = hit.position
	if (hit.normal as Vector3).y < 0.6:
		# A wall or a cupboard front: walk to the floor in front of it.
		point += (hit.normal as Vector3) * 0.5
		point.y = player.global_position.y
	walk_to(point)


## An inventory item released over a viewport position: use it on what is
## there (select it, then act as if the thing was tapped). Let go over
## nothing usable, it is just held up (selected), which is also how a UV
## torch lights up ink on the walls.
func drop(item_path: String, pos: Vector2) -> void:
	var thing: Interactable = player.pick(pos).get("interactable")
	Game.selected_item = item_path
	if thing == null:
		var item := Game.node_at(item_path) as Item
		Game.toast("You hold up the %s." % (item.display_name if item else "item"))
		return
	act_on(thing, player.pick(pos).position, item_path)


## The thing an item dragged to `pos` would be used on, for highlighting.
func thing_at(pos: Vector2) -> Interactable:
	return player.pick(pos).get("interactable")


func act_on(thing: Interactable, point: Vector3, item_path: String) -> void:
	cancel()  # a new tap replaces any walk or use still under way
	if player.eye().distance_to(point) <= FirstPersonPlayer.REACH:
		_use(thing, point, item_path)
		return
	_start_route(point)
	_pending = thing
	_pending_item = item_path
	_pending_point = point


func walk_to(point: Vector3) -> void:
	cancel()
	_start_route(point)


func _start_route(point: Vector3) -> void:
	_route = walk.route(player.global_position, point) if walk else PackedVector3Array([point])
	_route_i = 0
	_last_pos = player.global_position
	_stuck = 0.0


## Turns to face the point, then sends the intent.
func _use(thing: Interactable, point: Vector3, item_path: String) -> void:
	if _turn:
		_turn.kill()
	_turn = player.create_tween().set_trans(Tween.TRANS_SINE).set_ease(Tween.EASE_OUT)
	player.face_point(point, TURN_TIME, _turn)
	_turn.finished.connect(func() -> void:
		if is_instance_valid(thing) and thing.is_available():
			thing.client_interact(item_path))


## Called from the player's physics step: the direction to walk this frame
## (zero when not walking).
func steer(delta: float) -> Vector3:
	if _route.is_empty():
		return Vector3.ZERO
	var pos := player.global_position
	if _pending and player.eye().distance_to(_pending_point) <= ARRIVE_M:
		_arrive()
		return Vector3.ZERO
	var goal := _route[_route_i]
	var flat := Vector3(goal.x - pos.x, 0, goal.z - pos.z)
	while flat.length() < 0.15:
		_route_i += 1
		if _route_i >= _route.size():
			_arrive()
			return Vector3.ZERO
		goal = _route[_route_i]
		flat = Vector3(goal.x - pos.x, 0, goal.z - pos.z)
	_stuck += delta
	if _stuck >= STUCK_TIME:
		if pos.distance_to(_last_pos) < 0.12:
			_arrive()
			return Vector3.ZERO
		_stuck = 0.0
		_last_pos = pos
	var dir := flat.normalized()
	# Ease the view round towards where we are going.
	player.rotation.y = lerp_angle(player.rotation.y, atan2(-dir.x, -dir.z), 1.0 - exp(-5.0 * delta))
	return dir


func _arrive() -> void:
	var thing := _pending
	_route = PackedVector3Array()
	_pending = null
	if thing == null or not is_instance_valid(thing):
		return
	if player.eye().distance_to(_pending_point) <= FirstPersonPlayer.REACH + 0.4:
		_use(thing, _pending_point, _pending_item)
	else:
		Game.toast("You can't reach that from here.")


## The mouse-hovered thing (updated every physics step as the view moves).
func update_hover() -> Interactable:
	hover = null
	if dragging_item:
		hover = drag_target
	elif _mouse_inside and not _down:
		hover = player.pick(_mouse_pos).get("interactable")
	return hover


func mouse_position() -> Vector2:
	return _mouse_pos
