class_name JoinVerifier
extends RefCounted
## Decides whether a join token may enter the session (PLAN.md 7.4 step 3).
## M2 stub: a shared invite token passed to the server with --token (empty
## accepts everyone). M3 replaces it with POST /internal/sessions/{id}/verify.

var invite_token: String = ""


func _init(p_invite_token: String = "") -> void:
	invite_token = p_invite_token


## Returns {ok: true} or {ok: false, reason}.
func verify(token: String) -> Dictionary:
	if invite_token.is_empty() or token == invite_token:
		return {"ok": true}
	return {"ok": false, "reason": "bad_token"}
