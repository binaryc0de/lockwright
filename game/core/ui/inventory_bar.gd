class_name InventoryBar
extends HBoxContainer
## Team inventory strip (PLAN.md 6.4): everything the team holds, visible to
## all. Keys 1-9 or the wheel select an item to use on things; Q deselects;
## F inspects the selected item.

func _ready() -> void:
	add_theme_constant_override("separation", 8)
	Game.inventory_changed.connect(func(_i: Array[String]) -> void: _rebuild())
	Game.selected_item_changed.connect(func(_p: String) -> void: _rebuild())
	_rebuild()


func _rebuild() -> void:
	for c in get_children():
		c.queue_free()
	var inv := Game.inventory()
	for i in inv.size():
		var item := Game.node_at(inv[i]) as Item
		var b := Button.new()
		b.focus_mode = Control.FOCUS_NONE
		b.toggle_mode = true
		b.button_pressed = inv[i] == Game.selected_item
		b.text = "%d  %s" % [i + 1, item.display_name if item else inv[i]]
		b.custom_minimum_size = Vector2(120, 44)
		b.pressed.connect(select.bind(inv[i]))
		add_child(b)


func select(path: String) -> void:
	Game.selected_item = "" if Game.selected_item == path else path


func cycle(step: int) -> void:
	var inv := Game.inventory()
	if inv.is_empty():
		return
	var i := inv.find(Game.selected_item)
	i = posmod(i + step, inv.size()) if i >= 0 else (0 if step > 0 else inv.size() - 1)
	Game.selected_item = inv[i]
