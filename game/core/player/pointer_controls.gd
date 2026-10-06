class_name PointerControls
extends Node
## Point-and-tap controls for the FirstPersonPlayer (ADR-0038), for phones,
## tablets and anyone who finds WASD + mouse look awkward. One finger or the
## left mouse button does everything:
##   drag            look around
##   tap the floor   walk there (routed around furniture by the WalkMesh)
##   tap a thing     walk up to it if needed, turn to it, and use it
##   pinch / wheel   zoom the view in on small things
## A tap that lands just beside a small thing still counts (fingers are
## wide), and on touch screens things you can pick up glint when in reach.
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
## How far around a tap to look for a small thing, in CSS pixels.
const FINGER_PX := 28.0
const MOUSE_PX := 8.0
## Items glint (touch screens) within this distance of the eye.
const GLINT_M := 2.6

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
## Re-plans after getting stuck on the current walk.
var _unsticks := 0
var _pending_item := ""
var _pending_point := Vector3.ZERO
var _last_pos := Vector3.ZERO
var _stuck := 0.0
## Where the current walk is headed, and which walk mesh planned it.
var _goal := Vector3.ZERO
var _route_gen := 0
var _replans := 0
## Waiting for a re-bake (a door just opened) before planning again.
var _await_bake := false
var _turn: Tween
var _fingers := {}  # touch index -> position
var _pinch_d := 0.0
var _pinching := false
var _glinting: Array[Interactable] = []
var _glint_timer := 0.0


func _init(p: FirstPersonPlayer) -> void:
	player = p


func is_walking() -> bool:
	return not _route.is_empty() or _await_bake


## Stops walking and drops any interaction still to come (a pending walk-up
## or the turn before a use).
func cancel() -> void:
	_route = PackedVector3Array()
	_pending = null
	_await_bake = false
	if _turn:
		_turn.kill()
		_turn = null


## Returns true if the event was used.
func handle(event: InputEvent) -> bool:
	if event is InputEventScreenTouch:
		var t := event as InputEventScreenTouch
		if t.pressed:
			_fingers[t.index] = t.position
		else:
			_fingers.erase(t.index)
		if _fingers.size() == 2:
			_pinching = true
			_down = false  # the first finger's press is no longer a tap or a look
			var f: Array = _fingers.values()
			_pinch_d = (f[0] as Vector2).distance_to(f[1])
		elif _fingers.is_empty():
			_pinching = false
		return false
	if event is InputEventScreenDrag:
		var d := event as InputEventScreenDrag
		_fingers[d.index] = d.position
		if _pinching and _fingers.size() == 2:
			var f: Array = _fingers.values()
			var dist := (f[0] as Vector2).distance_to(f[1])
			if _pinch_d > 1.0:
				player.set_zoom(player.zoom * dist / _pinch_d)
			_pinch_d = dist
			return true
		return false
	if _pinching and (event is InputEventMouseButton or event is InputEventMouseMotion):
		return true
	if event is InputEventMouseButton:
		var b := event as InputEventMouseButton
		if b.pressed and (b.button_index == MOUSE_BUTTON_WHEEL_UP or b.button_index == MOUSE_BUTTON_WHEEL_DOWN):
			# The mouse wheel zooms (the inventory is clickable in this mode).
			player.set_zoom(player.zoom * (1.15 if b.button_index == MOUSE_BUTTON_WHEEL_UP else 1.0 / 1.15))
			return true
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
	# Zoomed in, the same finger travel turns less (the view is narrower).
	var k := DRAG_TURN / maxf(width, 1.0) / player.zoom * (-1.0 if Settings.drag_grabs_world else 1.0)
	player.turn(-relative.x * k, -relative.y * k * (-1.0 if Settings.invert_y else 1.0))


## A tap (or click) at a viewport position.
func tap(pos: Vector2) -> void:
	var hit := pick_near(pos)
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
	var hit := pick_near(pos)
	var thing: Interactable = hit.get("interactable")
	Game.selected_item = item_path
	if thing == null:
		var item := Game.node_at(item_path) as Item
		Game.toast("You hold up the %s." % (item.display_name if item else "item"))
		return
	act_on(thing, hit.position, item_path)


## The thing an item dragged to `pos` would be used on, for highlighting.
func thing_at(pos: Vector2) -> Interactable:
	return pick_near(pos).get("interactable")


