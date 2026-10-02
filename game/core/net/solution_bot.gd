class_name SolutionBot
extends Node
## Headless test client (ADR-0015): once joined, replays solution steps
## [first, last] over the network, standing at each target before acting,
## then exits. Exit codes: 0 done, 2 an intent failed, 3 join rejected,
## 4 timed out. With `wait_for_win`, it stays until the session is won.
##   godot --headless --path game -- --connect HOST:PORT --name bot --bot \
##     [--bot-steps 0-6] [--bot-wait-win]

const STEP_DELAY_S := 0.25
const TIMEOUT_S := 90.0

var first_step: int = 0
var last_step: int = -1          # -1 = through the end
var wait_for_win: bool = false
## Value for submit_flag steps ("" = the offline dev flag).
var flag_value: String = ""
## Stay until some challenge's connection card has a URL (its container is up).
var wait_for_card: bool = false

var _queue: Array = []
var _busy := false
var _delay := 0.0
var _started := false
var _deadline := TIMEOUT_S


func _ready() -> void:
	# The client session starts once the room has loaded (asynchronously),
	# which can be well after the welcome; a rejoin re-welcomes an existing one.
	Game.session_started.connect(func() -> void: call_deferred("_begin"))
	Game.net.welcomed.connect(func(_i: Dictionary) -> void: call_deferred("_begin"))
	Game.net.rejected.connect(func(reason: String) -> void: _finish(3, "join rejected: %s" % reason))
	Game.session_finished.connect(func(won: bool) -> void:
		print("BOT: session finished event, won=%s" % won))


func _begin() -> void:
	if _started or not Game.has_session():
		return
	_started = true
	var steps: Array = Game.manifest.solution
	var last := steps.size() - 1 if last_step < 0 else mini(last_step, steps.size() - 1)
	for i in range(first_step, last + 1):
		_queue.append([i, steps[i]])
	print("BOT %s: joined, replaying steps %d-%d" % [Game.local_player_id, first_step, last])
	Game.start_clock()


var _printed_cards := {}


## Prints each challenge's connection card once (test scripts read it).
func _print_cards() -> void:
	var w := Game.world()
	if w == null:
		return
	for id: String in w.challenges:
		var h: Dictionary = w.challenges[id]
		var line := "BOT: challenge %s url=%s note=%s" % [id, h.get("url", ""), h.get("note", "")]
		if _printed_cards.get(id, "") != line:
			_printed_cards[id] = line
			print(line)


func _has_card_url() -> bool:
	var w := Game.world()
	if w:
		for id: String in w.challenges:
			if not str(w.challenges[id].get("url", "")).is_empty():
				return true
	return false


func _process(delta: float) -> void:
	_print_cards()
	_deadline -= delta
	if _deadline <= 0.0:
		_finish(4, "timed out")
		return
	if not _started or _busy:
		return
	_delay -= delta
	if _delay > 0.0:
		return
	if _queue.is_empty():
		if wait_for_card and not _has_card_url():
			return
		if wait_for_win:
			if not (Game.world() and Game.world().won):
				return
			# Also covers rejoining a session that was won while we were away.
			print("BOT: session finished, won=true")
		_finish(0, "all steps done")
		return
	var entry: Array = _queue.pop_front()
	var i: int = entry[0]
	var step: Dictionary = entry[1]
	var intent := SolutionPlayer.intent_for(step, Game._nodes, Game.vars(), flag_value if not flag_value.is_empty() else SolutionPlayer.DEV_FLAG)
	if intent.has("error"):
		_finish(2, "step %d: %s" % [i, intent["error"]])
		return
	if intent.is_empty():
		print("BOT: step %d %s (observation only)" % [i, step.get("act")])
		_delay = STEP_DELAY_S
		return
	var node := Game.node_at(intent["path"])
	Game.report_position(node.global_position, 0.0)
	_busy = true
	Game.request(node, intent["verb"], intent["payload"], func(r: Dictionary) -> void:
		_busy = false
		_delay = STEP_DELAY_S
		if r.get("ok", false):
			print("BOT: step %d %s %s ok" % [i, intent["verb"], intent["path"]])
		else:
			_finish(2, "step %d %s %s failed: %s" % [i, intent["verb"], intent["path"], r]))


func _finish(code: int, why: String) -> void:
	print("BOT %s: exit %d (%s)" % [Game.local_player_id, code, why])
	set_process(false)
	Game.end_session()
	get_tree().quit(code)
