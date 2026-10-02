extends RefCounted
## Builds a small room in code that exercises every SDK node, plus its
## manifest, for headless tests of the authority (no scene files needed).
##
##   Desk (ContainerProp, unlocked) > Contents > Torch (UVTorch "uv_torch")
##   Cabinet (ContainerProp, locked_by Cabinet/Keypad) > Contents > Diagram (Document)
##   Cabinet/Keypad (KeypadLock, code {{cabinet_code}})
##   Laptop (Terminal, challenge "intranet"), Gate (FlagGate -> CageLock)
##   CageLock (MaglockGate), CageDoor (Door locked_by CageLock)
##   Panel (PatchPanel A:2,B:1 -> ExitKeypad), ExitKeypad (KeypadLock 417062, unpowered)
##   Note (Document), Lever (Lever -> nothing), Key (Item "brass_key"), Box (KeyLock brass_key)


static func manifest() -> RoomManifest:
	return RoomManifest.from_dict({
		"id": "test_room",
		"title": "Test Room",
		"mode": {"duration_minutes": 60, "players": {"min": 1, "max": 4}, "auto_nudge_minutes": 6},
		"entry_scene": "res://rooms/test_room/room.tscn",
		"variables": {"cabinet_code": {"type": "digits", "length": 4}},
		"puzzles": [
			{"id": "find_uv", "title": "Find the torch", "requires": [],
				"solved_when": {"item_picked_up": "uv_torch"}, "hints": ["h1a", "h1b", "h1c"]},
			{"id": "open_cabinet", "title": "Open the cabinet", "requires": ["find_uv"],
				"solved_when": {"node_state": {"path": "Cabinet/Keypad", "state": "unlocked"}}, "hints": ["h2a", "h2b", "h2c"]},
			{"id": "hack", "title": "Hack", "requires": [],
				"solved_when": {"flag_accepted": {"challenge": "intranet"}}, "hints": ["h3a", "h3b", "h3c"]},
			{"id": "power", "title": "Power", "requires": ["hack", "open_cabinet"],
				"solved_when": {"node_state": {"path": "Panel", "state": "solved"}}, "hints": ["h4a", "h4b", "h4c"]},
			{"id": "escape", "title": "Escape", "requires": ["power"],
				"solved_when": {"all_of": [{"node_state": {"path": "ExitKeypad", "state": "unlocked"}}]}, "hints": ["h5a", "h5b", "h5c"]},
		],
		"exit": {"puzzle": "escape"},
		"ctf": {"challenges": [{"id": "intranet", "title": "Intranet", "kind": "service", "difficulty": "easy"}]},
	})


static func build() -> RoomRoot:
	var root := RoomRoot.new()
	root.name = "TestRoom"

	var desk := _add(root, ContainerProp.new(), "Desk") as ContainerProp
	var desk_contents := _add(desk, Node3D.new(), "Contents")
	desk.contents = NodePath("Contents")
	var torch := _add(desk_contents, UVTorch.new(), "Torch") as UVTorch
	torch.item_id = "uv_torch"

	var cabinet := _add(root, ContainerProp.new(), "Cabinet") as ContainerProp
	var keypad := _add(cabinet, KeypadLock.new(), "Keypad") as KeypadLock
	keypad.code = "{{cabinet_code}}"
	cabinet.locked_by = NodePath("Keypad")
	var cab_contents := _add(cabinet, Node3D.new(), "Contents")
	cabinet.contents = NodePath("Contents")
	var diagram := _add(cab_contents, Document.new(), "Diagram") as Document
	diagram.title = "Network diagram"

	var laptop := _add(root, Terminal.new(), "Laptop") as Terminal
	laptop.challenge_id = "intranet"
	var cage_lock := _add(root, MaglockGate.new(), "CageLock")
	var gate := _add(root, FlagGate.new(), "Gate") as FlagGate
	gate.challenge_id = "intranet"
	gate.targets = [NodePath("../CageLock")]
	var cage_door := _add(root, Door.new(), "CageDoor") as Door
	cage_door.locked_by = NodePath("../CageLock")

	var exit_keypad := _add(root, KeypadLock.new(), "ExitKeypad") as KeypadLock
	exit_keypad.code = "417062"
	exit_keypad.starts_powered = false
	var panel := _add(root, PatchPanel.new(), "Panel") as PatchPanel
	panel.cable_ids = ["A", "B"]
	panel.port_count = 4
	panel.solution = "A:2,B:1"
	panel.targets = [NodePath("../ExitKeypad")]

	var note := _add(root, Document.new(), "Note") as Document
	note.title = "Sticky note"
	_add(root, Lever.new(), "Lever")
	var key := _add(root, Item.new(), "Key") as Item
	key.item_id = "brass_key"
	var box := _add(root, KeyLock.new(), "Box") as KeyLock
	box.key_item_id = "brass_key"
	box.consume_key = true
	return root


static func _add(parent: Node, child: Node, n: String) -> Node:
	child.name = n
	parent.add_child(child)
	child.owner = parent.owner if parent.owner else parent
	return child
