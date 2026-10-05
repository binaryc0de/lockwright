class_name Hud
extends CanvasLayer
## In-room HUD: crosshair, context prompt, toasts, intercom banner, clock,
## inventory, and the focused panels. While a panel is open the mouse is free
## and the player is frozen.

signal leave_requested

const HELP := "E interact   F inspect item   1-9 select item   Q deselect   Tab evidence   H hints   Esc menu"
const HELP_POINTER := "Drag to look   Tap the floor to walk   Tap things to use them   Drag an item onto something to use it"
const HELP_POINTER_MOUSE := "Drag to look   Click the floor to walk   Click things to use them   Drag an item onto something to use it"

var player: FirstPersonPlayer
var _modal: ModalPanel = null
var _prompt: Label
var _toast: Label
var _toast_tween: Tween
var _banner: PanelContainer
var _banner_text: Label
var _banner_timer: SceneTreeTimer
var _clock: Label
var _inventory: InventoryBar
var _ended_shown: bool = false
var _ended_won := false
## Browser build: pointer lock needs a click and Esc releases it (ADR-0023).
var _click_hint: Label = null
var _was_captured := false
## Point-and-tap controls (ADR-0038): buttons for what keys do on a desktop.
var _toolbar: HBoxContainer
var _help: Label
var _portrait_tip: Label
var pointer_mode := false


func setup(p: FirstPersonPlayer) -> void:
	player = p
	player.target_changed.connect(func(_t: Interactable) -> void: _update_prompt())
	Game.selected_item_changed.connect(func(_s: String) -> void: _update_prompt())
	Game.toasted.connect(toast)
	Game.hint_revealed.connect(func(_p: String, tier: int, text: String, auto: bool) -> void:
		_show_banner(("Intercom (offered hint): " if auto else "Intercom (hint %d): " % tier) + text))
	Game.narrated.connect(func(t: String) -> void: _show_banner(t))
	Game.puzzle_solved.connect(func(_id: String) -> void: toast("Progress!"))
	Game.session_finished.connect(func(won: bool) -> void: show_end(won))
	Game.time_up.connect(func() -> void: show_end(false))
	Game.hud = self
	apply_controls()


## Applies Settings.controls: classic (captured mouse, keys) or point-and-tap.
func apply_controls() -> void:
	pointer_mode = Settings.pointer_controls()
	if player:
		player.set_pointer_mode(pointer_mode)
	_toolbar.visible = pointer_mode
	_help.text = (HELP_POINTER if Device.is_touch() else HELP_POINTER_MOUSE) if pointer_mode else HELP
	_inventory.show_inspect_button = pointer_mode
	_inventory.rebuild()
	_set_free_mouse(_modal != null)


func _ready() -> void:
	layer = 10
	var root := Control.new()
	root.set_anchors_preset(Control.PRESET_FULL_RECT)
	root.mouse_filter = Control.MOUSE_FILTER_IGNORE
	add_child(root)

	var cross := Label.new()
	_cross = cross
	cross.text = "+"
	cross.add_theme_font_size_override("font_size", 22)
	cross.set_anchors_preset(Control.PRESET_CENTER)
	cross.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	cross.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
	cross.grow_horizontal = Control.GROW_DIRECTION_BOTH
	cross.grow_vertical = Control.GROW_DIRECTION_BOTH
	root.add_child(cross)

	_prompt = _label(root, Control.PRESET_CENTER, 22)
	_prompt.position.y += 48
	_toast = _label(root, Control.PRESET_CENTER, 22)
	_toast.position.y += 92
	_toast.modulate.a = 0.0

	_clock = _label(root, Control.PRESET_TOP_RIGHT, 30)
	_clock.position += Vector2(-24, 16)
	_clock.horizontal_alignment = HORIZONTAL_ALIGNMENT_RIGHT
	_clock.grow_horizontal = Control.GROW_DIRECTION_BEGIN

	var help := _label(root, Control.PRESET_BOTTOM_RIGHT, 15)
	_help = help
	help.text = HELP
	help.horizontal_alignment = HORIZONTAL_ALIGNMENT_RIGHT
	help.grow_horizontal = Control.GROW_DIRECTION_BEGIN
	help.grow_vertical = Control.GROW_DIRECTION_BEGIN
	help.position += Vector2(-16, -12)
	help.modulate.a = 0.7
	_build_toolbar(root)

	_inventory = InventoryBar.new()
	_inventory.set_anchors_preset(Control.PRESET_CENTER_BOTTOM)
	_inventory.grow_horizontal = Control.GROW_DIRECTION_BOTH
	_inventory.grow_vertical = Control.GROW_DIRECTION_BEGIN
	_inventory.position.y -= 40
	root.add_child(_inventory)
	_inventory.item_dragged.connect(_on_item_dragged)
	_inventory.inspect_requested.connect(_inspect_selected)

	_banner = PanelContainer.new()
	_banner.set_anchors_preset(Control.PRESET_CENTER_TOP)
	_banner.grow_horizontal = Control.GROW_DIRECTION_BOTH
	_banner.position.y += 20
	_banner.visible = false
	_banner_text = Label.new()
	_banner_text.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	_banner_text.custom_minimum_size = Vector2(760, 0)
	_banner_text.add_theme_font_size_override("font_size", 21)
	var m := MarginContainer.new()
	for side in ["left", "right", "top", "bottom"]:
		m.add_theme_constant_override("margin_" + side, 14)
	m.add_child(_banner_text)
	_banner.add_child(m)
	root.add_child(_banner)


