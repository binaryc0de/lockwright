class_name GraphicsQuality
extends RefCounted
## Graphics presets (M4 performance pass, ADR-0021). Rooms author their look
## at "high"; lower presets switch off or cheapen the expensive effects in
## every WorldEnvironment under `root` and in the viewport. Generic: no room
## knows about presets.
##   high:   as authored (SDFGI, SSIL, SSAO, volumetric fog, glow)
##   medium: no SSIL; SDFGI and fog at reduced quality; SSAO low, half size
##   low:    no SDFGI (ambient raised to stand in), fog, SSIL or SSAO;
##           3D rendered at 77 % with FSR upscaling

const LEVELS := ["low", "medium", "high"]
## Ambient energy added when SDFGI is turned off, so rooms keep roughly the
## brightness the missing bounce light gave them.
const NO_GI_AMBIENT := 0.18
const SWITCHED := ["sdfgi_enabled", "ssil_enabled", "ssao_enabled", "volumetric_fog_enabled", "ambient_light_energy"]


static func apply(root: Node, level: String) -> void:
	if not level in LEVELS:
		level = "high"
	for we: WorldEnvironment in root.find_children("*", "WorldEnvironment", true, false):
		var env := we.environment
		if env == null:
			continue
		if not env.has_meta("eb_authored"):
			env.set_meta("eb_authored", env.duplicate())
		var a: Environment = env.get_meta("eb_authored")
		for p in SWITCHED:
			env.set(p, a.get(p))
		if level != "high":
			env.ssil_enabled = false
		if level == "low":
			env.ssao_enabled = false
			env.volumetric_fog_enabled = false
			if a.sdfgi_enabled:
				env.sdfgi_enabled = false
				env.ambient_light_energy = a.ambient_light_energy + NO_GI_AMBIENT
	_global(level)
	var vp := root.get_viewport()
	if vp:
		vp.scaling_3d_mode = Viewport.SCALING_3D_MODE_FSR if level == "low" else Viewport.SCALING_3D_MODE_BILINEAR
		vp.scaling_3d_scale = 0.77 if level == "low" else 1.0


static func _global(level: String) -> void:
	var rays: int = ProjectSettings.get_setting("rendering/global_illumination/sdfgi/probe_ray_count", 1)
	var fog_size: int = ProjectSettings.get_setting("rendering/environment/volumetric_fog/volume_size", 64)
	var fog_depth: int = ProjectSettings.get_setting("rendering/environment/volumetric_fog/volume_depth", 64)
	var ssao_q: int = ProjectSettings.get_setting("rendering/environment/ssao/quality", 2)
	if level == "medium":
		rays = RenderingServer.ENV_SDFGI_RAY_COUNT_8
		fog_size = mini(fog_size, 48)
		fog_depth = mini(fog_depth, 48)
		ssao_q = RenderingServer.ENV_SSAO_QUALITY_LOW
	RenderingServer.environment_set_sdfgi_ray_count(rays)
	RenderingServer.environment_set_volumetric_fog_volume_size(fog_size, fog_depth)
	RenderingServer.environment_set_ssao_quality(ssao_q, true,
		ProjectSettings.get_setting("rendering/environment/ssao/adaptive_target", 0.5),
		ProjectSettings.get_setting("rendering/environment/ssao/blur_passes", 2),
		ProjectSettings.get_setting("rendering/environment/ssao/fadeout_from", 50.0),
		ProjectSettings.get_setting("rendering/environment/ssao/fadeout_to", 300.0))
