class_name TouchBot
extends Node
## Test client (ADR-0038): plays a room's solution offline the way a phone
## player does, through injected finger touches only. It turns with drags,
## walks and uses things with taps, presses panel buttons, and drags items
## out of the inventory. Each step it cannot do by touch is logged as a
## TOUCH-FAIL with the reason, then done by intent so the run carries on and
## finds every gap. Prints "TOUCHBOT: done, N problems"; headless runs quit
## with 0 (none) or 2.
##   godot --path game -- --room clockmaker --touchbot     (or ?room=..&touchbot=1)

const STEP_PAUSE_S := 0.4
const WALK_TIMEOUT_S := 25.0
## Finger travel per drag gesture, as a share of the screen width.
const MAX_DRAG := 0.5

var session: PlaySession
## Steps before this one are done by intent (to start a touch run part-way).
var first_step := 0
var problems: Array[String] = []

var _results: Array = []  # [path, verb, ok]
var _last_change_ms := 0


func _ready() -> void:
	Game.intent_result.connect(func(path: String, verb: String, r: Dictionary) -> void:
		_results.append([path, verb, bool(r.get("ok", false))]))
	Game.toasted.connect(func(t: String) -> void: print("TOUCHBOT:   (toast) %s" % t))
	Game.node_state_changed.connect(func(_p: String, _s: Dictionary) -> void: _last_change_ms = Time.get_ticks_msec())
	_run.call_deferred()


func _player() -> FirstPersonPlayer:
	return session.player


func _hud() -> Hud:
	return session.hud


func _run() -> void:
	await _frames(30)
	Settings.controls = "point"
	_hud().apply_controls()
	await _frames(10)
	_close_panels_by_touch()
	Game.start_clock()
	var steps: Array = Game.manifest.solution
	print("TOUCHBOT: %d steps in %s" % [steps.size(), Game.manifest.id])
	for i in steps.size():
		if i < first_step:
			var intent := SolutionPlayer.intent_for(steps[i], Game._nodes, Game.vars())
			if intent.has("path"):
				var n := Game.node_at(intent["path"])
				_player().place_at(Transform3D(Basis(), _player().pointer.walk.route(_player().global_position, n.global_position)[-1]))
				Game.report_position(n.global_position, 0.0)
				Game.request(n, intent["verb"], intent["payload"])
				await _wait(0.2)
			continue
		await _step(i, steps[i])
		await _settle()
	await _wait(1.0)
	var won := Game.world() != null and Game.world().won
	print("TOUCHBOT: won=%s" % won)
	if not won:
		problems.append("the room was not won")
	print("TOUCHBOT: done, %d problems" % problems.size())
	for p in problems:
		print("TOUCHBOT:   %s" % p)
	if DisplayServer.get_name() == "headless":
		get_tree().quit(0 if problems.is_empty() else 2)


func _step(i: int, step: Dictionary) -> void:
	var act := str(step.get("act"))
	var intent := SolutionPlayer.intent_for(step, Game._nodes, Game.vars())
	if intent.has("error"):
		_fail(i, act, str(intent["error"]), {})
		return
	var target_path := str(step.get("node", step.get("target", step.get("lock", ""))))
	if act == "pick_up" or act == "submit_flag":
		target_path = str(intent["path"])
	var node := Game.node_at(target_path) as Interactable
	if intent.is_empty():
		# Observation only (looking at a mark on a wall): turn to it if it exists.
		if node:
			await _look_at(_aim_point(node))
		print("TOUCHBOT: step %d %s %s (looked)" % [i, act, target_path])
		return
	_results.clear()
	var why := ""
	match act:
		"interact" when node is PatchPanel:
			why = await _patch(node as PatchPanel, str(intent["payload"].get("value", "")))
		"pick_up", "interact", "examine", "use":
			why = await _tap_thing(node, str(intent["verb"]))
			if why.is_empty() and _hud().is_modal_open():
				await _wait(0.3)
				_close_panels_by_touch()
		"input_code":
			why = await _enter_code(node, str(intent["payload"]["value"]))
		"use_on":
			why = await _use_item(str(intent["payload"]["item"]), node)
		"submit_flag":
			why = await _submit_flag(node as Terminal, str(intent["payload"]["value"]))
		_:
			why = "no touch way to %s" % act
	var t := 0.0
	while why.is_empty() and not _succeeded(str(intent["path"]), node) and t < 8.0:
		await _wait(0.25)
		t += 0.25
	if why.is_empty() and not _succeeded(str(intent["path"]), node):
		why = "touched, but the step did not take effect (results: %s, modal %s)" % [_results, _hud()._modal]
	if not why.is_empty():
		_fail(i, act, "%s: %s" % [target_path, why], intent)
	else:
		print("TOUCHBOT: step %d %s %s ok (at %s)" % [i, act, target_path, _player().global_position.snapped(Vector3.ONE * 0.1)])
	_close_panels_by_touch()


