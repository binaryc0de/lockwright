package main

import (
	"io"
	"net/http"
	"net/http/cookiejar"
	"net/http/httptest"
	"net/url"
	"os"
	"os/exec"
	"regexp"
	"strconv"
	"strings"
	"testing"
	"time"
)

const testFlag = "TESTFLAG-not-a-real-format-123"

func setup(t *testing.T) (*httptest.Server, *http.Client) {
	t.Helper()
	ts := httptest.NewServer(newServer(testFlag).routes())
	t.Cleanup(ts.Close)
	jar, _ := cookiejar.New(nil)
	return ts, &http.Client{Jar: jar}
}

func body(t *testing.T, r *http.Response) string {
	t.Helper()
	defer r.Body.Close()
	b, _ := io.ReadAll(r.Body)
	return string(b)
}

func login(t *testing.T, ts *httptest.Server, c *http.Client, user, pass string) *http.Response {
	t.Helper()
	r, err := c.PostForm(ts.URL+"/login", url.Values{"username": {user}, "password": {pass}})
	if err != nil {
		t.Fatal(err)
	}
	return r
}

func TestHealthz(t *testing.T) {
	ts, c := setup(t)
	r, _ := c.Get(ts.URL + "/healthz")
	if r.StatusCode != 200 || body(t, r) != "ok\n" {
		t.Fatalf("healthz %d", r.StatusCode)
	}
}

func TestWrongCredentialsAndNoAccessWithoutLogin(t *testing.T) {
	ts, c := setup(t)
	for _, creds := range [][2]string{{"mreyes", "kestrel#2019"}, {"admin", password}, {"", ""}} {
		r := login(t, ts, c, creds[0], creds[1])
		b := body(t, r)
		if r.StatusCode != http.StatusUnauthorized || !strings.Contains(b, "Invalid username or password") {
			t.Fatalf("login %v: %d", creds, r.StatusCode)
		}
	}
	r, _ := c.Get(ts.URL + "/tickets/view?id=1040")
	b := body(t, r)
	if strings.Contains(b, testFlag) || !strings.Contains(b, "Sign in") {
		t.Fatal("ticket readable without logging in")
	}
	// A forged cookie does not log you in.
	u, _ := url.Parse(ts.URL)
	c.Jar.SetCookies(u, []*http.Cookie{{Name: cookieName, Value: "mreyes.deadbeef"}})
	r, _ = c.Get(ts.URL + "/tickets")
	if b := body(t, r); strings.Contains(b, "My tickets") {
		t.Fatal("forged cookie accepted")
	}
}

func TestIntendedPath(t *testing.T) {
	ts, c := setup(t)
	r := login(t, ts, c, " mreyes ", password)
	b := body(t, r)
	if !strings.Contains(b, "My tickets") || !strings.Contains(b, "view?id=1042") {
		t.Fatalf("ticket list missing after login: %d", r.StatusCode)
	}
	if strings.Contains(b, testFlag) || strings.Contains(b, "1040") {
		t.Fatal("the flag ticket is listed without the IDOR")
	}
	r, _ = c.Get(ts.URL + "/tickets/view?id=1042")
	if b := body(t, r); strings.Contains(b, testFlag) {
		t.Fatal("flag on the user's own ticket")
	}
	// The IDOR: a neighbouring id shows someone else's ticket, with the token.
	r, _ = c.Get(ts.URL + "/tickets/view?id=1040")
	b = body(t, r)
	if r.StatusCode != 200 || !strings.Contains(b, testFlag) || !strings.Contains(b, "maglock") {
		t.Fatalf("flag ticket not reachable by id: %d", r.StatusCode)
	}
	for _, id := range []string{"1036", "9999", "abc", ""} {
		r, _ = c.Get(ts.URL + "/tickets/view?id=" + id)
		if b := body(t, r); r.StatusCode != 404 || strings.Contains(b, testFlag) {
			t.Fatalf("id %q: %d", id, r.StatusCode)
		}
	}
}

func TestFlagOnlyOnTheFacilitiesTicket(t *testing.T) {
	ts, c := setup(t)
	body(t, login(t, ts, c, username, password))
	for id, tk := range tickets() {
		r, _ := c.Get(ts.URL + "/tickets/view?id=" + strconv.Itoa(id))
		has := strings.Contains(body(t, r), testFlag)
		if has != (id == FlagTicketID) || has != tk.HasToken {
			t.Fatalf("ticket %d shows flag=%v", id, has)
		}
	}
}

func TestOutputIsEscaped(t *testing.T) {
	ts, c := setup(t)
	r := login(t, ts, c, "<script>x</script>", "nope")
	if b := body(t, r); strings.Contains(b, "<script>x</script>") {
		t.Fatal("username echoed unescaped")
	}
}

