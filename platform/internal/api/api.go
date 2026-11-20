// Package api serves the platform HTTP API (docs/API.md): public endpoints
// for game clients and /internal/* endpoints for game servers, which
// authenticate with their session's server token. Flag values are never
// logged, echoed or returned.
package api

import (
	"context"
	"crypto/subtle"
	"encoding/json"
	"errors"
	"fmt"
	"github.com/binaryc0de/lockwright/platform/internal/web"
	"io"
	"log/slog"
	"math"
	"mime"
	"net"
	"net/http"
	"net/http/httputil"
	"net/url"
	"os"
	"path/filepath"
	"regexp"
	"strconv"
	"strings"
	"sync"
	"time"

	"github.com/binaryc0de/lockwright/platform/internal/flags"
	"github.com/binaryc0de/lockwright/platform/internal/orchestrator"
	"github.com/binaryc0de/lockwright/platform/internal/rooms"
	"github.com/binaryc0de/lockwright/platform/internal/sessions"
	"github.com/binaryc0de/lockwright/platform/internal/store"
)

// Version is the platform API version reported to clients and room packs
// (room.yaml requires.platform is matched against it).
const Version = "0.1.0"

const (
	maxBody     = 64 << 10
	maxSnapshot = 4 << 20
)

// Orchestrator is the challenge runner (nil when Docker is unavailable).
type Orchestrator interface {
	Start(ctx context.Context, sessionID, roomID, roomVersion, roomDir string, chs []orchestrator.Challenge) (map[string]orchestrator.Handle, error)
	Stop(ctx context.Context, sessionID string) error
}

// GameServers starts game server processes (sessions.Manager).
type GameServers interface {
	EnsureRunning(ctx context.Context, sess store.Session) (int, error)
	Transport() string
	// Port is the running game server's port for a session (0 if none).
	Port(sessionID string) int
}

// Deps are the API's collaborators.
type Deps struct {
	Store         *store.Store
	Rooms         *rooms.Catalog
	Servers       GameServers
	Orchestrator  Orchestrator // may be nil
	Limiter       *flags.Limiter
	Secret        []byte // platform secret for per-instance flags
	AdvertiseHost string // host players' clients connect to
	// WebDir, if set, holds the exported browser client (index.html, .wasm,
	// .pck); it is served at /play/ on the API's own origin (ADR-0023).
	WebDir string
	// PacksDir, if set, holds room packs built by tools/packroom
	// (<room>-<version>.pck plus its .json entry). The catalog lists each
	// room's pack and /download/packs/{file} serves it (ADR-0025).
	PacksDir string
	// MediaDir, if set, holds per-room intro videos (media/rooms/<id>/intro.mp4
	// and poster.jpg, tools/trailer/build.sh): the catalog and game API list
	// them and /media/rooms/{room}/{file} serves them.
	MediaDir string
	// MaxGames caps sessions that are not finished (0 = no cap); creating
	// more answers 503 games_full. Every game holds a game server and its
	// challenge containers, so the host sets this to what it can carry.
	MaxGames int
	// CreateLimit limits how often one client may create games (nil = none).
	CreateLimit *RateLimit
	// JoinLimit limits joins and game lookups by code per client, so codes
	// cannot be guessed by brute force when the site is public (nil = none).
	JoinLimit *RateLimit
	// PublicURL is the HTTPS origin players use (Tailscale serve/Funnel, a
	// cloud load balancer). When set, challenge cards point at this
	// platform's /ctf/ proxy instead of per-challenge ports (ADR-0029).
	PublicURL string
}

const defaultMaxRateLimitKeys = 4096

// RateLimit allows Max events per Window per key (in memory). Expired keys are
// swept periodically and the table is capped at MaxKeys (default 4096).
type RateLimit struct {
	Max       int
	Window    time.Duration
	MaxKeys   int
	mu        sync.Mutex
	seen      map[string][]time.Time
	lastSweep time.Time
	now       func() time.Time
}

// Allow records an event for key and reports whether it is within the limit.
func (l *RateLimit) Allow(key string) bool {
	l.mu.Lock()
	defer l.mu.Unlock()
	if l.seen == nil {
		l.seen = map[string][]time.Time{}
	}
	now := time.Now()
	if l.now != nil {
		now = l.now()
	}
	if l.lastSweep.IsZero() {
		l.lastSweep = now
	} else if l.Window > 0 && now.Sub(l.lastSweep) >= l.Window {
		l.sweepLocked(now)
	}
	keep := l.seen[key][:0]
	for _, t := range l.seen[key] {
		if now.Sub(t) < l.Window {
			keep = append(keep, t)
		}
	}
	if len(keep) >= l.Max {
		if len(keep) == 0 {
			delete(l.seen, key)
		} else {
			l.seen[key] = keep
		}
		return false
	}
	maxKeys := l.MaxKeys
	if maxKeys <= 0 {
		maxKeys = defaultMaxRateLimitKeys
	}
	if _, exists := l.seen[key]; !exists && len(l.seen) >= maxKeys {
		l.sweepLocked(now)
		if len(l.seen) >= maxKeys {
			l.evictOldestLocked()
		}
	}
	l.seen[key] = append(keep, now)
	return true
}

