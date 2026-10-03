package api

import (
	"bytes"
	"context"
	"encoding/json"
	"io"
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"strings"
	"testing"

	"github.com/binaryc0de/escapebox/platform/internal/flags"
	"github.com/binaryc0de/escapebox/platform/internal/orchestrator"
	"github.com/binaryc0de/escapebox/platform/internal/rooms"
	"github.com/binaryc0de/escapebox/platform/internal/store"
)

func TestHealthAndVersion(t *testing.T) {
	ts := httptest.NewServer(NewHandler(nil))
	defer ts.Close()
	for path, want := range map[string]string{"/healthz": `"status":"ok"`, "/api/version": `"platform":"` + Version + `"`} {
		resp, err := http.Get(ts.URL + path)
		if err != nil {
			t.Fatal(err)
		}
		b, _ := io.ReadAll(resp.Body)
		resp.Body.Close()
		if resp.StatusCode != 200 || !strings.Contains(string(b), want) {
			t.Fatalf("%s: %d %s", path, resp.StatusCode, b)
		}
	}
}

type fakeServers struct{ started []string }

func (f *fakeServers) EnsureRunning(_ context.Context, s store.Session) (int, error) {
	f.started = append(f.started, s.ID)
	return 7781, nil
}
func (f *fakeServers) Transport() string { return "enet" }

type fakeOrch struct{ started, stopped []string }

func (f *fakeOrch) Start(_ context.Context, sessionID, roomID, _, roomDir string, chs []orchestrator.Challenge) (map[string]orchestrator.Handle, error) {
	f.started = append(f.started, sessionID+"/"+roomID+"/"+chs[0].ID+"@"+filepath.Base(roomDir))
	return map[string]orchestrator.Handle{"intranet": {URL: "http://10.0.0.5:20001/", Host: "10.0.0.5", Port: 20001}}, nil
}
func (f *fakeOrch) Stop(_ context.Context, sessionID string) error {
	f.stopped = append(f.stopped, sessionID)
	return nil
}

type env struct {
	ts      *httptest.Server
	st      *store.Store
	servers *fakeServers
	orch    *fakeOrch
	secret  []byte
}

func setup(t *testing.T) *env {
	t.Helper()
	st, err := store.Open(context.Background(), ":memory:")
	if err != nil {
		t.Fatal(err)
	}
	cat, err := rooms.Load(filepath.Join("..", "..", "..", "game", "rooms"))
	if err != nil {
		t.Fatal(err)
	}
	e := &env{st: st, servers: &fakeServers{}, orch: &fakeOrch{}, secret: []byte("platform-secret")}
	e.ts = httptest.NewServer(NewHandler(&Deps{Store: st, Rooms: cat, Servers: e.servers, Orchestrator: e.orch,
		Limiter: flags.NewLimiter(), Secret: e.secret, AdvertiseHost: "10.0.0.5"}))
	t.Cleanup(func() { e.ts.Close(); st.Close() })
	return e
}

func (e *env) call(t *testing.T, method, path, token string, body any) (int, map[string]any) {
	t.Helper()
	var rdr io.Reader
	if s, ok := body.(string); ok {
		rdr = strings.NewReader(s)
	} else if body != nil {
		b, _ := json.Marshal(body)
		rdr = bytes.NewReader(b)
	}
	req, _ := http.NewRequest(method, e.ts.URL+path, rdr)
	if token != "" {
		req.Header.Set("Authorization", "Bearer "+token)
	}
	resp, err := http.DefaultClient.Do(req)
	if err != nil {
		t.Fatal(err)
	}
	defer resp.Body.Close()
	raw, _ := io.ReadAll(resp.Body)
	var out map[string]any
	_ = json.Unmarshal(raw, &out)
	if out == nil {
		out = map[string]any{"_raw": string(raw)}
	}
	return resp.StatusCode, out
}

func (e *env) newSession(t *testing.T) store.Session {
	t.Helper()
	code, out := e.call(t, "POST", "/api/sessions", "", map[string]string{"room_id": "night_shift"})
	if code != 201 {
		t.Fatalf("create session: %d %v", code, out)
	}
	sess, _ := e.st.Session(context.Background(), out["session_id"].(string))
	if sess.InviteCode != out["invite_code"] {
		t.Fatal("invite code mismatch")
	}
	return sess
}

