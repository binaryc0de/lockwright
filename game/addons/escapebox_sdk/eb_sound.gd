class_name EBSound
extends RefCounted
## SDK sound library (PLAN.md 6.9; CC0 Kenney sounds in the core assets).
## SDK nodes pick a key for each state change; rooms can override any node's
## sound with an AudioStream export. Never plays on a headless/server process.

const K := "res://assets/core/third_party/kenney/"
const LIBRARY := {
	"door_open": K + "rpg-audio/doorOpen_1.ogg",
	"door_close": K + "rpg-audio/doorClose_2.ogg",
	"drawer_open": K + "rpg-audio/creak1.ogg",
	"drawer_close": K + "impact-sounds/impactGeneric_light_002.ogg",
	"pick_up": K + "rpg-audio/handleSmallLeather.ogg",
	"paper": K + "rpg-audio/bookFlip2.ogg",
	"key": K + "interface-sounds/click_002.ogg",
	"accept": K + "interface-sounds/confirmation_002.ogg",
	"deny": K + "interface-sounds/error_004.ogg",
	"maglock_slam": K + "impact-sounds/impactMetal_heavy_002.ogg",
	"maglock_release": K + "sci-fi-sounds/forceField_001.ogg",
	"relay": K + "rpg-audio/metalLatch.ogg",
	"chime": K + "interface-sounds/bong_001.ogg",
	"win": K + "interface-sounds/confirmation_004.ogg",
}
const FOOTSTEPS := [
	K + "impact-sounds/footstep_carpet_000.ogg", K + "impact-sounds/footstep_carpet_001.ogg",
	K + "impact-sounds/footstep_carpet_002.ogg", K + "impact-sounds/footstep_carpet_003.ogg",
	K + "impact-sounds/footstep_carpet_004.ogg",
]

static var _cache := {}


static func enabled() -> bool:
	return DisplayServer.get_name() != "headless" and Game.mode != Game.Mode.SERVER


## `what` is a library key, a res:// path, or an AudioStream.
static func stream(what: Variant) -> AudioStream:
	if what is AudioStream:
		return what
	var path: String = LIBRARY.get(str(what), str(what))
	if path.is_empty() or not ResourceLoader.exists(path):
		return null
	if not _cache.has(path):
		_cache[path] = load(path)
	return _cache[path]


## A positional one-shot at `where`.
static func play_at(where: Node3D, what: Variant, volume_db: float = 0.0, pitch_jitter: float = 0.05) -> void:
	if not enabled() or where == null or not where.is_inside_tree():
		return
	var s := stream(what)
	if s == null:
		return
	var p := AudioStreamPlayer3D.new()
	p.stream = s
	p.volume_db = volume_db
	p.pitch_scale = 1.0 + randf_range(-pitch_jitter, pitch_jitter)
	p.unit_size = 4.0
	where.add_child(p)
	p.finished.connect(p.queue_free)
	p.play()


## A non-positional one-shot (UI feedback).
static func play_ui(parent: Node, what: Variant, volume_db: float = -4.0) -> void:
	if not enabled() or parent == null or not parent.is_inside_tree():
		return
	var s := stream(what)
	if s == null:
		return
	var p := AudioStreamPlayer.new()
	p.stream = s
	p.volume_db = volume_db
	parent.add_child(p)
	p.finished.connect(p.queue_free)
	p.play()
