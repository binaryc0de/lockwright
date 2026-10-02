// Command intranet is the Night Shift CTF challenge (PLAN.md Section 10):
// the Kestrel Logistics intranet. Players log in with credentials found in
// the room (B1, B2) and read other people's tickets by changing ?id= (an
// IDOR, B4). The maglock vendor's facilities ticket holds the per-session
// flag, read from the FLAG environment variable (never stored in the repo).
//
// Intentionally vulnerable: ticket access is not checked against the owner.
// Everything else (sessions, escaping) is done properly so the IDOR is the
// only way in.
package main

import (
	"crypto/hmac"
	"crypto/rand"
	"crypto/sha256"
	"crypto/subtle"
	"embed"
	"encoding/hex"
	"html/template"
	"log"
	"net/http"
	"os"
	"sort"
	"strconv"
	"strings"
	"time"
)

//go:embed templates/*.html
var templateFS embed.FS

// Credentials the room hands out: the sticky note's username and the guest
// WiFi card's reused password.
const (
	username = "mreyes"
	password = "Kestrel#2019"
)

// FlagTicketID is the facilities ticket holding the flag: two below the
// ticket mreyes is shown first (1042), so changing the id is enough.
const FlagTicketID = 1040

type ticket struct {
	ID       int
	Owner    string
	Team     string
	Title    string
	Status   string
	Opened   string
	Body     string
	HasToken bool // body is followed by the override token (the flag)
}

func tickets() map[int]ticket {
	list := []ticket{
		{1037, "jpatel", "Finance", "Expense portal times out", "Closed", "2026-09-14",
			"Portal times out when uploading receipts over 5 MB. Workaround: compress the PDF.", false},
		{1038, "dmorgan", "Security", "Night guard radio battery", "Open", "2026-09-21",
			"Handset 3 does not hold a charge past 02:00. Spare battery ordered.", false},
		{1039, "lchen", "Warehouse", "Label printer bay 4 jams", "Open", "2026-09-22",
			"Zebra printer in bay 4 jams on the second label. Rollers need cleaning.", false},
		{FlagTicketID, "facilities", "Facilities", "Server cage maglock - vendor override token", "Pending", "2026-09-30",
			"Vendor (SecureMag Ltd) has issued an emergency override token for the server cage maglock. " +
				"Paste it into the cage controller if the badge system is down. Do NOT share outside IT/Facilities.", true},
		{1041, username, "IT", "VPN certificate renewal", "Closed", "2026-09-29",
			"Renewed the site VPN certificate. Next renewal due September 2027.", false},
		{1042, username, "IT", "Core switch migration - night 2", "In progress", "2026-10-01",
			"Cutover at 23:30. Backup of core-sw taken. DNS moved. If the badge system flaps again, check the cage first.", false},
		{1043, "akhan", "HR", "New starter laptop", "Open", "2026-10-01",
			"Laptop for the new dispatcher, starting Monday. Standard image.", false},
	}
	out := map[int]ticket{}
	for _, t := range list {
		out[t.ID] = t
	}
	return out
}

type server struct {
	flag    string
	key     []byte
	tickets map[int]ticket
	tmpl    *template.Template
}

func newServer(flag string) *server {
	key := make([]byte, 32)
	if _, err := rand.Read(key); err != nil {
		log.Fatal(err)
	}
	return &server{
		flag:    flag,
		key:     key,
		tickets: tickets(),
		tmpl:    template.Must(template.ParseFS(templateFS, "templates/*.html")),
	}
}

func (s *server) routes() http.Handler {
	mux := http.NewServeMux()
	mux.HandleFunc("GET /healthz", func(w http.ResponseWriter, _ *http.Request) { w.Write([]byte("ok\n")) })
	mux.HandleFunc("GET /{$}", s.home)
	mux.HandleFunc("GET /login", s.loginForm)
	mux.HandleFunc("POST /login", s.login)
	mux.HandleFunc("POST /logout", s.logout)
	mux.HandleFunc("GET /tickets", s.authed(s.list))
	mux.HandleFunc("GET /tickets/view", s.authed(s.view))
	return securityHeaders(mux)
}

func securityHeaders(h http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("X-Content-Type-Options", "nosniff")
		w.Header().Set("Content-Security-Policy", "default-src 'self'; style-src 'unsafe-inline'")
		w.Header().Set("Cache-Control", "no-store")
		h.ServeHTTP(w, r)
	})
}

