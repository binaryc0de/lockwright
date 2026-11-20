// Package orchestrator runs a session's CTF challenges (PLAN.md 7.6,
// ADR-0018): image build, an internal (no egress) network per session,
// hardened containers with per-instance flags, health checks, and a TCP
// proxy that gives LAN players a port to attack. Flag values go only into
// the container environment; they are never logged or returned.
package orchestrator

import (
	"context"
	"crypto/sha256"
	"encoding/hex"
	"errors"
	"fmt"
	"io"
	"io/fs"
	"log/slog"
	"net"
	"net/http"
	"os"
	"path/filepath"
	"sort"
	"strconv"
	"strings"
	"sync"
	"sync/atomic"
	"time"

	"github.com/binaryc0de/lockwright/platform/internal/docker"
	"github.com/binaryc0de/lockwright/platform/internal/flags"
	"github.com/binaryc0de/lockwright/platform/internal/store"
)

// Engine is the Docker surface the orchestrator needs (docker.Client in production).
type Engine interface {
	ImageExists(ctx context.Context, ref string) (bool, error)
	BuildImage(ctx context.Context, dir, tag string, labels map[string]string) error
	CreateNetwork(ctx context.Context, n docker.NetworkSpec) (string, error)
	RemoveNetwork(ctx context.Context, id string) error
	CreateContainer(ctx context.Context, s docker.ContainerSpec) (string, error)
	StartContainer(ctx context.Context, id string) error
	InspectContainer(ctx context.Context, id, network string) (docker.ContainerInfo, error)
	RemoveContainer(ctx context.Context, id string) error
	ListByLabel(ctx context.Context, label, value string) ([]string, []string, error)
}

// Challenge is one ctf.challenges entry from room.json.
type Challenge struct {
	ID          string     `json:"id"`
	Title       string     `json:"title"`
	Kind        string     `json:"kind"`
	Build       string     `json:"build"`
	Ports       []Port     `json:"ports"`
	Flag        flags.Spec `json:"flag"`
	Healthcheck struct {
		Path     string `json:"path"`
		TimeoutS int    `json:"timeout_s"`
	} `json:"healthcheck"`
	Resources struct {
		CPU      float64 `json:"cpu"`
		MemoryMB int     `json:"memory_mb"`
		Pids     int     `json:"pids"`
	} `json:"resources"`
}

// Port is a container port a challenge exposes.
type Port struct {
	Container int    `json:"container"`
	Protocol  string `json:"protocol"`
}

// Handle is what a Terminal prop shows players (the connection card).
type Handle struct {
	URL  string `json:"url,omitempty"`
	Host string `json:"host,omitempty"`
	Port int    `json:"port,omitempty"`
	Note string `json:"note,omitempty"`
}

// Defaults for each challenge TCP proxy.
const (
	DefaultMaxConns    = 64
	DefaultIdleTimeout = 2 * time.Minute
)

// Config tunes the orchestrator.
type Config struct {
	AdvertiseHost string // address players' machines use to reach this host
	BindAddr      string // where proxy ports listen ("0.0.0.0" for the LAN)
	PortMin       int
	PortMax       int
	MaxConns      int           // concurrent connections per proxy (0 = DefaultMaxConns)
	IdleTimeout   time.Duration // idle timeout per proxied connection (0 = DefaultIdleTimeout)
	Secret        []byte        // platform secret for per-instance flags
	// Owner identifies this platform instance (OwnerFor its data directory).
	// Everything it creates carries it, and Cleanup removes only what carries
	// it, so a second platform on the same Docker (a test run beside the
	// always-on service) never tears down another's live challenges.
	Owner string
}

// Labels on everything the orchestrator creates.
const (
	LabelManaged = "escapebox.managed"
	LabelSession = "escapebox.session"
	LabelOwner   = "escapebox.owner"
)

// OwnerFor is a stable owner id for a platform whose data lives in dataDir.
func OwnerFor(dataDir string) string {
	if abs, err := filepath.Abs(dataDir); err == nil {
		dataDir = abs
	}
	sum := sha256.Sum256([]byte(dataDir))
	return hex.EncodeToString(sum[:6])
}

// Orchestrator manages challenge instances. Safe for concurrent use.
type Orchestrator struct {
	cfg   Config
	eng   Engine
	store *store.Store
	// Probe performs one health check; replaced in tests.
	Probe func(ctx context.Context, url string) error

	mu       sync.Mutex
	sessions map[string]*running
	ports    map[int]bool
	// One lock per session held across a whole Start or Stop, so overlapping
	// requests (a game server restarting mid-build) cannot interleave.
	locks map[string]*sync.Mutex
}