func (l *RateLimit) sweepLocked(now time.Time) {
	l.lastSweep = now
	for k, ts := range l.seen {
		keep := ts[:0]
		for _, t := range ts {
			if now.Sub(t) < l.Window {
				keep = append(keep, t)
			}
		}
		if len(keep) == 0 {
			delete(l.seen, k)
		} else {
			l.seen[k] = keep
		}
	}
}

func (l *RateLimit) evictOldestLocked() {
	var oldestKey string
	var oldestTime time.Time
	first := true
	for k, ts := range l.seen {
		var latest time.Time
		if len(ts) > 0 {
			latest = ts[len(ts)-1]
		}
		if first || latest.Before(oldestTime) {
			oldestKey = k
			oldestTime = latest
			first = false
		}
	}
	if !first {
		delete(l.seen, oldestKey)
	}
}

func isLoopbackAddr(remoteAddr string) bool {
	host, _, err := net.SplitHostPort(remoteAddr)
	if err != nil {
		host = remoteAddr
	}
	ip := net.ParseIP(host)
	return ip != nil && ip.IsLoopback()
}

// clientKey identifies the caller for rate limiting: when the connection came
// from a local reverse proxy (Tailscale Serve/Funnel, Caddy), use the rightmost
// X-Forwarded-For entry (the one the trusted local proxy appended) so callers
// cannot spoof the key by prepending fake addresses; otherwise use RemoteAddr.
func clientKey(r *http.Request) string {
	host, _, err := net.SplitHostPort(r.RemoteAddr)
	if err != nil {
		host = r.RemoteAddr
	}
	if ip := net.ParseIP(host); ip != nil && ip.IsLoopback() {
		vals := r.Header.Values("X-Forwarded-For")
		for i := len(vals) - 1; i >= 0; i-- {
			parts := strings.Split(vals[i], ",")
			for j := len(parts) - 1; j >= 0; j-- {
				if xff := strings.TrimSpace(parts[j]); xff != "" {
					return xff
				}
			}
		}
	}
	return host
}

// NewHandler returns the platform's HTTP handler. d may be nil (health and
// version only), which is what M0 tests use.
func NewHandler(d *Deps) http.Handler {
	mux := http.NewServeMux()
	mux.HandleFunc("GET /healthz", func(w http.ResponseWriter, _ *http.Request) {
		writeJSON(w, http.StatusOK, map[string]string{"status": "ok"})
	})
	mux.HandleFunc("GET /api/version", func(w http.ResponseWriter, _ *http.Request) {
		writeJSON(w, http.StatusOK, map[string]string{"platform": Version})
	})
	if d == nil {
		return mux
	}
	if d.Limiter == nil {
		d.Limiter = flags.NewLimiter()
	}
	a := &app{d: d}
	if d.WebDir != "" {
		mux.Handle("GET /play/", webClient(d.WebDir))
	}
	web.Register(mux)
	mux.HandleFunc("GET /api/catalog", a.catalog)
	if d.Servers != nil {
		mux.HandleFunc("GET /ws/{session}", a.wsProxy)
	}
	if d.PacksDir != "" {
		mux.HandleFunc("GET /download/packs/{file}", a.downloadPack)
	}
	if d.MediaDir != "" {
		mux.HandleFunc("GET /media/rooms/{room}/{file}", a.media)
	}
	mux.HandleFunc("POST /api/sessions", a.createSession)
	mux.HandleFunc("GET /api/sessions/{id}", a.getSession)
	mux.HandleFunc("GET /api/games/{code}", a.limitJoins(a.getGame))
	mux.HandleFunc("/ctf/{session}/{challenge}/{rest...}", a.ctfProxy)
	mux.HandleFunc("/ctf/{session}/{challenge}", func(w http.ResponseWriter, r *http.Request) {
		http.Redirect(w, r, r.URL.Path+"/", http.StatusMovedPermanently)
	})
	mux.HandleFunc("GET /api/status", a.status)
	mux.HandleFunc("POST /api/sessions/{id}/join", a.limitJoins(a.join))
	mux.HandleFunc("POST /api/join", a.limitJoins(a.joinByCode))
	mux.HandleFunc("POST /internal/sessions/{id}/verify", a.internal(a.verify))
	mux.HandleFunc("GET /internal/sessions/{id}/snapshot", a.internal(a.getSnapshot))
	mux.HandleFunc("PUT /internal/sessions/{id}/snapshot", a.internal(a.putSnapshot))
	mux.HandleFunc("POST /internal/sessions/{id}/events", a.internal(a.events))
	mux.HandleFunc("POST /internal/sessions/{id}/flags", a.internal(a.flag))
	mux.HandleFunc("POST /internal/sessions/{id}/challenges/start", a.internal(a.startChallenges))
	mux.HandleFunc("POST /internal/sessions/{id}/challenges/stop", a.internal(a.stopChallenges))
	mux.HandleFunc("POST /internal/sessions/{id}/finished", a.internal(a.finished))
	return mux
}

type app struct {
	d *Deps
	// slots serialises the cap check with the action that takes the slot
	// (creating a game, resuming one), so simultaneous requests cannot
	// overshoot -max-games.
	slots sync.Mutex
}

// --- public ---------------------------------------------------------------

