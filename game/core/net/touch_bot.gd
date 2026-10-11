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
## With `desktop` (--deskbot, ?deskbot=1) it plays the classic way instead:
## W A S D and mouse look, the crosshair and E, number keys for items, mouse
## clicks on panels and Esc to close them. Classic play needs a captured
## mouse, so it runs in a browser: when the game wants a click to capture the
## pointer it prints "DESKBOT: CLICK" and the test harness clicks the page.
## With `tour` (--bot-tour, &tour=1) it plays at a watching pace, to record a
## play-through: smooth turns, the briefing and every clue held open long
## enough to read, a pause after each step, and "step N begin" lines to time
## captions by (tools/playthrough.sh).

const STEP_PAUSE_S := 0.4
const WALK_TIMEOUT_S := 25.0
## Finger travel per drag gesture, as a share of the screen width.
const MAX_DRAG := 0.5
## Tour pace: the most the view turns per physics frame (about 140 degrees a
## second), and how long the briefing, a clue, a look and a step's result
## stay on screen.
const TOUR_TURN := 0.04
const TOUR_INTRO_S := 8.0
const TOUR_READ_S := 7.0
const TOUR_LOOK_S := 3.0
const TOUR_STEP_S := 1.5

var session: PlaySession
## Classic keyboard and mouse controls instead of touch.
var desktop := false
## Desktop: use items by freeing the cursor (I) and dragging them out of the
## inventory, instead of number keys and E.
var desktop_drag := false
## Play at a watching pace (see the class notes).
var tour := false
## Steps before this one are done by intent (to start a touch run part-way).
var first_step := 0
## Dev play from part-way: after the steps before first_step, stop and leave
## the room to the player (no touches of its own).
var hand_over := false
var problems: Array[String] = []

var _results: Array = []  # [path, verb, ok]
var _last_change_ms := 0
## Desktop mode plans walks on its own walk mesh (classic play has none).
var _planner: WalkMesh
var TAG := "TOUCHBOT"


func _ready() -> void:
	if desktop:
		TAG = "DESKBOT"
	Game.intent_result.connect(func(path: String, verb: String, r: Dictionary) -> void:
		_results.append([path, verb, bool(r.get("ok", false))]))
	Game.toasted.connect(func(t: String) -> void: print("%s:   (toast) %s" % [TAG, t]))
	Game.node_state_changed.connect(func(_p: String, _s: Dictionary) -> void: _last_change_ms = Time.get_ticks_msec())
	_run.call_deferred()


func _player() -> FirstPersonPlayer:
	return session.player


func _hud() -> Hud:
	return session.hud


func _walk() -> WalkMesh:
	return _planner if desktop else _player().pointer.walk