func _build_toolbar(root: Control) -> void:
	_toolbar = HBoxContainer.new()
	_toolbar.set_anchors_and_offsets_preset(Control.PRESET_TOP_LEFT)
	_toolbar.position = Vector2(16, 16)
	_toolbar.add_theme_constant_override("separation", 10)
	_toolbar.visible = false
	root.add_child(_toolbar)
	_tool("Menu", _open_pause)
	_tool("Evidence", _open_evidence)
	_tool("Hints", func() -> void: (_open(HintsPanel.new()) as HintsPanel).setup())
	if OS.has_feature("web") and bool(JavaScriptBridge.eval("!!document.fullscreenEnabled", true)):
		_tool("Full screen", func() -> void:
			var full := DisplayServer.window_get_mode() == DisplayServer.WINDOW_MODE_FULLSCREEN
			DisplayServer.window_set_mode(DisplayServer.WINDOW_MODE_WINDOWED if full else DisplayServer.WINDOW_MODE_FULLSCREEN))
	_portrait_tip = _label(root, Control.PRESET_CENTER_TOP, 22)
	_portrait_tip.position.y += 150
	_portrait_tip.text = "Tip: turn your phone sideways for a wider view."
	_portrait_tip.visible = false


func _tool(text: String, on_press: Callable) -> Button:
	var b := Button.new()
	b.text = text
	b.name = text.replace(" ", "")
	b.focus_mode = Control.FOCUS_NONE
	b.custom_minimum_size = Vector2(120, 64)
	b.add_theme_font_size_override("font_size", 20)
	b.pressed.connect(on_press)
	_toolbar.add_child(b)
	return b


func _open_pause() -> void:
	var p := _open(PauseMenu.new()) as PauseMenu
	p.setup()
	p.quit_requested.connect(func() -> void: leave_requested.emit())
	p.controls_changed.connect(apply_controls)


func _open_evidence() -> void:
	(_open(EvidenceBoard.new()) as EvidenceBoard).setup()
	if is_instance_valid(tutorial):
		tutorial.on_evidence_board_opened()


func _inspect_selected() -> void:
	var item := Game.node_at(Game.selected_item) as Item
	if item:
		open_item(item)
	else:
		toast("Select an item first.")


## An inventory item dragged over the room: highlight what it would be used
## on; when let go, use it there.
func _on_item_dragged(path: String, pos: Vector2, released: bool) -> void:
	if player == null or player.pointer == null or _modal != null:
		return
	var p := player.pointer
	if released:
		p.dragging_item = false
		p.drag_target = null
		if pos.x >= 0.0:
			p.drop(path, pos)
		return
	p.dragging_item = true
	p.drag_target = p.thing_at(pos)
	_drag_item_name = (Game.node_at(path) as Item).display_name if Game.node_at(path) is Item else ""
	_drag_pos = pos


var _drag_item_name := ""
var _drag_pos := Vector2.ZERO