func TestJoinAndVerify(t *testing.T) {
	e := setup(t)
	sess := e.newSession(t)
	if code, _ := e.call(t, "POST", "/api/sessions", "", map[string]string{"room_id": "nope"}); code != 404 {
		t.Fatalf("unknown room: %d", code)
	}
	if code, out := e.call(t, "POST", "/api/sessions/"+sess.ID+"/join", "", map[string]string{"display_name": "Alex", "invite_code": "WRONG1"}); code != 403 || out["error"] != "bad_invite" {
		t.Fatalf("bad invite: %d %v", code, out)
	}
	if code, _ := e.call(t, "POST", "/api/sessions/"+sess.ID+"/join", "", map[string]string{"display_name": "  ", "invite_code": sess.InviteCode}); code != 400 {
		t.Fatalf("blank name: %d", code)
	}
	if code, _ := e.call(t, "POST", "/api/sessions/"+sess.ID+"/join", "", `{"display_name":"A","invite_code":"x","extra":1}`); code != 400 {
		t.Fatalf("unknown field accepted: %d", code)
	}
	code, out := e.call(t, "POST", "/api/sessions/"+sess.ID+"/join", "", map[string]string{"display_name": "Alex", "invite_code": strings.ToLower(sess.InviteCode)})
	if code != 200 || out["host"] != "10.0.0.5" || out["port"] != float64(7781) || out["transport"] != "enet" || out["join_token"] == "" {
		t.Fatalf("join: %d %v", code, out)
	}
	if len(e.servers.started) != 1 {
		t.Fatal("game server not started")
	}
	tok := out["join_token"].(string)
	// Internal endpoints need this session's server token.
	if code, _ := e.call(t, "POST", "/internal/sessions/"+sess.ID+"/verify", "", map[string]string{"join_token": tok}); code != 401 {
		t.Fatalf("verify without auth: %d", code)
	}
	other := e.newSession(t)
	if code, _ := e.call(t, "POST", "/internal/sessions/"+sess.ID+"/verify", other.ServerToken, map[string]string{"join_token": tok}); code != 401 {
		t.Fatalf("verify with another session's token: %d", code)
	}
	code, out = e.call(t, "POST", "/internal/sessions/"+sess.ID+"/verify", sess.ServerToken, map[string]string{"join_token": tok})
	if code != 200 || out["display_name"] != "Alex" || !strings.HasPrefix(out["player_id"].(string), "p_") {
		t.Fatalf("verify: %d %v", code, out)
	}
	if code, _ := e.call(t, "POST", "/internal/sessions/"+sess.ID+"/verify", sess.ServerToken, map[string]string{"join_token": tok}); code != 403 {
		t.Fatalf("token reuse: %d", code)
	}
	code, out = e.call(t, "GET", "/api/sessions/"+sess.ID, "", nil)
	if code != 200 || out["room_id"] != "night_shift" || out["duration_minutes"] != float64(60) || len(out["players"].([]any)) != 1 {
		t.Fatalf("get session: %d %v", code, out)
	}
	if _, has := out["invite_code"]; has {
		t.Fatal("session details leak the invite code")
	}
	if _, has := out["server_token"]; has {
		t.Fatal("session details leak the server token")
	}
}