func (a *app) catalog(w http.ResponseWriter, _ *http.Request) {
	type entry struct {
		RoomID          string             `json:"room_id"`
		Title           string             `json:"title"`
		Version         string             `json:"version"`
		DurationMinutes int                `json:"duration_minutes"`
		Players         [2]int             `json:"players"`
		Challenges      int                `json:"challenges"`
		Difficulties    []rooms.Difficulty `json:"difficulties"`
		Pack            *packInfo          `json:"pack,omitempty"`
		Summary         string             `json:"summary"`
		Intro           *introInfo         `json:"intro,omitempty"`
	}
	out := []entry{}
	for _, r := range a.d.Rooms.All() {
		ds := r.Difficulties
		if ds == nil {
			ds = []rooms.Difficulty{}
		}
		out = append(out, entry{r.ID, r.Title, r.Version, r.Mode.DurationMinutes, [2]int{r.Mode.Players.Min, r.Mode.Players.Max}, len(r.CTF.Challenges), ds, a.pack(r), r.Summary, a.intro(r.ID)})
	}
	writeJSON(w, http.StatusOK, out)
}

func (a *app) createSession(w http.ResponseWriter, r *http.Request) {
	var in struct {
		RoomID     string `json:"room_id"`
		Difficulty string `json:"difficulty"`
	}
	if !readJSON(w, r, &in, maxBody) {
		return
	}
	room, ok := a.d.Rooms.Room(in.RoomID)
	if !ok {
		writeErr(w, http.StatusNotFound, "unknown_room", "No such room is installed.")
		return
	}
	if a.d.CreateLimit != nil && !a.d.CreateLimit.Allow(clientKey(r)) {
		writeErr(w, http.StatusTooManyRequests, "too_many_games", "You have started a lot of games just now. Wait a few minutes and try again.")
		return
	}
	a.slots.Lock()
	defer a.slots.Unlock()
	if a.d.MaxGames > 0 {
		n, err := a.d.Store.CountActive(r.Context())
		if err != nil {
			internalErr(w, err)
			return
		}
		if n >= a.d.MaxGames {
			writeErr(w, http.StatusServiceUnavailable, "games_full", fmt.Sprintf("All %d game slots are in use. Try again when a game finishes.", a.d.MaxGames))
			return
		}
	}
	if !room.HasDifficulty(in.Difficulty) {
		writeErr(w, http.StatusBadRequest, "unknown_difficulty", "The room has no such difficulty.")
		return
	}
	sess, err := a.d.Store.CreateSessionWithDifficulty(r.Context(), in.RoomID, in.Difficulty)
	if err != nil {
		internalErr(w, err)
		return
	}
	slog.Info("session created", "session", sess.ID, "room", sess.RoomID, "difficulty", sess.Difficulty)
	writeJSON(w, http.StatusCreated, map[string]string{"session_id": sess.ID, "invite_code": sess.InviteCode})
}

func (a *app) getSession(w http.ResponseWriter, r *http.Request) {
	sess, ok := a.session(w, r)
	if !ok {
		return
	}
	players, err := a.d.Store.Players(r.Context(), sess.ID)
	if err != nil {
		internalErr(w, err)
		return
	}
	if players == nil {
		players = []string{}
	}
	room, _ := a.d.Rooms.Room(sess.RoomID)
	writeJSON(w, http.StatusOK, map[string]any{
		"session_id": sess.ID, "room_id": sess.RoomID, "status": sess.Status, "players": players,
		"created_at": sess.CreatedAt.Unix(), "duration_minutes": room.Mode.DurationMinutes,
		"won": sess.Won, "elapsed_s": sess.ElapsedS, "hints_used": sess.HintsUsed,
	})
}

type joinRequest struct {
	DisplayName string `json:"display_name"`
	InviteCode  string `json:"invite_code"`
}

// joinByCode is join for players who only have the code the host read out.
func (a *app) joinByCode(w http.ResponseWriter, r *http.Request) {
	var in joinRequest
	if !readJSON(w, r, &in, maxBody) {
		return
	}
	sess, err := a.d.Store.SessionByInvite(r.Context(), in.InviteCode)
	if errors.Is(err, store.ErrNotFound) {
		writeErr(w, http.StatusNotFound, "bad_invite", "No game uses that join code.")
		return
	}
	if err != nil {
		internalErr(w, err)
		return
	}
	a.admit(w, r, sess, in)
}

func (a *app) join(w http.ResponseWriter, r *http.Request) {
	sess, ok := a.session(w, r)
	if !ok {
		return
	}
	var in joinRequest
	if !readJSON(w, r, &in, maxBody) {
		return
	}
	a.admit(w, r, sess, in)
}

