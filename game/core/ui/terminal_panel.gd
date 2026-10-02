class_name TerminalPanel
extends ModalPanel
## In-game terminal (PLAN.md 6.8). Remote mode: connection card + flag
## submission. Simulated mode: offline shell from the prop's `commands`.

var term: Terminal
var _log: RichTextLabel
var _input: LineEdit
var _status: Label


func setup(t: Terminal) -> void:
	term = t
	add_title(term.display_name)
	_log = RichTextLabel.new()
	_log.bbcode_enabled = true
	_log.scroll_following = true
	_log.custom_minimum_size = Vector2(700, 300)
	_log.add_theme_font_size_override("normal_font_size", 18)
	body().add_child(_log)
	if not term.banner.is_empty():
		_log.append_text(EBMarkdown.to_bbcode(EBTemplate.render(term.banner, Game.vars())) + "\n\n")
	_input = LineEdit.new()
	_input.text_submitted.connect(_on_submit)
	_status = Label.new()
	if term.mode == "remote":
		_show_connection_card()
		_input.placeholder_text = "Paste the flag here and press Enter"
	else:
		_input.placeholder_text = "Type a command (help)"
	body().add_child(_input)
	body().add_child(_status)
	add_close_button()
	_input.grab_focus.call_deferred()
	if term.current_state.get("state") == "solved":
		_status.text = "ACCESS GRANTED: flag already accepted."


func _show_connection_card() -> void:
	var w := Game.world()
	var handle: Dictionary = w.challenges.get(term.challenge_id, {}) if w else {}
	var c: Dictionary = Game.manifest.challenge(term.challenge_id) if Game.manifest else {}
	var lines := PackedStringArray(["[b]CONNECTION CARD[/b]"])
	lines.append("Challenge: %s (%s)" % [c.get("title", term.challenge_id), c.get("difficulty", "?")])
	if handle.has("url"):
		lines.append("Target: [code]%s[/code]" % handle["url"])
	elif handle.has("host"):
		lines.append("Target: [code]%s:%s[/code]" % [handle["host"], handle.get("port", "")])
	if handle.has("note"):
		lines.append("[i]%s[/i]" % handle["note"])
	lines.append("Attack it from your own machine with your own tools, then submit the flag below.")
	_log.append_text("\n".join(lines) + "\n\n")


func _on_submit(text: String) -> void:
	_input.clear()
	if term.mode == "remote":
		var r := Game.request(term, "submit_flag", {"value": text})
		if r.get("ok", false):
			_status.text = "ACCESS GRANTED"
			_log.append_text("[color=#5f5]> flag accepted[/color]\n")
		elif r.has("retry_after_s"):
			_status.text = "Too many attempts. Wait %d s." % int(r["retry_after_s"])
		else:
			_status.text = "Flag rejected."
			_log.append_text("[color=#f55]> flag rejected[/color]\n")
		return
	if text.strip_edges() == "clear":
		_log.clear()
		return
	_log.append_text("[b]$ %s[/b]\n%s\n" % [text.replace("[", "[lb]"), term.run_command(text).replace("[", "[lb]")])