func _run() -> void:
	await _frames(30)
	Settings.controls = "classic" if desktop else "point"
	_hud().apply_controls()
	if desktop:
		_planner = WalkMesh.new()
		add_child(_planner)
		_planner.setup(Game.room)
	await _frames(10)
	if tour:
		await _wait(TOUR_INTRO_S)
	await _close_panels()
	Game.start_clock()
	var steps: Array = Game.manifest.solution
	print("%s: %d steps in %s" % [TAG, steps.size(), Game.manifest.id])
	if first_step > 0 and Game.room is RoomRoot and (Game.room as RoomRoot).airlock() != null:
		# Steps done by intent start inside: routes from the ledge stop at a
		# sealed airlock door.
		_player().place_at((Game.room as RoomRoot).airlock().late_spawn_transform())
		await _frames(2)
	for i in steps.size():
		if hand_over and i == first_step:
			# Stand where the next step can be done from, facing it.
			var next := SolutionPlayer.intent_for(steps[i], Game._nodes, Game.vars())
			var target := Game.node_at(str(next.get("path", steps[i].get("node", steps[i].get("target", ""))))) as Node3D
			if target:
				if target is Interactable:
					await _reach(target as Interactable)
				await _look_at(_aim_point(target))
			await _wait(1.0)
			print("%s: handed over at step %d" % [TAG, i])
			return
		if i < first_step:
			var intent := SolutionPlayer.intent_for(steps[i], Game._nodes, Game.vars())
			if intent.has("path"):
				var n := Game.node_at(intent["path"])
				_player().place_at(Transform3D(Basis(), _walk().route(_player().global_position, n.global_position)[-1]))
				Game.report_position(n.global_position, 0.0)
				Game.request(n, intent["verb"], intent["payload"])
				await _wait(0.2)
			continue
		if Game.world() and Game.world().won:
			print("%s: won before step %d; the rest of the solution is not needed" % [TAG, i])
			break
		if tour:
			print("%s: step %d begin" % [TAG, i])
		await _step(i, steps[i])
		await _settle()
		if tour:
			await _wait(TOUR_STEP_S)
	await _wait(1.0)
	var won := Game.world() != null and Game.world().won
	print("%s: won=%s" % [TAG, won])
	if tour:
		await _wait(8.0)  # the end screen
	if not won:
		problems.append("the room was not won")
	print("%s: done, %d problems" % [TAG, problems.size()])
	for p in problems:
		print("%s:   %s" % [TAG, p])
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
			if tour:
				await _wait(TOUR_LOOK_S)
		print("%s: step %d %s %s (looked)" % [TAG, i, act, target_path])
		return
	_results.clear()
	var why := ""
	match act:
		"interact" when node is PatchPanel:
			why = await _patch(node as PatchPanel, str(intent["payload"].get("value", "")))
		"interact" when node is IndexedMechanism and intent["verb"] == "set":
			why = await _set_mechanism(node as IndexedMechanism, str(intent["payload"].get("value", "")))
		"pick_up", "interact", "examine", "use":
			why = await _tap_thing(node, str(intent["verb"]))
			if why.is_empty() and _hud().is_modal_open():
				await _wait(TOUR_READ_S if tour else 0.3)
				await _close_panels()
		"input_code":
			why = await _enter_code(node, str(intent["payload"]["value"]))
		"use_on":
			why = await _use_item(str(intent["payload"]["item"]), node)
		"submit_flag":
			why = await _submit_flag(node as Terminal, str(intent["payload"]["value"]))
		_:
			why = "no way to %s" % act
	if why.is_empty() and node is IndexedMechanism and intent["verb"] == "set":
		_results.append([str(intent["path"]), "set", true])  # _set_mechanism checked the position
	var t := 0.0
	while why.is_empty() and not _succeeded(str(intent["path"]), node) and t < 8.0:
		await _wait(0.25)
		t += 0.25
	if why.is_empty() and not _succeeded(str(intent["path"]), node):
		why = "touched, but the step did not take effect (results: %s, modal %s)" % [_results, _hud()._modal]
	if not why.is_empty():
		_fail(i, act, "%s: %s" % [target_path, why], intent)
	else:
		print("%s: step %d %s %s ok (at %s)" % [TAG, i, act, target_path, _player().global_position.snapped(Vector3.ONE * 0.1)])
	await _close_panels()


## Waits, as a player watching would, until nothing has changed for a moment
## (a case swinging open on a spring, a door finishing) and the walk mesh has
## caught up.
func _settle() -> void:
	await _wait(STEP_PAUSE_S)
	var t := 0.0
	while t < 10.0 and (Time.get_ticks_msec() - _last_change_ms < 2500 or _walk().pending()):
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
	print("%s: %s %s" % [TAG, "DESK-FAIL" if desktop else "TOUCH-FAIL", line])
	await _close_panels()
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
	if desktop:
		# Like a player reading the prompt before pressing E: aim until the
		# crosshair is on it, and check again just before the key.
		for attempt in 3:
			var why := await _aim(node)
			if not why.is_empty():
				return why
			await get_tree().physics_frame
			if _player().target == node:
				if tour:
					await _wait(0.5)  # reads the prompt
				await _key(KEY_E)
				await _wait(0.3)
				return ""
		return "the crosshair kept slipping off it onto %s" % (_player().target.eb_path if _player().target else "nothing")
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
		if c.is_visible_in_tree() and c.mouse_filter != Control.MOUSE_FILTER_IGNORE \
				and c.get_global_rect().has_point(s):
			return true
	return false