## Waits, as a player watching would, until nothing has changed for a moment
## (a case swinging open on a spring, a door finishing) and the walk mesh has
## caught up.
func _settle() -> void:
	await _wait(STEP_PAUSE_S)
	var t := 0.0
	while t < 10.0 and (Time.get_ticks_msec() - _last_change_ms < 2500 or _player().pointer.walk.pending()):
		await _wait(0.25)
		t += 0.25


func _succeeded(path: String, node: Node) -> bool:
	for r: Array in _results:
		if r[0] == path and r[2]:
			return true
	return node is Lock and (node as Lock).is_unlocked()


## Logs the gap, then does the step by intent so later steps can run.
func _fail(i: int, act: String, why: String, intent: Dictionary) -> void:
	var line := "step %d %s: %s (player at %s)" % [i, act, why, _player().global_position.snapped(Vector3.ONE * 0.1)]
	problems.append(line)
	print("TOUCHBOT: TOUCH-FAIL %s" % line)
	_close_panels_by_touch()
	if intent.has("path"):
		Game.report_position(Game.node_at(intent["path"]).global_position, 0.0)
		Game.request(Game.node_at(intent["path"]), intent["verb"], intent["payload"])
		await _wait(0.5)


# --- Reaching and tapping things ---------------------------------------------

## Taps `node` the way a player would: from where it can be seen and touched.
## Returns "" or why it could not.
func _tap_thing(node: Interactable, verb: String) -> String:
	if node is Item or node is Document or node is Lock or node is Terminal or node is PatchPanel:
		pass
	elif node.current_verb() != verb and node.current_verb() != "use":
		return "a tap would %s, the step needs %s" % [node.current_verb(), verb]
	var at: Variant = await _reach(node)
	if at is String:
		return at
	await _tap(at)
	await _wait_walk()
	await _wait(PointerControls.TURN_TIME + 0.3)
	return ""


## Brings `node` into view and touch range; returns a screen position that
## picks it, or a reason (String).
func _reach(node: Interactable) -> Variant:
	var aim := _aim_point(node)
	await _look_at(aim)
	var at: Variant = _tappable_point(node)
	if at is Vector2:
		return at
	# Try standing spots around it, nearest first, as a player would.
	var spots: Array[Vector3] = []
	for r: float in [1.0, 1.6]:
		for k in 8:
			var a := TAU * k / 8.0
			spots.append(aim + Vector3(sin(a) * r, -1.1, cos(a) * r))
	var here := _player().global_position
	spots.sort_custom(func(a: Vector3, b: Vector3) -> bool: return a.distance_to(here) < b.distance_to(here))
	for spot in spots.slice(0, 8):
		_player().pointer.walk_to(spot)
		await _wait_walk()
		await _look_at(aim)
		at = _tappable_point(node)
		if at is Vector2:
			return at
	var cam := _player().camera
	var hit := _player().pick(cam.unproject_position(aim)) if not cam.is_position_behind(aim) else {}
	var what := "nothing"
	if not hit.is_empty():
		what = "%s at %.1f m" % [Game.room.get_path_to(hit.collider), _player().eye().distance_to(hit.position)]
	return "not tappable from 8 spots around it; from the last, %.1f m away, a tap at its centre hits %s" % [_player().eye().distance_to(aim), what]


## A screen point whose pick is `node`: its centre or around its collider.
func _tappable_point(node: Interactable) -> Variant:
	var cam := _player().camera
	var box := _bounds(node)
	var points: Array[Vector3] = [box.get_center()]
	for f in [0.2, 0.8]:
		for g in [0.2, 0.8]:
			for h in [0.25, 0.75]:
				points.append(box.position + box.size * Vector3(f, h, g))
	var vp := _player().get_viewport().get_visible_rect().size
	for p in points:
		if cam.is_position_behind(p):
			continue
		var s := cam.unproject_position(p)
		if s.x < 8 or s.y < 8 or s.x > vp.x - 8 or s.y > vp.y - 8:
			continue
		if _over_ui(s):
			continue
		if _player().pick(s).get("interactable") == node:
			return s
	return null