func _label(parent: Control, preset: Control.LayoutPreset, size: int) -> Label:
	var l := Label.new()
	l.set_anchors_preset(preset)
	l.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	l.grow_horizontal = Control.GROW_DIRECTION_BOTH
	l.add_theme_font_size_override("font_size", size)
	l.add_theme_color_override("font_outline_color", Color.BLACK)
	l.add_theme_constant_override("outline_size", 6)
	parent.add_child(l)
	return l


func _process(_delta: float) -> void:
	if Game.has_session():
		_clock.text = SessionClock.format_remaining(Game.remaining_s())
		_clock.modulate = Color(1, 0.4, 0.4) if Game.remaining_s() < 300 else Color.WHITE
	if OS.has_feature("web") and not pointer_mode:
		_web_pointer_lock()
	if pointer_mode:
		_place_prompt()
		var vp := get_viewport().get_visible_rect().size
		_portrait_tip.visible = Device.is_touch() and vp.y > vp.x and _modal == null
	elif _click_hint:
		_click_hint.visible = false


## Point-and-tap: the prompt follows the mouse (or the dragged item); fingers
## do not hover, so on touch screens it only shows while dragging an item.
func _place_prompt() -> void:
	var dragging := player != null and player.pointer != null and player.pointer.dragging_item
	var at := _drag_pos if dragging else (player.pointer.mouse_position() if player and player.pointer else Vector2.ZERO)
	_prompt.position = at + Vector2(-_prompt.size.x / 2.0, 46 if not dragging else -110)


## Browsers only lock the pointer after a click, and Esc releases it without
## the game seeing the key: show "click to play" while the mouse is free, and
## treat a lost lock as Esc (open the pause menu).
func _web_pointer_lock() -> void:
	var captured := Input.mouse_mode == Input.MOUSE_MODE_CAPTURED
	if _was_captured and not captured and _modal == null and Game.has_session():
		_open_pause()
	_was_captured = captured
	if _click_hint == null:
		_click_hint = Label.new()
		_click_hint.text = "Click to play"
		_click_hint.add_theme_font_size_override("font_size", 28)
		_click_hint.set_anchors_and_offsets_preset(Control.PRESET_CENTER)
		_click_hint.mouse_filter = Control.MOUSE_FILTER_IGNORE
		add_child(_click_hint)
	_click_hint.visible = not captured and _modal == null and Game.has_session()


func _update_prompt() -> void:
	var t := player.target if player else null
	if t == null:
		_prompt.text = ""
		return
	if pointer_mode:
		var dragging := player.pointer != null and player.pointer.dragging_item
		if dragging:
			_prompt.text = "Use %s on %s" % [_drag_item_name, t.display_name] if t.accepts_items else t.prompt(_drag_item_name)
			return
		var sel := Game.node_at(Game.selected_item) as Item
		_prompt.text = t.prompt(sel.display_name if sel else "")
		return
	var item := Game.node_at(Game.selected_item) as Item
	_prompt.text = "[E] " + t.prompt(item.display_name if item else "")


func toast(text: String) -> void:
	_toast.text = text
	if _toast_tween:
		_toast_tween.kill()
	_toast.modulate.a = 1.0
	_toast_tween = create_tween()
	_toast_tween.tween_interval(1.6)
	_toast_tween.tween_property(_toast, "modulate:a", 0.0, 0.6)


func _show_banner(text: String) -> void:
	_banner_text.text = text
	_banner.visible = true
	var timer := get_tree().create_timer(10.0)
	_banner_timer = timer
	timer.timeout.connect(func() -> void:
		if _banner_timer == timer:
			_banner.visible = false)


# --- Panels ------------------------------------------------------------------

func is_modal_open() -> bool:
	return _modal != null


func _open(panel: ModalPanel) -> ModalPanel:
	if _modal:
		_modal.close()
	_modal = panel
	add_child(panel)
	panel.closed.connect(func() -> void:
		if _modal == panel:
			_modal = null
			_set_free_mouse(false))
	_set_free_mouse(true)
	return panel


## Moves the camera in on a device while its focused panel is open.
func _focus(target: Node3D, panel: ModalPanel) -> void:
	if player == null or not is_instance_valid(player):
		return
	var at := target.global_position
	var shapes := target.find_children("*", "CollisionShape3D", true, false)
	if not shapes.is_empty():
		at = (shapes[0] as Node3D).global_position
	player.focus_on(at)
	panel.closed.connect(func() -> void:
		if is_instance_valid(player):
			player.unfocus())


