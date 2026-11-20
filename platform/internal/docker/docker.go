// Package docker is a minimal Docker Engine API client over the standard
// library (ADR-0018): just what challenge orchestration needs. It honours
// DOCKER_HOST (unix:// or tcp://), so rootless Docker works unchanged.
package docker

import (
	"archive/tar"
	"bufio"
	"bytes"
	"context"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"io/fs"
	"net"
	"net/http"
	"net/url"
	"os"
	"path/filepath"
	"strings"
	"time"
)

// APIVersion is used until the daemon tells us its own (Ping negotiates:
// Docker 29 rejects anything below 1.44, older daemons below their maximum).
const APIVersion = "v1.43"

// ErrNotFound is returned for 404s from the Engine.
var ErrNotFound = errors.New("docker: not found")

// Client talks to one Docker Engine.
type Client struct {
	http    *http.Client
	base    string // "http://docker" for unix sockets, "http://host:port" for tcp
	version string // "v1.47" after Ping; APIVersion before
}

// FromEnv builds a client from DOCKER_HOST (default unix:///var/run/docker.sock).
func FromEnv() (*Client, error) {
	host := os.Getenv("DOCKER_HOST")
	if host == "" {
		host = "unix:///var/run/docker.sock"
	}
	return New(host)
}

// New builds a client for a DOCKER_HOST-style address.
func New(host string) (*Client, error) {
	u, err := url.Parse(host)
	if err != nil {
		return nil, fmt.Errorf("docker host %q: %w", host, err)
	}
	switch u.Scheme {
	case "unix":
		sock := u.Path
		tr := &http.Transport{DialContext: func(ctx context.Context, _, _ string) (net.Conn, error) {
			var d net.Dialer
			return d.DialContext(ctx, "unix", sock)
		}}
		return &Client{http: &http.Client{Transport: tr}, base: "http://docker", version: APIVersion}, nil
	case "tcp", "http":
		return &Client{http: &http.Client{}, base: "http://" + u.Host, version: APIVersion}, nil
	}
	return nil, fmt.Errorf("docker host %q: unsupported scheme", host)
}

func (c *Client) do(ctx context.Context, method, path string, query url.Values, body io.Reader, contentType string) (*http.Response, error) {
	u := c.base + "/" + c.version + path
	if len(query) > 0 {
		u += "?" + query.Encode()
	}
	req, err := http.NewRequestWithContext(ctx, method, u, body)
	if err != nil {
		return nil, err
	}
	if contentType != "" {
		req.Header.Set("Content-Type", contentType)
	}
	resp, err := c.http.Do(req)
	if err != nil {
		return nil, fmt.Errorf("docker %s %s: %w", method, path, err)
	}
	if resp.StatusCode == http.StatusNotFound {
		resp.Body.Close()
		return nil, ErrNotFound
	}
	if resp.StatusCode >= 400 {
		defer resp.Body.Close()
		var e struct {
			Message string `json:"message"`
		}
		b, _ := io.ReadAll(io.LimitReader(resp.Body, 64<<10))
		_ = json.Unmarshal(b, &e)
		if e.Message == "" {
			e.Message = strings.TrimSpace(string(b))
		}
		return nil, fmt.Errorf("docker %s %s: %d %s", method, path, resp.StatusCode, e.Message)
	}
	return resp, nil
}

func (c *Client) doJSON(ctx context.Context, method, path string, query url.Values, in, out any) error {
	var body io.Reader
	ct := ""
	if in != nil {
		b, err := json.Marshal(in)
		if err != nil {
			return err
		}
		body = bytes.NewReader(b)
		ct = "application/json"
	}
	resp, err := c.do(ctx, method, path, query, body, ct)
	if err != nil {
		return err
	}
	defer resp.Body.Close()
	if out == nil {
		_, _ = io.Copy(io.Discard, resp.Body)
		return nil
	}
	return json.NewDecoder(resp.Body).Decode(out)
}

// Ping checks the Engine is reachable and adopts its API version (the
// unversioned /_ping is accepted by every daemon).
func (c *Client) Ping(ctx context.Context) error {
	req, err := http.NewRequestWithContext(ctx, http.MethodGet, c.base+"/_ping", nil)
	if err != nil {
		return err
	}
	resp, err := c.http.Do(req)
	if err != nil {
		return fmt.Errorf("docker ping: %w", err)
	}
	defer resp.Body.Close()
	if resp.StatusCode != http.StatusOK {
		return fmt.Errorf("docker ping: %d", resp.StatusCode)
	}
	if v := resp.Header.Get("Api-Version"); v != "" {
		c.version = "v" + strings.TrimPrefix(v, "v")
	}
	return nil
}

// Version is the API version requests use.
func (c *Client) Version() string { return c.version }

