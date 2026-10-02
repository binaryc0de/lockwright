class_name DevFlagValidator
extends FlagValidator
## M1 offline stub: accepts any non-empty flag so the CTF step can be played
## without the platform. Never used when a platform URL is configured.


func validate(_session_id: String, _challenge_id: String, value: String, _player_id: String) -> Dictionary:
	return {"accepted": not value.strip_edges().is_empty()}