func (o *Orchestrator) sessionLock(id string) *sync.Mutex {
	o.mu.Lock()
	defer o.mu.Unlock()
	if o.locks[id] == nil {
		o.locks[id] = &sync.Mutex{}
	}
	return o.locks[id]
}

type running struct {
	handles    map[string]Handle
	proxies    []*proxy
	containers []string
	network    string
}

// New returns an orchestrator.
func New(cfg Config, eng Engine, st *store.Store) *Orchestrator {
	if cfg.BindAddr == "" {
		cfg.BindAddr = "0.0.0.0"
	}
	if cfg.MaxConns <= 0 {
		cfg.MaxConns = DefaultMaxConns
	}
	if cfg.IdleTimeout <= 0 {
		cfg.IdleTimeout = DefaultIdleTimeout
	}
	return &Orchestrator{cfg: cfg, eng: eng, store: st, Probe: httpProbe, sessions: map[string]*running{}, ports: map[int]bool{}, locks: map[string]*sync.Mutex{}}
}

// ImageTag is the image name for a challenge: room, challenge, room version
// and a hash of the build context, so editing the challenge rebuilds it.
func ImageTag(roomID, challengeID, version, contextHash string) string {
	if version == "" {
		version = "dev"
	}
	return fmt.Sprintf("escapebox/%s-%s:%s-%s", roomID, challengeID, version, contextHash[:12])
}

// Start brings up every challenge for a session and returns their handles.
// Idempotent: a session that is already running returns its handles.
func (o *Orchestrator) Start(ctx context.Context, sessionID, roomID, roomVersion, roomDir string, chs []Challenge) (map[string]Handle, error) {
	l := o.sessionLock(sessionID)
	l.Lock()
	defer l.Unlock()
	o.mu.Lock()
	if r, ok := o.sessions[sessionID]; ok {
		out := cloneHandles(r.handles)
		o.mu.Unlock()
		return out, nil
	}
	o.mu.Unlock()

	r := &running{handles: map[string]Handle{}}
	ok := false
	defer func() {
		if !ok {
			o.teardown(context.WithoutCancel(ctx), sessionID, r)
		}
	}()
	labels := map[string]string{LabelManaged: "1", LabelSession: sessionID}
	if o.cfg.Owner != "" {
		labels[LabelOwner] = o.cfg.Owner
	}
	netName := "esc_" + sessionID
	netID, err := o.eng.CreateNetwork(ctx, docker.NetworkSpec{Name: netName, Internal: true, Labels: labels})
	if err != nil {
		return nil, fmt.Errorf("session network: %w", err)
	}
	r.network = netID
	for _, ch := range chs {
		h, err := o.startOne(ctx, sessionID, roomID, roomVersion, roomDir, netName, netID, labels, ch, r)
		if err != nil {
			return nil, fmt.Errorf("challenge %s: %w", ch.ID, err)
		}
		r.handles[ch.ID] = h
	}
	o.mu.Lock()
	o.sessions[sessionID] = r
	o.mu.Unlock()
	ok = true
	return cloneHandles(r.handles), nil
}