// --- sessions: an HMAC-signed cookie holding the user name -------------------

const cookieName = "kl_session"

func (s *server) sign(user string) string {
	m := hmac.New(sha256.New, s.key)
	m.Write([]byte(user))
	return user + "." + hex.EncodeToString(m.Sum(nil))
}

func (s *server) user(r *http.Request) string {
	c, err := r.Cookie(cookieName)
	if err != nil {
		return ""
	}
	user, _, ok := strings.Cut(c.Value, ".")
	if !ok || subtle.ConstantTimeCompare([]byte(s.sign(user)), []byte(c.Value)) != 1 {
		return ""
	}
	return user
}

func (s *server) authed(h func(http.ResponseWriter, *http.Request, string)) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		u := s.user(r)
		if u == "" {
			http.Redirect(w, r, "/login", http.StatusSeeOther)
			return
		}
		h(w, r, u)
	}
}

// --- pages ----------------------------------------------------------------------

func (s *server) home(w http.ResponseWriter, r *http.Request) {
	if s.user(r) != "" {
		http.Redirect(w, r, "/tickets", http.StatusSeeOther)
		return
	}
	http.Redirect(w, r, "/login", http.StatusSeeOther)
}

func (s *server) loginForm(w http.ResponseWriter, r *http.Request) {
	s.render(w, http.StatusOK, "login.html", map[string]any{"Expired": r.URL.Query().Has("expired")})
}

func (s *server) login(w http.ResponseWriter, r *http.Request) {
	u := strings.TrimSpace(r.FormValue("username"))
	p := r.FormValue("password")
	okUser := subtle.ConstantTimeCompare([]byte(u), []byte(username)) == 1
	okPass := subtle.ConstantTimeCompare([]byte(p), []byte(password)) == 1
	if !okUser || !okPass {
		time.Sleep(300 * time.Millisecond) // slow down guessing; brute force is not the intended path
		s.render(w, http.StatusUnauthorized, "login.html", map[string]any{"Error": "Invalid username or password.", "Username": u})
		return
	}
	http.SetCookie(w, &http.Cookie{Name: cookieName, Value: s.sign(username), Path: "/", HttpOnly: true, SameSite: http.SameSiteLaxMode})
	http.Redirect(w, r, "/tickets", http.StatusSeeOther)
}

func (s *server) logout(w http.ResponseWriter, r *http.Request) {
	http.SetCookie(w, &http.Cookie{Name: cookieName, Value: "", Path: "/", MaxAge: -1})
	http.Redirect(w, r, "/login", http.StatusSeeOther)
}

func (s *server) list(w http.ResponseWriter, _ *http.Request, user string) {
	var mine []ticket
	for _, t := range s.tickets {
		if t.Owner == user {
			mine = append(mine, t)
		}
	}
	sort.Slice(mine, func(i, j int) bool { return mine[i].ID > mine[j].ID })
	s.render(w, http.StatusOK, "list.html", map[string]any{"User": user, "Tickets": mine})
}

// view shows any ticket by id. THE VULNERABILITY: it never checks that the
// ticket belongs to the logged-in user.
func (s *server) view(w http.ResponseWriter, r *http.Request, user string) {
	id, err := strconv.Atoi(r.URL.Query().Get("id"))
	t, ok := s.tickets[id]
	if err != nil || !ok {
		s.render(w, http.StatusNotFound, "view.html", map[string]any{"User": user, "Missing": true})
		return
	}
	data := map[string]any{"User": user, "T": t}
	if t.HasToken {
		data["Token"] = s.flag
	}
	s.render(w, http.StatusOK, "view.html", data)
}

func (s *server) render(w http.ResponseWriter, status int, name string, data map[string]any) {
	w.Header().Set("Content-Type", "text/html; charset=utf-8")
	w.WriteHeader(status)
	if err := s.tmpl.ExecuteTemplate(w, name, data); err != nil {
		log.Printf("render %s: %v", name, err)
	}
}

func main() {
	flag := strings.TrimSpace(os.Getenv("FLAG"))
	if flag == "" {
		log.Fatal("FLAG is not set; the platform injects it per session")
	}
	addr := os.Getenv("ADDR")
	if addr == "" {
		addr = ":8080"
	}
	srv := &http.Server{Addr: addr, Handler: newServer(flag).routes(), ReadHeaderTimeout: 10 * time.Second}
	log.Printf("Kestrel intranet listening on %s", addr)
	log.Fatal(srv.ListenAndServe())
}