func _aim_point(node: Node3D) -> Vector3:
	return _bounds(node).get_center()


## World bounds of the node's visible colliders (its origin if it has none).
func _bounds(node: Node3D) -> AABB:
	var box := AABB()
	var first := true
	for cs: CollisionShape3D in node.find_children("*", "CollisionShape3D", true, false):
		if cs.disabled or cs.shape == null or Interactable.owner_of(cs) != node:
			continue
		var b := cs.global_transform * cs.shape.get_debug_mesh().get_aabb()
		box = b if first else box.merge(b)
		first = false
	return AABB(node.global_position, Vector3.ZERO) if first else box


func _over_ui(s: Vector2) -> bool:
	for c: Control in _hud().find_children("*", "Control", true, false):
		if c.is_visible_in_tree() and c.mouse_filter == Control.MOUSE_FILTER_STOP \
				and (c is Button or c is PanelContainer) and c.get_global_rect().has_point(s):
			return true
	return false


## Turns the view onto `point` with finger drags, as a player would.
func _look_at(point: Vector3) -> void:
	var p := _player()
	var width := p.get_viewport().get_visible_rect().size.x
	var k := PointerControls.DRAG_TURN / maxf(width, 1.0)
	for pass_i in 4:
		var to := point - p.eye()
		var yaw := wrapf(atan2(-to.x, -to.z) - p.rotation.y, -PI, PI)
		var pitch := atan2(to.y, Vector2(to.x, to.z).length()) - p.camera.rotation.x
		if absf(yaw) < 0.02 and absf(pitch) < 0.02:
			return
		# turn() takes -relative * k, so a finger moving left turns left.
		var dx := clampf(-yaw / k, -MAX_DRAG * width, MAX_DRAG * width)
		var dy := clampf(-pitch / k, -MAX_DRAG * width * 0.5, MAX_DRAG * width * 0.5)
		# A finger that moves less than the tap slop taps instead of turning.
		if Vector2(dx, dy).length() < PointerControls.TAP_SLOP * 2.0:
			return
		await _drag(Vector2(width * 0.5, p.get_viewport().get_visible_rect().size.y * 0.4), Vector2(dx, dy))


func _wait_walk() -> void:
	var t := 0.0
	while _player().pointer.is_walking() and t < WALK_TIMEOUT_S:
		await get_tree().physics_frame
		t += 1.0 / Engine.physics_ticks_per_second


# --- Panels ------------------------------------------------------------------

func _enter_code(lock: Interactable, value: String) -> String:
	if lock is SequenceLock:
		return await _strike_sequence(lock as SequenceLock, value)
	var why := await _tap_thing(lock, "submit_code")
	if not why.is_empty():
		return why
	await _wait(0.3)
	var panel: Node = _hud()._modal
	if panel is KeypadPanel:
		for ch in value:
			if not await _press_button(panel, ch):
				return "keypad has no %s key" % ch
		await _press_button(panel, "ENT")
		return ""
	if panel is DialLockPanel:
		var dial := lock as DialLock
		var want := dial.parse_code(value)
		if want.is_empty():
			return "the dial cannot show %s" % value
		var arrows: Array[Button] = []
		for b: Button in panel.find_children("*", "Button", true, false):
			if b.tooltip_text.begins_with("Turn"):
				arrows.append(b)
		for w in want.size():
			var n := dial.symbols(w).size()
			var cur := DialLock.dials_of(dial.current_state)[w]
			var fwd := posmod(want[w] - cur, n)
			var down := fwd <= n / 2
			for _t in (fwd if down else n - fwd):
				await _touch_control(arrows[w * 2 + (1 if down else 0)])
		return ""
	return "tapping it opened %s, not a code panel" % (panel.get_class() if panel else "nothing")


## Patch panel: tap each cable's port picker (a dropdown), choose the port,
## then tap Connect. The choice in the opened list is made in code: popup
## item rectangles are not exposed, and the tap that opens it is the test.
func _patch(pp: PatchPanel, value: String) -> String:
	var why := await _tap_thing(pp, "patch")
	if not why.is_empty():
		return why
	await _wait(0.3)
	var ui := _hud()._modal as PatchPanelUI
	if ui == null:
		return "tapping it opened no patch view"
	for pair in value.split(","):
		var kv := pair.split(":")
		var picker: OptionButton = ui._pickers.get(kv[0].strip_edges())
		if picker == null:
			return "no picker for cable %s" % kv[0]
		await _touch_control(picker)
		await _frames(3)
		if not picker.get_popup().visible:
			return "tapping cable %s's picker did not open its list" % kv[0]
		picker.select(picker.get_item_index(int(kv[1])))
		picker.get_popup().hide()
		await _frames(2)
	if not await _press_button(ui, "Connect"):
		return "no Connect button"
	return ""


