extends Node3D
## Asset review stage (docs/ASSET_PIPELINE.md Section 9). Renders the prop
## at `prop_path`, saves a screenshot when `-- --screenshot <png>` is given,
## then quits. Run windowed, briefly (ADR-0003):
##   godot --path game --rendering-method gl_compatibility \
##     res://tests/scenes/keypad_showcase.tscn -- --screenshot /tmp/shot.png

@export_file("*.glb", "*.tscn") var prop_path: String
@export var frames_before_capture: int = 30

var _out: String = ""
var _frames: int = 0


func _ready() -> void:
	var args := OS.get_cmdline_user_args()
	var i := args.find("--screenshot")
	if i >= 0 and i + 1 < args.size():
		_out = args[i + 1]
	var scene: PackedScene = load(prop_path)
	if scene:
		$Prop.add_child(scene.instantiate())


func _process(_delta: float) -> void:
	if _out.is_empty():
		return
	_frames += 1
	if _frames == frames_before_capture:
		var err := get_viewport().get_texture().get_image().save_png(_out)
		print("screenshot %s -> %s" % [_out, error_string(err)])
		get_tree().quit(0 if err == OK else 1)
