class_name PlatformFlagValidator
extends FlagValidator
## M3 flag checks (PLAN.md 7.5): the platform owns flags, rate limits and the
## submission log. Blocking but bounded (ADR-0018 point 6). Never logs `value`.

var client: PlatformClient


func _init(p_client: PlatformClient) -> void:
	client = p_client


func validate(_session_id: String, challenge_id: String, value: String, player_id: String) -> Dictionary:
	var r := client.request_blocking(HTTPClient.METHOD_POST, client.internal_path("flags"),
		{"challenge_id": challenge_id, "value": value, "player_id": player_id}, 3.0)
	var data: Variant = r["data"]
	if (r["code"] == 200 or r["code"] == 429) and data is Dictionary:
		var out := {"accepted": bool(data.get("accepted", false))}
		if data.has("retry_after_s"):
			out["retry_after_s"] = int(data["retry_after_s"])
		return out
	return {"accepted": false, "error": "platform_unreachable"}


## Real handles arrive asynchronously (SessionServer asks the platform); until
## then the connection card says the service is starting.
func start_challenges(_session_id: String, challenges: Array) -> Dictionary:
	var out := {}
	for c: Dictionary in challenges:
		out[c["id"]] = {"note": "Starting this challenge's service... the address appears here in a moment."}
	return out