func TestFlagsCheckedAndRateLimited(t *testing.T) {
	e := setup(t)
	sess := e.newSession(t)
	path := "/internal/sessions/" + sess.ID + "/flags"
	right := flags.PerInstance(e.secret, sess.ID, "intranet", "FLAG{{{nonce}}}")
	if code, out := e.call(t, "POST", path, sess.ServerToken, map[string]string{"challenge_id": "nope", "value": right, "player_id": "p"}); code != 404 {
		t.Fatalf("unknown challenge: %d %v", code, out)
	}
	code, out := e.call(t, "POST", path, sess.ServerToken, map[string]string{"challenge_id": "intranet", "value": "FLAG{guess}", "player_id": "p"})
	if code != 200 || out["accepted"] != false {
		t.Fatalf("wrong flag: %d %v", code, out)
	}
	for k, v := range out {
		if s, ok := v.(string); ok && strings.Contains(s, "guess") {
			t.Fatalf("response echoes the value in %s", k)
		}
	}
	code, out = e.call(t, "POST", path, sess.ServerToken, map[string]string{"challenge_id": "intranet", "value": " " + right + " ", "player_id": "p"})
	if code != 200 || out["accepted"] != true {
		t.Fatalf("right flag: %d %v", code, out)
	}
	// Another session's flag is wrong here.
	other := e.newSession(t)
	code, out = e.call(t, "POST", "/internal/sessions/"+other.ID+"/flags", other.ServerToken, map[string]string{"challenge_id": "intranet", "value": right, "player_id": "p"})
	if out["accepted"] != false {
		t.Fatal("flag from another session accepted")
	}
	for i := 0; i < 9; i++ {
		code, out = e.call(t, "POST", "/internal/sessions/"+other.ID+"/flags", other.ServerToken, map[string]string{"challenge_id": "intranet", "value": "x", "player_id": "p"})
	}
	if out["retry_after_s"] != float64(30) {
		t.Fatalf("10th wrong attempt: %d %v", code, out)
	}
	code, out = e.call(t, "POST", "/internal/sessions/"+other.ID+"/flags", other.ServerToken, map[string]string{"challenge_id": "intranet", "value": right, "player_id": "p"})
	if code != 429 || out["accepted"] != false {
		t.Fatalf("during cooldown: %d %v", code, out)
	}
	total, ok, _ := e.st.FlagAttempts(context.Background(), sess.ID, "intranet")
	if total != 2 || ok != 1 {
		t.Fatalf("attempts recorded %d/%d", total, ok)
	}
}

func TestSnapshotsEventsChallengesFinish(t *testing.T) {
	e := setup(t)
	sess := e.newSession(t)
	base := "/internal/sessions/" + sess.ID
	if code, _ := e.call(t, "GET", base+"/snapshot", sess.ServerToken, nil); code != 404 {
		t.Fatalf("fresh snapshot: %d", code)
	}
	if code, _ := e.call(t, "PUT", base+"/snapshot", sess.ServerToken, "not json"); code != 400 {
		t.Fatalf("bad snapshot accepted: %d", code)
	}
	if code, _ := e.call(t, "PUT", base+"/snapshot", sess.ServerToken, map[string]any{"version": 1, "nodes": map[string]any{}}); code != 204 {
		t.Fatalf("put snapshot: %d", code)
	}
	code, out := e.call(t, "GET", base+"/snapshot", sess.ServerToken, nil)
	if code != 200 || out["version"] != float64(1) {
		t.Fatalf("get snapshot: %d %v", code, out)
	}
	if code, _ := e.call(t, "POST", base+"/events", sess.ServerToken, []map[string]any{{"at": 1.5, "kind": "puzzle_solved", "data": map[string]string{"puzzle": "find_uv"}}, {"at": 2, "kind": "hint_revealed", "player_id": "p_x"}}); code != 204 {
		t.Fatalf("events: %d", code)
	}
	evs, _ := e.st.Events(context.Background(), sess.ID)
	if len(evs) != 2 || evs[0].Data != `{"puzzle":"find_uv"}` {
		t.Fatalf("events stored %+v", evs)
	}
	code, out = e.call(t, "POST", base+"/challenges/start", sess.ServerToken, nil)
	h, _ := out["handles"].(map[string]any)
	if code != 200 || h["intranet"] == nil || e.orch.started[0] != sess.ID+"/night_shift/intranet@night_shift" {
		t.Fatalf("challenges/start: %d %v %v", code, out, e.orch.started)
	}
	if code, _ := e.call(t, "POST", base+"/finished", sess.ServerToken, map[string]any{"win": true, "elapsed_s": 1900, "hints_used": 1}); code != 204 {
		t.Fatalf("finished: %d", code)
	}
	got, _ := e.st.Session(context.Background(), sess.ID)
	if got.Status != store.StatusFinished || !got.Won || got.ElapsedS != 1900 {
		t.Fatalf("finish not stored %+v", got)
	}
}

