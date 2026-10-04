package main

import (
	"encoding/base64"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"strings"
	"testing"
)

func TestNarrateWritesTheWavAndSkipsWhenUpToDate(t *testing.T) {
	wav := append([]byte("RIFF"), make([]byte, 60)...)
	calls := 0
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		calls++
		if r.Header.Get("x-goog-api-key") != "test-key" {
			t.Errorf("missing key header")
		}
		var body map[string]any
		_ = json.NewDecoder(r.Body).Decode(&body)
		if body["model"] != defaultModel || !strings.Contains(mustJSON(body), `"voice":"Sulafat"`) || !strings.Contains(mustJSON(body), "speech_metadata") {
			t.Errorf("request %s", mustJSON(body))
		}
		_ = json.NewEncoder(w).Encode(map[string]any{"steps": []any{map[string]any{"content": []any{map[string]any{"data": base64.StdEncoding.EncodeToString(wav)}}}}})
	}))
	defer srv.Close()
	t.Setenv("GEMINI_API_KEY", "test-key")
	dir := t.TempDir()
	os.WriteFile(filepath.Join(dir, "narration.json"), []byte(`{"voice":"Sulafat","style":"warm","text":"Mind the clocks."}`), 0o644)
	if err := run(dir, srv.URL, false); err != nil {
		t.Fatal(err)
	}
	got, _ := os.ReadFile(filepath.Join(dir, "narration.wav"))
	if string(got) != string(wav) {
		t.Fatalf("wav %d bytes", len(got))
	}
	if err := run(dir, srv.URL, false); err != nil || calls != 1 {
		t.Fatalf("up-to-date run called the API again (calls=%d, err=%v)", calls, err)
	}
}

func TestErrorsNeverEchoTheKey(t *testing.T) {
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		http.Error(w, `{"error":"quota"}`, http.StatusTooManyRequests)
	}))
	defer srv.Close()
	_, err := synthesize(srv.URL, "secret-key-value", Script{Voice: "Kore", Text: "x"})
	if err == nil || strings.Contains(err.Error(), "secret-key-value") || !strings.Contains(err.Error(), "429") {
		t.Fatalf("err = %v", err)
	}
}

func mustJSON(v any) string { b, _ := json.Marshal(v); return string(b) }