func (o *Orchestrator) startOne(ctx context.Context, sessionID, roomID, roomVersion, roomDir, netName, netID string, labels map[string]string, ch Challenge, r *running) (Handle, error) {
	if len(ch.Ports) == 0 {
		return Handle{}, errors.New("no ports declared")
	}
	buildDir, err := confined(roomDir, ch.Build)
	if err != nil {
		return Handle{}, err
	}
	hash, err := contextHash(buildDir)
	if err != nil {
		return Handle{}, fmt.Errorf("hash build context: %w", err)
	}
	tag := ImageTag(roomID, ch.ID, roomVersion, hash)
	exists, err := o.eng.ImageExists(ctx, tag)
	if err != nil {
		return Handle{}, err
	}
	if !exists {
		slog.Info("building challenge image", "tag", tag)
		if err := o.eng.BuildImage(ctx, buildDir, tag, map[string]string{LabelManaged: "1"}); err != nil {
			return Handle{}, err
		}
	}
	env := map[string]string{}
	if ch.Flag.Type == "per_instance" && ch.Flag.InjectEnv != "" {
		env[ch.Flag.InjectEnv] = flags.PerInstance(o.cfg.Secret, sessionID, ch.ID, ch.Flag.Format)
	}
	cid, err := o.eng.CreateContainer(ctx, docker.ContainerSpec{
		Name: fmt.Sprintf("esc_%s_%s", sessionID, ch.ID), Image: tag, Env: env, Labels: labels,
		Network: netName, CPUs: ch.Resources.CPU, MemoryMB: ch.Resources.MemoryMB, PidsMax: ch.Resources.Pids,
	})
	if err != nil {
		return Handle{}, err
	}
	r.containers = append(r.containers, cid)
	if err := o.eng.StartContainer(ctx, cid); err != nil {
		return Handle{}, err
	}
	info, err := o.eng.InspectContainer(ctx, cid, netName)
	if err != nil {
		return Handle{}, err
	}
	if info.IP == "" {
		return Handle{}, errors.New("container has no address on the session network")
	}
	target := net.JoinHostPort(info.IP, strconv.Itoa(ch.Ports[0].Container))
	if ch.Healthcheck.Path != "" {
		if err := o.waitHealthy(ctx, "http://"+target+ch.Healthcheck.Path, ch.Healthcheck.TimeoutS); err != nil {
			return Handle{}, err
		}
	}
	p, port, err := o.listen()
	if err != nil {
		return Handle{}, err
	}
	p.target = target
	r.proxies = append(r.proxies, p)
	go p.serve()
	if o.store != nil {
		if err := o.store.PutInstance(ctx, store.Instance{SessionID: sessionID, ChallengeID: ch.ID, ContainerID: cid, NetworkID: netID, HostPort: port}); err != nil {
			return Handle{}, err
		}
	}
	h := Handle{Host: o.cfg.AdvertiseHost, Port: port}
	if ch.Ports[0].Protocol == "http" {
		h.URL = fmt.Sprintf("http://%s/", net.JoinHostPort(o.cfg.AdvertiseHost, strconv.Itoa(port)))
	}
	return h, nil
}

// Stop tears a session's challenges down. Flags stay derivable, so a later
// Start gives players the same flags.
func (o *Orchestrator) Stop(ctx context.Context, sessionID string) error {
	l := o.sessionLock(sessionID)
	l.Lock()
	defer l.Unlock()
	o.mu.Lock()
	r := o.sessions[sessionID]
	delete(o.sessions, sessionID)
	o.mu.Unlock()
	if r == nil {
		r = &running{}
	}
	return o.teardown(ctx, sessionID, r)
}

// Handles returns a copy of a running session's handles (nil if not running).
func (o *Orchestrator) Handles(sessionID string) map[string]Handle {
	o.mu.Lock()
	defer o.mu.Unlock()
	if r := o.sessions[sessionID]; r != nil {
		return cloneHandles(r.handles)
	}
	return nil
}

func cloneHandles(in map[string]Handle) map[string]Handle {
	out := make(map[string]Handle, len(in))
	for k, v := range in {
		out[k] = v
	}
	return out
}

func (o *Orchestrator) teardown(ctx context.Context, sessionID string, r *running) error {
	var errs []error
	for _, p := range r.proxies {
		p.close()
		o.mu.Lock()
		delete(o.ports, p.port)
		o.mu.Unlock()
	}
	cs, ns, err := o.eng.ListByLabel(ctx, LabelSession, sessionID)
	if err != nil {
		errs = append(errs, err)
	}
	cs = append(cs, r.containers...)
	if r.network != "" {
		ns = append(ns, r.network)
	}
	for _, id := range uniq(cs) {
		if err := o.eng.RemoveContainer(ctx, id); err != nil {
			errs = append(errs, err)
		}
	}
	for _, id := range uniq(ns) {
		if err := o.eng.RemoveNetwork(ctx, id); err != nil {
			errs = append(errs, err)
		}
	}
	if o.store != nil {
		if err := o.store.DeleteInstances(ctx, sessionID); err != nil {
			errs = append(errs, err)
		}
	}
	return errors.Join(errs...)
}

