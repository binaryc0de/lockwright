class_name Settings
extends RefCounted
## Player preferences (PLAN.md 6.2 and 6.9 accessibility), saved per user.

const PATH := "user://settings.cfg"

static var mouse_sensitivity: float = 0.0025
static var invert_y: bool = false
static var fov: float = 80.0
static var text_scale: float = 1.0
static var display_name: String = "Player"
## Last server joined from the menu (host[:port]).
static var last_server: String = ""
static var last_ws: bool = false


static func load_settings() -> void:
	var cfg := ConfigFile.new()
	if cfg.load(PATH) != OK:
		return
	mouse_sensitivity = clampf(cfg.get_value("input", "mouse_sensitivity", mouse_sensitivity), 0.0005, 0.01)
	invert_y = cfg.get_value("input", "invert_y", invert_y)
	fov = clampf(cfg.get_value("video", "fov", fov), 75.0, 90.0)
	text_scale = clampf(cfg.get_value("ui", "text_scale", text_scale), 0.75, 2.0)
	display_name = str(cfg.get_value("player", "display_name", display_name)).left(24)
	last_server = str(cfg.get_value("network", "last_server", last_server)).left(120)
	last_ws = bool(cfg.get_value("network", "last_ws", last_ws))


static func save_settings() -> void:
	var cfg := ConfigFile.new()
	cfg.set_value("input", "mouse_sensitivity", mouse_sensitivity)
	cfg.set_value("input", "invert_y", invert_y)
	cfg.set_value("video", "fov", fov)
	cfg.set_value("ui", "text_scale", text_scale)
	cfg.set_value("player", "display_name", display_name)
	cfg.set_value("network", "last_server", last_server)
	cfg.set_value("network", "last_ws", last_ws)
	cfg.save(PATH)
