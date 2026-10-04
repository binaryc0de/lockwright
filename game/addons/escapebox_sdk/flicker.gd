@icon("res://addons/escapebox_sdk/icons/eb_node.svg")
class_name Flicker
extends Node
## Makes its parent Light3D flicker like a candle or a torch (smoothed noise
## on the energy). Presentation only; does nothing on the server.

## Fraction of the light's energy that wanders (0.15 = +-15 %).
@export_range(0.0, 1.0) var amount: float = 0.15
## How fast it wanders (noise cycles per second).
@export var speed: float = 6.0
@export var seed_offset: float = 0.0

var _light: Light3D
var _base := 1.0
var _t := 0.0
var _noise := FastNoiseLite.new()


func _ready() -> void:
	_light = get_parent() as Light3D
	if _light == null or DisplayServer.get_name() == "headless":
		set_process(false)
		return
	_base = _light.light_energy
	_noise.frequency = 1.0
	_t = seed_offset * 37.0


func energy_at(t: float) -> float:
	return _base * (1.0 + amount * _noise.get_noise_1d(t))


func _process(delta: float) -> void:
	_t += delta * speed
	_light.light_energy = energy_at(_t)
