package docker

import (
	"archive/tar"
	"bytes"
	"context"
	"encoding/json"
	"errors"
	"io"
	"net"
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"strings"
	"sync"
	"testing"
)

// fakeEngine records requests and answers like the Docker Engine.
type fakeEngine struct {
	mu       sync.Mutex
	requests []string
	bodies   map[string][]byte
}

func (f *fakeEngine) ServeHTTP(w http.ResponseWriter, r *http.Request) {
	f.mu.Lock()
	b, _ := io.ReadAll(r.Body)
	key := r.Method + " " + strings.TrimPrefix(r.URL.Path, "/"+APIVersion)
	f.requests = append(f.requests, key+"?"+r.URL.RawQuery)
	if f.bodies == nil {
		f.bodies = map[string][]byte{}
	}
	f.bodies[key] = b
	f.mu.Unlock()
	switch {
	case key == "GET /_ping":
		w.Write([]byte("OK"))
	case key == "GET /images/present:1/json":
		w.Write([]byte(`{}`))
	case strings.HasPrefix(key, "GET /images/"):
		http.Error(w, `{"message":"No such image"}`, 404)
	case key == "POST /build":
		if r.URL.Query().Get("t") == "broken:1" {
			w.Write([]byte("{\"stream\":\"Step 1/2\"}\n{\"error\":\"RUN false: exit 1\"}\n"))
			return
		}
		w.Write([]byte("{\"stream\":\"Successfully built\"}\n"))
	case key == "POST /networks/create":
		w.Write([]byte(`{"Id":"net123"}`))
	case key == "POST /containers/create":
		w.Write([]byte(`{"Id":"ctr123"}`))
	case key == "POST /containers/ctr123/start":
		w.WriteHeader(204)
	case key == "GET /containers/ctr123/json":
		w.Write([]byte(`{"State":{"Running":true},"NetworkSettings":{"Networks":{"esc_s1":{"IPAddress":"172.30.0.2"}}}}`))
	case strings.HasPrefix(key, "DELETE /containers/gone"), strings.HasPrefix(key, "DELETE /networks/gone"):
		http.Error(w, `{"message":"no such"}`, 404)
	case strings.HasPrefix(key, "DELETE "):
		w.WriteHeader(204)
	case key == "GET /containers/json":
		w.Write([]byte(`[{"Id":"c1"},{"Id":"c2"}]`))
	case key == "GET /networks":
		w.Write([]byte(`[{"Id":"n1"}]`))
	default:
		http.Error(w, `{"message":"unexpected `+key+`"}`, 500)
	}
}

func client(t *testing.T) (*Client, *fakeEngine) {
	t.Helper()
	f := &fakeEngine{}
	ts := httptest.NewServer(f)
	t.Cleanup(ts.Close)
	c, err := New("tcp://" + strings.TrimPrefix(ts.URL, "http://"))
	if err != nil {
		t.Fatal(err)
	}
	return c, f
}

func TestContainerIsHardened(t *testing.T) {
	c, f := client(t)
	ctx := context.Background()
	id, err := c.CreateContainer(ctx, ContainerSpec{
		Name: "esc_s1_intranet", Image: "escapebox/night_shift-intranet:0.1.0", Network: "esc_s1",
		Env: map[string]string{"FLAG": "secret"}, CPUs: 0.5, MemoryMB: 256,
		Labels: map[string]string{"escapebox.session": "s1"},
	})
	if err != nil || id != "ctr123" {
		t.Fatalf("create: %q %v", id, err)
	}
	var body struct {
		Image      string
		Env        []string
		HostConfig struct {
			NetworkMode    string
			CapDrop        []string
			SecurityOpt    []string
			ReadonlyRootfs bool
			PidsLimit      int
			Memory         int64
			NanoCpus       int64
			Privileged     bool
		}
	}
	if err := json.Unmarshal(f.bodies["POST /containers/create"], &body); err != nil {
		t.Fatal(err)
	}
	h := body.HostConfig
	if h.NetworkMode != "esc_s1" || len(h.CapDrop) != 1 || h.CapDrop[0] != "ALL" ||
		len(h.SecurityOpt) != 1 || h.SecurityOpt[0] != "no-new-privileges:true" || !h.ReadonlyRootfs ||
		h.PidsLimit != 128 || h.Memory != 256<<20 || h.NanoCpus != 5e8 || h.Privileged {
		t.Fatalf("not hardened: %+v", h)
	}
	if len(body.Env) != 1 || body.Env[0] != "FLAG=secret" {
		t.Fatalf("env %v", body.Env)
	}
	if !strings.Contains(f.requests[0], "name=esc_s1_intranet") {
		t.Fatalf("name not passed: %v", f.requests)
	}
}