// Cleanup removes everything a previous platform process left behind
// (its proxies died with it). Call once at start-up.
func (o *Orchestrator) Cleanup(ctx context.Context) error {
	label, value := LabelManaged, "1"
	if o.cfg.Owner != "" {
		label, value = LabelOwner, o.cfg.Owner
	}
	cs, ns, err := o.eng.ListByLabel(ctx, label, value)
	if err != nil {
		return err
	}
	var errs []error
	for _, id := range cs {
		errs = append(errs, o.eng.RemoveContainer(ctx, id))
	}
	for _, id := range ns {
		errs = append(errs, o.eng.RemoveNetwork(ctx, id))
	}
	return errors.Join(errs...)
}

func (o *Orchestrator) waitHealthy(ctx context.Context, url string, timeoutS int) error {
	if timeoutS <= 0 {
		timeoutS = 30
	}
	deadline := time.Now().Add(time.Duration(timeoutS) * time.Second)
	var last error
	for time.Now().Before(deadline) {
		pctx, cancel := context.WithTimeout(ctx, 2*time.Second)
		last = o.Probe(pctx, url)
		cancel()
		if last == nil {
			return nil
		}
		select {
		case <-ctx.Done():
			return ctx.Err()
		case <-time.After(250 * time.Millisecond):
		}
	}
	return fmt.Errorf("not healthy after %ds: %v", timeoutS, last)
}

var probeClient = &http.Client{
	Timeout: 2 * time.Second,
	CheckRedirect: func(*http.Request, []*http.Request) error {
		return http.ErrUseLastResponse
	},
}

func httpProbe(ctx context.Context, url string) error {
	req, err := http.NewRequestWithContext(ctx, http.MethodGet, url, nil)
	if err != nil {
		return err
	}
	resp, err := probeClient.Do(req)
	if err != nil {
		return err
	}
	defer resp.Body.Close()
	if resp.StatusCode != http.StatusOK {
		return fmt.Errorf("health check returned %d", resp.StatusCode)
	}
	return nil
}

// listen grabs the first free port in the configured range.
func (o *Orchestrator) listen() (*proxy, int, error) {
	o.mu.Lock()
	defer o.mu.Unlock()
	for port := o.cfg.PortMin; port <= o.cfg.PortMax; port++ {
		if o.ports[port] {
			continue
		}
		ln, err := net.Listen("tcp", net.JoinHostPort(o.cfg.BindAddr, strconv.Itoa(port)))
		if err != nil {
			continue
		}
		o.ports[port] = true
		return &proxy{
			ln:          ln,
			port:        port,
			maxConns:    o.cfg.MaxConns,
			idleTimeout: o.cfg.IdleTimeout,
			conns:       map[net.Conn]bool{},
		}, port, nil
	}
	return nil, 0, fmt.Errorf("no free port in %d-%d", o.cfg.PortMin, o.cfg.PortMax)
}

// confined resolves rel inside root (including symlinks) and refuses anything
// that escapes it.
func confined(root, rel string) (string, error) {
	if filepath.IsAbs(rel) {
		return "", fmt.Errorf("build path %q escapes the room directory", rel)
	}
	p := filepath.Join(root, rel)
	if !withinDir(root, p) {
		return "", fmt.Errorf("build path %q escapes the room directory", rel)
	}
	rootReal, err := filepath.EvalSymlinks(root)
	if err != nil {
		return "", fmt.Errorf("resolve room directory: %w", err)
	}
	pReal, err := filepath.EvalSymlinks(p)
	if err != nil {
		return "", fmt.Errorf("no build directory %s: %w", p, err)
	}
	if !withinDir(rootReal, pReal) {
		return "", fmt.Errorf("build path %q escapes the room directory", rel)
	}
	dfReal, err := filepath.EvalSymlinks(filepath.Join(pReal, "Dockerfile"))
	if err != nil {
		return "", fmt.Errorf("no Dockerfile in %s", pReal)
	}
	if !withinDir(rootReal, dfReal) {
		return "", fmt.Errorf("Dockerfile in %q escapes the room directory", rel)
	}
	if st, err := os.Stat(dfReal); err != nil || st.IsDir() {
		return "", fmt.Errorf("no Dockerfile in %s", pReal)
	}
	return pReal, nil
}

func withinDir(root, target string) bool {
	r, err := filepath.Rel(root, target)
	if err != nil {
		return false
	}
	return r != ".." && !strings.HasPrefix(r, ".."+string(filepath.Separator))
}

