class_name FlagValidator
extends RefCounted
## Decides whether a submitted flag is correct (PLAN.md 7.5). The real
## validator (M3) asks the platform, which owns flags, rate limits, and the
## submission log. Implementations must never log or echo `value`.


## Returns {accepted: bool, retry_after_s?: int, error?: String}.
func validate(_session_id: String, _challenge_id: String, _value: String, _player_id: String) -> Dictionary:
	return {"accepted": false, "error": "no_validator"}


## Connection handles for the session's challenges (PLAN.md 7.6), keyed by
## challenge id. The dev stub has no real services.
func start_challenges(_session_id: String, challenges: Array) -> Dictionary:
	var out := {}
	for c: Dictionary in challenges:
		out[c["id"]] = {"note": "Dev mode: this challenge's service is not running. Any non-empty flag is accepted."}
	return out