func TestNetworkIsInternal(t *testing.T) {
	c, f := client(t)
	id, err := c.CreateNetwork(context.Background(), NetworkSpec{Name: "esc_s1", Internal: true, Labels: map[string]string{"a": "b"}})
	if err != nil || id != "net123" {
		t.Fatalf("network %q %v", id, err)
	}
	var body map[string]any
	json.Unmarshal(f.bodies["POST /networks/create"], &body)
	if body["Internal"] != true || body["Name"] != "esc_s1" {
		t.Fatalf("network body %v", body)
	}
}

func TestImagesBuildsInspectRemove(t *testing.T) {
	c, f := client(t)
	ctx := context.Background()
	if err := c.Ping(ctx); err != nil {
		t.Fatal(err)
	}
	if ok, err := c.ImageExists(ctx, "present:1"); !ok || err != nil {
		t.Fatalf("present image: %v %v", ok, err)
	}
	if ok, err := c.ImageExists(ctx, "absent:1"); ok || err != nil {
		t.Fatalf("absent image: %v %v", ok, err)
	}
	dir := t.TempDir()
	os.WriteFile(filepath.Join(dir, "Dockerfile"), []byte("FROM scratch\n"), 0o644)
	if err := c.BuildImage(ctx, dir, "ok:1", nil); err != nil {
		t.Fatal(err)
	}
	if err := c.BuildImage(ctx, dir, "broken:1", nil); err == nil || !strings.Contains(err.Error(), "RUN false") {
		t.Fatalf("build error not surfaced: %v", err)
	}
	if !bytes.Contains(f.bodies["POST /build"], []byte("FROM scratch")) {
		t.Fatal("build context missing the Dockerfile")
	}
	info, err := c.InspectContainer(ctx, "ctr123", "esc_s1")
	if err != nil || !info.Running || info.IP != "172.30.0.2" {
		t.Fatalf("inspect %+v %v", info, err)
	}
	if err := c.StartContainer(ctx, "ctr123"); err != nil {
		t.Fatal(err)
	}
	if err := c.RemoveContainer(ctx, "gone"); err != nil {
		t.Fatalf("removing a missing container should succeed: %v", err)
	}
	if err := c.RemoveNetwork(ctx, "gone"); err != nil {
		t.Fatalf("removing a missing network should succeed: %v", err)
	}
	cs, ns, err := c.ListByLabel(ctx, "escapebox.managed", "1")
	if err != nil || len(cs) != 2 || len(ns) != 1 {
		t.Fatalf("list %v %v %v", cs, ns, err)
	}
	if _, err := c.do(ctx, "GET", "/nothing-here", nil, nil, ""); err == nil || errors.Is(err, ErrNotFound) {
		t.Fatalf("500 should be an error with a message, got %v", err)
	}
}

func TestUnixSocketTransport(t *testing.T) {
	sock := filepath.Join(t.TempDir(), "d.sock")
	l, err := net.Listen("unix", sock)
	if err != nil {
		t.Skip("unix sockets unavailable:", err)
	}
	srv := &http.Server{Handler: &fakeEngine{}}
	go srv.Serve(l)
	t.Cleanup(func() { srv.Close() })
	c, err := New("unix://" + sock)
	if err != nil {
		t.Fatal(err)
	}
	if err := c.Ping(context.Background()); err != nil {
		t.Fatal(err)
	}
	if _, err := New("ssh://x"); err == nil {
		t.Fatal("unsupported scheme accepted")
	}
}

func TestTarDirIsDeterministicAndSkipsLinks(t *testing.T) {
	dir := t.TempDir()
	os.MkdirAll(filepath.Join(dir, "templates"), 0o755)
	os.WriteFile(filepath.Join(dir, "Dockerfile"), []byte("FROM scratch\n"), 0o644)
	os.WriteFile(filepath.Join(dir, "templates", "a.html"), []byte("<p>"), 0o644)
	os.Symlink("/etc/passwd", filepath.Join(dir, "link"))
	a, err := tarDir(dir)
	if err != nil {
		t.Fatal(err)
	}
	b, _ := tarDir(dir)
	if !bytes.Equal(a, b) {
		t.Fatal("tar not deterministic")
	}
	var names []string
	tr := tar.NewReader(bytes.NewReader(a))
	for {
		h, err := tr.Next()
		if err != nil {
			break
		}
		names = append(names, h.Name)
	}
	if strings.Join(names, ",") != "Dockerfile,templates/,templates/a.html" {
		t.Fatalf("tar entries %v", names)
	}
}