## Turns the view onto `point` with finger drags (or the mouse), as a player
## would.
func _look_at(point: Vector3) -> void:
	if desktop:
		await _mouse_look_at(point)
		return
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
	if desktop:
		return
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
				await _press_control(arrows[w * 2 + (1 if down else 0)])
		return ""
	return "tapping it opened %s, not a code panel" % (panel.get_class() if panel else "nothing")


## A stepped control (plate, screen, mirror): tap it until it shows the
## position, as a player would; each tap moves it one step.
func _set_mechanism(m: IndexedMechanism, value: String) -> String:
	var want := m.index_of(value)
	if want < 0:
		return "it has no position %s" % value
	# On a tour, a control that can be worked through a sight is set the way
	# its puzzle means: looking through the sight and using its buttons.
	if tour and desktop:
		var vp := _sight_for(m)
		if vp:
			return await _set_through_sight(vp, m, want)
	for _t in m.detents.size():
		if int(m.current_state.get("index", 0)) == want:
			return ""
		var before := int(m.current_state.get("index", 0))
		var why := await _tap_thing(m, "turn")
		if not why.is_empty():
			return why
		var t := 0.0
		while t < 3.0 and int(m.current_state.get("index", 0)) == before:
			await _wait(0.1)
			t += 0.1
	return "" if int(m.current_state.get("index", 0)) == want else "tapping it did not bring it to %s" % value


## An open Viewpoint in the room that lists `m` among its controls.
func _sight_for(m: IndexedMechanism) -> Viewpoint:
	# find_children's type filter knows native classes only, not class_names.
	for n in Game.room.find_children("*", "", true, false):
		var vp := n as Viewpoint
		if vp == null or not vp.is_open():
			continue
		for p in vp.controls:
			if vp.get_node_or_null(p) == m:
				return vp
	return null


func _set_through_sight(vp: Viewpoint, m: IndexedMechanism, want: int) -> String:
	var i := -1
	for k in vp.controls.size():
		if vp.get_node_or_null(vp.controls[k]) == m:
			i = k
	if not _hud()._modal is ViewpointPanel:
		var why := await _tap_thing(vp, "look")
		if not why.is_empty():
			return why
		await _wait(1.0)
	var panel := _hud()._modal as ViewpointPanel
	if panel == null:
		return "using the sight opened no view"
	var button := panel.find_child("Control%d" % i, true, false) as Button
	if button == null:
		return "the sight has no button for it"
	for _t in m.detents.size():
		if int(m.current_state.get("index", 0)) == want:
			break
		var before := int(m.current_state.get("index", 0))
		await _press_control(button)
		var t := 0.0
		while t < 3.0 and int(m.current_state.get("index", 0)) == before:
			await _wait(0.1)
			t += 0.1
		await _wait(m.move_time + 0.4)
	await _wait(1.5)  # a look at the result before stepping back
	return "" if int(m.current_state.get("index", 0)) == want else "the sight's button did not bring it to %d" % want


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
		await _press_control(picker)
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
	await _press_control(field)  # focus (a phone would raise its keyboard here)
	field.text = value
	field.text_submitted.emit(value)
	await _wait(0.5)
	return ""


func _press_button(panel: Node, text: String) -> bool:
	for b: Button in panel.find_children("*", "Button", true, false):
		if b.text == text and b.is_visible_in_tree():
			await _press_control(b)
			return true
	return false


