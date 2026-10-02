class_name Hud
extends CanvasLayer
## In-room HUD: crosshair, context prompt, toasts, intercom banner, clock,
## inventory, and the focused panels. While a panel is open the mouse is free
## and the player is frozen.

signal leave_requested

const HELP := "E interact   F inspect item   1-9 select item   Q deselect   Tab evidence   H hints   Esc menu"

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


func _ready() -> void:
	layer = 10
	var root := Control.new()
	root.set_anchors_preset(Control.PRESET_FULL_RECT)
	root.mouse_filter = Control.MOUSE_FILTER_IGNORE
	add_child(root)

	var cross := Label.new()
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
	help.text = HELP
	help.horizontal_alignment = HORIZONTAL_ALIGNMENT_RIGHT
	help.grow_horizontal = Control.GROW_DIRECTION_BEGIN
	help.grow_vertical = Control.GROW_DIRECTION_BEGIN
	help.position += Vector2(-16, -12)
	help.modulate.a = 0.7

	_inventory = InventoryBar.new()
	_inventory.set_anchors_preset(Control.PRESET_CENTER_BOTTOM)
	_inventory.grow_horizontal = Control.GROW_DIRECTION_BOTH
	_inventory.grow_vertical = Control.GROW_DIRECTION_BEGIN
	_inventory.position.y -= 48
	root.add_child(_inventory)

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


func _update_prompt() -> void:
	var t := player.target if player else null
	if t == null:
		_prompt.text = ""
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


func _set_free_mouse(free: bool) -> void:
	Input.mouse_mode = Input.MOUSE_MODE_VISIBLE if free else Input.MOUSE_MODE_CAPTURED
	if player:
		player.input_enabled = not free


func open_document(doc: Document) -> void:
	EBSound.play_ui(self, "paper", -6.0)
	(_open(InspectPanel.new()) as InspectPanel).show_document(doc)


func open_item(item: Item) -> void:
	(_open(InspectPanel.new()) as InspectPanel).show_item(item)


func open_keypad(lock: KeypadLock) -> void:
	(_open(KeypadPanel.new()) as KeypadPanel).setup(lock)


func open_patch_panel(panel: PatchPanel) -> void:
	(_open(PatchPanelUI.new()) as PatchPanelUI).setup(panel)


func open_terminal(term: Terminal) -> void:
	(_open(TerminalPanel.new()) as TerminalPanel).setup(term)


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
	if event is InputEventMouseButton and event.pressed and Input.mouse_mode != Input.MOUSE_MODE_CAPTURED:
		_set_free_mouse(false)
		get_viewport().set_input_as_handled()
		return
	var handled := true
	if event.is_action_pressed("evidence_board"):
		(_open(EvidenceBoard.new()) as EvidenceBoard).setup()
		if is_instance_valid(tutorial):
			tutorial.on_evidence_board_opened()
	elif event.is_action_pressed("hints"):
		(_open(HintsPanel.new()) as HintsPanel).setup()
	elif event.is_action_pressed("pause"):
		var p := _open(PauseMenu.new()) as PauseMenu
		p.setup()
		p.quit_requested.connect(func() -> void: leave_requested.emit())
	elif event.is_action_pressed("inspect_item"):
		var item := Game.node_at(Game.selected_item) as Item
		if item:
			open_item(item)
		else:
			toast("Select an item first (1-9).")
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
