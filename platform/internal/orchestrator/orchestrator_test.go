package orchestrator

import (
	"context"
	"errors"
	"io"
	"net"
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"strconv"
	"strings"
	"sync"
	"testing"
	"time"

	"github.com/binaryc0de/lockwright/platform/internal/docker"
	"github.com/binaryc0de/lockwright/platform/internal/flags"
	"github.com/binaryc0de/lockwright/platform/internal/store"
)

// fakeEngine keeps containers and networks in memory; every container's IP
// is 127.0.0.1 so the proxy reaches a local test server.
type fakeEngine struct {
	mu         sync.Mutex
	images     map[string]bool
	builds     int
	nets       map[string]bool
	containers map[string]docker.ContainerSpec
	next       int
}

func newFake() *fakeEngine {
	return &fakeEngine{images: map[string]bool{}, nets: map[string]bool{}, containers: map[string]docker.ContainerSpec{}}
}

func (f *fakeEngine) id(prefix string) string { f.next++; return prefix + strconv.Itoa(f.next) }
func (f *fakeEngine) ImageExists(_ context.Context, ref string) (bool, error) {
	f.mu.Lock()
	defer f.mu.Unlock()
	return f.images[ref], nil
}
func (f *fakeEngine) BuildImage(_ context.Context, dir, tag string, _ map[string]string) error {
	f.mu.Lock()
	defer f.mu.Unlock()
	if _, err := os.Stat(filepath.Join(dir, "Dockerfile")); err != nil {
		return err
	}
	f.images[tag] = true
	f.builds++
	return nil
}
func (f *fakeEngine) CreateNetwork(_ context.Context, n docker.NetworkSpec) (string, error) {
	f.mu.Lock()
	defer f.mu.Unlock()
	if !n.Internal {
		return "", errors.New("test: network must be internal")
	}
	if !strings.HasPrefix(n.BridgeName, docker.BridgePrefix) || len(n.BridgeName) > 15 {
		return "", errors.New("test: invalid bridge name " + n.BridgeName)
	}
	id := f.id("net")
	f.nets[id] = true
	return id, nil
}
func (f *fakeEngine) RemoveNetwork(_ context.Context, id string) error {
	f.mu.Lock()
	defer f.mu.Unlock()
	delete(f.nets, id)
	return nil
}
func (f *fakeEngine) CreateContainer(_ context.Context, s docker.ContainerSpec) (string, error) {
	f.mu.Lock()
	defer f.mu.Unlock()
	id := f.id("ctr")
	f.containers[id] = s
	return id, nil
}
func (f *fakeEngine) StartContainer(context.Context, string) error { return nil }
func (f *fakeEngine) InspectContainer(context.Context, string, string) (docker.ContainerInfo, error) {
	return docker.ContainerInfo{Running: true, IP: "127.0.0.1"}, nil
}
func (f *fakeEngine) RemoveContainer(_ context.Context, id string) error {
	f.mu.Lock()
	defer f.mu.Unlock()
	delete(f.containers, id)
	return nil
}
func (f *fakeEngine) ListByLabel(_ context.Context, label, value string) ([]string, []string, error) {
	f.mu.Lock()
	defer f.mu.Unlock()
	var cs []string
	for id, s := range f.containers {
		if s.Labels[label] == value {
			cs = append(cs, id)
		}
	}
	return cs, nil, nil
}

func roomDir(t *testing.T) string {
	t.Helper()
	dir := t.TempDir()
	os.MkdirAll(filepath.Join(dir, "ctf", "web"), 0o755)
	os.WriteFile(filepath.Join(dir, "ctf", "web", "Dockerfile"), []byte("FROM scratch\n"), 0o644)
	return dir
}

