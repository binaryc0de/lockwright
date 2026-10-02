package api

import (
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"testing"
)

func TestHealthAndVersion(t *testing.T) {
	srv := httptest.NewServer(NewHandler())
	defer srv.Close()

	for path, want := range map[string]map[string]string{
		"/healthz":     {"status": "ok"},
		"/api/version": {"platform": Version},
	} {
		resp, err := http.Get(srv.URL + path)
		if err != nil {
			t.Fatal(err)
		}
		var got map[string]string
		if err := json.NewDecoder(resp.Body).Decode(&got); err != nil {
			t.Fatal(err)
		}
		resp.Body.Close()
		if resp.StatusCode != http.StatusOK || got[keyOf(want)] != want[keyOf(want)] {
			t.Errorf("%s: status %d body %v, want %v", path, resp.StatusCode, got, want)
		}
	}

	resp, err := http.Post(srv.URL+"/healthz", "application/json", nil)
	if err != nil {
		t.Fatal(err)
	}
	resp.Body.Close()
	if resp.StatusCode != http.StatusMethodNotAllowed {
		t.Errorf("POST /healthz: got %d, want 405", resp.StatusCode)
	}
}

func keyOf(m map[string]string) string {
	for k := range m {
		return k
	}
	return ""
}
