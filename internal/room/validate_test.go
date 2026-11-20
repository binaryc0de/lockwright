package room

import (
	"os"
	"path/filepath"
	"strings"
	"testing"
)

const goodYAML = `spec_version: 1
id: test_room
title: Test Room
version: 0.1.0
authors: [tester]
requires: { platform: ">=0.1", sdk: ">=0.1" }
mode:
  duration_minutes: 60
  players: { min: 1, max: 4 }
  auto_nudge_minutes: 6
entry_scene: res://rooms/test_room/room.tscn
briefing:
  intro_md: briefing/intro.md
  win_md: briefing/win.md
  timeout_md: briefing/timeout.md
variables:
  cabinet_code: { type: digits, length: 4 }
puzzles:
  - id: find_torch
    title: Find the torch
    requires: []
    solved_when: { item_picked_up: uv_torch }
    hints: ["Look around.", "Check the desk.", "Top drawer."]
  - id: open_cabinet
    title: Open the cabinet
    requires: [find_torch]
    solved_when: { node_state: { path: "Cabinet/Keypad", state: unlocked } }
    hints: ["Shine it.", "The whiteboard.", "The code is on the whiteboard."]
  - id: hack
    title: Hack the intranet
    requires: []
    solved_when: { flag_accepted: { challenge: intranet } }
    hints: ["The laptop.", "Tickets.", "Change the id."]
  - id: escape
    title: Escape
    requires: [open_cabinet, hack]
    solved_when:
      all_of:
        - { node_state: { path: "ExitDoor", state: open } }
    hints: ["The door.", "The keypad.", "Enter the code."]
exit: { puzzle: escape }
ctf:
  challenges:
    - id: intranet
      title: Intranet
      kind: service
      difficulty: easy
      build: ctf/intranet
      ports: [{ container: 8080, protocol: http }]
      flag: { type: per_instance, format: "FLAG{{{nonce}}}", inject_env: FLAG }
      healthcheck: { path: /healthz, timeout_s: 30 }
      hints: ["a", "b", "c"]
solution:
  - { act: pick_up, item: uv_torch }
  - { act: input_code, lock: "Cabinet/Keypad", value: "{{cabinet_code}}" }
  - { act: submit_flag, challenge: intranet, value: "{{flags.intranet}}" }
`

const roomScene = `[gd_scene load_steps=2 format=3]

[ext_resource type="PackedScene" path="res://rooms/test_room/scenes/cabinet.tscn" id="1_cab"]

[node name="TestRoom" type="Node3D"]

[node name="Cabinet" parent="." instance=ExtResource("1_cab")]

[node name="ExitDoor" type="Node3D" parent="."]
`

const cabinetScene = `[gd_scene format=3]

[node name="Cabinet" type="Node3D"]

[node name="Keypad" type="Node3D" parent="."]

[node name="Led" type="Node3D" parent="Keypad"]
`

// writeRoom creates <tmp>/game/rooms/test_room with the given room.yaml and
// returns (roomDir, resRoot).
func writeRoom(t *testing.T, yaml string) (string, string) {
	t.Helper()
	res := filepath.Join(t.TempDir(), "game")
	dir := filepath.Join(res, "rooms", "test_room")
	files := map[string]string{
		"room.yaml":               yaml,
		"room.tscn":               roomScene,
		"scenes/cabinet.tscn":     cabinetScene,
		"briefing/intro.md":       "intro",
		"briefing/win.md":         "win",
		"briefing/timeout.md":     "timeout",
		"ctf/intranet/Dockerfile": "FROM scratch\n",
	}
	for name, body := range files {
		p := filepath.Join(dir, name)
		if err := os.MkdirAll(filepath.Dir(p), 0o755); err != nil {
			t.Fatal(err)
		}
		if err := os.WriteFile(p, []byte(body), 0o644); err != nil {
			t.Fatal(err)
		}
	}
	if err := WriteJSON(dir); err != nil {
		t.Fatal(err)
	}
	return dir, res
}

func validate(t *testing.T, yaml string) *Report {
	t.Helper()
	dir, res := writeRoom(t, yaml)
	s, err := CompileSchema(filepath.Join("..", "..", "docs", "schema", "room.schema.json"))
	if err != nil {
		t.Fatalf("compile schema: %v", err)
	}
	return Validate(dir, res, s)
}

func hasIssue(r *Report, level Level, code, substr string) bool {
	for _, i := range r.Issues {
		if i.Level == level && i.Code == code && strings.Contains(i.Msg, substr) {
			return true
		}
	}
	return false
}