var _cross: Label


func _set_free_mouse(free: bool) -> void:
	Input.mouse_mode = Input.MOUSE_MODE_VISIBLE if free or pointer_mode else Input.MOUSE_MODE_CAPTURED
	# The crosshair would sit on top of a panel's middle (a dial's letter).
	if _cross:
		_cross.visible = not free and not pointer_mode
	if _toolbar:
		_toolbar.visible = pointer_mode and not free
	if player:
		player.input_enabled = not free


func open_document(doc: Document) -> void:
	EBSound.play_ui(self, "paper", -6.0)
	(_open(InspectPanel.new()) as InspectPanel).show_document(doc)


func open_item(item: Item) -> void:
	(_open(InspectPanel.new()) as InspectPanel).show_item(item)


func open_keypad(lock: KeypadLock) -> void:
	_focus(lock, (_open(KeypadPanel.new()) as KeypadPanel))
	(_modal as KeypadPanel).setup(lock)


func open_dial_lock(lock: DialLock) -> void:
	_focus(lock, (_open(DialLockPanel.new()) as DialLockPanel))
	(_modal as DialLockPanel).setup(lock)


func open_patch_panel(panel: PatchPanel) -> void:
	_focus(panel, (_open(PatchPanelUI.new()) as PatchPanelUI))
	(_modal as PatchPanelUI).setup(panel)


func open_terminal(term: Terminal) -> void:
	_focus(term, (_open(TerminalPanel.new()) as TerminalPanel))
	(_modal as TerminalPanel).setup(term)


var tutorial: TutorialOverlay = null


func open_briefing() -> void:
	# Rooms with an airlock teach the controls in-world instead (ADR-0020).
	var gate := Game.room.airlock() if Game.room else null
	if gate:
		if not gate.is_sealed():
			tutorial = TutorialOverlay.new()
			add_child(tutorial)
			tutorial.setup(player, gate)
		return
	var p := _open(ModalPanel.new())
	p.add_title(Game.manifest.title)
	var text := RichTextLabel.new()
	text.bbcode_enabled = true
	text.fit_content = true
	text.custom_minimum_size = Vector2(640, 0)
	text.add_theme_font_size_override("normal_font_size", 20)
	text.text = EBMarkdown.to_bbcode(Game.manifest.briefing("intro_md")) + "\n\n[i]" + HELP + "[/i]"
	p.body().add_child(text)
	p.add_close_button("Start")
	p.closed.connect(Game.start_clock)


func show_end(won: bool) -> void:
	if _ended_shown and (not won or _ended_won):
		return
	_ended_shown = true
	_ended_won = won
	EBSound.play_ui(self, "win" if won else "deny", 0.0)
	var p := _open(EndScreen.new()) as EndScreen
	p.setup(won)
	p.quit_requested.connect(func() -> void: leave_requested.emit())


## Shows the end screen if the world is already over (joining or rejoining
## a session that was won or timed out while we were away).
func sync_end_state() -> void:
	var w := Game.world()
	if w == null:
		return
	if w.finished:
		show_end(w.won)
	elif w.timed_out:
		show_end(false)


func _unhandled_input(event: InputEvent) -> void:
	if _modal != null or not Game.has_session():
		return
	if not pointer_mode and event is InputEventMouseButton and event.pressed and Input.mouse_mode != Input.MOUSE_MODE_CAPTURED:
		_set_free_mouse(false)
		get_viewport().set_input_as_handled()
		return
	var handled := true
	if event.is_action_pressed("evidence_board"):
		_open_evidence()
	elif event.is_action_pressed("hints"):
		(_open(HintsPanel.new()) as HintsPanel).setup()
	elif event.is_action_pressed("pause"):
		_open_pause()
	elif event.is_action_pressed("inspect_item"):
		_inspect_selected()
	elif event.is_action_pressed("deselect_item"):
		Game.selected_item = ""
	elif event.is_action_pressed("next_item"):
		_inventory.cycle(1)
	elif event.is_action_pressed("prev_item"):
		_inventory.cycle(-1)
	else:
		handled = false
		for i in 9:
			if event.is_action_pressed("select_item_%d" % (i + 1)):
				var inv := Game.inventory()
				if i < inv.size():
					_inventory.select(inv[i])
				handled = true
	if handled:
		get_viewport().set_input_as_handled()