// ImageExists reports whether an image reference is present locally.
func (c *Client) ImageExists(ctx context.Context, ref string) (bool, error) {
	err := c.doJSON(ctx, http.MethodGet, "/images/"+url.PathEscape(ref)+"/json", nil, nil, nil)
	if errors.Is(err, ErrNotFound) {
		return false, nil
	}
	return err == nil, err
}

// BuildImage builds `dir` (which must contain a Dockerfile) and tags it.
func (c *Client) BuildImage(ctx context.Context, dir, tag string, labels map[string]string) error {
	tarball, err := tarDir(dir)
	if err != nil {
		return fmt.Errorf("build context %s: %w", dir, err)
	}
	lb, _ := json.Marshal(labels)
	q := url.Values{"t": {tag}, "rm": {"1"}, "forcerm": {"1"}, "labels": {string(lb)}}
	resp, err := c.do(ctx, http.MethodPost, "/build", q, bytes.NewReader(tarball), "application/x-tar")
	if err != nil {
		return err
	}
	defer resp.Body.Close()
	// The build streams JSON lines; an "error" line means it failed.
	sc := bufio.NewScanner(resp.Body)
	sc.Buffer(make([]byte, 64<<10), 1<<20)
	var last string
	for sc.Scan() {
		var line struct {
			Stream string `json:"stream"`
			Error  string `json:"error"`
		}
		if json.Unmarshal(sc.Bytes(), &line) != nil {
			continue
		}
		if line.Error != "" {
			return fmt.Errorf("build %s: %s", tag, strings.TrimSpace(line.Error))
		}
		if s := strings.TrimSpace(line.Stream); s != "" {
			last = s
		}
	}
	if err := sc.Err(); err != nil {
		return fmt.Errorf("build %s: %w (last: %s)", tag, err, last)
	}
	return nil
}

// BridgePrefix is the fixed Linux interface prefix given to every challenge
// bridge so host firewall rules (e.g. iptables -i ebx+) match only challenge
// networks and leave other Docker networks untouched.
const BridgePrefix = "ebx"

// BridgeName derives a deterministic 15-character Linux bridge interface name
// starting with BridgePrefix from a Docker network name.
func BridgeName(netName string) string {
	sum := sha256.Sum256([]byte(netName))
	return BridgePrefix + hex.EncodeToString(sum[:6])
}

// NetworkSpec describes a session network.
type NetworkSpec struct {
	Name       string
	Internal   bool // no route out of the network (no egress)
	BridgeName string
	Labels     map[string]string
}

// CreateNetwork creates a bridge network and returns its id.
func (c *Client) CreateNetwork(ctx context.Context, n NetworkSpec) (string, error) {
	var out struct {
		ID string `json:"Id"`
	}
	body := map[string]any{
		"Name":           n.Name,
		"Driver":         "bridge",
		"Internal":       n.Internal,
		"CheckDuplicate": true,
		"Labels":         n.Labels,
	}
	if n.BridgeName != "" {
		body["Options"] = map[string]string{
			"com.docker.network.bridge.name": n.BridgeName,
		}
	}
	err := c.doJSON(ctx, http.MethodPost, "/networks/create", nil, body, &out)
	return out.ID, err
}

// RemoveNetwork deletes a network (missing is not an error).
func (c *Client) RemoveNetwork(ctx context.Context, id string) error {
	err := c.doJSON(ctx, http.MethodDelete, "/networks/"+url.PathEscape(id), nil, nil, nil)
	if errors.Is(err, ErrNotFound) {
		return nil
	}
	return err
}

// Limits applied when a challenge does not declare its own.
const (
	DefaultMemoryMB = 256
	DefaultCPUs     = 0.5
	DefaultPidsMax  = 128
	DefaultUser     = "65534:65534"
)

// ContainerSpec is a hardened challenge container (ADR-0018).
type ContainerSpec struct {
	Name     string
	Image    string
	User     string // "" = DefaultUser (65534:65534)
	Env      map[string]string
	Labels   map[string]string
	Network  string
	CPUs     float64 // 0 = DefaultCPUs
	MemoryMB int     // 0 = DefaultMemoryMB
	PidsMax  int     // 0 = DefaultPidsMax
}

// containerBody is the Engine payload; split out so tests can check hardening.
func containerBody(s ContainerSpec) map[string]any {
	env := make([]string, 0, len(s.Env))
	for k, v := range s.Env {
		env = append(env, k+"="+v)
	}
	user := s.User
	if user == "" {
		user = DefaultUser
	}
	pids := s.PidsMax
	if pids <= 0 {
		pids = DefaultPidsMax
	}
	host := map[string]any{
		"NetworkMode":    s.Network,
		"CapDrop":        []string{"ALL"},
		"SecurityOpt":    []string{"no-new-privileges:true"},
		"ReadonlyRootfs": true,
		"Tmpfs":          map[string]string{"/tmp": "rw,noexec,nosuid,size=16m"},
		"PidsLimit":      pids,
		"RestartPolicy":  map[string]string{"Name": "no"},
		"Privileged":     false,
	}
	// Always limited: a room that omits `resources` gets the defaults
	// (ADR-0018; review M3-P1).
	mem := s.MemoryMB
	if mem <= 0 {
		mem = DefaultMemoryMB
	}
	cpus := s.CPUs
	if cpus <= 0 {
		cpus = DefaultCPUs
	}
	host["Memory"] = int64(mem) << 20
	host["MemorySwap"] = int64(mem) << 20
	host["NanoCpus"] = int64(cpus * 1e9)
	return map[string]any{
		"Image":           s.Image,
		"User":            user,
		"Env":             env,
		"Labels":          s.Labels,
		"NetworkDisabled": false,
		"HostConfig":      host,
	}
}

