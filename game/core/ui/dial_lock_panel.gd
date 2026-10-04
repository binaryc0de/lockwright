class_name DialLockPanel
extends ModalPanel
## Focused view of a DialLock: one column per wheel with up/down buttons. Each
## click is a "turn" intent; the shown symbols come from the lock's replicated
## state, so a teammate turning the same lock is seen live.

var lock: DialLock
var _shown: Array[Label] = []
var _status: Label


func setup(p_lock: DialLock) -> void:
	lock = p_lock
	add_title(lock.display_name)
	var row := HBoxContainer.new()
	row.alignment = BoxContainer.ALIGNMENT_CENTER
	row.add_theme_constant_override("separation", 14)
	for i in lock.wheels.size():
		if i > 0 and not lock.separator.is_empty():
			var sep := Label.new()
			sep.text = lock.separator
			sep.add_theme_font_size_override("font_size", 40)
			row.add_child(sep)
		var col := VBoxContainer.new()
		col.alignment = BoxContainer.ALIGNMENT_CENTER
		if i < lock.wheel_labels.size():
			var cap := Label.new()
			cap.text = lock.wheel_labels[i]
			cap.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
			col.add_child(cap)
		col.add_child(_button(true, i, -1))
		var l := Label.new()
		l.custom_minimum_size = Vector2(64, 56)
		l.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
		l.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
		l.add_theme_font_size_override("font_size", 40)
		col.add_child(l)
		_shown.append(l)
		col.add_child(_button(false, i, 1))
		row.add_child(col)
	body().add_child(row)
	_status = Label.new()
	_status.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	body().add_child(_status)
	add_close_button()
	lock.state_applied.connect(_on_state)
	_on_state(lock.current_state)


## Up/down buttons draw a triangle icon rather than "▲"/"▼": the web build's
## font has no such glyphs and showed empty boxes.
func _button(up: bool, wheel: int, step: int) -> Button:
	var b := Button.new()
	b.icon = arrow_icon(up)
	b.icon_alignment = HORIZONTAL_ALIGNMENT_CENTER
	b.tooltip_text = "Turn up" if up else "Turn down"
	b.custom_minimum_size = Vector2(64, 44)
	b.focus_mode = Control.FOCUS_NONE
	b.pressed.connect(turn.bind(wheel, step))
	return b


## Turns wheel `wheel` by `step` (+1 forward, -1 back).
func turn(wheel: int, step: int) -> void:
	Game.request(lock, "turn", {"wheel": wheel, "step": step})


func _on_state(state: Dictionary) -> void:
	if not is_instance_valid(self):
		return
	var dials := DialLock.dials_of(state)
	for i in _shown.size():
		var syms := lock.symbols(i)
		_shown[i].text = syms[posmod(dials[i] if i < dials.size() else 0, syms.size())]
	if state.get("state") == "unlocked":
		_status.text = "It gives."
		if is_inside_tree():
			get_tree().create_timer(0.9).timeout.connect(close)


static var _arrows := {}


## A white triangle (pointing up or down), antialiased, drawn once.
static func arrow_icon(up: bool) -> ImageTexture:
	if _arrows.has(up):
		return _arrows[up]
	var w := 28
	var h := 18
	var img := Image.create(w, h, false, Image.FORMAT_RGBA8)
	for y in h:
		for x in w:
			# Coverage by 4x4 supersampling of the triangle's inside.
			var hits := 0
			for sy in 4:
				for sx in 4:
					var px := x + (sx + 0.5) / 4.0
					var py := y + (sy + 0.5) / 4.0
					var t := py / h if up else 1.0 - py / h  # 0 at the tip
					if absf(px - w / 2.0) <= t * w / 2.0:
						hits += 1
			img.set_pixel(x, y, Color(1, 1, 1, hits / 16.0))
	var tex := ImageTexture.create_from_image(img)
	_arrows[up] = tex
	return tex
