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
	"crypto/rand"
	"crypto/subtle"
	"embed"
	"encoding/hex"
	"errors"
	"html/template"
	"log"
	"net/http"
	"os"
	"regexp"
	"sort"
	"strconv"
	"strings"
	"sync"
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

// Account lockout (the room's IT password policy): after MaxFailures wrong
// passwords in a row for a username, that username is locked for LockFor.
// Applying the same lockout to every username keeps guessing impractical
// without revealing which usernames exist (ADR-0022).
const (
	MaxFailures    = 5
	LockFor        = 3 * time.Minute
	maxLockoutKeys = 1024
)

// prefixRe is what a proxy may put in X-Forwarded-Prefix: a plain path
// (the escapebox platform uses /ctf/<session>/<challenge>). Anything else is
// ignored, so the header cannot turn redirects into open redirects.
var prefixRe = regexp.MustCompile(`^(/[A-Za-z0-9_-]{1,64}){1,4}$`)

// base is the path prefix the app is served under ("" when served at /),
// from the proxy's X-Forwarded-Prefix (ADR-0029).
func base(r *http.Request) string {
	if p := strings.TrimSuffix(r.Header.Get("X-Forwarded-Prefix"), "/"); prefixRe.MatchString(p) {
		return p
	}
	return ""
}

// cookiePath scopes the session cookie to this app's prefix, so challenges of
// different games on one public host never see each other's logins.
func cookiePath(r *http.Request) string { return base(r) + "/" }

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

type lockoutEntry struct {
	failures    int
	lockedUntil time.Time
	lastSeen    time.Time
}

type sessionEntry struct {
	user    string
	expires time.Time
}

type server struct {
	flag    string
	tickets map[int]ticket
	tmpl    *template.Template

	mu             sync.Mutex
	lockouts       map[string]*lockoutEntry
	maxLockoutKeys int
	sessions       map[string]sessionEntry
	now            func() time.Time
}

func newServer(flag string) *server {
	return &server{
		flag:           flag,
		tickets:        tickets(),
		tmpl:           template.Must(template.ParseFS(templateFS, "templates/*.html")),
		lockouts:       map[string]*lockoutEntry{},
		maxLockoutKeys: maxLockoutKeys,
		sessions:       map[string]sessionEntry{},
		now:            time.Now,
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

const maxBodyBytes = 8 << 10

func securityHeaders(h http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		r.Body = http.MaxBytesReader(w, r.Body, maxBodyBytes)
		w.Header().Set("X-Content-Type-Options", "nosniff")
		w.Header().Set("Content-Security-Policy", "default-src 'self'; style-src 'unsafe-inline'")
		w.Header().Set("Cache-Control", "no-store")
		h.ServeHTTP(w, r)
	})
}

// --- sessions: server-side random session ids with expiry and revocation -----

const (
	cookieName  = "kl_session"
	sessionTTL  = 2 * time.Hour
	maxSessions = 256
)

func isHTTPS(r *http.Request) bool {
	return r.TLS != nil || strings.EqualFold(strings.TrimSpace(r.Header.Get("X-Forwarded-Proto")), "https")
}

func (s *server) newSession(user string) (string, error) {
	raw := make([]byte, 32)
	if _, err := rand.Read(raw); err != nil {
		return "", err
	}
	sid := hex.EncodeToString(raw)
	s.mu.Lock()
	defer s.mu.Unlock()
	now := s.now()
	for k, ent := range s.sessions {
		if !now.Before(ent.expires) {
			delete(s.sessions, k)
		}
	}
	if len(s.sessions) >= maxSessions {
		var oldestKey string
		var oldestExp time.Time
		first := true
		for k, ent := range s.sessions {
			if first || ent.expires.Before(oldestExp) {
				oldestKey = k
				oldestExp = ent.expires
				first = false
			}
		}
		if !first {
			delete(s.sessions, oldestKey)
		}
	}
	s.sessions[sid] = sessionEntry{user: user, expires: now.Add(sessionTTL)}
	return sid, nil
}

func (s *server) user(r *http.Request) string {
	c, err := r.Cookie(cookieName)
	if err != nil || c.Value == "" {
		return ""
	}
	s.mu.Lock()
	defer s.mu.Unlock()
	ent, ok := s.sessions[c.Value]
	if !ok {
		return ""
	}
	if !s.now().Before(ent.expires) {
		delete(s.sessions, c.Value)
		return ""
	}
	return ent.user
}

func (s *server) authed(h func(http.ResponseWriter, *http.Request, string)) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		u := s.user(r)
		if u == "" {
			http.Redirect(w, r, base(r)+"/login", http.StatusSeeOther)
			return
		}
		h(w, r, u)
	}
}

// --- pages ----------------------------------------------------------------------

func (s *server) home(w http.ResponseWriter, r *http.Request) {
	if s.user(r) != "" {
		http.Redirect(w, r, base(r)+"/tickets", http.StatusSeeOther)
		return
	}
	http.Redirect(w, r, base(r)+"/login", http.StatusSeeOther)
}

func (s *server) loginForm(w http.ResponseWriter, r *http.Request) {
	s.render(w, r, http.StatusOK, "login.html", map[string]any{"Expired": r.URL.Query().Has("expired")})
}