// fakeChallenge serves /healthz and / like a challenge container would.
func fakeChallenge(t *testing.T, healthy bool) (Challenge, int) {
	t.Helper()
	ts := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.URL.Path == "/healthz" && !healthy {
			w.WriteHeader(503)
			return
		}
		io.WriteString(w, "challenge:"+r.URL.Path)
	}))
	t.Cleanup(ts.Close)
	_, portStr, _ := net.SplitHostPort(strings.TrimPrefix(ts.URL, "http://"))
	port, _ := strconv.Atoi(portStr)
	ch := Challenge{ID: "web", Build: "ctf/web", Ports: []Port{{Container: port, Protocol: "http"}},
		Flag: flags.Spec{Type: "per_instance", Format: "FLAG{{{nonce}}}", InjectEnv: "FLAG"}}
	ch.Healthcheck.Path = "/healthz"
	ch.Healthcheck.TimeoutS = 1
	ch.Resources.CPU = 0.5
	ch.Resources.MemoryMB = 128
	ch.Resources.Pids = 64
	return ch, port
}

func setup(t *testing.T) (*Orchestrator, *fakeEngine, *store.Store) {
	t.Helper()
	st, err := store.Open(context.Background(), ":memory:")
	if err != nil {
		t.Fatal(err)
	}
	t.Cleanup(func() { st.Close() })
	f := newFake()
	o := New(Config{AdvertiseHost: "192.168.1.50", BindAddr: "127.0.0.1", PortMin: 23100, PortMax: 23199, Secret: []byte("k")}, f, st)
	return o, f, st
}

func TestStartProxiesTheChallengeAndStopTearsDown(t *testing.T) {
	ctx := context.Background()
	o, f, st := setup(t)
	ch, _ := fakeChallenge(t, true)
	dir := roomDir(t)
	hs, err := o.Start(ctx, "s1", "room", "0.1.0", dir, []Challenge{ch})
	if err != nil {
		t.Fatal(err)
	}
	h := hs["web"]
	if h.Host != "192.168.1.50" || h.Port < 23100 || h.Port > 23199 || h.URL != "http://192.168.1.50:"+strconv.Itoa(h.Port)+"/" {
		t.Fatalf("handle %+v", h)
	}
	resp, err := http.Get("http://127.0.0.1:" + strconv.Itoa(h.Port) + "/tickets")
	if err != nil {
		t.Fatal(err)
	}
	b, _ := io.ReadAll(resp.Body)
	resp.Body.Close()
	if string(b) != "challenge:/tickets" {
		t.Fatalf("through the proxy got %q", b)
	}
	// The per-instance flag went into the container environment, nowhere else.
	var spec docker.ContainerSpec
	for _, s := range f.containers {
		spec = s
	}
	if spec.Env["FLAG"] != flags.PerInstance([]byte("k"), "s1", "web", "FLAG{{{nonce}}}") || spec.Network != "esc_s1" ||
		spec.CPUs != 0.5 || spec.MemoryMB != 128 || spec.PidsMax != 64 || spec.Labels[LabelSession] != "s1" {
		t.Fatalf("container spec %+v", spec)
	}
	if strings.Contains(h.URL+h.Note, "FLAG{") {
		t.Fatal("flag leaked into the handle")
	}
	if ins, _ := st.Instances(ctx, "s1"); len(ins) != 1 || ins[0].HostPort != h.Port {
		t.Fatalf("instance not stored: %+v", ins)
	}
	// Idempotent.
	again, err := o.Start(ctx, "s1", "room", "0.1.0", dir, []Challenge{ch})
	if err != nil || again["web"].Port != h.Port || f.builds != 1 {
		t.Fatalf("second start: %+v %v builds=%d", again, err, f.builds)
	}
	if err := o.Stop(ctx, "s1"); err != nil {
		t.Fatal(err)
	}
	if len(f.containers) != 0 || len(f.nets) != 0 {
		t.Fatalf("left behind: %v %v", f.containers, f.nets)
	}
	if _, err := net.DialTimeout("tcp", "127.0.0.1:"+strconv.Itoa(h.Port), 200*time.Millisecond); err == nil {
		t.Fatal("proxy port still open after Stop")
	}
	if ins, _ := st.Instances(ctx, "s1"); len(ins) != 0 {
		t.Fatal("instances not forgotten")
	}
	// Restart reuses the image and frees/reuses ports.
	hs2, err := o.Start(ctx, "s1", "room", "0.1.0", dir, []Challenge{ch})
	if err != nil || f.builds != 1 {
		t.Fatalf("restart: %v builds=%d", err, f.builds)
	}
	if hs2["web"].Port != h.Port {
		t.Fatalf("port not reused: %d vs %d", hs2["web"].Port, h.Port)
	}
	o.Stop(ctx, "s1")
}