func TestValidRoomPasses(t *testing.T) {
	r := validate(t, goodYAML)
	if r.Failed() || len(r.Issues) > 0 {
		t.Fatalf("expected clean report, got %v", r.Issues)
	}
}

func TestRejectsCycle(t *testing.T) {
	y := strings.Replace(goodYAML,
		"  - id: find_torch\n    title: Find the torch\n    requires: []",
		"  - id: find_torch\n    title: Find the torch\n    requires: [escape]", 1)
	r := validate(t, y)
	if !hasIssue(r, Error, "graph", "cycle") {
		t.Fatalf("expected cycle error, got %v", r.Issues)
	}
}

func TestRejectsUnknownPrerequisite(t *testing.T) {
	y := strings.Replace(goodYAML, "requires: [open_cabinet, hack]", "requires: [open_cabinet, hack, nope]", 1)
	r := validate(t, y)
	if !hasIssue(r, Error, "graph", `unknown puzzle "nope"`) {
		t.Fatalf("expected unknown prerequisite error, got %v", r.Issues)
	}
}

func TestRejectsMissingExit(t *testing.T) {
	y := strings.Replace(goodYAML, "exit: { puzzle: escape }", "exit: { puzzle: nowhere }", 1)
	r := validate(t, y)
	if !hasIssue(r, Error, "graph", "exit.puzzle") {
		t.Fatalf("expected exit error, got %v", r.Issues)
	}
}

func TestWarnsOnOrphanPuzzle(t *testing.T) {
	y := strings.Replace(goodYAML, "requires: [open_cabinet, hack]", "requires: [open_cabinet]", 1)
	r := validate(t, y)
	if r.Failed() || !hasIssue(r, Warning, "graph", `"hack" does not lead to the exit`) {
		t.Fatalf("expected orphan warning only, got %v", r.Issues)
	}
}

func TestResolvesNodePathsThroughInstancedScenes(t *testing.T) {
	y := strings.Replace(goodYAML, `path: "Cabinet/Keypad"`, `path: "Cabinet/Keypad/Led"`, 1)
	if r := validate(t, y); r.Failed() {
		t.Fatalf("nested instanced path should resolve, got %v", r.Issues)
	}
	y = strings.Replace(goodYAML, `path: "Cabinet/Keypad"`, `path: "Cabinet/Missing"`, 1)
	r := validate(t, y)
	if !hasIssue(r, Error, "node_path", "Cabinet/Missing") {
		t.Fatalf("expected node_path error, got %v", r.Issues)
	}
}

func TestSchemaRejectsTooFewHints(t *testing.T) {
	y := strings.Replace(goodYAML, `hints: ["Look around.", "Check the desk.", "Top drawer."]`, `hints: ["Only one."]`, 1)
	r := validate(t, y)
	if !hasIssue(r, Error, "schema", "/puzzles/0/hints") {
		t.Fatalf("expected schema error on hints, got %v", r.Issues)
	}
}

func TestSchemaRejectsUnknownKeyAndBadCondition(t *testing.T) {
	r := validate(t, goodYAML+"bogus_key: 1\n")
	if !hasIssue(r, Error, "schema", "bogus_key") {
		t.Fatalf("expected unknown key error, got %v", r.Issues)
	}
	y := strings.Replace(goodYAML, "solved_when: { item_picked_up: uv_torch }", "solved_when: { item_picked_up: uv_torch, flag_accepted: { challenge: intranet } }", 1)
	if r := validate(t, y); !hasIssue(r, Error, "schema", "/puzzles/0/solved_when") {
		t.Fatalf("expected single-key condition error, got %v", r.Issues)
	}
}

func TestSchemaRequiresNonceInPerInstanceFlag(t *testing.T) {
	y := strings.Replace(goodYAML, `format: "FLAG{{{nonce}}}"`, `format: "FLAG{{{session}}}"`, 1)
	if r := validate(t, y); !hasIssue(r, Error, "schema", "/ctf/challenges/0/flag/format") {
		t.Fatalf("expected flag format error, got %v", r.Issues)
	}
}

func TestRejectsLiteralFlagWithoutEchoingIt(t *testing.T) {
	dir, res := writeRoom(t, goodYAML)
	secret := "FLAG{d34db33f_real_value}"
	if err := os.WriteFile(filepath.Join(dir, "ctf", "intranet", "app.py"), []byte("x = 1\nFLAG = '"+secret+"'\n"), 0o644); err != nil {
		t.Fatal(err)
	}
	s, _ := CompileSchema(filepath.Join("..", "..", "docs", "schema", "room.schema.json"))
	r := Validate(dir, res, s)
	if !hasIssue(r, Error, "flag_literal", "ctf/intranet/app.py:2") {
		t.Fatalf("expected literal flag error, got %v", r.Issues)
	}
	for _, i := range r.Issues {
		if strings.Contains(i.Msg, "d34db33f") {
			t.Fatalf("report leaked the flag value: %v", i)
		}
	}
}