func (a *app) admit(w http.ResponseWriter, r *http.Request, sess store.Session, in joinRequest) {
	name := strings.TrimSpace(in.DisplayName)
	if name == "" || len([]rune(name)) > 24 {
		writeErr(w, http.StatusBadRequest, "bad_name", "Pick a display name of 1-24 characters.")
		return
	}
	code := strings.ToUpper(strings.TrimSpace(in.InviteCode))
	if subtle.ConstantTimeCompare([]byte(code), []byte(sess.InviteCode)) != 1 {
		writeErr(w, http.StatusForbidden, "bad_invite", "That invite code is not for this session.")
		return
	}
	if sess.Expired {
		writeErr(w, http.StatusGone, "game_expired", "This game expired. Start a new one from the lobby.")
		return
	}
	// Resuming a game that holds no slot (its players left, or the platform
	// restarted) needs a free one, like starting a new game.
	if a.d.MaxGames > 0 && sess.Status != store.StatusFinished && a.d.Servers.Port(sess.ID) == 0 {
		a.slots.Lock()
		defer a.slots.Unlock()
		holds, err := a.d.Store.HoldsSlot(r.Context(), sess)
		if err != nil {
			internalErr(w, err)
			return
		}
		if !holds {
			n, err := a.d.Store.CountActive(r.Context())
			if err != nil {
				internalErr(w, err)
				return
			}
			if n >= a.d.MaxGames {
				writeErr(w, http.StatusServiceUnavailable, "games_full", fmt.Sprintf("All %d game slots are in use; this game resumes when one frees up.", a.d.MaxGames))
				return
			}
		}
	}
	token, _, err := a.d.Store.MintJoinToken(r.Context(), sess.ID, name)
	if err != nil {
		internalErr(w, err)
		return
	}
	port, err := a.d.Servers.EnsureRunning(r.Context(), sess)
	if err != nil {
		slog.Error("cannot start game server", "session", sess.ID, "err", err)
		writeErr(w, http.StatusServiceUnavailable, "server_unavailable", "The game server could not start. Try again in a moment.")
		return
	}
	writeJSON(w, http.StatusOK, map[string]any{"session_id": sess.ID, "room_id": sess.RoomID, "host": a.d.AdvertiseHost, "port": port, "transport": a.d.Servers.Transport(), "join_token": token,
		"ws_path": "/ws/" + sess.ID})
}

// --- internal (game server -> platform) -------------------------------------

type internalHandler func(w http.ResponseWriter, r *http.Request, sess store.Session)

// internal authenticates a game server with its session's server token.
func (a *app) internal(h internalHandler) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		// Game servers call the platform directly on this host. Requests that
		// came through a proxy or tunnel (Funnel, serve, a load balancer) never
		// reach internal endpoints, whatever token they carry.
		if !directLocal(r) {
			writeErr(w, http.StatusForbidden, "internal_only", "Internal endpoint.")
			return
		}
		sess, err := a.d.Store.Session(r.Context(), r.PathValue("id"))
		got, hasBearer := strings.CutPrefix(r.Header.Get("Authorization"), "Bearer ")
		if err != nil || !hasBearer || subtle.ConstantTimeCompare([]byte(got), []byte(sess.ServerToken)) != 1 {
			writeErr(w, http.StatusUnauthorized, "unauthorized", "Bad server token.")
			return
		}
		h(w, r, sess)
	}
}

func (a *app) verify(w http.ResponseWriter, r *http.Request, sess store.Session) {
	var in struct {
		JoinToken string `json:"join_token"`
	}
	if !readJSON(w, r, &in, maxBody) {
		return
	}
	pid, name, err := a.d.Store.ConsumeJoinToken(r.Context(), sess.ID, in.JoinToken)
	if errors.Is(err, store.ErrTokenInvalid) {
		writeErr(w, http.StatusForbidden, "bad_token", "Join token is invalid, used or expired.")
		return
	}
	if err != nil {
		internalErr(w, err)
		return
	}
	writeJSON(w, http.StatusOK, map[string]string{"player_id": pid, "display_name": name})
}

func (a *app) getSnapshot(w http.ResponseWriter, r *http.Request, sess store.Session) {
	b, err := a.d.Store.Snapshot(r.Context(), sess.ID)
	if errors.Is(err, store.ErrNotFound) {
		writeErr(w, http.StatusNotFound, "no_snapshot", "Fresh session.")
		return
	}
	if err != nil {
		internalErr(w, err)
		return
	}
	w.Header().Set("Content-Type", "application/json")
	w.Write(b)
}

func (a *app) putSnapshot(w http.ResponseWriter, r *http.Request, sess store.Session) {
	if !requireJSON(w, r) {
		return
	}
	b, err := io.ReadAll(http.MaxBytesReader(w, r.Body, maxSnapshot))
	if err != nil {
		writeErr(w, http.StatusRequestEntityTooLarge, "too_large", "Snapshot too large.")
		return
	}
	if !json.Valid(b) {
		writeErr(w, http.StatusBadRequest, "bad_json", "Snapshot is not JSON.")
		return
	}
	if err := a.d.Store.PutSnapshot(r.Context(), sess.ID, b); err != nil {
		internalErr(w, err)
		return
	}
	w.WriteHeader(http.StatusNoContent)
}

func (a *app) events(w http.ResponseWriter, r *http.Request, sess store.Session) {
	var in []struct {
		At       float64         `json:"at"`
		Kind     string          `json:"kind"`
		PlayerID string          `json:"player_id"`
		Data     json.RawMessage `json:"data"`
	}
	if !readJSON(w, r, &in, maxBody) {
		return
	}
	evs := make([]store.Event, 0, len(in))
	for _, e := range in {
		if e.Kind == "" {
			writeErr(w, http.StatusBadRequest, "bad_event", "Every event needs a kind.")
			return
		}
		data := string(e.Data)
		if data == "" || data == "null" {
			data = "{}"
		}
		evs = append(evs, store.Event{At: e.At, Kind: e.Kind, PlayerID: e.PlayerID, Data: data})
	}
	if err := a.d.Store.AppendEvents(r.Context(), sess.ID, evs); err != nil {
		internalErr(w, err)
		return
	}
	w.WriteHeader(http.StatusNoContent)
}