func TestUnhealthyChallengeIsRolledBack(t *testing.T) {
	ctx := context.Background()
	o, f, _ := setup(t)
	o.Probe = func(context.Context, string) error { return errors.New("down") }
	ch, _ := fakeChallenge(t, false)
	if _, err := o.Start(ctx, "s2", "room", "0.1.0", roomDir(t), []Challenge{ch}); err == nil || !strings.Contains(err.Error(), "not healthy") {
		t.Fatalf("want health failure, got %v", err)
	}
	if len(f.containers) != 0 || len(f.nets) != 0 || o.Handles("s2") != nil {
		t.Fatal("failed start left resources behind")
	}
}

func TestBuildPathMustStayInsideTheRoom(t *testing.T) {
	ctx := context.Background()
	o, _, _ := setup(t)
	ch, _ := fakeChallenge(t, true)
	for _, bad := range []string{"../../etc", "/etc", "ctf/missing"} {
		ch.Build = bad
		if _, err := o.Start(ctx, "s3", "room", "0.1.0", roomDir(t), []Challenge{ch}); err == nil {
			t.Fatalf("build path %q accepted", bad)
		}
	}
	// Symlink directory pointing outside the room must be rejected.
	dir := roomDir(t)
	outside := t.TempDir()
	_ = os.WriteFile(filepath.Join(outside, "Dockerfile"), []byte("FROM scratch\n"), 0o644)
	if err := os.Symlink(outside, filepath.Join(dir, "ctf", "escape_dir")); err != nil {
		t.Fatal(err)
	}
	ch.Build = "ctf/escape_dir"
	if _, err := o.Start(ctx, "s3b", "room", "0.1.0", dir, []Challenge{ch}); err == nil {
		t.Fatal("symlink build directory outside room accepted")
	}
	// Symlink Dockerfile pointing outside the room must also be rejected.
	_ = os.MkdirAll(filepath.Join(dir, "ctf", "escape_df"), 0o755)
	if err := os.Symlink(filepath.Join(outside, "Dockerfile"), filepath.Join(dir, "ctf", "escape_df", "Dockerfile")); err != nil {
		t.Fatal(err)
	}
	ch.Build = "ctf/escape_df"
	if _, err := o.Start(ctx, "s3c", "room", "0.1.0", dir, []Challenge{ch}); err == nil {
		t.Fatal("symlink Dockerfile outside room accepted")
	}
}

func TestEditingTheChallengeChangesTheImageTag(t *testing.T) {
	dir := roomDir(t)
	a, _ := contextHash(filepath.Join(dir, "ctf", "web"))
	os.WriteFile(filepath.Join(dir, "ctf", "web", "main.go"), []byte("package main"), 0o644)
	b, _ := contextHash(filepath.Join(dir, "ctf", "web"))
	if a == b || ImageTag("r", "c", "1.0", a) == ImageTag("r", "c", "1.0", b) {
		t.Fatal("context change did not change the tag")
	}
	if !strings.HasPrefix(ImageTag("r", "c", "", a), "escapebox/r-c:dev-") {
		t.Fatal("empty version not tagged dev")
	}
}

func TestCleanupRemovesLeftovers(t *testing.T) {
	ctx := context.Background()
	o, f, _ := setup(t)
	f.containers["old1"] = docker.ContainerSpec{Labels: map[string]string{LabelManaged: "1"}}
	f.containers["mine"] = docker.ContainerSpec{Labels: map[string]string{}}
	if err := o.Cleanup(ctx); err != nil {
		t.Fatal(err)
	}
	if _, ok := f.containers["old1"]; ok {
		t.Fatal("leftover not removed")
	}
	if _, ok := f.containers["mine"]; !ok {
		t.Fatal("unmanaged container removed")
	}
}

