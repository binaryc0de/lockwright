class_name RemotePlayers
extends Node3D
## Teammates as seen by this client (PLAN.md 6.2): a capsule with a head
## lamp and a name tag per remote player, eased toward the 15 Hz roster.

const EYE_HEIGHT := 1.6
const SMOOTH := 12.0

var _avatars: Dictionary = {}   # player id -> Node3D
var _targets: Dictionary = {}   # player id -> {pos, yaw}


func _ready() -> void:
	Game.net.roster_updated.connect(_on_roster)


func _on_roster(roster: Dictionary) -> void:
	for pid: String in roster:
		if pid == Game.local_player_id:
			continue
		var r: Dictionary = roster[pid]
		if not _avatars.has(pid):
			_avatars[pid] = _make_avatar(str(r.get("name", pid)))
			add_child(_avatars[pid])
			(_avatars[pid] as Node3D).global_position = (r["pos"] as Vector3) - Vector3.UP * EYE_HEIGHT
		_targets[pid] = r
	for pid: String in _avatars.keys():
		if not roster.has(pid):
			(_avatars[pid] as Node).queue_free()
			_avatars.erase(pid)
			_targets.erase(pid)


func _process(delta: float) -> void:
	var k := 1.0 - exp(-SMOOTH * delta)
	for pid: String in _avatars:
		var a := _avatars[pid] as Node3D
		var t: Dictionary = _targets[pid]
		var feet: Vector3 = (t["pos"] as Vector3) - Vector3.UP * EYE_HEIGHT
		a.global_position = a.global_position.lerp(feet, k)
		a.rotation.y = lerp_angle(a.rotation.y, float(t["yaw"]), k)


func avatar_count() -> int:
	return _avatars.size()


func _make_avatar(display_name: String) -> Node3D:
	var root := Node3D.new()
	root.name = "Avatar_" + display_name.validate_node_name()
	var body := MeshInstance3D.new()
	var capsule := CapsuleMesh.new()
	capsule.radius = 0.28
	capsule.height = 1.75
	var mat := StandardMaterial3D.new()
	mat.albedo_color = Color(0.22, 0.32, 0.45)
	mat.roughness = 0.6
	capsule.material = mat
	body.mesh = capsule
	body.position.y = 0.875
	root.add_child(body)
	var lamp := SpotLight3D.new()
	lamp.position = Vector3(0, EYE_HEIGHT, -0.25)
	lamp.light_energy = 0.8
	lamp.spot_range = 4.0
	lamp.spot_angle = 22.0
	lamp.light_color = Color(1, 0.95, 0.85)
	root.add_child(lamp)
	var tag := Label3D.new()
	tag.text = display_name
	tag.billboard = BaseMaterial3D.BILLBOARD_ENABLED
	tag.pixel_size = 0.004
	tag.font_size = 40
	tag.outline_size = 8
	tag.position.y = 2.05
	tag.no_depth_test = true
	root.add_child(tag)
	return root
