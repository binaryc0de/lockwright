extends GdUnitTestSuite
## M0 acceptance: the Codex-built keypad_4.glb imports with per-button meshes
## and faces -Z (docs/ASSET_PIPELINE.md Section 6).

const GLB := "res://assets/core/props/keypad_4.glb"
const KEYS: PackedStringArray = [
	"btn_0", "btn_1", "btn_2", "btn_3", "btn_4", "btn_5", "btn_6", "btn_7", "btn_8", "btn_9",
	"btn_clear", "btn_enter",
]


func _instance() -> Node3D:
	var scene: PackedScene = load(GLB)
	assert_object(scene).is_not_null()
	var root: Node3D = auto_free(scene.instantiate())
	add_child(root)
	return root


func test_every_key_is_its_own_mesh() -> void:
	var root := _instance()
	for key in KEYS:
		var node := root.find_child(key, true, false)
		assert_object(node).override_failure_message("missing %s" % key).is_not_null()
		assert_object(node).is_instanceof(MeshInstance3D)


func test_screen_and_led_are_separate_meshes() -> void:
	var root := _instance()
	for part in ["screen", "led_status"]:
		assert_object(root.find_child(part, true, false)).is_instanceof(MeshInstance3D)


func test_keys_face_minus_z_from_a_back_plate_at_zero() -> void:
	var root := _instance()
	for key in KEYS:
		var mesh: MeshInstance3D = root.find_child(key, true, false)
		var aabb := mesh.global_transform * mesh.get_aabb()
		assert_float(aabb.end.z).override_failure_message("%s not in front of the plate" % key).is_less_equal(0.0005)
		assert_float(aabb.position.z).is_less(0.0)


func test_has_collision() -> void:
	var root := _instance()
	var bodies := root.find_children("*", "StaticBody3D", true, false)
	assert_int(bodies.size()).is_greater_equal(1)
