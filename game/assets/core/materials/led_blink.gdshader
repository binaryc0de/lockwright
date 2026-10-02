shader_type spatial;
// Equipment LEDs that blink (M4 polish). Every LED gets its own phase and
// pattern from a hash of its model-space cell, so one mesh of many LEDs
// reads as many independent lights: some steady, some disk/network
// activity flicker, some slow status blink. Presentation only.

uniform sampler2D palette : source_color, filter_linear_mipmap;
uniform float energy = 2.0;
// Size of the cell one LED occupies, in model metres.
uniform float cell = 0.012;
uniform float steady_share : hint_range(0.0, 1.0) = 0.35;
uniform float slow_share : hint_range(0.0, 1.0) = 0.2;

varying vec3 model_pos;

void vertex() {
	model_pos = VERTEX;
}

float hash(vec3 p) {
	p = fract(p * vec3(0.1031, 0.1030, 0.0973));
	p += dot(p, p.yxz + 33.33);
	return fract((p.x + p.y) * p.z);
}

void fragment() {
	vec3 c = texture(palette, UV).rgb;
	float h = hash(floor(model_pos / cell) + 17.0);
	float on = 1.0;
	if (h > steady_share + slow_share) {
		// Activity: irregular bursts, re-rolled about 12 times a second.
		float t = floor(TIME * (8.0 + 8.0 * h));
		on = step(0.45, hash(vec3(t, h * 91.0, 3.0)));
	} else if (h > steady_share) {
		// Status: about 1 Hz, own phase.
		on = step(0.5, fract(TIME * (0.6 + h) + h * 7.0));
	}
	ALBEDO = c * 0.25;
	ROUGHNESS = 0.3;
	EMISSION = c * energy * mix(0.06, 1.0, on);
}
