extends RefCounted
## An in-code room for the clockwork SDK nodes (ADR-0033), wired the way the
## Clockmaker's Study uses them:
##
##   Rings (DialLock "ABC" x3, code CAB) -> RingSpring (AllOfGate) -> Box
##   Box (ContainerProp locked_by Rings)
##   GearA, GearB (KeyLock gear_a / gear_b) -> Gears (AllOfGate) -> Bird
##   Bird (SequencePlayer, {{melody}}), Bars (SequenceLock {{melody}}, pads 1-5)
##   Bars -> ClockGate (AllOfGate) -> Clock (DialLock hour:minute, unpowered,
##   hands HourHand/MinuteHand, code {{true_time}})
##   GearItemA/GearItemB (Items), Wall (SessionClock 23:00 with hands)


static func manifest() -> RoomManifest:
	return RoomManifest.from_dict({
		"id": "clockwork_test",
		"title": "Clockwork Test",
		"mode": {"duration_minutes": 60, "players": {"min": 1, "max": 4}, "auto_nudge_minutes": 0},
		"entry_scene": "res://rooms/clockwork_test/room.tscn",
		"variables": {
			"melody": {"type": "choice", "choices": ["31524", "24153"]},
			"true_time": {"type": "choice", "choices": ["7:25", "10:50"]},
		},
		"puzzles": [
			{"id": "rings", "title": "Rings", "requires": [],
				"solved_when": {"node_state": {"path": "Rings", "state": "unlocked"}}, "hints": ["a", "b", "c"]},
			{"id": "fit", "title": "Fit gears", "requires": [],
				"solved_when": {"all_of": [{"node_state": {"path": "GearA", "state": "unlocked"}},
					{"node_state": {"path": "GearB", "state": "unlocked"}}]}, "hints": ["a", "b", "c"]},
			{"id": "song", "title": "Song", "requires": ["fit"],
				"solved_when": {"node_state": {"path": "Bars", "state": "unlocked"}}, "hints": ["a", "b", "c"]},
			{"id": "clock", "title": "Clock", "requires": ["song", "rings"],
				"solved_when": {"node_state": {"path": "Clock", "state": "unlocked"}}, "hints": ["a", "b", "c"]},
		],
		"exit": {"puzzle": "clock"},
	})


static func build() -> RoomRoot:
	var root := RoomRoot.new()
	root.name = "ClockworkRoom"

	var rings := _add(root, DialLock.new(), "Rings") as DialLock
	rings.wheels = ["ABC", "ABC", "ABC"]
	rings.code = "CAB"
	for i in 3:
		_add(rings, Node3D.new(), "Ring%d" % i)
	rings.hand_parts = [NodePath("Ring0"), NodePath("Ring1"), NodePath("Ring2")]
	rings.hand_turn = Vector3(360, 0, 0)
	var box := _add(root, ContainerProp.new(), "Box") as ContainerProp
	box.locked_by = NodePath("../Rings")
	var spring := _add(root, AllOfGate.new(), "RingSpring") as AllOfGate
	spring.inputs = [NodePath("../Rings")]
	spring.targets = [NodePath("../Box")]

	for id in ["a", "b"]:
		var item := _add(root, Item.new(), "GearItem" + id.to_upper()) as Item
		item.item_id = "gear_" + id
		var slot := _add(root, KeyLock.new(), "Gear" + id.to_upper()) as KeyLock
		slot.key_item_id = "gear_" + id
		slot.consume_key = true

	var bird := _add(root, SequencePlayer.new(), "Bird") as SequencePlayer
	bird.sequence = "{{melody}}"
	_add(bird, Node3D.new(), "Tail")
	bird.pointer = NodePath("Tail")
	var gears := _add(root, AllOfGate.new(), "Gears") as AllOfGate
	gears.inputs = [NodePath("../GearA"), NodePath("../GearB")]
	gears.targets = [NodePath("../Bird")]

	var bars := _add(root, SequenceLock.new(), "Bars") as SequenceLock
	bars.code = "{{melody}}"
	for i in range(1, 6):
		var pad := _add(bars, SequencePad.new(), "Bar%d" % i) as SequencePad
		pad.symbol = str(i)
		pad.tone_hz = 400.0 + 50.0 * i

	var clock := _add(root, DialLock.new(), "Clock") as DialLock
	clock.wheels = ["12,1,2,3,4,5,6,7,8,9,10,11", "00,05,10,15,20,25,30,35,40,45,50,55"]
	clock.separator = ":"
	clock.start_code = "11:05"
	clock.code = "{{true_time}}"
	clock.starts_powered = false
	_add(clock, Node3D.new(), "HourHand")
	_add(clock, Node3D.new(), "MinuteHand")
	clock.hand_parts = [NodePath("HourHand"), NodePath("MinuteHand")]
	var clock_gate := _add(root, AllOfGate.new(), "ClockGate") as AllOfGate
	clock_gate.inputs = [NodePath("../Bars")]
	clock_gate.targets = [NodePath("../Clock")]

	var wall := _add(root, SessionClock.new(), "Wall") as SessionClock
	wall.wall_start = "23:00"
	_add(wall, Node3D.new(), "Hour")
	_add(wall, Node3D.new(), "Minute")
	wall.hour_hand = NodePath("Hour")
	wall.minute_hand = NodePath("Minute")
	return root


static func _add(parent: Node, child: Node, n: String) -> Node:
	child.name = n
	parent.add_child(child)
	child.owner = parent.owner if parent.owner else parent
	return child
