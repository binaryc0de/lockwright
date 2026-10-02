extends GdUnitTestSuite


func test_snapshot_survives_json_round_trip() -> void:
	var s := WorldState.new()
	s.nodes = {"Cabinet/Keypad": {"state": "unlocked", "powered": true, "attempts": 2, "last_ok": true}}
	s.inventory.assign(["Desk/Contents/Torch"])
	s.picked_up = {"uv_torch": true}
	s.evidence.assign([{"kind": "note", "id": 1, "text": "417?", "author": "Sam"}])
	s.puzzle("find_uv")["solved"] = true
	s.puzzle("find_uv")["hints_revealed"] = 2
	s.flags_accepted = {"intranet": 1234.5}
	s.vars = {"cabinet_code": "0042"}
	s.started_at = 1000.0
	s.duration_s = 3600
	s.timed_out = true
	s.challenges = {"intranet": {"note": "x"}}

	var restored := WorldState.from_dict(JSON.parse_string(JSON.stringify(s.to_dict())))
	assert_dict(restored.nodes["Cabinet/Keypad"]).contains_key_value("state", "unlocked")
	assert_array(restored.inventory).contains_exactly(["Desk/Contents/Torch"])
	assert_bool(restored.picked_up.has("uv_torch")).is_true()
	assert_bool(restored.is_solved("find_uv")).is_true()
	assert_int(restored.hints_used()).is_equal(2)
	assert_str(restored.vars["cabinet_code"]).is_equal("0042")
	assert_float(restored.remaining_s(1600.0)).is_equal(3000.0)
	assert_bool(restored.timed_out).is_true()
	# A second round trip is lossless (snapshots can be saved and restored repeatedly).
	var once: Dictionary = JSON.parse_string(JSON.stringify(s.to_dict()))
	assert_dict(JSON.parse_string(JSON.stringify(restored.to_dict()))).is_equal(once)


func test_rejects_unknown_snapshot_version() -> void:
	var s := WorldState.from_dict({"version": 99, "vars": {"x": "1"}})
	assert_dict(s.vars).is_empty()
	assert_error(func() -> void: WorldState.from_dict({"version": 99})).is_push_error("snapshot version 99 not supported")


func test_template_render() -> void:
	assert_str(EBTemplate.render("code {{a}}-{{ b }}-{{missing}}", {"a": "12", "b": 3})).is_equal("code 12-3-{{missing}}")
	assert_str(EBTemplate.render("plain", {})).is_equal("plain")
