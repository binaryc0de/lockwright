class_name FirstPersonPlayer
extends CharacterBody3D
## The local player (PLAN.md 6.2): walk ~3 m/s, no jump/crouch/sprint, mouse
## look, and a 3 m screen-centre ray that targets Interactables. Movement is
## client-authoritative; the authority only sanity-checks reach.

signal target_changed(target: Interactable)

const WALK_SPEED := 3.0
const ACCEL := 12.0
const EYE_HEIGHT := 1.6
## Distance between footstep sounds.
const STRIDE_M := 0.6
## Focused views: how close the camera comes, and how fast.
const FOCUS_DISTANCE := 0.55
const FOCUS_TIME := 0.25
const REACH := 3.0
const RADIUS := 0.3
const HEIGHT := 1.75
const PLAYER_LAYER := 3

var camera: Camera3D
var ray: RayCast3D
var target: Interactable = null
## True while a UI panel owns the mouse; the player then ignores input.
var input_enabled: bool = true

var _pitch: float = 0.0
var _report_timer: float = 0.0
var _stride := 0.0
var _focus_tween: Tween


func _ready() -> void:
	collision_layer = 1 << (PLAYER_LAYER - 1)
	collision_mask = 1  # world only; players do not block each other
	var shape := CollisionShape3D.new()
	var capsule := CapsuleShape3D.new()
	capsule.radius = RADIUS
	capsule.height = HEIGHT
	shape.shape = capsule
	shape.position.y = HEIGHT / 2.0
	add_child(shape)

	camera = Camera3D.new()
	camera.position.y = EYE_HEIGHT
	camera.fov = Settings.fov
	camera.near = 0.03
	add_child(camera)
	camera.make_current()

	ray = RayCast3D.new()
	ray.target_position = Vector3(0, 0, -REACH)
	ray.collision_mask = 1 | (1 << (Interactable.INTERACT_LAYER - 1))
	ray.collide_with_areas = false
	camera.add_child(ray)


func place_at(t: Transform3D) -> void:
	global_position = t.origin
	rotation.y = t.basis.get_euler().y
	_pitch = 0.0
	camera.rotation.x = 0.0


## Focused views (PLAN.md 6.5): move the camera in along the current line of
## sight until it is FOCUS_DISTANCE from `point`, looking at it. The path is the
## player's own view ray, so the camera never passes through walls.
func focus_on(point: Vector3) -> void:
	var eye := global_position + Vector3.UP * EYE_HEIGHT
	var to := point - eye
	if to.length() <= FOCUS_DISTANCE + 0.05:
		return
	var dir := to.normalized()
	var goal := Transform3D(Basis.looking_at(dir, Vector3.UP if absf(dir.y) < 0.99 else Vector3.BACK), point - dir * FOCUS_DISTANCE)
	_tween_camera(global_transform.affine_inverse() * goal)


func unfocus() -> void:
	_tween_camera(Transform3D(Basis.from_euler(Vector3(_pitch, 0, 0)), Vector3.UP * EYE_HEIGHT))


func is_focused() -> bool:
	return not camera.transform.origin.is_equal_approx(Vector3.UP * EYE_HEIGHT)


func _tween_camera(local: Transform3D) -> void:
	if _focus_tween:
		_focus_tween.kill()
	if not is_inside_tree():
		camera.transform = local
		return
	_focus_tween = create_tween().set_trans(Tween.TRANS_SINE).set_ease(Tween.EASE_OUT)
	_focus_tween.tween_property(camera, "transform", local, FOCUS_TIME)


func _unhandled_input(event: InputEvent) -> void:
	if not input_enabled:
		return
	if event is InputEventMouseMotion and Input.mouse_mode == Input.MOUSE_MODE_CAPTURED:
		var m := event as InputEventMouseMotion
		rotate_y(-m.relative.x * Settings.mouse_sensitivity)
		var dy := m.relative.y * Settings.mouse_sensitivity * (-1.0 if Settings.invert_y else 1.0)
		_pitch = clampf(_pitch - dy, deg_to_rad(-85), deg_to_rad(85))
		camera.rotation.x = _pitch
	elif event.is_action_pressed("interact") and Input.mouse_mode == Input.MOUSE_MODE_CAPTURED:
		if target and target.is_available():
			target.client_interact(Game.selected_item)
		get_viewport().set_input_as_handled()


func _physics_process(delta: float) -> void:
	var dir := Vector3.ZERO
	if input_enabled:
		var input := Input.get_vector("move_left", "move_right", "move_forward", "move_back")
		dir = (transform.basis * Vector3(input.x, 0, input.y)).normalized()
	var want := dir * WALK_SPEED
	velocity.x = move_toward(velocity.x, want.x, ACCEL * delta)
	velocity.z = move_toward(velocity.z, want.z, ACCEL * delta)
	if not is_on_floor():
		velocity.y -= ProjectSettings.get_setting("physics/3d/default_gravity", 9.8) * delta
	else:
		velocity.y = 0.0
	move_and_slide()
	if is_on_floor():
		_stride += Vector2(velocity.x, velocity.z).length() * delta
		if _stride >= STRIDE_M:
			_stride = 0.0
			EBSound.play_at(self, EBSound.FOOTSTEPS.pick_random(), -16.0, 0.08)
	_update_target()
	_report_timer -= delta
	if _report_timer <= 0.0:
		_report_timer = 1.0 / 15.0
		Game.report_position(global_position + Vector3.UP * EYE_HEIGHT, rotation.y)


func _update_target() -> void:
	var hit: Interactable = null
	if input_enabled and ray.is_colliding():
		var i := Interactable.owner_of(ray.get_collider())
		if i and i.is_available():
			hit = i
	if hit == target:
		return
	if target and is_instance_valid(target):
		target.set_highlighted(false)
	target = hit
	if target:
		target.set_highlighted(true)
	target_changed.emit(target)
