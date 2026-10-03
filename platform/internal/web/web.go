// Package web serves the lobby site (M5, ADR-0028): the platform's front
// door. Plain HTML/CSS/JS embedded in the binary; it talks to the public
// API (/api/catalog, /api/sessions, /api/games/{code}, /api/status) and sends
// players into the browser client at /play/?code=...
package web

import (
	"embed"
	"io/fs"
	"net/http"
)

//go:embed site
var files embed.FS

// Register adds the lobby routes to mux: / (lobby), /g/{code} (a game's
// page) and /site/ (assets).
func Register(mux *http.ServeMux) {
	site, _ := fs.Sub(files, "site")
	page := func(name string) http.HandlerFunc {
		return func(w http.ResponseWriter, r *http.Request) {
			b, err := fs.ReadFile(site, name)
			if err != nil {
				http.NotFound(w, r)
				return
			}
			w.Header().Set("Content-Type", "text/html; charset=utf-8")
			w.Header().Set("Cache-Control", "no-cache")
			w.Header().Set("X-Content-Type-Options", "nosniff")
			w.Header().Set("Referrer-Policy", "same-origin")
			_, _ = w.Write(b)
		}
	}
	mux.HandleFunc("GET /{$}", page("index.html"))
	mux.HandleFunc("GET /g/{code}", page("game.html"))
	assets := http.StripPrefix("/site/", http.FileServer(http.FS(site)))
	mux.Handle("GET /site/", http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Cache-Control", "no-cache")
		w.Header().Set("X-Content-Type-Options", "nosniff")
		assets.ServeHTTP(w, r)
	}))
}
