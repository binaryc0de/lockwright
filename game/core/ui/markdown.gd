class_name EBMarkdown
extends RefCounted
## Tiny Markdown subset -> BBCode for documents: #/## headings, **bold**,
## *italic*, `code`, "- " bullets. Square brackets are escaped first.


static func to_bbcode(md: String) -> String:
	var out := PackedStringArray()
	for raw in md.split("\n"):
		var line := raw.replace("[", "[lb]")
		if line.begins_with("## "):
			line = "[font_size=22][b]%s[/b][/font_size]" % line.substr(3)
		elif line.begins_with("# "):
			line = "[font_size=28][b]%s[/b][/font_size]" % line.substr(2)
		elif line.begins_with("- ") or line.begins_with("* "):
			line = "  •  " + line.substr(2)
		line = _wrap(line, "**", "[b]", "[/b]")
		line = _wrap(line, "*", "[i]", "[/i]")
		line = _wrap(line, "`", "[code]", "[/code]")
		out.append(line)
	return "\n".join(out)


@warning_ignore("integer_division")
static func _wrap(line: String, mark: String, open: String, close: String) -> String:
	var parts := line.split(mark)
	var pairs := (parts.size() - 1) / 2
	var s := parts[0]
	for i in range(1, parts.size()):
		if i % 2 == 0:
			s += parts[i]
		elif (i + 1) / 2 <= pairs:
			s += open + parts[i] + close
		else:
			s += mark + parts[i]  # unmatched marker stays literal
	return s