// flag checks a submission (PLAN.md 7.5). The value is used once and dropped.
func (a *app) flag(w http.ResponseWriter, r *http.Request, sess store.Session) {
	var in struct {
		ChallengeID string `json:"challenge_id"`
		Value       string `json:"value"`
		PlayerID    string `json:"player_id"`
	}
	if !readJSON(w, r, &in, maxBody) {
		return
	}
	room, _ := a.d.Rooms.Room(sess.RoomID)
	ch, ok := room.Challenge(in.ChallengeID)
	if !ok {
		writeErr(w, http.StatusNotFound, "unknown_challenge", "No such challenge in this room.")
		return
	}
	key := sess.ID + "/" + ch.ID
	allowed, wait, finish := a.d.Limiter.Reserve(key)
	if !allowed {
		writeJSON(w, http.StatusTooManyRequests, map[string]any{"accepted": false, "retry_after_s": seconds(wait)})
		return
	}
	committed := false
	defer func() {
		if !committed {
			finish(true)
		}
	}()
	accepted, err := flags.Check(ch.Flag, a.d.Secret, sess.ID, ch.ID, in.Value)
	if err != nil {
		internalErr(w, err)
		return
	}
	in.Value = ""
	if err := a.d.Store.RecordFlagAttempt(r.Context(), sess.ID, ch.ID, in.PlayerID, accepted); err != nil {
		internalErr(w, err)
		return
	}
	committed = true
	cool := finish(accepted)
	slog.Info("flag attempt", "session", sess.ID, "challenge", ch.ID, "player", in.PlayerID, "accepted", accepted)
	out := map[string]any{"accepted": accepted}
	if !accepted && cool > 0 {
		out["retry_after_s"] = seconds(cool)
	}
	writeJSON(w, http.StatusOK, out)
}

func (a *app) startChallenges(w http.ResponseWriter, r *http.Request, sess store.Session) {
	room, _ := a.d.Rooms.Room(sess.RoomID)
	if len(room.CTF.Challenges) == 0 {
		writeJSON(w, http.StatusOK, map[string]any{"handles": map[string]any{}})
		return
	}
	if a.d.Orchestrator == nil {
		writeErr(w, http.StatusServiceUnavailable, "docker_unavailable", "This platform cannot run challenge containers (Docker is not reachable).")
		return
	}
	ctx, cancel := context.WithTimeout(r.Context(), 10*time.Minute) // first run builds images
	defer cancel()
	hs, err := a.d.Orchestrator.Start(ctx, sess.ID, room.ID, room.Version, room.Dir, room.CTF.Challenges)
	if err != nil {
		slog.Error("challenge start failed", "session", sess.ID, "err", err)
		writeErr(w, http.StatusBadGateway, "challenge_failed", "The challenge could not start.")
		return
	}
	if a.d.PublicURL != "" {
		out := make(map[string]orchestrator.Handle, len(hs))
		for id, h := range hs {
			if h.URL != "" {
				h.URL = strings.TrimSuffix(a.d.PublicURL, "/") + "/ctf/" + sess.ID + "/" + id + "/"
				h.Host = ""
				h.Port = 0
			}
			out[id] = h
		}
		hs = out
	}
	writeJSON(w, http.StatusOK, map[string]any{"handles": hs})
}

func (a *app) stopChallenges(w http.ResponseWriter, r *http.Request, sess store.Session) {
	if a.d.Orchestrator != nil {
		if err := a.d.Orchestrator.Stop(r.Context(), sess.ID); err != nil {
			internalErr(w, err)
			return
		}
	}
	w.WriteHeader(http.StatusNoContent)
}

func (a *app) finished(w http.ResponseWriter, r *http.Request, sess store.Session) {
	var in struct {
		Win       bool `json:"win"`
		ElapsedS  int  `json:"elapsed_s"`
		HintsUsed int  `json:"hints_used"`
	}
	if !readJSON(w, r, &in, maxBody) {
		return
	}
	if err := a.d.Store.Finish(r.Context(), sess.ID, in.Win, in.ElapsedS, in.HintsUsed); err != nil {
		internalErr(w, err)
		return
	}
	a.d.Limiter.ForgetSession(sess.ID)
	if a.d.Orchestrator != nil {
		go func() {
			ctx, cancel := context.WithTimeout(context.Background(), time.Minute)
			defer cancel()
			if err := a.d.Orchestrator.Stop(ctx, sess.ID); err != nil {
				slog.Warn("challenge teardown", "session", sess.ID, "err", err)
			}
		}()
	}
	w.WriteHeader(http.StatusNoContent)
}

// --- helpers ------------------------------------------------------------------

