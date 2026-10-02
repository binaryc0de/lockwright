class_name EndScreen
extends ModalPanel
## Win / time's-up screen (PLAN.md 6.7): time, hints used, puzzle timeline.

signal quit_requested


func setup(won: bool) -> void:
	var w := Game.world()
	add_title("You escaped!" if won else "Time's up")
	var text := RichTextLabel.new()
	text.bbcode_enabled = true
	text.fit_content = true
	text.custom_minimum_size = Vector2(620, 0)
	text.add_theme_font_size_override("normal_font_size", 19)
	var md := Game.manifest.briefing("win_md" if won else "timeout_md")
	var bb := EBMarkdown.to_bbcode(md) + "\n\n" if not md.is_empty() else ""
	var end_t := w.finished_at if won else Time.get_unix_time_from_system()
	bb += "[b]Time:[/b] %s\n[b]Hints used:[/b] %d\n\n[b]Timeline[/b]\n" % [_fmt(end_t - w.started_at), w.hints_used()]
	var solved: Array = []
	for id: String in w.puzzles:
		if w.puzzles[id]["solved"]:
			solved.append([float(w.puzzles[id]["solved_at"]), id])
	solved.sort()
	for s in solved:
		var title: String = Game.manifest.puzzle(s[1]).get("title", s[1])
		bb += "  %s  %s\n" % [_fmt(s[0] - w.started_at), title]
	if not won:
		bb += "\n[i]The room stays open: keep exploring, hints are free.[/i]"
	text.text = bb
	body().add_child(text)
	add_close_button("Keep exploring")
	var quit := Button.new()
	quit.text = "Leave room"
	quit.pressed.connect(func() -> void: quit_requested.emit())
	body().add_child(quit)


static func _fmt(s: float) -> String:
	var t := maxi(int(s), 0)
	return "%d:%02d" % [t / 60, t % 60] if t < 3600 else "%d:%02d:%02d" % [t / 3600, (t / 60) % 60, t % 60]
