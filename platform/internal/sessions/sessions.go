// Package sessions runs one game server process per active session (PLAN.md
// 7.1, 7.3, docs/API.md "Session manager"): start on first join, restart on
// the next join after an idle exit (code 0), restart after a crash at most
// MaxCrashes times per CrashWindow.
package sessions

import (
	"context"
	"errors"
	"fmt"
	"log/slog"
	"net"
	"os"
	"os/exec"
	"strconv"
	"sync"
	"time"

	"github.com/binaryc0de/lockwright/platform/internal/store"
)

// Crash restart policy.
const (
	MaxCrashes  = 3
	CrashWindow = 10 * time.Minute
)

// Config tells the manager how to launch game servers.
type Config struct {
	// Command is the game server command before the game's own arguments,
	// e.g. ["godot", "--headless", "--path", "/srv/escapebox/game", "--"].
	Command     []string
	PortMin     int    // game ports, e.g. 7777
	PortMax     int    // e.g. 7799
	PlatformURL string // how game servers reach this platform, e.g. http://127.0.0.1:8080
	Transport   string // "enet" | "ws"
	// PackFor returns the --pack path for a room ("" = load from the game's rooms/).
	PackFor func(roomID string) string
	// ExtraArgs are appended to every game server's arguments (tests only).
	ExtraArgs []string
	// OnStopped runs (in its own goroutine) when a session's game server is
	// gone for good: idle exit or crash limit. The platform tears the
	// session's challenge containers down there (review M3-P2).
	OnStopped func(sessionID string)
}

// Process is a running game server (os/exec in production, fakes in tests).
type Process interface {
	Wait() (exitCode int, err error)
	Kill() error
}

// Launcher starts a game server process.
type Launcher func(ctx context.Context, args []string) (Process, error)

// Manager owns game server processes. Safe for concurrent use.
type Manager struct {
	cfg    Config
	store  *store.Store
	launch Launcher
	now    func() time.Time

	mu      sync.Mutex
	running map[string]*proc
	crashes map[string][]time.Time
	closed  bool
}

type proc struct {
	port int
	p    Process
	done chan struct{}
}

// New returns a manager that launches real processes.
func New(cfg Config, st *store.Store) *Manager {
	return NewWithLauncher(cfg, st, ExecLauncher)
}

// NewWithLauncher is New with an injectable launcher (tests).
func NewWithLauncher(cfg Config, st *store.Store, l Launcher) *Manager {
	if cfg.Transport == "" {
		cfg.Transport = "enet"
	}
	return &Manager{cfg: cfg, store: st, launch: l, now: time.Now, running: map[string]*proc{}, crashes: map[string][]time.Time{}}
}

// Port returns the game port of a running session (0 if not running).
func (m *Manager) Port(sessionID string) int {
	m.mu.Lock()
	defer m.mu.Unlock()
	if p := m.running[sessionID]; p != nil {
		return p.port
	}
	return 0
}

// Transport is the game transport clients should use.
func (m *Manager) Transport() string { return m.cfg.Transport }

// EnsureRunning starts the session's game server if needed and returns its port.
func (m *Manager) EnsureRunning(ctx context.Context, sess store.Session) (int, error) {
	m.mu.Lock()
	defer m.mu.Unlock()
	if m.closed {
		return 0, errors.New("platform is shutting down")
	}
	if p := m.running[sess.ID]; p != nil {
		return p.port, nil
	}
	return m.startLocked(ctx, sess)
}

func (m *Manager) startLocked(ctx context.Context, sess store.Session) (int, error) {
	port, err := m.freePortLocked()
	if err != nil {
		return 0, err
	}
	args := []string{"--server", "--session", sess.ID, "--room", sess.RoomID,
		"--port", strconv.Itoa(port), "--transport", m.cfg.Transport,
		"--platform", m.cfg.PlatformURL, "--token", sess.ServerToken}
	if m.cfg.PackFor != nil {
		if pack := m.cfg.PackFor(sess.RoomID); pack != "" {
			args = append(args, "--pack", pack)
		}
	}
	if sess.Difficulty != "" {
		args = append(args, "--difficulty", sess.Difficulty)
	}
	args = append(args, m.cfg.ExtraArgs...)
	p, err := m.launch(context.WithoutCancel(ctx), append(append([]string{}, m.cfg.Command...), args...))
	if err != nil {
		return 0, fmt.Errorf("start game server: %w", err)
	}
	pr := &proc{port: port, p: p, done: make(chan struct{})}
	m.running[sess.ID] = pr
	if m.store != nil {
		// A finished session reopened for post-game viewing stays finished.
		if cur, err := m.store.Session(ctx, sess.ID); err == nil && cur.Status != store.StatusFinished {
			_ = m.store.SetStatus(ctx, sess.ID, store.StatusRunning)
		}
	}
	slog.Info("game server started", "session", sess.ID, "room", sess.RoomID, "port", port)
	go m.watch(sess, pr)
	return port, nil
}

