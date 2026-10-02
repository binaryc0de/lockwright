class_name NetTimeouts
extends RefCounted
## Client-side ENet timeouts toward the server (ADR-0015): notice a dead
## server in about 6 s instead of up to 30 s, so a crash turns into a reconnect
## quickly. Applied only after the room has loaded (loading stalls the main
## loop). The server keeps ENet's defaults so slow-loading clients are not
## dropped. WebSocket peers keep their defaults.

const LIMIT := 32
const MIN_MS := 3000
const MAX_MS := 6000


static func apply(mp: MultiplayerPeer, peer_id: int) -> void:
	var enet := mp as ENetMultiplayerPeer
	if enet == null:
		return
	var p := enet.get_peer(peer_id)
	if p:
		p.set_timeout(LIMIT, MIN_MS, MAX_MS)
