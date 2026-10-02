class_name EvidenceBoard
extends ModalPanel
## Shared evidence board (PLAN.md 6.4): every document anyone has read is
## pinned automatically; players add free-text notes. Server-owned.

var _list: ItemList
var _detail: RichTextLabel
var _note: LineEdit
var _remove: Button
var _entries: Array[Dictionary] = []


func setup() -> void:
	add_title("Evidence board")
	var split := HBoxContainer.new()
	split.add_theme_constant_override("separation", 12)
	_list = ItemList.new()
	_list.custom_minimum_size = Vector2(300, 420)
	_list.item_selected.connect(_show)
	split.add_child(_list)
	_detail = RichTextLabel.new()
	_detail.bbcode_enabled = true
	_detail.custom_minimum_size = Vector2(560, 420)
	_detail.add_theme_font_size_override("normal_font_size", 19)
	split.add_child(_detail)
	body().add_child(split)
	var row := HBoxContainer.new()
	_note = LineEdit.new()
	_note.placeholder_text = "Add a note for the team..."
	_note.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	_note.max_length = 500
	_note.text_submitted.connect(func(_t: String) -> void: _add())
	row.add_child(_note)
	var add := Button.new()
	add.text = "Pin note"
	add.pressed.connect(_add)
	row.add_child(add)
	_remove = Button.new()
	_remove.text = "Remove note"
	_remove.disabled = true
	_remove.pressed.connect(_remove_selected)
	row.add_child(_remove)
	body().add_child(row)
	add_close_button("Close (Tab / Esc)")
	Game.evidence_changed.connect(_refresh)
	_refresh(Game.world().evidence if Game.world() else ([] as Array[Dictionary]))


func _refresh(evidence: Array[Dictionary]) -> void:
	_entries = evidence.duplicate()
	_list.clear()
	for e in _entries:
		if e["kind"] == "doc":
			_list.add_item("📄 " + str(e["title"]))
		else:
			_list.add_item("📝 %s: %s" % [e.get("author", "?"), str(e["text"]).left(40)])
	_detail.text = "[i]Select an entry.[/i]" if not _entries.is_empty() else "[i]Nothing pinned yet. Read documents to pin them here.[/i]"
	_remove.disabled = true


func _show(i: int) -> void:
	var e := _entries[i]
	_remove.disabled = e["kind"] != "note"
	if e["kind"] == "note":
		_detail.text = "[b]Note by %s[/b]\n\n%s" % [e.get("author", "?"), str(e["text"]).replace("[", "[lb]")]
		return
	var doc := Game.node_at(e["path"]) as Document
	if doc == null:
		_detail.text = "[b]%s[/b]" % e["title"]
		return
	var bb := "[b]%s[/b]\n\n%s" % [doc.title, EBMarkdown.to_bbcode(doc.text_md)]
	if not doc.back_text_md.is_empty():
		bb += "\n\n[i](back)[/i]\n" + EBMarkdown.to_bbcode(doc.back_text_md)
	_detail.clear()
	if doc.texture:
		# Image-backed clues must stay readable from the board, not just in the room.
		_detail.add_image(doc.texture, 540)
		_detail.newline()
	_detail.append_text(bb)


func _add() -> void:
	if Game.add_note(_note.text).get("ok", false):
		_note.clear()


func _remove_selected() -> void:
	var sel := _list.get_selected_items()
	if sel.is_empty():
		return
	var e := _entries[sel[0]]
	if e["kind"] == "note":
		Game.remove_note(int(e["id"]))


func _unhandled_input(event: InputEvent) -> void:
	if event.is_action_pressed("evidence_board") and not _note.has_focus():
		close()
		get_viewport().set_input_as_handled()
		return
	super(event)