func (m *Manager) watch(sess store.Session, pr *proc) {
	code, err := pr.p.Wait()
	close(pr.done)
	m.mu.Lock()
	defer m.mu.Unlock()
	if m.running[sess.ID] != pr {
		return // stopped on purpose (Stop/Close), not a crash or idle exit
	}
	delete(m.running, sess.ID)
	if m.closed {
		return
	}
	ctx := context.Background()
	if code == 0 && err == nil {
		slog.Info("game server idle-stopped", "session", sess.ID)
		if m.store != nil {
			if cur, e := m.store.Session(ctx, sess.ID); e == nil && cur.Status != store.StatusFinished {
				_ = m.store.SetStatus(ctx, sess.ID, store.StatusIdle)
			}
		}
		m.stopped(sess.ID)
		return
	}
	now := m.now()
	recent := m.crashes[sess.ID][:0]
	for _, t := range m.crashes[sess.ID] {
		if now.Sub(t) < CrashWindow {
			recent = append(recent, t)
		}
	}
	recent = append(recent, now)
	m.crashes[sess.ID] = recent
	if len(recent) > MaxCrashes {
		slog.Error("game server keeps crashing; giving up until the next join", "session", sess.ID, "code", code, "err", err)
		if m.store != nil {
			if cur, e := m.store.Session(ctx, sess.ID); e == nil && cur.Status != store.StatusFinished {
				_ = m.store.SetStatus(ctx, sess.ID, store.StatusIdle)
			}
		}
		m.stopped(sess.ID)
		return
	}
	slog.Warn("game server crashed; restarting from the last snapshot", "session", sess.ID, "code", code, "err", err)
	if _, e := m.startLocked(ctx, sess); e != nil {
		slog.Error("restart failed", "session", sess.ID, "err", e)
	}
}

func (m *Manager) stopped(sessionID string) {
	if m.cfg.OnStopped != nil {
		go m.cfg.OnStopped(sessionID)
	}
}

// Stop kills a session's game server (finished sessions, tests).
func (m *Manager) Stop(sessionID string) {
	m.mu.Lock()
	pr := m.running[sessionID]
	delete(m.running, sessionID)
	m.mu.Unlock()
	if pr != nil {
		_ = pr.p.Kill()
		<-pr.done
	}
}

// Close kills every game server; game servers save snapshots continuously,
// so the next platform start resumes them on join.
func (m *Manager) Close() {
	m.mu.Lock()
	m.closed = true
	all := m.running
	m.running = map[string]*proc{}
	m.mu.Unlock()
	for _, pr := range all {
		_ = pr.p.Kill()
		<-pr.done
	}
}

// freePortLocked picks a game port nobody (not even another program) uses.
func (m *Manager) freePortLocked() (int, error) {
	used := map[int]bool{}
	for _, p := range m.running {
		used[p.port] = true
	}
	for port := m.cfg.PortMin; port <= m.cfg.PortMax; port++ {
		if used[port] || !udpFree(port) {
			continue
		}
		return port, nil
	}
	return 0, fmt.Errorf("no free game port in %d-%d", m.cfg.PortMin, m.cfg.PortMax)
}

func udpFree(port int) bool {
	c, err := net.ListenPacket("udp", ":"+strconv.Itoa(port))
	if err != nil {
		return false
	}
	c.Close()
	l, err := net.Listen("tcp", ":"+strconv.Itoa(port))
	if err != nil {
		return false
	}
	l.Close()
	return true
}

// ExecLauncher runs the game server as a child process, logging its output.
func ExecLauncher(ctx context.Context, args []string) (Process, error) {
	cmd := exec.CommandContext(ctx, args[0], args[1:]...)
	cmd.Stdout = os.Stdout
	cmd.Stderr = os.Stderr
	if err := cmd.Start(); err != nil {
		return nil, err
	}
	return execProc{cmd}, nil
}

type execProc struct{ cmd *exec.Cmd }

func (e execProc) Wait() (int, error) {
	err := e.cmd.Wait()
	var ee *exec.ExitError
	if errors.As(err, &ee) {
		return ee.ExitCode(), nil
	}
	if err != nil {
		return -1, err
	}
	return 0, nil
}

func (e execProc) Kill() error { return e.cmd.Process.Kill() }