func TestAccountLocksAfterFiveFailures(t *testing.T) {
	srv := newServer(testFlag)
	now := time.Unix(1_800_000_000, 0)
	srv.now = func() time.Time { return now }
	ts := httptest.NewServer(srv.routes())
	t.Cleanup(ts.Close)
	jar, _ := cookiejar.New(nil)
	c := &http.Client{Jar: jar}
	for i := 0; i < MaxFailures-1; i++ {
		if r := login(t, ts, c, username, "nope"); r.StatusCode != http.StatusUnauthorized {
			t.Fatalf("failure %d: %d", i+1, r.StatusCode)
		}
	}
	r := login(t, ts, c, username, "nope")
	if b := body(t, r); r.StatusCode != http.StatusTooManyRequests || !strings.Contains(b, "locked") {
		t.Fatalf("5th failure should lock: %d", r.StatusCode)
	}
	// Even the right password is refused while locked.
	r = login(t, ts, c, username, password)
	if b := body(t, r); r.StatusCode != http.StatusTooManyRequests || strings.Contains(b, "My tickets") {
		t.Fatalf("locked account let the right password in: %d", r.StatusCode)
	}
	now = now.Add(LockFor + time.Second)
	r = login(t, ts, c, username, password)
	if b := body(t, r); !strings.Contains(b, "My tickets") {
		t.Fatalf("lock did not expire: %d", r.StatusCode)
	}
}

func TestSuccessResetsTheFailureCount(t *testing.T) {
	ts, c := setup(t)
	for i := 0; i < MaxFailures-1; i++ {
		body(t, login(t, ts, c, username, "nope"))
	}
	body(t, login(t, ts, c, username, password))
	for i := 0; i < MaxFailures-1; i++ {
		if r := login(t, ts, c, username, "nope"); r.StatusCode != http.StatusUnauthorized {
			t.Fatalf("counter not reset: failure %d gave %d", i+1, r.StatusCode)
		}
	}
}

// The hard-mode USB stick (room.tscn, Item file shadow.bak) must hold the
// sha512crypt hash of this challenge's password, or hard mode is unwinnable.
func TestUSBStickHashIsThePassword(t *testing.T) {
	if _, err := exec.LookPath("openssl"); err != nil {
		t.Skip("openssl not installed")
	}
	scene, err := os.ReadFile("../../room.tscn")
	if err != nil {
		t.Fatal(err)
	}
	m := regexp.MustCompile(`(?m)^mreyes:(\$6\$([^$]+)\$[^:]+):`).FindSubmatch(scene)
	if m == nil {
		t.Fatal("no mreyes sha512crypt line in room.tscn")
	}
	out, err := exec.Command("openssl", "passwd", "-6", "-salt", string(m[2]), password).Output()
	if err != nil {
		t.Fatal(err)
	}
	if strings.TrimSpace(string(out)) != string(m[1]) {
		t.Fatal("the hash on the USB stick is not the intranet password's")
	}
}

func TestServedUnderAProxyPrefix(t *testing.T) {
	srv := newServer(testFlag)
	prefix := "/ctf/s3ss10n/intranet"
	// Stand in for the platform's proxy: strip the prefix, set the header.
	proxy := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		r2 := r.Clone(r.Context())
		r2.URL.Path = strings.TrimPrefix(r.URL.Path, prefix)
		if r2.URL.Path == "" {
			r2.URL.Path = "/"
		}
		r2.Header.Set("X-Forwarded-Prefix", prefix)
		srv.routes().ServeHTTP(w, r2)
	}))
	defer proxy.Close()
	jar, _ := cookiejar.New(nil)
	c := &http.Client{Jar: jar}
	r, err := c.PostForm(proxy.URL+prefix+"/login", url.Values{"username": {username}, "password": {password}})
	if err != nil {
		t.Fatal(err)
	}
	b := body(t, r)
	if r.Request.URL.Path != prefix+"/tickets" || !strings.Contains(b, `href="`+prefix+`/tickets/view?id=1042"`) || !strings.Contains(b, `action="`+prefix+`/logout"`) {
		t.Fatalf("not prefixed: landed on %s", r.Request.URL.Path)
	}
	u, _ := url.Parse(proxy.URL + prefix + "/tickets")
	if len(jar.Cookies(u)) != 1 {
		t.Fatal("session cookie not scoped to the prefix")
	}
	if other, _ := url.Parse(proxy.URL + "/ctf/othergame/intranet/tickets"); len(jar.Cookies(other)) != 0 {
		t.Fatal("cookie leaks to another game's prefix")
	}
	// A hostile header is ignored rather than turned into a redirect.
	req := httptest.NewRequest("GET", "/", nil)
	req.Header.Set("X-Forwarded-Prefix", "//evil.example")
	rec := httptest.NewRecorder()
	srv.routes().ServeHTTP(rec, req)
	if loc := rec.Header().Get("Location"); loc != "/login" {
		t.Fatalf("redirect with a hostile prefix: %q", loc)
	}
}
