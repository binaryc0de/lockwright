class_name PlatformJoinVerifier
extends JoinVerifier
## M3 join verification (PLAN.md 7.4 step 3): the platform consumes the
## single-use join token and names the player.

var client: PlatformClient


func _init(p_client: PlatformClient) -> void:
	client = p_client


func verify_async(token: String, on_done: Callable) -> void:
	client.request_async(HTTPClient.METHOD_POST, client.internal_path("verify"), {"join_token": token},
		func(code: int, data: Variant) -> void:
			if code == 200 and data is Dictionary:
				on_done.call({"ok": true, "player_id": str(data.get("player_id", "")), "display_name": str(data.get("display_name", ""))})
			elif code == 0:
				on_done.call({"ok": false, "reason": "platform_unreachable"})
			else:
				on_done.call({"ok": false, "reason": "bad_token"}))
