class_name HintsPanel
extends ModalPanel
## Tiered hints (PLAN.md 6.6): lists open puzzles, reveals the next tier on
## request. Reveals go through the authority so they are logged and counted.

var _rows: VBoxContainer
var _graph: PuzzleGraph


func setup() -> void:
	add_title("Hints")
	var intro := Label.new()
	intro.text = "Pick what you're stuck on. Each request reveals the next, more direct tier; the last tier gives the answer."
	intro.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	intro.custom_minimum_size = Vector2(640, 0)
	body().add_child(intro)
	var scroll := ScrollContainer.new()
	scroll.custom_minimum_size = Vector2(680, 380)
	_rows = VBoxContainer.new()
	_rows.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	scroll.add_child(_rows)
	body().add_child(scroll)
	var nudge := CheckBox.new()
	nudge.text = "Let the intercom offer a hint when we've been stuck for a while"
	nudge.button_pressed = Game.world().auto_nudge
	nudge.toggled.connect(Game.set_auto_nudge)
	body().add_child(nudge)
	add_close_button("Close (H / Esc)")
	_graph = PuzzleGraph.new(Game.manifest.puzzles, Game.manifest.exit_puzzle)
	Game.puzzles_changed.connect(func(_p: Dictionary) -> void: _refresh())
	_refresh()


func _refresh() -> void:
	for c in _rows.get_children():
		c.queue_free()
	var w := Game.world()
	var hints := HintService.new(_graph)
	var open := _graph.open_puzzles(w)
	if open.is_empty():
		var l := Label.new()
		l.text = "Nothing open right now."
		_rows.add_child(l)
	for id in open:
		var p := _graph.get_puzzle(id)
		var title := Label.new()
		title.text = p.get("title", id)
		title.add_theme_font_size_override("font_size", 21)
		_rows.add_child(title)
		var shown := hints.revealed(w, id)
		for i in shown.size():
			var t := Label.new()
			t.text = "  %d. %s" % [i + 1, shown[i]]
			t.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
			t.custom_minimum_size = Vector2(640, 0)
			_rows.add_child(t)
		var total := hints.tiers(id).size()
		var b := Button.new()
		b.size_flags_horizontal = Control.SIZE_SHRINK_BEGIN
		if shown.size() < total:
			b.text = "Get hint %d of %d" % [shown.size() + 1, total]
			b.pressed.connect(func() -> void: Game.request_hint(id))
		else:
			b.text = "No more hints"
			b.disabled = true
		_rows.add_child(b)


func _unhandled_input(event: InputEvent) -> void:
	if event.is_action_pressed("hints"):
		close()
		get_viewport().set_input_as_handled()
		return
	super(event)