// contextHash hashes every regular file under dir (path + contents).
func contextHash(dir string) (string, error) {
	var files []string
	err := filepath.WalkDir(dir, func(p string, d fs.DirEntry, err error) error {
		if err != nil {
			return err
		}
		if d.Type().IsRegular() {
			files = append(files, p)
		}
		return nil
	})
	if err != nil {
		return "", err
	}
	sort.Strings(files)
	h := sha256.New()
	for _, f := range files {
		rel, _ := filepath.Rel(dir, f)
		io.WriteString(h, filepath.ToSlash(rel)+"\x00")
		b, err := os.ReadFile(f)
		if err != nil {
			return "", err
		}
		h.Write(b)
		h.Write([]byte{0})
	}
	return hex.EncodeToString(h.Sum(nil)), nil
}

func uniq(in []string) []string {
	seen := map[string]bool{}
	var out []string
	for _, s := range in {
		if s != "" && !seen[s] {
			seen[s] = true
			out = append(out, s)
		}
	}
	return out
}

// --- TCP proxy -----------------------------------------------------------------

type proxy struct {
	ln          net.Listener
	port        int
	target      string
	maxConns    int
	idleTimeout time.Duration

	mu     sync.Mutex
	active int
	conns  map[net.Conn]bool
	closed bool
}

func (p *proxy) serve() {
	for {
		c, err := p.ln.Accept()
		if err != nil {
			return
		}
		if !p.acquire(c) {
			c.Close()
			continue
		}
		go p.pipe(c)
	}
}

func (p *proxy) pipe(client net.Conn) {
	var upstream net.Conn
	defer func() {
		client.Close()
		if upstream != nil {
			upstream.Close()
		}
		p.release(client, upstream)
	}()
	u, err := net.DialTimeout("tcp", p.target, 3*time.Second)
	if err != nil {
		return
	}
	upstream = u
	if !p.trackUpstream(upstream) {
		return
	}
	var lastActivity atomic.Int64
	lastActivity.Store(time.Now().UnixNano())
	var wg sync.WaitGroup
	wg.Add(2)
	copyDir := func(dst, src net.Conn) {
		defer wg.Done()
		if err := copyIdle(dst, src, p.idleTimeout, &lastActivity); err != nil {
			client.Close()
			upstream.Close()
			return
		}
		closeWrite(dst)
	}
	go copyDir(upstream, client)
	go copyDir(client, upstream)
	wg.Wait()
}

func copyIdle(dst, src net.Conn, idle time.Duration, lastActivity *atomic.Int64) error {
	buf := make([]byte, 32*1024)
	for {
		if idle > 0 {
			_ = src.SetReadDeadline(time.Now().Add(idle))
		}
		n, rerr := src.Read(buf)
		if n > 0 {
			lastActivity.Store(time.Now().UnixNano())
			if idle > 0 {
				_ = dst.SetWriteDeadline(time.Now().Add(idle))
			}
			if _, werr := dst.Write(buf[:n]); werr != nil {
				return werr
			}
			lastActivity.Store(time.Now().UnixNano())
		}
		if rerr != nil {
			if errors.Is(rerr, io.EOF) {
				return nil
			}
			var ne net.Error
			if idle > 0 && errors.As(rerr, &ne) && ne.Timeout() {
				if time.Since(time.Unix(0, lastActivity.Load())) < idle {
					continue
				}
			}
			return rerr
		}
	}
}

func closeWrite(c net.Conn) {
	if cw, ok := c.(interface{ CloseWrite() error }); ok {
		_ = cw.CloseWrite()
	}
}

func (p *proxy) acquire(client net.Conn) bool {
	p.mu.Lock()
	defer p.mu.Unlock()
	if p.closed || (p.maxConns > 0 && p.active >= p.maxConns) {
		return false
	}
	p.active++
	p.conns[client] = true
	return true
}

func (p *proxy) trackUpstream(upstream net.Conn) bool {
	p.mu.Lock()
	defer p.mu.Unlock()
	if p.closed {
		return false
	}
	p.conns[upstream] = true
	return true
}

func (p *proxy) release(client, upstream net.Conn) {
	p.mu.Lock()
	defer p.mu.Unlock()
	delete(p.conns, client)
	if upstream != nil {
		delete(p.conns, upstream)
	}
	if p.active > 0 {
		p.active--
	}
}

func (p *proxy) close() {
	p.mu.Lock()
	p.closed = true
	conns := p.conns
	p.conns = map[net.Conn]bool{}
	p.mu.Unlock()
	p.ln.Close()
	for c := range conns {
		c.Close()
	}
}