func (a *app) session(w http.ResponseWriter, r *http.Request) (store.Session, bool) {
	sess, err := a.d.Store.Session(r.Context(), r.PathValue("id"))
	if errors.Is(err, store.ErrNotFound) {
		writeErr(w, http.StatusNotFound, "unknown_session", "No such session.")
		return store.Session{}, false
	}
	if err != nil {
		internalErr(w, err)
		return store.Session{}, false
	}
	return sess, true
}

func requireJSON(w http.ResponseWriter, r *http.Request) bool {
	mt, _, err := mime.ParseMediaType(r.Header.Get("Content-Type"))
	if err != nil || mt != "application/json" {
		writeErr(w, http.StatusUnsupportedMediaType, "unsupported_media_type", "Content-Type must be application/json.")
		return false
	}
	return true
}

func readJSON(w http.ResponseWriter, r *http.Request, v any, limit int64) bool {
	if !requireJSON(w, r) {
		return false
	}
	dec := json.NewDecoder(http.MaxBytesReader(w, r.Body, limit))
	dec.DisallowUnknownFields()
	if err := dec.Decode(v); err != nil {
		writeErr(w, http.StatusBadRequest, "bad_json", "Request body is not the expected JSON.")
		return false
	}
	return true
}

func seconds(d time.Duration) int { return int(math.Ceil(d.Seconds())) }

func writeJSON(w http.ResponseWriter, status int, v any) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(status)
	_ = json.NewEncoder(w).Encode(v)
}

func writeErr(w http.ResponseWriter, status int, code, msg string) {
	writeJSON(w, status, map[string]string{"error": code, "message": msg})
}

func internalErr(w http.ResponseWriter, err error) {
	slog.Error("request failed", "err", err)
	writeErr(w, http.StatusInternalServerError, "internal", "Something went wrong on the platform.")
}

// Compile-time check that sessions.Manager satisfies GameServers.
var _ GameServers = (*sessions.Manager)(nil)

// webClient serves the exported browser client. index.html is never cached
// (it names the current build); the large .wasm/.pck files are revalidated.
// A precompressed <file>.gz next to a file (tools/export.sh) is sent instead
// to browsers that accept gzip (ADR-0024).
func webClient(dir string) http.Handler {
	files := http.StripPrefix("/play/", http.FileServer(http.Dir(dir)))
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if strings.HasSuffix(r.URL.Path, "/") || strings.HasSuffix(r.URL.Path, ".html") {
			w.Header().Set("Cache-Control", "no-store")
		} else {
			w.Header().Set("Cache-Control", "no-cache")
		}
		w.Header().Add("Vary", "Accept-Encoding")
		rel := strings.TrimPrefix(r.URL.Path, "/play/")
		if rel != "" && !strings.HasSuffix(rel, "/") && strings.Contains(r.Header.Get("Accept-Encoding"), "gzip") {
			clean := filepath.Clean("/" + rel)
			gz := filepath.Join(dir, filepath.FromSlash(clean)+".gz")
			if f, err := os.Open(gz); err == nil {
				defer f.Close()
				if st, err := f.Stat(); err == nil && !st.IsDir() {
					ct := mime.TypeByExtension(filepath.Ext(clean))
					if ct == "" {
						ct = "application/octet-stream"
					}
					w.Header().Set("Content-Type", ct)
					w.Header().Set("Content-Encoding", "gzip")
					http.ServeContent(w, r, "", st.ModTime(), f)
					return
				}
			}
		}
		files.ServeHTTP(w, r)
	})
}

// introInfo is a room's intro video as the site shows it.
type introInfo struct {
	Video  string `json:"video"`
	Poster string `json:"poster,omitempty"`
}

// mediaFiles are the only files /media/rooms/{room}/ serves.
var mediaFiles = map[string]string{"intro.mp4": "video/mp4", "poster.jpg": "image/jpeg"}

// intro lists a room's intro video, if one has been built.
func (a *app) intro(roomID string) *introInfo {
	if a.d.MediaDir == "" {
		return nil
	}
	dir := filepath.Join(a.d.MediaDir, "rooms", roomID)
	if st, err := os.Stat(filepath.Join(dir, "intro.mp4")); err != nil || st.Size() == 0 {
		return nil
	}
	in := &introInfo{Video: "/media/rooms/" + roomID + "/intro.mp4"}
	if _, err := os.Stat(filepath.Join(dir, "poster.jpg")); err == nil {
		in.Poster = "/media/rooms/" + roomID + "/poster.jpg"
	}
	return in
}

// media serves a catalog room's intro video and poster (ranges allowed, so
// browsers can seek).
func (a *app) media(w http.ResponseWriter, r *http.Request) {
	room, file := r.PathValue("room"), r.PathValue("file")
	ct, ok := mediaFiles[file]
	if _, listed := a.d.Rooms.Room(room); !ok || !listed {
		writeErr(w, http.StatusNotFound, "not_found", "No such file.")
		return
	}
	w.Header().Set("Content-Type", ct)
	w.Header().Set("Cache-Control", "no-cache")
	http.ServeFile(w, r, filepath.Join(a.d.MediaDir, "rooms", room, file))
}

// packInfo is a room pack as clients download it.
type packInfo struct {
	File   string `json:"file"`
	SHA256 string `json:"sha256"`
	Size   int64  `json:"size"`
	URL    string `json:"url"`
	// Mobile is the same room with phone/tablet textures (ADR-0038), when built.
	Mobile *packInfo `json:"mobile,omitempty"`
}

