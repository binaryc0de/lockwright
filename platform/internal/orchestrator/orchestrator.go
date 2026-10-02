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
	"time"

	"github.com/binaryc0de/escapebox/platform/internal/docker"
	"github.com/binaryc0de/escapebox/platform/internal/flags"
	"github.com/binaryc0de/escapebox/platform/internal/store"
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
	Host string `json:"host"`
	Port int    `json:"port"`
	Note string `json:"note,omitempty"`
}

// Config tunes the orchestrator.
type Config struct {
	AdvertiseHost string // address players' machines use to reach this host
	BindAddr      string // where proxy ports listen ("0.0.0.0" for the LAN)
	PortMin       int
	PortMax       int
	Secret        []byte // platform secret for per-instance flags
}

// Labels on everything the orchestrator creates.
const (
	LabelManaged = "escapebox.managed"
	LabelSession = "escapebox.session"
)

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
	return &Orchestrator{cfg: cfg, eng: eng, store: st, Probe: httpProbe, sessions: map[string]*running{}, ports: map[int]bool{}}
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
	o.mu.Lock()
	if r, ok := o.sessions[sessionID]; ok {
		o.mu.Unlock()
		return r.handles, nil
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
	return r.handles, nil
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
		Network: netName, CPUs: ch.Resources.CPU, MemoryMB: ch.Resources.MemoryMB,
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
	o.mu.Lock()
	r := o.sessions[sessionID]
	delete(o.sessions, sessionID)
	o.mu.Unlock()
	if r == nil {
		r = &running{}
	}
	return o.teardown(ctx, sessionID, r)
}

// Handles returns a running session's handles (nil if not running).
func (o *Orchestrator) Handles(sessionID string) map[string]Handle {
	o.mu.Lock()
	defer o.mu.Unlock()
	if r := o.sessions[sessionID]; r != nil {
		return r.handles
	}
	return nil
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
	cs, ns, err := o.eng.ListByLabel(ctx, LabelManaged, "1")
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

func httpProbe(ctx context.Context, url string) error {
	req, _ := http.NewRequestWithContext(ctx, http.MethodGet, url, nil)
	resp, err := http.DefaultClient.Do(req)
	if err != nil {
		return err
	}
	resp.Body.Close()
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
		return &proxy{ln: ln, port: port, conns: map[net.Conn]bool{}}, port, nil
	}
	return nil, 0, fmt.Errorf("no free port in %d-%d", o.cfg.PortMin, o.cfg.PortMax)
}

// confined resolves rel inside root and refuses anything that escapes it.
func confined(root, rel string) (string, error) {
	p := filepath.Join(root, rel)
	r, err := filepath.Rel(root, p)
	if err != nil || r == ".." || strings.HasPrefix(r, ".."+string(filepath.Separator)) || filepath.IsAbs(rel) {
		return "", fmt.Errorf("build path %q escapes the room directory", rel)
	}
	if st, err := os.Stat(filepath.Join(p, "Dockerfile")); err != nil || st.IsDir() {
		return "", fmt.Errorf("no Dockerfile in %s", p)
	}
	return p, nil
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
	ln     net.Listener
	port   int
	target string

	mu     sync.Mutex
	conns  map[net.Conn]bool
	closed bool
}

func (p *proxy) serve() {
	for {
		c, err := p.ln.Accept()
		if err != nil {
			return
		}
		go p.pipe(c)
	}
}

func (p *proxy) pipe(client net.Conn) {
	upstream, err := net.DialTimeout("tcp", p.target, 3*time.Second)
	if err != nil {
		client.Close()
		return
	}
	if !p.track(client, upstream) {
		client.Close()
		upstream.Close()
		return
	}
	done := make(chan struct{}, 2)
	go func() { io.Copy(upstream, client); done <- struct{}{} }()
	go func() { io.Copy(client, upstream); done <- struct{}{} }()
	<-done
	client.Close()
	upstream.Close()
	<-done
	p.untrack(client, upstream)
}

func (p *proxy) track(cs ...net.Conn) bool {
	p.mu.Lock()
	defer p.mu.Unlock()
	if p.closed {
		return false
	}
	for _, c := range cs {
		p.conns[c] = true
	}
	return true
}

func (p *proxy) untrack(cs ...net.Conn) {
	p.mu.Lock()
	defer p.mu.Unlock()
	for _, c := range cs {
		delete(p.conns, c)
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
