// Command platform is the escapebox platform service (PLAN.md Section 5):
// sessions, join tokens, game server processes, snapshots, flags and
// challenge containers, over HTTP (docs/API.md).
package main

import (
	"context"
	"crypto/rand"
	"errors"
	"flag"
	"fmt"
	"log/slog"
	"net"
	"net/http"
	"os"
	"os/signal"
	"path/filepath"
	"strconv"
	"strings"
	"syscall"
	"time"

	"github.com/binaryc0de/escapebox/platform/internal/api"
	"github.com/binaryc0de/escapebox/platform/internal/docker"
	"github.com/binaryc0de/escapebox/platform/internal/flags"
	"github.com/binaryc0de/escapebox/platform/internal/orchestrator"
	"github.com/binaryc0de/escapebox/platform/internal/rooms"
	"github.com/binaryc0de/escapebox/platform/internal/sessions"
	"github.com/binaryc0de/escapebox/platform/internal/store"
)

func main() {
	if err := run(); err != nil {
		slog.Error("platform stopped", "err", err)
		os.Exit(1)
	}
}

func run() error {
	addr := flag.String("addr", ":8080", "HTTP listen address")
	dataDir := flag.String("data", "data", "data directory (database, platform secret)")
	roomsDir := flag.String("rooms", "game/rooms", "installed rooms (each <id>/room.json)")
	drafts := flag.Bool("drafts", false, "also offer draft rooms (room.yaml draft: true, ADR-0030); for a private development platform, never the public one")
	godot := flag.String("godot", "godot", "Godot binary used to run game servers")
	gameDir := flag.String("game", "game", "Godot project directory for game servers")
	advertise := flag.String("advertise", "", "address players' machines use to reach this host (default: auto-detect the LAN address)")
	platformURL := flag.String("platform-url", "", "how game servers reach this platform (default http://127.0.0.1:<addr port>)")
	gamePorts := flag.String("game-ports", "7777-7799", "UDP/TCP port range for game servers")
	challengePorts := flag.String("challenge-ports", "20000-20999", "TCP port range for challenge proxies")
	transport := flag.String("transport", "enet", "game transport for clients: enet or ws")
	mediaDir := flag.String("media", "", "serve per-room intro videos from this directory (media/rooms/<id>/intro.mp4, poster.jpg)")
	packsDir := flag.String("packs", "", "serve room packs built by tools/packroom from this directory (catalog + /download/packs/, ADR-0025)")
	maxGames := flag.Int("max-games", 4, "most games (sessions not finished) at once; 0 = no cap")
	expireAfter := flag.Duration("expire-unjoined", 30*time.Minute, "finish games nobody joined after this long")
	abandonAfter := flag.Duration("expire-abandoned", 12*time.Hour, "finish idle games (players left, no server) this long after they were created")
	publicURL := flag.String("public-url", "", "HTTPS origin players use (e.g. https://host.tailnet.ts.net); challenge cards then go through this platform's /ctf/ proxy (ADR-0029)")
	webDir := flag.String("web", "", "serve the exported browser client from this directory at /play/ (ADR-0023)")
	testTrust := flag.Bool("test-trust-positions", false, "TEST ONLY: start game servers with --trust-positions so headless bots can teleport")
	flag.Parse()

	ctx, stop := signal.NotifyContext(context.Background(), os.Interrupt, syscall.SIGTERM)
	defer stop()

	if err := os.MkdirAll(*dataDir, 0o700); err != nil {
		return err
	}
	secret, err := loadSecret(filepath.Join(*dataDir, "secret.key"))
	if err != nil {
		return err
	}
	st, err := store.Open(ctx, filepath.Join(*dataDir, "platform.db"))
	if err != nil {
		return err
	}
	defer st.Close()
	if n, err := st.ResetLiveStatuses(ctx); err != nil {
		return err
	} else if n > 0 {
		slog.Info("games from the previous run marked idle (restorable on rejoin)", "count", n)
	}
	load := rooms.Load
	if *drafts {
		load = rooms.LoadWithDrafts
	}
	cat, err := load(*roomsDir)
	if err != nil {
		return fmt.Errorf("rooms: %w", err)
	}
	host := *advertise
	if host == "" {
		host = lanAddress()
	}
	gmin, gmax, err := portRange(*gamePorts)
	if err != nil {
		return err
	}
	cmin, cmax, err := portRange(*challengePorts)
	if err != nil {
		return err
	}
	if *platformURL == "" {
		_, port, _ := net.SplitHostPort(*addr)
		*platformURL = "http://127.0.0.1:" + port
	}
	gameAbs, _ := filepath.Abs(*gameDir)
	var extra []string
	if *testTrust {
		slog.Warn("TEST MODE: game servers accept teleporting positions (--test-trust-positions)")
		extra = append(extra, "--trust-positions")
	}
	deps := &api.Deps{Store: st, Rooms: cat, Limiter: flags.NewLimiter(), Secret: secret, AdvertiseHost: host, WebDir: *webDir, PacksDir: *packsDir, MediaDir: *mediaDir,
		MaxGames: *maxGames, CreateLimit: &api.RateLimit{Max: 6, Window: 10 * time.Minute},
		JoinLimit: &api.RateLimit{Max: 30, Window: time.Minute}, PublicURL: *publicURL}
	mgr := sessions.New(sessions.Config{
		Command:     []string{*godot, "--headless", "--path", gameAbs, "--"},
		PortMin:     gmin,
		PortMax:     gmax,
		PlatformURL: *platformURL,
		Transport:   *transport,
		ExtraArgs:   extra,
		OnStopped: func(id string) {
			if orch := deps.Orchestrator; orch != nil {
				c, cancel := context.WithTimeout(context.Background(), time.Minute)
				defer cancel()
				if err := orch.Stop(c, id); err != nil {
					slog.Warn("challenge teardown after the game server stopped", "session", id, "err", err)
				}
			}
		},
	}, st)
	defer mgr.Close()

	deps.Servers = mgr
	if orch, err := startOrchestrator(ctx, host, cmin, cmax, secret, st, orchestrator.OwnerFor(*dataDir)); err != nil {
		slog.Warn("challenge containers disabled: Docker is not reachable", "err", err)
	} else {
		deps.Orchestrator = orch
		defer func() {
			c, cancel := context.WithTimeout(context.Background(), 30*time.Second)
			defer cancel()
			_ = orch.Cleanup(c)
		}()
	}

	go func() {
		t := time.NewTicker(time.Minute)
		defer t.Stop()
		for {
			select {
			case <-ctx.Done():
				return
			case <-t.C:
				if n, err := st.ExpireAbandoned(ctx, time.Now().Add(-*abandonAfter)); err != nil {
					slog.Warn("expiring abandoned games", "err", err)
				} else if n > 0 {
					slog.Info("abandoned games finished", "count", n)
				}
				ids, err := st.ExpireUnjoined(ctx, time.Now().Add(-*expireAfter))
				if err != nil {
					slog.Warn("expiring unjoined games", "err", err)
				}
				for _, id := range ids {
					slog.Info("game expired: nobody joined", "session", id)
				}
			}
		}
	}()
	srv := &http.Server{Addr: *addr, Handler: api.NewHandler(deps), ReadHeaderTimeout: 10 * time.Second}
	go func() {
		<-ctx.Done()
		shutdown, cancel := context.WithTimeout(context.Background(), 10*time.Second)
		defer cancel()
		_ = srv.Shutdown(shutdown)
	}()
	names := []string{}
	for _, r := range cat.All() {
		names = append(names, r.ID)
	}
	slog.Info("platform listening", "addr", *addr, "version", api.Version, "advertise", host, "rooms", strings.Join(names, ","), "hidden_drafts", strings.Join(cat.Hidden(), ","), "challenges", deps.Orchestrator != nil)
	if err := srv.ListenAndServe(); err != nil && !errors.Is(err, http.ErrServerClosed) {
		return err
	}
	return nil
}