## What a tap at `pos` means: the thing under it, or, if nothing usable is
## exactly there, the nearest usable thing within a fingertip of it.
func pick_near(pos: Vector2) -> Dictionary:
	return player.pick_near(pos, finger_radius())


## A fingertip (or a mouse's few pixels) in viewport units.
func finger_radius() -> float:
	var css := Device.window_css().x
	var per_css := player.get_viewport().get_visible_rect().size.x / css if css > 0.0 else 1.0
	return (FINGER_PX if Device.is_touch() else MOUSE_PX) * per_css


func act_on(thing: Interactable, point: Vector3, item_path: String) -> void:
	cancel()  # a new tap replaces any walk or use still under way
	if player.eye().distance_to(point) <= FirstPersonPlayer.REACH:
		_use(thing, point, item_path)
		return
	# Head for the side it was tapped from: the walkable spot nearest the
	# thing itself can be behind a thin wall.
	var toward := player.eye() - point
	toward.y = 0.0
	var approach := point + toward.normalized() * 0.7 if toward.length() > 0.01 else point
	approach.y = point.y - 1.0
	_replans = 0
	_start_route(approach)
	_pending = thing
	_pending_item = item_path
	_pending_point = point


func walk_to(point: Vector3) -> void:
	cancel()
	_replans = 0
	_start_route(point)


func _start_route(point: Vector3) -> void:
	_unsticks = 0
	_goal = point
	_route_gen = walk.generation if walk else 0
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
	if _await_bake:
		if walk.pending():
			return Vector3.ZERO
		_await_bake = false
		_start_route(_goal)
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
			# Caught on a corner the route hugged (it is planned for a thinner
			# agent than the capsule): plan again through the middle of the
			# walkable areas before giving up.
			if walk and _unsticks < 2:
				_unsticks += 1
				_route = walk.route(pos, _goal, false)
				_route_i = 0
				_stuck = 0.0
				_last_pos = pos
				return Vector3.ZERO
			_arrive()
			return Vector3.ZERO
		_stuck = 0.0
		_last_pos = pos
	var dir := flat.normalized()
	# Ease the view round towards where we are going.
	player.rotation.y = lerp_angle(player.rotation.y, atan2(-dir.x, -dir.z), 1.0 - exp(-5.0 * delta))
	return dir


func _arrive() -> void:
	# Stopped short because the route came from before a door opened (the
	# walk mesh re-bakes once doors finish moving): plan again on the new one.
	var short := player.eye().distance_to(_pending_point) > FirstPersonPlayer.REACH if _pending else _flat_distance(_goal) > 0.6
	if walk and _replans < 2 and short and (walk.pending() or walk.generation != _route_gen):
		_replans += 1
		_route = PackedVector3Array()
		_await_bake = true
		return
	var thing := _pending
	_route = PackedVector3Array()
	_pending = null
	if thing == null or not is_instance_valid(thing):
		return
	if player.eye().distance_to(_pending_point) <= FirstPersonPlayer.REACH + 0.4:
		_use(thing, _pending_point, _pending_item)
	else:
		Game.toast("You can't reach that from here.")


func _flat_distance(p: Vector3) -> float:
	return Vector2(player.global_position.x - p.x, player.global_position.z - p.z).length()


## Touch screens show no hover highlight, so things in reach that can be
## picked up glint faintly instead (Settings.glint_items).
func _update_glints(delta: float) -> void:
	_glint_timer -= delta
	if _glint_timer > 0.0:
		return
	_glint_timer = 0.3
	var want: Array[Interactable] = []
	if Settings.glint_items and Device.is_touch() and player.input_enabled:
		for n: Variant in Game._nodes.values():
			var item := n as Item
			if item and item.is_available() and player.eye().distance_to(item.global_position) <= GLINT_M \
					and player.camera.is_position_in_frustum(item.global_position):
				want.append(item)
	for i in _glinting:
		if is_instance_valid(i) and not i in want:
			i.set_glint(false)
	for i in want:
		i.set_glint(true)
	_glinting = want


func _exit_tree() -> void:
	for i in _glinting:
		if is_instance_valid(i):
			i.set_glint(false)


## The mouse-hovered thing (updated every physics step as the view moves).
func update_hover() -> Interactable:
	_update_glints(player.get_physics_process_delta_time())
	hover = null
	if dragging_item:
		hover = drag_target
	elif _mouse_inside and not _down:
		hover = player.pick(_mouse_pos).get("interactable")
	return hover


func mouse_position() -> Vector2:
	return _mouse_pos