var packFileRe = regexp.MustCompile(`^[a-z0-9_]+-[0-9]+\.[0-9]+\.[0-9]+(-[0-9A-Za-z.-]+)?\.pck$`)

// pack reads the packroom entry for the room's current version, if built.
func (a *app) pack(r rooms.Room) *packInfo {
	if a.d.PacksDir == "" {
		return nil
	}
	b, err := os.ReadFile(filepath.Join(a.d.PacksDir, r.ID+"-"+r.Version+".json"))
	if err != nil {
		return nil
	}
	type variant struct {
		File   string `json:"pack_file"`
		SHA256 string `json:"sha256"`
		Size   int64  `json:"size"`
	}
	var e struct {
		variant
		Mobile *variant `json:"mobile"`
	}
	if json.Unmarshal(b, &e) != nil {
		return nil
	}
	info := func(v variant) *packInfo {
		if !packFileRe.MatchString(v.File) {
			return nil
		}
		if st, err := os.Stat(filepath.Join(a.d.PacksDir, v.File)); err != nil || st.Size() != v.Size {
			return nil // entry and pack disagree: rebuild with tools/packroom
		}
		return &packInfo{File: v.File, SHA256: v.SHA256, Size: v.Size, URL: "/download/packs/" + v.File}
	}
	p := info(e.variant)
	if p != nil && e.Mobile != nil {
		p.Mobile = info(*e.Mobile)
	}
	return p
}

// offersPack reports whether file is the current pack of a catalog room, so
// packs of draft rooms (ADR-0030) and stale versions are not served.
func (a *app) offersPack(file string) bool {
	for _, room := range a.d.Rooms.All() {
		if p := a.pack(room); p != nil && (p.File == file || p.Mobile != nil && p.Mobile.File == file) {
			return true
		}
	}
	return false
}

func (a *app) downloadPack(w http.ResponseWriter, r *http.Request) {
	name := r.PathValue("file")
	if !packFileRe.MatchString(name) || !a.offersPack(name) {
		writeErr(w, http.StatusNotFound, "not_found", "No such pack.")
		return
	}
	w.Header().Set("Content-Type", "application/octet-stream")
	w.Header().Set("Cache-Control", "no-cache")
	w.Header().Add("Vary", "Accept-Encoding")
	path := filepath.Join(a.d.PacksDir, name)
	// A fresh precompressed copy (tools/packroom) goes to clients that accept
	// gzip; they verify the SHA-256 of the decompressed pack.
	if strings.Contains(r.Header.Get("Accept-Encoding"), "gzip") {
		if pst, err := os.Stat(path); err == nil {
			if f, err := os.Open(path + ".gz"); err == nil {
				defer f.Close()
				if gst, err := f.Stat(); err == nil && !gst.ModTime().Before(pst.ModTime()) {
					// A whole response with its length: http.ServeContent drops
					// Content-Length once Content-Encoding is set, and desktop
					// clients measure download progress against it.
					w.Header().Set("Content-Encoding", "gzip")
					w.Header().Set("Content-Length", strconv.FormatInt(gst.Size(), 10))
					w.WriteHeader(http.StatusOK)
					if r.Method != http.MethodHead {
						_, _ = io.Copy(w, f)
					}
					return
				}
			}
		}
	}
	http.ServeFile(w, r, path)
}

// wsProxy forwards a WebSocket to the session's game server (ADR-0026).
// Browsers on an HTTPS page may only open wss:// on the page's own origin, so
// they reach every game through this one TLS endpoint instead of per-game
// ports. The game server still checks the join token.
func (a *app) wsProxy(w http.ResponseWriter, r *http.Request) {
	port := a.d.Servers.Port(r.PathValue("session"))
	if port == 0 || !strings.EqualFold(r.Header.Get("Upgrade"), "websocket") {
		writeErr(w, http.StatusNotFound, "not_found", "No running game for this session.")
		return
	}
	target := &url.URL{Scheme: "http", Host: net.JoinHostPort("127.0.0.1", strconv.Itoa(port))}
	p := httputil.NewSingleHostReverseProxy(target)
	p.Director = func(req *http.Request) {
		req.URL.Scheme, req.URL.Host, req.URL.Path, req.URL.RawPath = target.Scheme, target.Host, "/", ""
		req.Host = target.Host
	}
	p.ServeHTTP(w, r)
}