## Closes any open panel with its own Close/Resume button (Esc on a desktop).
func _close_panels() -> void:
	var panel: Node = _hud()._modal
	if panel == null or panel is EndScreen:
		return  # the end screen is meant to stay
	if desktop:
		await _key(KEY_ESCAPE)
		await _frames(3)
		if _hud()._modal == null:
			return
	var screen := Rect2(Vector2.ZERO, _player().get_viewport().get_visible_rect().size)
	for b: Button in panel.find_children("*", "Button", true, false):
		if (b.text.begins_with("Close") or b.text.begins_with("Start") or b.text.begins_with("Resume")) \
				and b.is_visible_in_tree() and screen.has_point(_centre(b)) and _visible_in_scroll(b):
			await _press_control(b)
			await _frames(3)
			if _hud()._modal == null:
				return
	problems.append("a %s panel could not be closed%s" % [panel.get_class(), " with Esc or its Close button" if desktop else " with a Close button a finger could reach"])
	print("%s: FAIL %s" % [TAG, problems[-1]])
	(panel as ModalPanel).close()


## False when `c` is scrolled out of its ScrollContainer's view.
func _visible_in_scroll(c: Control) -> bool:
	var n := c.get_parent()
	while n != null and not n is ScrollContainer:
		n = n.get_parent()
	if n == null:
		return true
	var sc := n as ScrollContainer
	var view := Rect2(sc.get_global_transform_with_canvas().origin, sc.size * sc.get_global_transform_with_canvas().get_scale())
	return view.has_point(_centre(c))


# --- Inventory drag ----------------------------------------------------------

func _use_item(item_path: String, target: Interactable) -> String:
	if desktop:
		return await _use_item_keys(item_path, target)
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


## Presses a button: a finger tap, or a mouse click on a desktop.
func _press_control(c: Control) -> void:
	if desktop:
		await _click(_centre(c))
	else:
		await _tap(_centre(c))
	if tour:
		await _wait(0.35)


## A finger tap at a viewport position.
func _tap(at: Vector2) -> void:
	# A quick finger: down and up before the next frame, whatever the frame
	# rate (a slow device would otherwise stretch the tap past the tap window).
	_touch(at, true)
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


# --- Desktop: keyboard and mouse ---------------------------------------------

## Classic play needs the pointer captured; in a browser only a real click on
## the page can do that, so ask the harness for one, as a player clicks to play.
func _ensure_captured() -> String:
	var t := 0.0
	while Input.mouse_mode != Input.MOUSE_MODE_CAPTURED and t < 15.0:
		if _hud()._modal != null:
			await _close_panels()
		if OS.has_feature("web"):
			print("DESKBOT: CLICK")
		else:
			Input.mouse_mode = Input.MOUSE_MODE_CAPTURED
		await _wait(0.5)
		t += 0.5
	return "" if Input.mouse_mode == Input.MOUSE_MODE_CAPTURED else "the mouse could not be captured (a headless engine cannot; run --deskbot in a browser)"


## Turns the view with mouse movement until the crosshair is on `point`.
func _mouse_look_at(point: Vector3) -> void:
	if not (await _ensure_captured()).is_empty():
		return
	var p := _player()
	var sens := Settings.mouse_sensitivity
	for pass_i in 4:
		var to := point - p.eye()
		var yaw := wrapf(atan2(-to.x, -to.z) - p.rotation.y, -PI, PI)
		var pitch := atan2(to.y, Vector2(to.x, to.z).length()) - p.camera.rotation.x
		if absf(yaw) < 0.01 and absf(pitch) < 0.01:
			return
		# Classic look: yaw -= x * sens, pitch -= y * sens (not inverted).
		var rel := Vector2(-yaw / sens, -pitch / sens * (-1.0 if Settings.invert_y else 1.0))
		var steps := maxi(1, int(ceil(rel.length() / 120.0)))
		if tour:
			steps = maxi(steps, int(ceil(Vector2(yaw, pitch).length() / TOUR_TURN)))
		for k in steps:
			var ev := InputEventMouseMotion.new()
			ev.relative = rel / steps
			Input.parse_input_event(ev)
			await get_tree().physics_frame
	await get_tree().physics_frame