func TestChallengesWithoutDocker(t *testing.T) {
	e := setup(t)
	st, _ := store.Open(context.Background(), ":memory:")
	defer st.Close()
	cat, _ := rooms.Load(filepath.Join("..", "..", "..", "game", "rooms"))
	ts := httptest.NewServer(NewHandler(&Deps{Store: st, Rooms: cat, Servers: e.servers, Secret: e.secret, AdvertiseHost: "h"}))
	defer ts.Close()
	sess, _ := st.CreateSession(context.Background(), "night_shift")
	req, _ := http.NewRequest("POST", ts.URL+"/internal/sessions/"+sess.ID+"/challenges/start", nil)
	req.Header.Set("Authorization", "Bearer "+sess.ServerToken)
	resp, err := http.DefaultClient.Do(req)
	if err != nil {
		t.Fatal(err)
	}
	resp.Body.Close()
	if resp.StatusCode != 503 {
		t.Fatalf("no docker: %d", resp.StatusCode)
	}
}

func TestJoinByCode(t *testing.T) {
	e := setup(t)
	sess := e.newSession(t)
	code, out := e.call(t, "POST", "/api/join", "", map[string]string{"display_name": "Sam", "invite_code": strings.ToLower(sess.InviteCode)})
	if code != 200 || out["session_id"] != sess.ID || out["room_id"] != "night_shift" || out["join_token"] == "" {
		t.Fatalf("join by code: %d %v", code, out)
	}
	if code, out := e.call(t, "POST", "/api/join", "", map[string]string{"display_name": "Sam", "invite_code": "QQQQQQ"}); code != 404 || out["error"] != "bad_invite" {
		t.Fatalf("unknown code: %d %v", code, out)
	}
}

func TestDifficultyInCatalogAndSessions(t *testing.T) {
	e := setup(t)
	resp, err := http.Get(e.ts.URL + "/api/catalog")
	if err != nil {
		t.Fatal(err)
	}
	var cat []struct {
		RoomID       string `json:"room_id"`
		Difficulties []struct {
			ID string `json:"id"`
		} `json:"difficulties"`
	}
	_ = json.NewDecoder(resp.Body).Decode(&cat)
	resp.Body.Close()
	if len(cat) != 1 || len(cat[0].Difficulties) != 2 || cat[0].Difficulties[1].ID != "hard" {
		t.Fatalf("catalog difficulties: %+v", cat)
	}
	code, out := e.call(t, "POST", "/api/sessions", "", map[string]string{"room_id": "night_shift", "difficulty": "hard"})
	if code != 201 {
		t.Fatalf("create hard session: %d %v", code, out)
	}
	if s, _ := e.st.Session(context.Background(), out["session_id"].(string)); s.Difficulty != "hard" {
		t.Fatalf("stored difficulty %q", s.Difficulty)
	}
	if code, out := e.call(t, "POST", "/api/sessions", "", map[string]string{"room_id": "night_shift", "difficulty": "insane"}); code != 400 || out["error"] != "unknown_difficulty" {
		t.Fatalf("unknown difficulty: %d %v", code, out)
	}
}

func TestServesTheWebClient(t *testing.T) {
	dir := t.TempDir()
	_ = os.WriteFile(filepath.Join(dir, "index.html"), []byte("<title>escapebox</title>"), 0o644)
	_ = os.WriteFile(filepath.Join(dir, "index.wasm"), []byte("\x00asm"), 0o644)
	ts := httptest.NewServer(NewHandler(&Deps{WebDir: dir}))
	defer ts.Close()
	resp, err := http.Get(ts.URL + "/")
	if err != nil {
		t.Fatal(err)
	}
	b, _ := io.ReadAll(resp.Body)
	resp.Body.Close()
	if resp.StatusCode != 200 || !strings.Contains(string(b), "escapebox") || resp.Header.Get("Cache-Control") != "no-store" {
		t.Fatalf("/ -> %d %q %q", resp.StatusCode, b, resp.Header.Get("Cache-Control"))
	}
	resp, _ = http.Get(ts.URL + "/play/index.wasm")
	resp.Body.Close()
	if ct := resp.Header.Get("Content-Type"); ct != "application/wasm" {
		t.Fatalf("wasm content type %q", ct)
	}
	if resp, _ := http.Get(ts.URL + "/play/../secret.key"); resp.StatusCode == 200 {
		t.Fatal("path escaped the web dir")
	}
}