func (s *server) login(w http.ResponseWriter, r *http.Request) {
	if err := r.ParseForm(); err != nil {
		var mbe *http.MaxBytesError
		if errors.As(err, &mbe) {
			http.Error(w, "Request body too large.", http.StatusRequestEntityTooLarge)
			return
		}
		http.Error(w, "Bad request.", http.StatusBadRequest)
		return
	}
	u := strings.TrimSpace(r.PostFormValue("username"))
	p := r.PostFormValue("password")
	okUser := subtle.ConstantTimeCompare([]byte(u), []byte(username)) == 1
	okPass := subtle.ConstantTimeCompare([]byte(p), []byte(password)) == 1
	s.mu.Lock()
	now := s.now()
	s.sweepLockoutsLocked(now)
	st := s.lockouts[u]
	locked := st != nil && now.Before(st.lockedUntil)
	switch {
	case locked:
		st.lastSeen = now
	case okUser && okPass:
		delete(s.lockouts, u)
	default:
		if st == nil {
			s.evictLockoutIfFullLocked(now)
			st = &lockoutEntry{}
			s.lockouts[u] = st
		}
		st.lastSeen = now
		st.failures++
		if st.failures >= MaxFailures {
			st.failures = 0
			st.lockedUntil = now.Add(LockFor)
			locked = true
		}
	}
	s.mu.Unlock()
	if locked {
		time.Sleep(300 * time.Millisecond)
		s.render(w, r, http.StatusTooManyRequests, "login.html", map[string]any{
			"Error": "Account locked after too many failed sign-ins (IT policy). Try again in a few minutes.", "Username": u})
		return
	}
	if !okUser || !okPass {
		time.Sleep(300 * time.Millisecond) // slow down guessing; brute force is not the intended path
		s.render(w, r, http.StatusUnauthorized, "login.html", map[string]any{"Error": "Invalid username or password.", "Username": u})
		return
	}
	sid, err := s.newSession(username)
	if err != nil {
		http.Error(w, "Could not start session.", http.StatusInternalServerError)
		return
	}
	http.SetCookie(w, &http.Cookie{
		Name:     cookieName,
		Value:    sid,
		Path:     cookiePath(r),
		MaxAge:   int(sessionTTL.Seconds()),
		HttpOnly: true,
		SameSite: http.SameSiteLaxMode,
		Secure:   isHTTPS(r),
	})
	http.Redirect(w, r, base(r)+"/tickets", http.StatusSeeOther)
}

func (s *server) sweepLockoutsLocked(now time.Time) {
	for k, st := range s.lockouts {
		if !now.Before(st.lockedUntil) && (st.failures == 0 || now.Sub(st.lastSeen) >= LockFor) {
			delete(s.lockouts, k)
		}
	}
}

func (s *server) evictLockoutIfFullLocked(now time.Time) {
	capKeys := s.maxLockoutKeys
	if capKeys <= 0 {
		capKeys = maxLockoutKeys
	}
	if len(s.lockouts) < capKeys {
		return
	}
	// Prefer evicting an unlocked entry so spraying unknown names cannot clear
	// an active lockout; fall back to the oldest entry if all are locked.
	var victim string
	var victimLocked bool
	var victimTime time.Time
	first := true
	for k, st := range s.lockouts {
		isLocked := now.Before(st.lockedUntil)
		if first || (!isLocked && victimLocked) || (isLocked == victimLocked && st.lastSeen.Before(victimTime)) {
			victim = k
			victimLocked = isLocked
			victimTime = st.lastSeen
			first = false
		}
	}
	if !first {
		delete(s.lockouts, victim)
	}
}

func (s *server) logout(w http.ResponseWriter, r *http.Request) {
	if c, err := r.Cookie(cookieName); err == nil && c.Value != "" {
		s.mu.Lock()
		delete(s.sessions, c.Value)
		s.mu.Unlock()
	}
	http.SetCookie(w, &http.Cookie{
		Name:     cookieName,
		Value:    "",
		Path:     cookiePath(r),
		MaxAge:   -1,
		HttpOnly: true,
		SameSite: http.SameSiteLaxMode,
		Secure:   isHTTPS(r),
	})
	http.Redirect(w, r, base(r)+"/login", http.StatusSeeOther)
}

func (s *server) list(w http.ResponseWriter, r *http.Request, user string) {
	var mine []ticket
	for _, t := range s.tickets {
		if t.Owner == user {
			mine = append(mine, t)
		}
	}
	sort.Slice(mine, func(i, j int) bool { return mine[i].ID > mine[j].ID })
	s.render(w, r, http.StatusOK, "list.html", map[string]any{"User": user, "Tickets": mine})
}

// view shows any ticket by id. THE VULNERABILITY: it never checks that the
// ticket belongs to the logged-in user.
func (s *server) view(w http.ResponseWriter, r *http.Request, user string) {
	id, err := strconv.Atoi(r.URL.Query().Get("id"))
	t, ok := s.tickets[id]
	if err != nil || !ok {
		s.render(w, r, http.StatusNotFound, "view.html", map[string]any{"User": user, "Missing": true})
		return
	}
	data := map[string]any{"User": user, "T": t}
	if t.HasToken {
		data["Token"] = s.flag
	}
	s.render(w, r, http.StatusOK, "view.html", data)
}

func (s *server) render(w http.ResponseWriter, r *http.Request, status int, name string, data map[string]any) {
	data["Base"] = base(r)
	w.Header().Set("Content-Type", "text/html; charset=utf-8")
	w.WriteHeader(status)
	if err := s.tmpl.ExecuteTemplate(w, name, data); err != nil {
		log.Printf("render %s: %v", name, err)
	}
}

func newHTTPServer(addr string, h http.Handler) *http.Server {
	return &http.Server{
		Addr:              addr,
		Handler:           h,
		ReadHeaderTimeout: 5 * time.Second,
		ReadTimeout:       10 * time.Second,
		WriteTimeout:      15 * time.Second,
		IdleTimeout:       60 * time.Second,
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
	srv := newHTTPServer(addr, newServer(flag).routes())
	log.Printf("Kestrel intranet listening on %s", addr)
	log.Fatal(srv.ListenAndServe())
}