func startOrchestrator(ctx context.Context, host string, pmin, pmax int, secret []byte, st *store.Store, owner string) (*orchestrator.Orchestrator, error) {
	dc, err := docker.FromEnv()
	if err != nil {
		return nil, err
	}
	pctx, cancel := context.WithTimeout(ctx, 3*time.Second)
	defer cancel()
	if err := dc.Ping(pctx); err != nil {
		return nil, err
	}
	o := orchestrator.New(orchestrator.Config{AdvertiseHost: host, BindAddr: "0.0.0.0", PortMin: pmin, PortMax: pmax, Secret: secret, Owner: owner}, dc, st)
	if err := o.Cleanup(ctx); err != nil {
		slog.Warn("cleanup of old challenge containers", "err", err)
	}
	return o, nil
}

// loadSecret reads the platform secret, creating a random one (0600) on first run.
func loadSecret(path string) ([]byte, error) {
	b, err := os.ReadFile(path)
	if err == nil && len(b) >= 32 {
		return b, nil
	}
	if err != nil && !errors.Is(err, os.ErrNotExist) {
		return nil, err
	}
	b = make([]byte, 32)
	if _, err := rand.Read(b); err != nil {
		return nil, err
	}
	if err := os.WriteFile(path, b, 0o600); err != nil {
		return nil, err
	}
	return b, nil
}

// lanAddress finds the address of the interface used for outbound traffic
// (no packet is sent), falling back to 127.0.0.1.
func lanAddress() string {
	c, err := net.Dial("udp", "192.0.2.1:9")
	if err != nil {
		return "127.0.0.1"
	}
	defer c.Close()
	return c.LocalAddr().(*net.UDPAddr).IP.String()
}

func portRange(s string) (int, int, error) {
	a, b, ok := strings.Cut(s, "-")
	lo, err1 := strconv.Atoi(a)
	hi, err2 := strconv.Atoi(b)
	if !ok || err1 != nil || err2 != nil || lo < 1 || hi > 65535 || lo > hi {
		return 0, 0, fmt.Errorf("bad port range %q (want like 7777-7799)", s)
	}
	return lo, hi, nil
}
