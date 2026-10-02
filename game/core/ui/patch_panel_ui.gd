class_name PatchPanelUI
extends ModalPanel
## Focused patch-cable view: pick a port for every cable, then connect.

var panel: PatchPanel
var _pickers: Dictionary = {}  # cable id -> OptionButton
var _status: Label


func setup(p: PatchPanel) -> void:
	panel = p
	add_title(panel.display_name)
	var current: Dictionary = panel.current_state.get("connections", {})
	var grid := GridContainer.new()
	grid.columns = 2
	for id in panel.cable_ids:
		var l := Label.new()
		l.text = "Cable " + panel.label_of(id)
		grid.add_child(l)
		var o := OptionButton.new()
		o.add_item("(unplugged)", 0)
		for port in range(1, panel.port_count + 1):
			o.add_item("Port %d" % port, port)
		o.select(o.get_item_index(int(current.get(id, 0))))
		grid.add_child(o)
		_pickers[id] = o
	body().add_child(grid)
	_status = Label.new()
	body().add_child(_status)
	var connect := Button.new()
	connect.text = "Connect"
	connect.pressed.connect(_connect)
	body().add_child(connect)
	add_close_button()


func _connect() -> void:
	var m := {}
	for id: String in _pickers:
		var port: int = (_pickers[id] as OptionButton).get_selected_id()
		if port == 0:
			_status.text = "Every cable needs a port."
			return
		m[id] = port
	Game.request(panel, "patch", {"value": PatchPanel.format_mapping(m)}, _on_result)


func _on_result(r: Dictionary) -> void:
	if not is_instance_valid(self) or not is_inside_tree():
		return
	if r.get("ok", false):
		_status.text = "Relay clicks. Something powers up."
		get_tree().create_timer(1.0).timeout.connect(close)
	else:
		_status.text = r.get("message", "Nothing happens.")