// getGame is the public view of a game by its join code, for the lobby's
// game page: never tokens or internal ids beyond what joining already uses.
func (a *app) getGame(w http.ResponseWriter, r *http.Request) {
	sess, err := a.d.Store.SessionByInvite(r.Context(), r.PathValue("code"))
	if errors.Is(err, store.ErrNotFound) {
		writeErr(w, http.StatusNotFound, "bad_invite", "No game has that code.")
		return
	}
	if err != nil {
		internalErr(w, err)
		return
	}
	players, err := a.d.Store.Players(r.Context(), sess.ID)
	if err != nil {
		internalErr(w, err)
		return
	}
	if players == nil {
		players = []string{}
	}
	room, _ := a.d.Rooms.Room(sess.RoomID)
	diff, diffTitle := sess.Difficulty, ""
	for i, d := range room.Difficulties {
		if d.ID == diff || (diff == "" && i == 0) {
			diff, diffTitle = d.ID, d.Title
			break
		}
	}
	writeJSON(w, http.StatusOK, map[string]any{
		"code": sess.InviteCode, "room_id": sess.RoomID, "title": room.Title, "difficulty": diff,
		"difficulty_title": diffTitle, "status": sess.Status, "players": players,
		"players_max": room.Mode.Players.Max, "duration_minutes": room.Mode.DurationMinutes,
		"hacker_room": len(room.CTF.Challenges) > 0, "created_at": sess.CreatedAt.Unix(),
		"won": sess.Won, "elapsed_s": sess.ElapsedS, "expired": sess.Expired,
		"intro": a.intro(sess.RoomID),
	})
}

// status is the public overview: how many games are waiting, running or
// done, and the cap. No codes (they are invitations).
func (a *app) status(w http.ResponseWriter, r *http.Request) {
	counts, err := a.d.Store.CountByStatus(r.Context())
	if err != nil {
		internalErr(w, err)
		return
	}
	active, err := a.d.Store.CountActive(r.Context())
	if err != nil {
		internalErr(w, err)
		return
	}
	running := counts[store.StatusStarting] + counts[store.StatusRunning]
	free := -1 // no cap
	if a.d.MaxGames > 0 {
		free = max(0, a.d.MaxGames-active)
	}
	writeJSON(w, http.StatusOK, map[string]any{
		"waiting":   active - running, // new games waiting for their first player
		"running":   running,
		"finished":  counts[store.StatusFinished],
		"max_games": a.d.MaxGames,
		"free":      free,
	})
}

// directLocal: a loopback connection that did not come through a proxy.
func directLocal(r *http.Request) bool {
	host, _, err := net.SplitHostPort(r.RemoteAddr)
	if err != nil {
		return false
	}
	ip := net.ParseIP(host)
	return ip != nil && ip.IsLoopback() && r.Header.Get("X-Forwarded-For") == "" &&
		r.Header.Get("Tailscale-Funnel-Request") == "" && r.Header.Get("Forwarded") == ""
}

func (a *app) limitJoins(h http.HandlerFunc) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		if a.d.JoinLimit != nil && !a.d.JoinLimit.Allow(clientKey(r)) {
			writeErr(w, http.StatusTooManyRequests, "too_many_joins", "Too many attempts. Wait a minute and try again.")
			return
		}
		h(w, r)
	}
}

var ctfIDRe = regexp.MustCompile(`^[a-z0-9_]{1,64}$`)

// ctfProxy serves a running game's web challenge at
// /ctf/{session}/{challenge}/..., forwarding to the challenge's local proxy
// port with X-Forwarded-Prefix so the app builds links under it (ADR-0029).
// Nothing is served for finished games or challenges that are not running.
func (a *app) ctfProxy(w http.ResponseWriter, r *http.Request) {
	sid, cid := r.PathValue("session"), r.PathValue("challenge")
	if !ctfIDRe.MatchString(sid) || !ctfIDRe.MatchString(cid) {
		http.NotFound(w, r)
		return
	}
	sess, err := a.d.Store.Session(r.Context(), sid)
	if err != nil || sess.Status == store.StatusFinished {
		http.NotFound(w, r)
		return
	}
	insts, err := a.d.Store.Instances(r.Context(), sid)
	if err != nil {
		internalErr(w, err)
		return
	}
	port := 0
	for _, in := range insts {
		if in.ChallengeID == cid {
			port = in.HostPort
		}
	}
	if port == 0 {
		http.Error(w, "This challenge is not running (yet). It starts with the game.", http.StatusNotFound)
		return
	}
	prefix := "/ctf/" + sid + "/" + cid
	proto := "http"
	if r.TLS != nil || (isLoopbackAddr(r.RemoteAddr) && strings.EqualFold(strings.TrimSpace(r.Header.Get("X-Forwarded-Proto")), "https")) {
		proto = "https"
	}
	target := &url.URL{Scheme: "http", Host: net.JoinHostPort("127.0.0.1", strconv.Itoa(port))}
	p := httputil.NewSingleHostReverseProxy(target)
	p.Director = func(req *http.Request) {
		req.URL.Scheme, req.URL.Host = target.Scheme, target.Host
		req.URL.Path = "/" + r.PathValue("rest")
		req.URL.RawPath = ""
		req.Host = target.Host
		req.Header.Set("X-Forwarded-Prefix", prefix)
		req.Header.Set("X-Forwarded-Proto", proto)
		req.Header.Del("Cookie")
		for _, c := range r.Cookies() {
			if !strings.HasPrefix(c.Name, "escapebox") {
				req.AddCookie(c)
			}
		}
	}
	p.ModifyResponse = func(resp *http.Response) error {
		// Isolate proxied challenge pages into an opaque origin so challenge XSS
		// cannot read platform cookies, storage or same-origin API responses.
		resp.Header.Add("Content-Security-Policy", "sandbox allow-forms allow-scripts allow-popups")
		return nil
	}
	p.ServeHTTP(w, r)
}
