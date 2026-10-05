class_name Device
extends RefCounted
## What kind of device the client runs on (ADR-0038). Phones and tablets get
## point-and-tap controls, a larger UI and a lighter 3D resolution.

static var _touch: int = -1

## The main pointer is a finger; or, where a browser says otherwise (an
## Android emulator did), a touch screen on a phone or tablet. iPads ask for
## desktop pages and say "Macintosh".
const TOUCH_TEST := "matchMedia('(pointer: coarse)').matches" \
	+ " || (navigator.maxTouchPoints > 0 && /Android|iPhone|iPad|iPod|Mobile/i.test(navigator.userAgent))" \
	+ " || (navigator.maxTouchPoints > 1 && /Macintosh/.test(navigator.userAgent))"


## True when the main pointer is a finger (phone, tablet). A laptop with a
## touch screen still counts as a mouse device.
static func is_touch() -> bool:
	if _touch < 0:
		if OS.has_feature("web"):
			_touch = 1 if bool(JavaScriptBridge.eval(TOUCH_TEST, true)) else 0
		else:
			_touch = 1 if OS.has_feature("mobile") else 0
	return _touch == 1


## True when the GPU takes phone texture formats (ETC2) but not the desktop
## ones (S3TC): phones and tablets. Such clients download the "-mobile" room
## packs (ADR-0038); anything else keeps the desktop packs, which Godot can
## still unpack if it must.
static func wants_mobile_textures() -> bool:
	return OS.has_feature("etc2") and not OS.has_feature("s3tc")


## For tests: pretend to be (or not be) a touch device.
static func force_touch(on: bool) -> void:
	_touch = 1 if on else 0


## Extra UI scale for small touch screens, so text and buttons stay finger
## sized. The project stretches a 1920x1080 canvas to the window; on a phone
## in landscape that alone shrinks a 22 px label to about 8 CSS px.
static func ui_factor(window_css: Vector2) -> float:
	if not is_touch() or window_css.x <= 0.0 or window_css.y <= 0.0:
		return 1.0
	var stretch := minf(window_css.x / 1920.0, window_css.y / 1080.0)
	return clampf(0.62 / stretch, 1.0, 1.9)


## The browser window's size in CSS pixels (the window size elsewhere).
static func window_css() -> Vector2:
	if OS.has_feature("web"):
		return Vector2(float(JavaScriptBridge.eval("window.innerWidth", true)), float(JavaScriptBridge.eval("window.innerHeight", true)))
	return Vector2(DisplayServer.window_get_size())


## Sets the UI scale: the player's text size times the small-screen factor.
## Re-run when the window changes size (a phone turned sideways).
static func apply_ui_scale(root: Window) -> void:
	root.content_scale_factor = Settings.text_scale * ui_factor(window_css())
