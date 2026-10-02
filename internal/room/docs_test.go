package room

import (
	"bytes"
	"os"
	"path/filepath"
	"regexp"
	"testing"

	"github.com/santhosh-tekuri/jsonschema/v6"
	"go.yaml.in/yaml/v3"
)

// The complete example in docs/ROOM_AUTHORING.md must stay valid against the
// schema, so the guide cannot drift from the format.
func TestRoomAuthoringExampleMatchesSchema(t *testing.T) {
	doc, err := os.ReadFile(filepath.Join("..", "..", "docs", "ROOM_AUTHORING.md"))
	if err != nil {
		t.Fatal(err)
	}
	m := regexp.MustCompile("(?s)```yaml\n(spec_version:.*?)```").FindSubmatch(doc)
	if m == nil {
		t.Fatal("no complete room.yaml example (starting with spec_version) in ROOM_AUTHORING.md")
	}
	var v any
	if err := yaml.Unmarshal(m[1], &v); err != nil {
		t.Fatal(err)
	}
	l := &Loaded{Doc: v}
	js, err := l.JSON()
	if err != nil {
		t.Fatal(err)
	}
	inst, err := jsonschema.UnmarshalJSON(bytes.NewReader(js))
	if err != nil {
		t.Fatal(err)
	}
	s, err := CompileSchema(filepath.Join("..", "..", "docs", "schema", "room.schema.json"))
	if err != nil {
		t.Fatal(err)
	}
	if err := s.Validate(inst); err != nil {
		t.Fatalf("ROOM_AUTHORING.md example is invalid: %v", err)
	}
}
