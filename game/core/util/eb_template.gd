class_name EBTemplate
extends RefCounted
## {{name}} substitution for room strings (lock codes, UV text, solution
## values). Unknown names are left as-is so mistakes stay visible.

static var _re: RegEx


static func render(text: String, vars: Dictionary) -> String:
	if not text.contains("{{"):
		return text
	if _re == null:
		_re = RegEx.create_from_string("\\{\\{\\s*([A-Za-z0-9_.]+)\\s*\\}\\}")
	var out := ""
	var pos := 0
	for m in _re.search_all(text):
		out += text.substr(pos, m.get_start() - pos)
		var key := m.get_string(1)
		out += str(vars[key]) if vars.has(key) else m.get_string()
		pos = m.get_end()
	return out + text.substr(pos)
