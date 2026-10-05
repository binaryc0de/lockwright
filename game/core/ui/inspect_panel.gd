class_name InspectPanel
extends ModalPanel
## Close-up view (PLAN.md 6.3). Documents: readable text, flip to the back,
## UV text when a UV torch is selected. Items: the item's meshes in a small
## 3D view the player can rotate (drag) and zoom (wheel), plus description.

var _text: RichTextLabel
var _doc: Document
var _back: bool = false
var _pivot: Node3D
var _cam: Camera3D
var _dragging: bool = false


func show_document(doc: Document) -> void:
	_doc = doc
	add_title(doc.title)
	if doc.texture:
		var tex := TextureRect.new()
		tex.texture = doc.texture
		tex.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
		tex.stretch_mode = TextureRect.STRETCH_KEEP_ASPECT_CENTERED
		tex.custom_minimum_size = Vector2(640, 420)
		body().add_child(tex)
	_text = _rich()
	body().add_child(_text)
	if not doc.back_text_md.is_empty():
		var flip := Button.new()
		flip.text = "Flip over"
		flip.pressed.connect(func() -> void:
			_back = not _back
			_render_doc())
		body().add_child(flip)
	add_close_button()
	_render_doc()


func show_item(item: Item) -> void:
	add_title(item.display_name)
	var view := SubViewportContainer.new()
	view.custom_minimum_size = Vector2(520, 360)
	view.stretch = true
	var vp := SubViewport.new()
	vp.own_world_3d = true
	vp.transparent_bg = false
	view.add_child(vp)
	var env := WorldEnvironment.new()
	env.environment = Environment.new()
	env.environment.background_mode = Environment.BG_COLOR
	env.environment.background_color = Color(0.12, 0.12, 0.13)
	env.environment.ambient_light_source = Environment.AMBIENT_SOURCE_COLOR
	env.environment.ambient_light_color = Color(0.6, 0.6, 0.6)
	vp.add_child(env)
	var light := DirectionalLight3D.new()
	light.rotation_degrees = Vector3(-40, 30, 0)
	vp.add_child(light)
	_pivot = Node3D.new()
	vp.add_child(_pivot)
	var aabb := ItemIcons.copy_meshes(item, _pivot)
	_pivot.position = -aabb.get_center()
	var holder := Node3D.new()
	vp.add_child(holder)
	_pivot.reparent(holder, false)
	_pivot = holder
	_cam = Camera3D.new()
	_cam.position = Vector3(0, 0, maxf(aabb.get_longest_axis_size() * 2.2, 0.15))
	vp.add_child(_cam)
	view.gui_input.connect(_on_view_input)
	body().add_child(view)
	var hint := Label.new()
	hint.text = "Drag to rotate, wheel to zoom."
	body().add_child(hint)
	_text = _rich()
	var text := item.description
	if Game.uv_active() and not item.uv_text.is_empty():
		text += "\n\n[UV] " + item.uv_text
	_text.text = EBMarkdown.to_bbcode(text)
	body().add_child(_text)
	if not item.file_name.is_empty():
		_add_file(item.file_name, EBTemplate.render(item.file_text, Game.vars()))
	add_close_button()


## A file on an item: shown, copyable, and savable to the player's Downloads.
func _add_file(file_name: String, content: String) -> void:
	var label := Label.new()
	label.text = "File on it: %s" % file_name
	body().add_child(label)
	var box := TextEdit.new()
	box.text = content
	box.editable = false
	box.custom_minimum_size = Vector2(640, 150)
	box.add_theme_font_override("font", SystemFont.new())
	box.add_theme_font_size_override("font_size", 15)
	body().add_child(box)
	var row := HBoxContainer.new()
	var status := Label.new()
	var copy := Button.new()
	copy.text = "Copy to clipboard"
	copy.pressed.connect(func() -> void:
		DisplayServer.clipboard_set(content)
		status.text = "Copied.")
	row.add_child(copy)
	var save := Button.new()
	save.text = "Save to Downloads"
	save.pressed.connect(func() -> void:
		var path := InspectPanel.save_to_downloads(file_name, content)
		status.text = ("Saved to %s" % path) if not path.is_empty() else "Could not save the file.")
	row.add_child(save)
	row.add_child(status)
	body().add_child(row)


## Writes `content` to the player's Downloads folder (or the user data folder
## if there is none). Returns the path, or "" on failure.
static func save_to_downloads(file_name: String, content: String) -> String:
	if OS.has_feature("web"):
		JavaScriptBridge.download_buffer(content.to_utf8_buffer(), file_name.get_file(), "text/plain")
		return "your browser's downloads"
	var dir := OS.get_system_dir(OS.SYSTEM_DIR_DOWNLOADS)
	if dir.is_empty() or not DirAccess.dir_exists_absolute(dir):
		dir = ProjectSettings.globalize_path("user://")
	var path := dir.path_join(file_name.get_file())
	var f := FileAccess.open(path, FileAccess.WRITE)
	if f == null:
		return ""
	f.store_string(content)
	f.close()
	return path


func _render_doc() -> void:
	var md := _doc.back_text_md if _back else _doc.text_md
	var bb := EBMarkdown.to_bbcode(md)
	if Game.uv_active() and not _doc.uv_text.is_empty():
		bb += "\n\n[color=#b48cff][b]Under UV light:[/b] %s[/color]" % EBMarkdown.to_bbcode(EBTemplate.render(_doc.uv_text, Game.vars()))
	_text.text = ("[i](back)[/i]\n" if _back else "") + bb


func _rich() -> RichTextLabel:
	var r := RichTextLabel.new()
	r.bbcode_enabled = true
	r.fit_content = true
	r.scroll_active = false
	r.custom_minimum_size = Vector2(640, 0)
	r.add_theme_font_size_override("normal_font_size", 20)
	return r


func _on_view_input(event: InputEvent) -> void:
	if event is InputEventMouseButton:
		var b := event as InputEventMouseButton
		if b.button_index == MOUSE_BUTTON_LEFT:
			_dragging = b.pressed
		elif b.button_index == MOUSE_BUTTON_WHEEL_UP and b.pressed:
			_cam.position.z = maxf(_cam.position.z * 0.9, 0.05)
		elif b.button_index == MOUSE_BUTTON_WHEEL_DOWN and b.pressed:
			_cam.position.z = minf(_cam.position.z * 1.1, 5.0)
	elif event is InputEventMouseMotion and _dragging:
		var m := event as InputEventMouseMotion
		_pivot.rotate_y(m.relative.x * 0.01)
		_pivot.rotate_x(m.relative.y * 0.01)