func TestRejectsStaleRoomJSON(t *testing.T) {
	dir, res := writeRoom(t, goodYAML)
	if err := os.WriteFile(filepath.Join(dir, "room.yaml"), []byte(strings.Replace(goodYAML, "title: Test Room", "title: Renamed", 1)), 0o644); err != nil {
		t.Fatal(err)
	}
	s, _ := CompileSchema(filepath.Join("..", "..", "docs", "schema", "room.schema.json"))
	if r := Validate(dir, res, s); !hasIssue(r, Error, "room_json", "stale") {
		t.Fatalf("expected stale room.json error, got %v", r.Issues)
	}
}

func TestRejectsUndeclaredTemplateVariable(t *testing.T) {
	y := strings.Replace(goodYAML, `value: "{{cabinet_code}}"`, `value: "{{safe_code}}"`, 1)
	if r := validate(t, y); !hasIssue(r, Error, "template", "safe_code") {
		t.Fatalf("expected template error, got %v", r.Issues)
	}
}

func TestWarnsOnForbiddenAPIInRoomScript(t *testing.T) {
	dir, res := writeRoom(t, goodYAML)
	if err := os.MkdirAll(filepath.Join(dir, "scripts"), 0o755); err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(filepath.Join(dir, "scripts", "bad.gd"), []byte("class_name Bad\nfunc f():\n\tvar h = HTTPRequest.new()\n"), 0o644); err != nil {
		t.Fatal(err)
	}
	s, _ := CompileSchema(filepath.Join("..", "..", "docs", "schema", "room.schema.json"))
	r := Validate(dir, res, s)
	if !hasIssue(r, Warning, "forbidden_api", "HTTPRequest") || !hasIssue(r, Warning, "class_name", "bad.gd") {
		t.Fatalf("expected forbidden api and class_name warnings, got %v", r.Issues)
	}
}

// An inherited prefab (root node instancing a base scene) placed under an
// instanced node must expose the base scene's children under that prefix.
func TestResolvesInheritedPrefabUnderInstance(t *testing.T) {
	dir, res := writeRoom(t, goodYAML)
	base := "[gd_scene format=3]\n\n[node name=\"Base\" type=\"Node3D\"]\n\n[node name=\"Keypad\" type=\"Node3D\" parent=\".\"]\n"
	inherited := "[gd_scene format=3]\n\n[ext_resource type=\"PackedScene\" path=\"res://rooms/test_room/scenes/base.tscn\" id=\"1_b\"]\n\n[node name=\"Cabinet\" instance=ExtResource(\"1_b\")]\n\n[node name=\"Drawer\" type=\"Node3D\" parent=\".\"]\n"
	for name, body := range map[string]string{"scenes/base.tscn": base, "scenes/cabinet.tscn": inherited} {
		if err := os.WriteFile(filepath.Join(dir, name), []byte(body), 0o644); err != nil {
			t.Fatal(err)
		}
	}
	paths, err := ScenePaths(filepath.Join(dir, "room.tscn"), res)
	if err != nil {
		t.Fatal(err)
	}
	for _, want := range []string{"Cabinet", "Cabinet/Keypad", "Cabinet/Drawer", "ExitDoor"} {
		if !paths[want] {
			t.Errorf("missing %q in %v", want, paths)
		}
	}
}

const difficultiesYAML = `difficulties:
  - id: standard
    title: Standard
  - id: hard
    title: Hard
    description: Crack the password yourself.
    puzzles:
      hack:
        requires: [open_cabinet]
        hints: ["Hard 1.", "Hard 2.", "Hard 3."]
    challenges:
      intranet: { hints: ["x", "y", "z"] }
    solution:
      - { act: pick_up, item: uv_torch }
      - { act: input_code, lock: "Cabinet/Keypad", value: "{{cabinet_code}}" }
      - { act: submit_flag, challenge: intranet, value: "{{flags.intranet}}" }
`

func TestDifficultiesValidate(t *testing.T) {
	r := validate(t, goodYAML+difficultiesYAML)
	if r.Failed() || len(r.Issues) > 0 {
		t.Fatalf("expected clean report, got %v", r.Issues)
	}
}

