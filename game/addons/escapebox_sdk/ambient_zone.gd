@icon("res://addons/escapebox_sdk/icons/eb_node.svg")
class_name AmbientZone
extends Node3D
## Positional room tone (PLAN.md 6.9): a loop synthesised at start-up from a
## mains hum (+ harmonics), filtered noise (fans, air) and an optional
## buzz flutter (fluorescent tubes), so rooms need no audio files for it.
## Presentation only; silent on the server.

@export var hum_hz: float = 50.0
## 0..1 loudness of the hum and its harmonics.
@export_range(0.0, 1.0) var hum_level: float = 0.2
@export_range(1, 8) var harmonics: int = 3
## 0..1 loudness of low-passed noise.
@export_range(0.0, 1.0) var noise_level: float = 0.0
@export var noise_cutoff_hz: float = 900.0
## 0..1 amplitude flutter at 2 x hum_hz (fluorescent buzz).
@export_range(0.0, 1.0) var buzz: float = 0.0
## Clock ticks per second (0 = none), alternating tick and tock, and their
## loudness 0..1.
@export var tick_per_s: float = 0.0
@export_range(0.0, 1.0) var tick_level: float = 0.5
## Optional: sound only while this SDK node's state[only_when_key], as text,
## equals only_when_value (a clock that ticks once it is wound:
## key "powered", value "true").
@export var only_when: NodePath
@export var only_when_key: String = "state"
@export var only_when_value: String = ""
@export var volume_db: float = -18.0
@export var unit_size: float = 3.0
@export var max_distance: float = 14.0

const RATE := 22050
const SECONDS := 2.0
const FADE := 0.1

var player: AudioStreamPlayer3D


func _ready() -> void:
	if not EBSound.enabled():
		return
	player = AudioStreamPlayer3D.new()
	player.stream = make_loop()
	player.volume_db = volume_db
	player.unit_size = unit_size
	player.max_distance = max_distance
	add_child(player)
	var watched := get_node_or_null(only_when) as EBNode
	if watched:
		watched.state_applied.connect(_on_watched_state)
		_on_watched_state(watched.current_state)
	else:
		player.play()


## Whether a watched node's state lets the zone sound.
func condition_met(state: Dictionary) -> bool:
	return str(state.get(only_when_key, "")) == only_when_value


func _on_watched_state(state: Dictionary) -> void:
	if player == null:
		return
	var on := condition_met(state)
	if on and not player.playing:
		player.play()
	elif not on and player.playing:
		player.stop()


## 16-bit mono loop. The hum uses whole cycles over the loop length; the
## noise tail is cross-faded into its head so the loop point does not click.
func make_loop() -> AudioStreamWAV:
	var n := int(RATE * SECONDS)
	var fade := int(RATE * FADE)
	var rng := RandomNumberGenerator.new()
	rng.seed = 417
	var alpha := clampf(TAU * noise_cutoff_hz / RATE, 0.0, 1.0)
	var noise := PackedFloat32Array()
	noise.resize(n + fade)
	var lp := 0.0
	for i in n + fade:
		lp += alpha * (rng.randf_range(-1.0, 1.0) - lp)
		noise[i] = lp
	for i in fade:
		var w := float(i) / fade
		noise[i] = noise[i] * w + noise[n + i] * (1.0 - w)
	var data := PackedByteArray()
	data.resize(n * 2)
	var hum_norm := 0.0
	for h in range(1, harmonics + 1):
		hum_norm += 1.0 / h
	for i in n:
		var t := float(i) / RATE
		var hum := 0.0
		for h in range(1, harmonics + 1):
			hum += sin(TAU * hum_hz * h * t) / h
		var flutter := 1.0 - buzz * 0.5 * (1.0 + sin(TAU * hum_hz * 2.0 * t))
		var v := (hum_level * hum / hum_norm + noise_level * noise[i] * 3.0) * flutter * 0.5
		if tick_per_s > 0.0:
			v += tick_sample(t) * tick_level
		data.encode_s16(i * 2, int(clampf(v, -1.0, 1.0) * 32767.0))
	var w := AudioStreamWAV.new()
	w.format = AudioStreamWAV.FORMAT_16_BITS
	w.mix_rate = RATE
	w.stereo = false
	w.data = data
	w.loop_mode = AudioStreamWAV.LOOP_FORWARD
	w.loop_begin = 0
	w.loop_end = n
	return w


## One sample of the tick track at time t: a short woody click with a brass
## ping, the "tock" a little lower. Whole ticks fit the loop when
## tick_per_s * SECONDS is a whole number.
func tick_sample(t: float) -> float:
	var period := 1.0 / tick_per_s
	var k := int(floor(t / period))
	var dt := t - k * period
	if dt > 0.04:
		return 0.0
	var ping := 2600.0 if k % 2 == 0 else 2100.0
	var env := exp(-dt * 220.0)
	return env * (0.6 * sin(TAU * ping * dt) + 0.4 * sin(TAU * ping * 0.37 * dt))

