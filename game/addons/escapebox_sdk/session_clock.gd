@icon("res://addons/escapebox_sdk/icons/eb_node.svg")
class_name SessionClock
extends EBNode
## Countdown display bound to the server-owned timer (PLAN.md 6.7). Writes
## MM:SS (or H:MM:SS) into a Label3D child named by `label`. With
## `wall_start` it is a clock in the story's time instead: it starts at that
## time of day and runs forward with the session ("23:00" reaches midnight
## after 60 minutes); the label then shows H:MM and optional hands turn.

@export var label: NodePath
## Story time of day when the clock starts, "HH:MM"; empty = plain countdown.
@export var wall_start: String = ""
## Optional clock hands (wall_start only), turned from where the scene puts
## them at 12:00 by hand_turn per full revolution.
@export var hour_hand: NodePath
@export var minute_hand: NodePath
@export var hand_turn: Vector3 = Vector3(0, 0, -360)

var _hand_base := {}


func _process(_delta: float) -> void:
	var remaining := Game.remaining_s()
	var l := get_node_or_null(label) as Label3D
	if wall_start.is_empty():
		if l:
			l.text = format_remaining(remaining)
		return
	var duration := float(Game.world().duration_s) if Game.has_session() else 0.0
	var minutes := wall_minutes(wall_start, duration - remaining)
	if l:
		l.text = format_wall(minutes)
	_turn(hour_hand, fmod(minutes / 720.0, 1.0))
	_turn(minute_hand, fmod(minutes / 60.0, 1.0))


func _turn(path: NodePath, fraction: float) -> void:
	var p := get_node_or_null(path) as Node3D
	if p == null:
		return
	if not _hand_base.has(p):
		_hand_base[p] = p.rotation_degrees
	p.rotation_degrees = (_hand_base[p] as Vector3) + hand_turn * fraction


static func format_remaining(s: float) -> String:
	var t := int(ceil(s))
	if t >= 3600:
		return "%d:%02d:%02d" % [t / 3600, (t / 60) % 60, t % 60]
	return "%02d:%02d" % [t / 60, t % 60]


## Minutes past midnight shown by a wall clock that started at `start`
## ("HH:MM") `elapsed_s` seconds ago, wrapped to one day.
static func wall_minutes(start: String, elapsed_s: float) -> float:
	var hm := start.split(":")
	var base := 0.0
	if hm.size() == 2 and hm[0].is_valid_int() and hm[1].is_valid_int():
		base = int(hm[0]) * 60.0 + int(hm[1])
	return fmod(base + maxf(elapsed_s, 0.0) / 60.0, 1440.0)


## 12-hour "H:MM" for minutes past midnight (0 -> "12:00").
static func format_wall(minutes: float) -> String:
	var m := int(minutes)
	var h := (m / 60) % 12
	return "%d:%02d" % [12 if h == 0 else h, m % 60]
