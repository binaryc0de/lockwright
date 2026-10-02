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
	"io"
	"log/slog"
	"math"
	"net/http"
	"strings"
	"time"

	"github.com/binaryc0de/escapebox/platform/internal/flags"
	"github.com/binaryc0de/escapebox/platform/internal/orchestrator"
	"github.com/binaryc0de/escapebox/platform/internal/rooms"
	"github.com/binaryc0de/escapebox/platform/internal/sessions"
	"github.com/binaryc0de/escapebox/platform/internal/store"
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
	a := &app{d}
	mux.HandleFunc("GET /api/catalog", a.catalog)
	mux.HandleFunc("POST /api/sessions", a.createSession)
	mux.HandleFunc("GET /api/sessions/{id}", a.getSession)
	mux.HandleFunc("POST /api/sessions/{id}/join", a.join)
	mux.HandleFunc("POST /api/join", a.joinByCode)
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

type app struct{ d *Deps }

// --- public ---------------------------------------------------------------

func (a *app) catalog(w http.ResponseWriter, _ *http.Request) {
	type entry struct {
		RoomID          string `json:"room_id"`
		Title           string `json:"title"`
		Version         string `json:"version"`
		DurationMinutes int    `json:"duration_minutes"`
		Players         [2]int `json:"players"`
		Challenges      int    `json:"challenges"`
	}
	out := []entry{}
	for _, r := range a.d.Rooms.All() {
		out = append(out, entry{r.ID, r.Title, r.Version, r.Mode.DurationMinutes, [2]int{r.Mode.Players.Min, r.Mode.Players.Max}, len(r.CTF.Challenges)})
	}
	writeJSON(w, http.StatusOK, out)
}

func (a *app) createSession(w http.ResponseWriter, r *http.Request) {
	var in struct {
		RoomID string `json:"room_id"`
	}
	if !readJSON(w, r, &in, maxBody) {
		return
	}
	if _, ok := a.d.Rooms.Room(in.RoomID); !ok {
		writeErr(w, http.StatusNotFound, "unknown_room", "No such room is installed.")
		return
	}
	sess, err := a.d.Store.CreateSession(r.Context(), in.RoomID)
	if err != nil {
		internalErr(w, err)
		return
	}
	slog.Info("session created", "session", sess.ID, "room", sess.RoomID)
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
	writeJSON(w, http.StatusOK, map[string]any{"session_id": sess.ID, "room_id": sess.RoomID, "host": a.d.AdvertiseHost, "port": port, "transport": a.d.Servers.Transport(), "join_token": token})
}

// --- internal (game server -> platform) -------------------------------------

type internalHandler func(w http.ResponseWriter, r *http.Request, sess store.Session)

// internal authenticates a game server with its session's server token.
func (a *app) internal(h internalHandler) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
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
	if allowed, wait := a.d.Limiter.Allow(key); !allowed {
		writeJSON(w, http.StatusTooManyRequests, map[string]any{"accepted": false, "retry_after_s": seconds(wait)})
		return
	}
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
	slog.Info("flag attempt", "session", sess.ID, "challenge", ch.ID, "player", in.PlayerID, "accepted", accepted)
	out := map[string]any{"accepted": accepted}
	if !accepted {
		if cool := a.d.Limiter.Wrong(key); cool > 0 {
			out["retry_after_s"] = seconds(cool)
		}
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

func readJSON(w http.ResponseWriter, r *http.Request, v any, limit int64) bool {
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