func TestVariantAppliesOverrides(t *testing.T) {
	dir, _ := writeRoom(t, goodYAML+difficultiesYAML)
	l, err := Load(dir)
	if err != nil {
		t.Fatal(err)
	}
	v := l.Manifest.Variant("hard")
	for _, p := range v.Puzzles {
		if p.ID == "hack" && (len(p.Requires) != 1 || p.Requires[0] != "open_cabinet" || p.Hints[0] != "Hard 1.") {
			t.Fatalf("hack not overridden: %+v", p)
		}
	}
	for _, p := range l.Manifest.Puzzles {
		if p.ID == "hack" && len(p.Requires) != 0 {
			t.Fatalf("base manifest was modified: %+v", p)
		}
	}
	if b := l.Manifest.Variant("nope"); len(b.Solution) != len(l.Manifest.Solution) {
		t.Fatal("unknown difficulty should be the base")
	}
}

func TestDifficultyChecksTheVariedGraphAndSolution(t *testing.T) {
	cycle := strings.Replace(goodYAML+difficultiesYAML, "        requires: [open_cabinet]", "        requires: [escape]", 1)
	if r := validate(t, cycle); !hasIssue(r, Error, "graph", "difficulty hard: puzzle graph has a cycle") {
		t.Fatalf("expected a cycle in the hard variant, got %v", r.Issues)
	}
	badPath := strings.Replace(goodYAML+difficultiesYAML, `      - { act: input_code, lock: "Cabinet/Keypad"`, `      - { act: input_code, lock: "Nowhere/Keypad"`, 1)
	if r := validate(t, badPath); !hasIssue(r, Error, "node_path", "difficulty hard: solution[1].lock") {
		t.Fatalf("expected a bad node path in the hard solution, got %v", r.Issues)
	}
	unknown := strings.Replace(goodYAML+difficultiesYAML, "      hack:\n", "      nope:\n", 1)
	if r := validate(t, unknown); !hasIssue(r, Error, "difficulty", `unknown puzzle "nope"`) {
		t.Fatalf("expected unknown puzzle override, got %v", r.Issues)
	}
	dup := goodYAML + difficultiesYAML + "  - id: hard\n    title: Again\n"
	if r := validate(t, dup); !hasIssue(r, Error, "difficulty", `duplicate difficulty id "hard"`) {
		t.Fatalf("expected duplicate id, got %v", r.Issues)
	}
}

func TestRejectsOverridesOnNonEditableInstances(t *testing.T) {
	dir, res := writeRoom(t, goodYAML)
	scene := filepath.Join(res, "rooms", "test_room", "room.tscn")
	_ = os.WriteFile(scene, []byte(roomScene+"\n[node name=\"Led\" parent=\"Cabinet/Keypad\"]\nvisible = false\n"), 0o644)
	r := Validate(dir, res, nil)
	if !hasIssue(r, Error, "editable", `instance "Cabinet"`) {
		t.Fatalf("expected an editable error, got %v", r.Issues)
	}
	_ = os.WriteFile(scene, []byte(roomScene+"\n[node name=\"Led\" parent=\"Cabinet/Keypad\"]\nvisible = false\n\n[editable path=\"Cabinet\"]\n"), 0o644)
	if r := Validate(dir, res, nil); hasIssue(r, Error, "editable", "") {
		t.Fatalf("editable instance still rejected: %v", r.Issues)
	}
}

func TestDraftFlagValidates(t *testing.T) {
	if r := validate(t, goodYAML+"draft: true\n"); r.Failed() {
		t.Fatalf("draft: true rejected: %v", r.Issues)
	}
	if r := validate(t, goodYAML+"draft: yes please\n"); !r.Failed() {
		t.Fatal("non-boolean draft accepted")
	}
}

func TestChallengeResourcesPidsValidates(t *testing.T) {
	y := strings.Replace(goodYAML,
		"      healthcheck: { path: /healthz, timeout_s: 30 }",
		"      healthcheck: { path: /healthz, timeout_s: 30 }\n      resources: { cpu: 0.5, memory_mb: 256, pids: 64 }", 1)
	if r := validate(t, y); r.Failed() {
		t.Fatalf("valid resources.pids rejected: %v", r.Issues)
	}
	for _, bad := range []string{"0", "99999"} {
		yb := strings.Replace(y, "pids: 64", "pids: "+bad, 1)
		if r := validate(t, yb); !hasIssue(r, Error, "schema", "/ctf/challenges/0/resources/pids") {
			t.Fatalf("pids: %s accepted: %v", bad, r.Issues)
		}
	}
}