func _strike_sequence(lock: SequenceLock, value: String) -> String:
	var pads := {}
	for pad: SequencePad in Game.room.find_children("*", "SequencePad", true, false):
		if pad.lock() == lock:
			pads[pad.symbol.to_upper()] = pad
	var symbols := value.split(",") if value.contains(",") else value.split("")
	for sym in symbols:
		var pad: SequencePad = pads.get(sym.strip_edges().to_upper())
		if pad == null:
			return "no pad for %s" % sym
		var why := await _tap_thing(pad, pad.current_verb())
		if not why.is_empty():
			return "pad %s: %s" % [sym, why]
	return ""


func _submit_flag(term: Terminal, value: String) -> String:
	var why := await _tap_thing(term, "terminal")
	if not why.is_empty():
		return why
	await _wait(0.3)
	var panel: Node = _hud()._modal
	if not panel is TerminalPanel:
		return "tapping it opened %s" % (panel.get_class() if panel else "nothing")
	var field: LineEdit = (panel as TerminalPanel)._input
	await _touch_control(field)  # focus (a phone would raise its keyboard here)
	field.text = value
	field.text_submitted.emit(value)
	await _wait(0.5)
	return ""


func _press_button(panel: Node, text: String) -> bool:
	for b: Button in panel.find_children("*", "Button", true, false):
		if b.text == text and b.is_visible_in_tree():
			await _touch_control(b)
			return true
	return false


## Closes any open panel with its own Close/Resume button.
func _close_panels_by_touch() -> void:
	var panel: Node = _hud()._modal
	if panel == null:
		return
	for b: Button in panel.find_children("*", "Button", true, false):
		if b.text.begins_with("Close") or b.text.begins_with("Start") or b.text.begins_with("Resume"):
			await _touch_control(b)
			await _frames(3)
			return
	(panel as ModalPanel).close()


# --- Inventory drag ----------------------------------------------------------

func _use_item(item_path: String, target: Interactable) -> String:
	var at: Variant = await _reach(target)
	if at is String:
		return at
	var i := Game.inventory().find(item_path)
	if i < 0:
		return "the item is not in the inventory"
	var slot := _hud()._inventory.get_node_or_null("Slot%d" % (i + 1)) as Control
	if slot == null:
		return "no inventory slot for it"
	var from := _centre(slot)
	await _drag(from, (at as Vector2) - from, 16)
	await _wait_walk()
	await _wait(PointerControls.TURN_TIME + 0.3)
	return ""


# --- Injected touches --------------------------------------------------------

func _centre(c: Control) -> Vector2:
	return c.get_global_transform_with_canvas() * (c.size / 2.0)


func _touch_control(c: Control) -> void:
	await _tap(_centre(c))


## A finger tap at a viewport position.
func _tap(at: Vector2) -> void:
	_touch(at, true)
	await _frames(2)
	_touch(at, false)
	await _frames(3)


## A finger pressed at `from`, moved by `by` over `steps` frames, lifted.
func _drag(from: Vector2, by: Vector2, steps: int = 10) -> void:
	_touch(from, true)
	await _frames(1)
	var last := from
	for s in range(1, steps + 1):
		var at := from + by * float(s) / steps
		var ev := InputEventScreenDrag.new()
		ev.index = 0
		ev.position = _to_window(at)
		ev.relative = _to_window(at) - _to_window(last)
		Input.parse_input_event(ev)
		last = at
		await _frames(1)
	_touch(last, false)
	await _frames(3)


func _touch(at: Vector2, pressed: bool) -> void:
	var ev := InputEventScreenTouch.new()
	ev.index = 0
	ev.position = _to_window(at)
	ev.pressed = pressed
	Input.parse_input_event(ev)


## Viewport (canvas) coordinates to the window pixels input events arrive in.
func _to_window(at: Vector2) -> Vector2:
	return _player().get_viewport().get_screen_transform() * at


func _frames(n: int) -> void:
	for _i in n:
		await get_tree().process_frame


func _wait(s: float) -> void:
	await get_tree().create_timer(s).timeout