## Puts the crosshair on `node` from within reach, walking there with the keys
## if needed. Returns "" or why not.
func _aim(node: Interactable) -> String:
	var why := await _ensure_captured()
	if not why.is_empty():
		return why
	if await _crosshair_on(node):
		return ""
	var aim := _aim_point(node)
	var toward := _player().eye() - aim
	toward.y = 0.0
	var spots: Array[Vector3] = []
	# First in front of what it faces (a panel on a wall), then the nearest
	# place the walk reaches (a thing down in a pit is seen from its edge).
	var facing := node.global_basis.z.normalized()
	facing.y = 0.0
	if facing.length() > 0.5:
		var front := aim + facing.normalized() * 1.0
		var to_front := _walk().route(_player().global_position, Vector3(front.x, _player().global_position.y, front.z))
		if not to_front.is_empty():
			spots.append(to_front[to_front.size() - 1])
	var reach := _walk().route(_player().global_position, aim)
	if not reach.is_empty():
		spots.append(reach[reach.size() - 1])
	if toward.length() > 0.01:
		spots.append(aim + toward.normalized() * 1.0 + Vector3.DOWN * 1.1)
	for r: float in [1.0, 1.6]:
		for k in 8:
			var a := TAU * k / 8.0
			spots.append(aim + Vector3(sin(a) * r, -1.1, cos(a) * r))
	# Past the first spot it is hunting; a tour marks that span so the
	# recording can cut it (tools/playthrough.py).
	var hunting := false
	for spot in spots.slice(0, 11):
		if tour and spot != spots[0] and not hunting:
			hunting = true
			print("%s: hunt begin" % TAG)
		await _walk_keys_to(spot)
		if await _crosshair_on(node):
			if hunting:
				print("%s: hunt end" % TAG)
			return ""
	if hunting:
		print("%s: hunt end" % TAG)
	return "the crosshair could not be put on it from 11 spots (last at %s, %.1f m away; the crosshair hits %s)" % [
		_player().global_position.snapped(Vector3.ONE * 0.1), _player().eye().distance_to(aim),
		Game.room.get_path_to(_player().ray.get_collider()) if _player().ray.is_colliding() else "nothing"]


## Looks at the node's centre and around its collider until the crosshair
## targets it within reach.
func _crosshair_on(node: Interactable) -> bool:
	var box := _bounds(node)
	var points: Array[Vector3] = [box.get_center()]
	for f in [0.25, 0.75]:
		for h in [0.3, 0.7]:
			points.append(box.position + box.size * Vector3(f, h, 0.5))
			points.append(box.position + box.size * Vector3(0.5, h, f))
	for pt in points:
		if _player().eye().distance_to(pt) > FirstPersonPlayer.REACH + 0.2:
			continue
		await _mouse_look_at(pt)
		await get_tree().physics_frame
		await get_tree().physics_frame
		if _player().target == node:
			return true
	return false


## Walks to `spot` on the planned route with W held, steering with the mouse.
func _walk_keys_to(spot: Vector3) -> void:
	var route := _walk().route(_player().global_position, spot)
	_hold(KEY_W, true)
	for wp in route:
		if tour:
			# Turn on the spot to face the next leg, then walk it: steering
			# at tour pace with W held would circle the waypoint.
			var to := Vector3(wp.x, _player().eye().y, wp.z)
			var flat_to := Vector2(wp.x - _player().global_position.x, wp.z - _player().global_position.z)
			var off := wrapf(atan2(-flat_to.x, -flat_to.y) - _player().rotation.y, -PI, PI)
			if flat_to.length() > 0.25 and absf(off) > 0.3:
				_hold(KEY_W, false)
				await _mouse_look_at(to)
				_hold(KEY_W, true)
		var t := 0.0
		var last := _player().global_position
		var stuck := 0.0
		while t < WALK_TIMEOUT_S:
			var pos := _player().global_position
			var flat := Vector2(wp.x - pos.x, wp.z - pos.z)
			if flat.length() < 0.25:
				break
			await _mouse_look_at(Vector3(wp.x, _player().eye().y, wp.z))
			for f in 6:
				await get_tree().physics_frame
			t += 6.0 / Engine.physics_ticks_per_second
			stuck += 6.0 / Engine.physics_ticks_per_second
			if stuck > 0.8:
				if pos.distance_to(last) < 0.1:
					break
				last = pos
				stuck = 0.0
	_hold(KEY_W, false)
	await get_tree().physics_frame