// A platform only cleans up what it created: a test platform starting beside
// the always-on service must not remove the service's live challenges.
func TestCleanupLeavesOtherPlatformsAlone(t *testing.T) {
	ctx := context.Background()
	o, f, _ := setup(t)
	o.cfg.Owner = OwnerFor("data-a")
	f.containers["mine"] = docker.ContainerSpec{Labels: map[string]string{LabelManaged: "1", LabelOwner: o.cfg.Owner}}
	f.containers["other"] = docker.ContainerSpec{Labels: map[string]string{LabelManaged: "1", LabelOwner: OwnerFor("data-b")}}
	f.containers["unlabelled"] = docker.ContainerSpec{Labels: map[string]string{LabelManaged: "1"}}
	if err := o.Cleanup(ctx); err != nil {
		t.Fatal(err)
	}
	if _, ok := f.containers["mine"]; ok {
		t.Fatal("own leftover not removed")
	}
	for _, id := range []string{"other", "unlabelled"} {
		if _, ok := f.containers[id]; !ok {
			t.Fatalf("%s removed by another platform's cleanup", id)
		}
	}
	ch, _ := fakeChallenge(t, true)
	if _, err := o.Start(ctx, "s1", "room", "1.0.0", roomDir(t), []Challenge{ch}); err != nil {
		t.Fatal(err)
	}
	for id, c := range f.containers {
		if c.Labels[LabelSession] == "s1" && c.Labels[LabelOwner] != o.cfg.Owner {
			t.Fatalf("container %s started without the owner label: %v", id, c.Labels)
		}
	}
	if OwnerFor("data-a") == OwnerFor("data-b") || OwnerFor("data") != OwnerFor("./data") {
		t.Fatal("owner ids not stable per data directory")
	}
}

func TestConcurrentStartsAndStopDoNotInterleave(t *testing.T) {
	ctx := context.Background()
	o, f, _ := setup(t)
	ch, _ := fakeChallenge(t, true)
	dir := roomDir(t)
	var wg sync.WaitGroup
	for i := 0; i < 4; i++ {
		wg.Add(1)
		go func() {
			defer wg.Done()
			if _, err := o.Start(ctx, "s9", "room", "0.1.0", dir, []Challenge{ch}); err != nil {
				t.Error(err)
			}
		}()
	}
	wg.Wait()
	f.mu.Lock()
	nets, ctrs, builds := len(f.nets), len(f.containers), f.builds
	f.mu.Unlock()
	if nets != 1 || ctrs != 1 || builds != 1 {
		t.Fatalf("concurrent starts created nets=%d containers=%d builds=%d", nets, ctrs, builds)
	}
	if err := o.Stop(ctx, "s9"); err != nil {
		t.Fatal(err)
	}
	if len(f.nets) != 0 || len(f.containers) != 0 || o.Handles("s9") != nil {
		t.Fatal("stop after concurrent starts left resources")
	}
}

func TestProxyHonoursBindAddr(t *testing.T) {
	o, _, _ := setup(t) // BindAddr: "127.0.0.1"
	p, _, err := o.listen()
	if err != nil {
		t.Fatal(err)
	}
	defer p.close()
	addr := p.ln.Addr().(*net.TCPAddr)
	if !addr.IP.Equal(net.ParseIP("127.0.0.1")) {
		t.Fatalf("listener bound to %s, want 127.0.0.1", addr.IP)
	}
}

func TestHTTPProbeRefusesRedirectsAndHasTimeout(t *testing.T) {
	if probeClient.Timeout <= 0 {
		t.Fatalf("probeClient has no timeout: %v", probeClient.Timeout)
	}
	targetHit := false
	target := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, _ *http.Request) {
		targetHit = true
		w.WriteHeader(http.StatusOK)
	}))
	defer target.Close()
	ch := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		http.Redirect(w, r, target.URL+"/secret", http.StatusFound)
	}))
	defer ch.Close()
	err := httpProbe(context.Background(), ch.URL+"/healthz")
	if err == nil || !strings.Contains(err.Error(), "302") {
		t.Fatalf("expected 302 error, got %v", err)
	}
	if targetHit {
		t.Fatal("httpProbe followed redirect to target")
	}
	// Slow server times out via context / client timeout.
	release := make(chan struct{})
	slow := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		select {
		case <-release:
		case <-r.Context().Done():
		}
	}))
	defer func() { close(release); slow.Close() }()
	ctx, cancel := context.WithTimeout(context.Background(), 100*time.Millisecond)
	defer cancel()
	if err := httpProbe(ctx, slow.URL+"/healthz"); err == nil {
		t.Fatal("slow health check unexpectedly succeeded")
	}
}

