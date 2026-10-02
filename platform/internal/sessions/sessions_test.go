package sessions

import (
	"context"
	"slices"
	"sync"
	"testing"
	"time"

	"github.com/binaryc0de/escapebox/platform/internal/store"
)

// fakeProc exits when told to, with a chosen code.
type fakeProc struct {
	exit chan int
	once sync.Once
}

func (f *fakeProc) Wait() (int, error) { return <-f.exit, nil }
func (f *fakeProc) Kill() error        { f.once.Do(func() { f.exit <- -9 }); return nil }
func (f *fakeProc) end(code int)       { f.once.Do(func() { f.exit <- code }) }

type launches struct {
	mu    sync.Mutex
	args  [][]string
	procs []*fakeProc
}

func (l *launches) launcher(_ context.Context, args []string) (Process, error) {
	l.mu.Lock()
	defer l.mu.Unlock()
	p := &fakeProc{exit: make(chan int, 1)}
	l.args = append(l.args, args)
	l.procs = append(l.procs, p)
	return p, nil
}

func (l *launches) count() int {
	l.mu.Lock()
	defer l.mu.Unlock()
	return len(l.procs)
}

func (l *launches) last() *fakeProc {
	l.mu.Lock()
	defer l.mu.Unlock()
	return l.procs[len(l.procs)-1]
}

func setup(t *testing.T) (*Manager, *launches, *store.Store, store.Session) {
	t.Helper()
	st, _ := store.Open(context.Background(), ":memory:")
	t.Cleanup(func() { st.Close() })
	sess, _ := st.CreateSession(context.Background(), "night_shift")
	l := &launches{}
	m := NewWithLauncher(Config{Command: []string{"godot", "--headless", "--path", "game", "--"}, PortMin: 27777, PortMax: 27790,
		PlatformURL: "http://127.0.0.1:8080", PackFor: func(string) string { return "/packs/night_shift.pck" }}, st, l.launcher)
	t.Cleanup(m.Close)
	return m, l, st, sess
}

func waitFor(t *testing.T, cond func() bool) {
	t.Helper()
	for i := 0; i < 200; i++ {
		if cond() {
			return
		}
		time.Sleep(5 * time.Millisecond)
	}
	t.Fatal("condition not reached")
}

func TestStartsOnceWithTheRightArguments(t *testing.T) {
	ctx := context.Background()
	m, l, st, sess := setup(t)
	port, err := m.EnsureRunning(ctx, sess)
	if err != nil || port < 27777 || port > 27790 {
		t.Fatalf("port %d err %v", port, err)
	}
	if again, _ := m.EnsureRunning(ctx, sess); again != port || l.count() != 1 {
		t.Fatalf("second EnsureRunning started another server")
	}
	args := l.args[0]
	for _, want := range [][]string{{"--session", sess.ID}, {"--room", "night_shift"}, {"--token", sess.ServerToken}, {"--platform", "http://127.0.0.1:8080"}, {"--pack", "/packs/night_shift.pck"}, {"--transport", "enet"}} {
		i := slices.Index(args, want[0])
		if i < 0 || args[i+1] != want[1] {
			t.Fatalf("args %v missing %v", args, want)
		}
	}
	if args[0] != "godot" || !slices.Contains(args, "--server") {
		t.Fatalf("command %v", args)
	}
	if s, _ := st.Session(ctx, sess.ID); s.Status != store.StatusRunning {
		t.Fatalf("status %s", s.Status)
	}
}

func TestIdleExitWaitsForTheNextJoin(t *testing.T) {
	ctx := context.Background()
	m, l, st, sess := setup(t)
	m.EnsureRunning(ctx, sess)
	l.last().end(0)
	waitFor(t, func() bool { return m.Port(sess.ID) == 0 })
	if s, _ := st.Session(ctx, sess.ID); s.Status != store.StatusIdle {
		t.Fatalf("status after idle exit %s", s.Status)
	}
	if l.count() != 1 {
		t.Fatal("idle exit restarted the server")
	}
	m.EnsureRunning(ctx, sess)
	if l.count() != 2 {
		t.Fatal("join after idle did not restart")
	}
}

func TestCrashRestartsAtMostThreeTimes(t *testing.T) {
	ctx := context.Background()
	m, l, _, sess := setup(t)
	m.EnsureRunning(ctx, sess)
	for i := 1; i <= MaxCrashes; i++ {
		l.last().end(1)
		waitFor(t, func() bool { return l.count() == i+1 })
	}
	l.last().end(1)
	waitFor(t, func() bool { return m.Port(sess.ID) == 0 })
	time.Sleep(30 * time.Millisecond)
	if l.count() != MaxCrashes+1 {
		t.Fatalf("restarted %d times, want %d", l.count()-1, MaxCrashes)
	}
}

func TestPortsAreDistinctPerSession(t *testing.T) {
	ctx := context.Background()
	m, _, st, a := setup(t)
	b, _ := st.CreateSession(ctx, "night_shift")
	pa, _ := m.EnsureRunning(ctx, a)
	pb, _ := m.EnsureRunning(ctx, b)
	if pa == pb {
		t.Fatalf("two sessions share port %d", pa)
	}
	m.Stop(a.ID)
	if m.Port(a.ID) != 0 {
		t.Fatal("Stop left the session running")
	}
}

func TestFinishedSessionStaysFinishedAndTeardownHookRuns(t *testing.T) {
	ctx := context.Background()
	st, _ := store.Open(ctx, ":memory:")
	defer st.Close()
	sess, _ := st.CreateSession(ctx, "night_shift")
	l := &launches{}
	stopped := make(chan string, 4)
	m := NewWithLauncher(Config{Command: []string{"godot"}, PortMin: 27791, PortMax: 27799,
		OnStopped: func(id string) { stopped <- id }}, st, l.launcher)
	defer m.Close()
	st.Finish(ctx, sess.ID, true, 100, 0)
	m.EnsureRunning(ctx, sess)
	if s, _ := st.Session(ctx, sess.ID); s.Status != store.StatusFinished {
		t.Fatalf("restart for viewing changed status to %s", s.Status)
	}
	l.last().end(0)
	select {
	case id := <-stopped:
		if id != sess.ID {
			t.Fatalf("hook for %s", id)
		}
	case <-time.After(2 * time.Second):
		t.Fatal("OnStopped not called after idle exit")
	}
	if s, _ := st.Session(ctx, sess.ID); s.Status != store.StatusFinished {
		t.Fatalf("idle exit changed a finished session to %s", s.Status)
	}
}