func _use_item_keys(item_path: String, target: Interactable) -> String:
	var i := Game.inventory().find(item_path)
	if i < 0:
		return "the item is not in the inventory"
	if desktop_drag:
		return await _use_item_cursor_drag(item_path, i, target)
	if i > 8:
		return "item %d has no number key (only 1-9)" % (i + 1)
	if Game.selected_item != item_path:
		await _key(KEY_1 + i)
		if tour:
			await _wait(0.6)
	if Game.selected_item != item_path:
		return "key %d did not select it" % (i + 1)
	var why := await _aim(target)
	if not why.is_empty():
		return why
	await _key(KEY_E)
	await _wait(0.3)
	if Game.selected_item == item_path and Game.inventory().has(item_path):
		await _key(KEY_Q)  # put it away again
	return ""


## A key tapped (pressed and released) through the real input path.
func _key(k: Key) -> void:
	_hold(k, true)
	await get_tree().physics_frame
	_hold(k, false)
	await _frames(2)


func _hold(k: Key, down: bool) -> void:
	var ev := InputEventKey.new()
	ev.physical_keycode = k
	ev.keycode = k
	ev.pressed = down
	Input.parse_input_event(ev)


## A left click at a viewport position, with the mouse moved there first.
func _click(at: Vector2) -> void:
	var m := InputEventMouseMotion.new()
	m.position = _to_window(at)
	m.global_position = m.position
	Input.parse_input_event(m)
	await _frames(1)
	for down: bool in [true, false]:
		var b := InputEventMouseButton.new()
		b.button_index = MOUSE_BUTTON_LEFT
		b.pressed = down
		b.position = _to_window(at)
		b.global_position = b.position
		Input.parse_input_event(b)
		await _frames(1)
	await _frames(2)


## Desktop drag and drop: aim at the target, free the cursor with I, drag the
## item's slot onto it with the mouse, then I again to look around.
func _use_item_cursor_drag(item_path: String, i: int, target: Interactable) -> String:
	var why := await _aim(target)
	if not why.is_empty():
		return why
	# A drop is only taken within reach of the body, not just of the crosshair:
	# step in close first, as a player would.
	if _player().eye().distance_to(_aim_point(target)) > FirstPersonPlayer.REACH * 0.8:
		var near := _walk().route(_player().global_position, _aim_point(target))
		if not near.is_empty():
			await _walk_keys_to(near[near.size() - 1])
		why = await _aim(target)
		if not why.is_empty():
			return why
	await _key(KEY_I)
	await _frames(3)
	if not _hud().cursor_mode:
		return "I did not free the cursor"
	var slot := _hud()._inventory.get_node_or_null("Slot%d" % (i + 1)) as Control
	if slot == null:
		await _key(KEY_I)
		return "no inventory slot for it"
	var from := _centre(slot)
	var to := _player().camera.unproject_position(_aim_point(target))
	_mouse_button(from, true)
	await _frames(1)
	for k in range(1, 13):
		var m := InputEventMouseMotion.new()
		m.position = _to_window(from.lerp(to, k / 12.0))
		m.global_position = m.position
		m.relative = _to_window(to - from) / 12.0
		m.button_mask = MOUSE_BUTTON_MASK_LEFT
		Input.parse_input_event(m)
		await _frames(1)
	_mouse_button(to, false)
	await _wait(0.4)
	if _hud().cursor_mode:
		await _key(KEY_I)
	return ""


func _mouse_button(at: Vector2, down: bool) -> void:
	var b := InputEventMouseButton.new()
	b.button_index = MOUSE_BUTTON_LEFT
	b.pressed = down
	b.position = _to_window(at)
	b.global_position = b.position
	Input.parse_input_event(b)