func TestProxyHalfCloseCapAndIdleTimeout(t *testing.T) {
	// Upstream reads until client half-closes (EOF), then responds and closes.
	upLn, err := net.Listen("tcp", "127.0.0.1:0")
	if err != nil {
		t.Fatal(err)
	}
	defer upLn.Close()
	go func() {
		for {
			c, err := upLn.Accept()
			if err != nil {
				return
			}
			go func(conn net.Conn) {
				defer conn.Close()
				req, err := io.ReadAll(conn)
				if err != nil {
					return
				}
				time.Sleep(20 * time.Millisecond)
				_, _ = conn.Write(append([]byte("reply:"), req...))
			}(c)
		}
	}()

	ln, err := net.Listen("tcp", "127.0.0.1:0")
	if err != nil {
		t.Fatal(err)
	}
	p := &proxy{
		ln:          ln,
		target:      upLn.Addr().String(),
		maxConns:    2,
		idleTimeout: 150 * time.Millisecond,
		conns:       map[net.Conn]bool{},
	}
	go p.serve()
	defer p.close()

	// 1. Half-close: client writes request, calls CloseWrite, still receives full reply.
	c1, err := net.Dial("tcp", ln.Addr().String())
	if err != nil {
		t.Fatal(err)
	}
	_, _ = c1.Write([]byte("ping"))
	if err := c1.(*net.TCPConn).CloseWrite(); err != nil {
		t.Fatal(err)
	}
	reply, err := io.ReadAll(c1)
	c1.Close()
	if err != nil || string(reply) != "reply:ping" {
		t.Fatalf("half-close reply = %q, err = %v; want reply:ping", reply, err)
	}

	// 2. Connection cap: hold 2 connections open; a 3rd is immediately closed.
	hold1, err := net.Dial("tcp", ln.Addr().String())
	if err != nil {
		t.Fatal(err)
	}
	defer hold1.Close()
	hold2, err := net.Dial("tcp", ln.Addr().String())
	if err != nil {
		t.Fatal(err)
	}
	defer hold2.Close()
	// Wait until both connections are acquired by the proxy.
	deadline := time.Now().Add(time.Second)
	for time.Now().Before(deadline) {
		p.mu.Lock()
		n := p.active
		p.mu.Unlock()
		if n == 2 {
			break
		}
		time.Sleep(5 * time.Millisecond)
	}
	c3, err := net.Dial("tcp", ln.Addr().String())
	if err != nil {
		t.Fatal(err)
	}
	_ = c3.SetReadDeadline(time.Now().Add(500 * time.Millisecond))
	buf := make([]byte, 1)
	_, err = c3.Read(buf)
	c3.Close()
	if !errors.Is(err, io.EOF) {
		t.Fatalf("3rd connection beyond cap: read err = %v, want EOF", err)
	}

	// 3. Idle timeout: the two held idle connections are closed after idleTimeout.
	_ = hold1.SetReadDeadline(time.Now().Add(time.Second))
	if _, err := hold1.Read(buf); err == nil {
		t.Fatal("idle connection was not closed after idleTimeout")
	}
	_ = hold2.SetReadDeadline(time.Now().Add(time.Second))
	if _, err := hold2.Read(buf); err == nil {
		t.Fatal("second idle connection was not closed after idleTimeout")
	}
	// Slots are released once idle connections close, so a new connection works again.
	deadline = time.Now().Add(time.Second)
	for time.Now().Before(deadline) {
		p.mu.Lock()
		n := p.active
		p.mu.Unlock()
		if n == 0 {
			break
		}
		time.Sleep(5 * time.Millisecond)
	}
	c4, err := net.Dial("tcp", ln.Addr().String())
	if err != nil {
		t.Fatal(err)
	}
	_, _ = c4.Write([]byte("again"))
	_ = c4.(*net.TCPConn).CloseWrite()
	reply, err = io.ReadAll(c4)
	c4.Close()
	if err != nil || string(reply) != "reply:again" {
		t.Fatalf("post-idle connection reply = %q, err = %v", reply, err)
	}
}
