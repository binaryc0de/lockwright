package main

import (
	"net/http"
	"testing"
)

func TestChallengeBindAddr(t *testing.T) {
	cases := []struct {
		explicit, publicURL, want string
	}{
		{"", "https://play.example.com", "127.0.0.1"},
		{"", "http://127.0.0.1:8080", "127.0.0.1"},
		{"", "", "0.0.0.0"},
		{"192.168.1.20", "https://play.example.com", "192.168.1.20"},
		{"0.0.0.0", "https://play.example.com", "0.0.0.0"},
		{"127.0.0.1", "", "127.0.0.1"},
	}
	for _, c := range cases {
		if got := challengeBindAddr(c.explicit, c.publicURL); got != c.want {
			t.Errorf("challengeBindAddr(%q, %q) = %q, want %q", c.explicit, c.publicURL, got, c.want)
		}
	}
}

func TestNewHTTPServerTimeouts(t *testing.T) {
	srv := newHTTPServer("127.0.0.1:8080", http.NewServeMux())
	if srv.ReadHeaderTimeout <= 0 || srv.IdleTimeout <= 0 {
		t.Fatalf("expected ReadHeaderTimeout and IdleTimeout to be set: %+v", srv)
	}
	if srv.ReadTimeout != 0 || srv.WriteTimeout != 0 {
		t.Fatalf("ReadTimeout/WriteTimeout must stay 0 for hijacked /ws/ connections: %+v", srv)
	}
}
