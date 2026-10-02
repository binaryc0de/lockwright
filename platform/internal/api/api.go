// Package api serves the platform HTTP API (docs/API.md). M0 ships only the
// health and version endpoints; the session, flag, and challenge endpoints
// arrive in M3.
package api

import (
	"encoding/json"
	"net/http"
)

// Version is the platform API version reported to clients and room packs
// (room.yaml requires.platform is matched against it).
const Version = "0.1.0"

// NewHandler returns the platform's HTTP handler.
func NewHandler() http.Handler {
	mux := http.NewServeMux()
	mux.HandleFunc("GET /healthz", func(w http.ResponseWriter, _ *http.Request) {
		writeJSON(w, http.StatusOK, map[string]string{"status": "ok"})
	})
	mux.HandleFunc("GET /api/version", func(w http.ResponseWriter, _ *http.Request) {
		writeJSON(w, http.StatusOK, map[string]string{"platform": Version})
	})
	return mux
}

func writeJSON(w http.ResponseWriter, status int, v any) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(status)
	_ = json.NewEncoder(w).Encode(v)
}
