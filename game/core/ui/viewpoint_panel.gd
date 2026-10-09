class_name ViewpointPanel
extends ModalPanel
## Looking through a Viewpoint: a slim strip along the bottom of the screen
## with one button per control and a Back button, so the view stays clear.
## The round view itself is a full-screen vignette the HUD lays under it.

var vp: Viewpoint


func setup(p_vp: Viewpoint) -> void:
	vp = p_vp
	var bg := StyleBoxFlat.new()
	bg.bg_color = Color(0.05, 0.05, 0.06, 0.6)
	bg.set_corner_radius_all(6)
	add_theme_stylebox_override("panel", bg)
	var row := HBoxContainer.new()
	row.alignment = BoxContainer.ALIGNMENT_CENTER
	row.add_theme_constant_override("separation", 12)
	for i in vp.controls.size():
		var b := Button.new()
		b.name = "Control%d" % i
		b.text = vp.control_names[i] if i < vp.control_names.size() else "Turn %d" % (i + 1)
		b.custom_minimum_size = Vector2(150, 48)
		b.focus_mode = Control.FOCUS_NONE
		b.pressed.connect(vp.work.bind(i))
		row.add_child(b)
	var back := Button.new()
	back.text = "Back (Esc)"
	back.custom_minimum_size = Vector2(120, 48)
	back.focus_mode = Control.FOCUS_NONE
	back.pressed.connect(close)
	row.add_child(back)
	body().add_child(row)


## Bottom centre instead of the middle of the screen.
func _place() -> void:
	if not is_inside_tree():
		return
	reset_size()
	var screen := get_viewport().get_visible_rect().size
	position = Vector2(((screen.x - size.x * scale.x) / 2.0), screen.y - size.y * scale.y - SCREEN_MARGIN).floor()


## A full-screen round mask: clear in the middle, dark brass rim, black out.
static func vignette() -> ColorRect:
	var r := ColorRect.new()
	r.name = "SightRing"
	r.set_anchors_preset(Control.PRESET_FULL_RECT)
	r.mouse_filter = Control.MOUSE_FILTER_IGNORE
	var sh := Shader.new()
	sh.code = """
shader_type canvas_item;
void fragment() {
	vec2 px = UV / SCREEN_PIXEL_SIZE;
	vec2 res = 1.0 / SCREEN_PIXEL_SIZE;
	float d = length(px - res * 0.5) / (min(res.x, res.y) * 0.5);
	float rim = smoothstep(0.80, 0.86, d) * (1.0 - smoothstep(0.88, 0.93, d));
	float out_ = smoothstep(0.88, 0.94, d);
	COLOR = vec4(mix(vec3(0.22, 0.15, 0.07) * rim, vec3(0.0), out_), max(rim * 0.9, out_));
}
"""
	var m := ShaderMaterial.new()
	m.shader = sh
	r.material = m
	return r
