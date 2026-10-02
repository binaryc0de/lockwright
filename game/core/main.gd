extends Node
## Boot: parse arguments and pick client or server mode (PLAN.md 6.1, 7.1).
## M0 only reports the mode; networking arrives in M2.


func _ready() -> void:
	var args := AppArgs.parse(OS.get_cmdline_user_args() + OS.get_cmdline_args(),
		OS.has_feature("dedicated_server"))
	for e in args.errors:
		push_error(e)
	print("escapebox %s mode, sdk %s, godot %s" % [
		"server" if args.is_server() else "client",
		EscapeboxSDK.VERSION,
		Engine.get_version_info().string,
	])
	if args.smoke_test or not args.errors.is_empty():
		get_tree().quit(0 if args.errors.is_empty() else 1)