// CreateContainer creates (but does not start) a container.
func (c *Client) CreateContainer(ctx context.Context, s ContainerSpec) (string, error) {
	var out struct {
		ID string `json:"Id"`
	}
	err := c.doJSON(ctx, http.MethodPost, "/containers/create", url.Values{"name": {s.Name}}, containerBody(s), &out)
	return out.ID, err
}

// StartContainer starts a created container.
func (c *Client) StartContainer(ctx context.Context, id string) error {
	return c.doJSON(ctx, http.MethodPost, "/containers/"+url.PathEscape(id)+"/start", nil, nil, nil)
}

// ContainerInfo is the subset of inspect output the orchestrator uses.
type ContainerInfo struct {
	Running bool
	IP      string // address on the named network
}

// InspectContainer returns state and the container's IP on `network`.
func (c *Client) InspectContainer(ctx context.Context, id, network string) (ContainerInfo, error) {
	var out struct {
		State struct {
			Running bool `json:"Running"`
		} `json:"State"`
		NetworkSettings struct {
			Networks map[string]struct {
				IPAddress string `json:"IPAddress"`
			} `json:"Networks"`
		} `json:"NetworkSettings"`
	}
	if err := c.doJSON(ctx, http.MethodGet, "/containers/"+url.PathEscape(id)+"/json", nil, nil, &out); err != nil {
		return ContainerInfo{}, err
	}
	return ContainerInfo{Running: out.State.Running, IP: out.NetworkSettings.Networks[network].IPAddress}, nil
}

// RemoveContainer force-removes a container (missing is not an error).
func (c *Client) RemoveContainer(ctx context.Context, id string) error {
	err := c.doJSON(ctx, http.MethodDelete, "/containers/"+url.PathEscape(id), url.Values{"force": {"1"}, "v": {"1"}}, nil, nil)
	if errors.Is(err, ErrNotFound) {
		return nil
	}
	return err
}

// ListByLabel returns container ids and network ids carrying label=value.
func (c *Client) ListByLabel(ctx context.Context, label, value string) (containers, networks []string, err error) {
	f, _ := json.Marshal(map[string][]string{"label": {label + "=" + value}})
	var cs []struct {
		ID string `json:"Id"`
	}
	if err := c.doJSON(ctx, http.MethodGet, "/containers/json", url.Values{"all": {"1"}, "filters": {string(f)}}, nil, &cs); err != nil {
		return nil, nil, err
	}
	var ns []struct {
		ID string `json:"Id"`
	}
	if err := c.doJSON(ctx, http.MethodGet, "/networks", url.Values{"filters": {string(f)}}, nil, &ns); err != nil {
		return nil, nil, err
	}
	for _, x := range cs {
		containers = append(containers, x.ID)
	}
	for _, x := range ns {
		networks = append(networks, x.ID)
	}
	return containers, networks, nil
}

// tarDir packs a build context. Files are written with fixed metadata so the
// same directory always produces the same context.
func tarDir(dir string) ([]byte, error) {
	var buf bytes.Buffer
	tw := tar.NewWriter(&buf)
	err := filepath.WalkDir(dir, func(p string, d fs.DirEntry, err error) error {
		if err != nil {
			return err
		}
		rel, _ := filepath.Rel(dir, p)
		if rel == "." {
			return nil
		}
		info, err := d.Info()
		if err != nil {
			return err
		}
		if !info.Mode().IsRegular() && !d.IsDir() {
			return nil // skip symlinks, sockets
		}
		h := &tar.Header{Name: filepath.ToSlash(rel), ModTime: time.Unix(0, 0), Mode: 0o644}
		if d.IsDir() {
			h.Typeflag, h.Name, h.Mode = tar.TypeDir, h.Name+"/", 0o755
			return tw.WriteHeader(h)
		}
		h.Typeflag, h.Size = tar.TypeReg, info.Size()
		if err := tw.WriteHeader(h); err != nil {
			return err
		}
		f, err := os.Open(p)
		if err != nil {
			return err
		}
		defer f.Close()
		_, err = io.Copy(tw, f)
		return err
	})
	if err != nil {
		return nil, err
	}
	if err := tw.Close(); err != nil {
		return nil, err
	}
	return buf.Bytes(), nil
}
