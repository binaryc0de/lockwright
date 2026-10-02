// Package flags derives, checks and rate-limits CTF flags (PLAN.md 7.5,
// ADR-0018). Flag values never leave this package except to be injected into
// a challenge container's environment; nothing here logs them.
package flags

import (
	"crypto/hmac"
	"crypto/sha256"
	"crypto/subtle"
	"encoding/hex"
	"errors"
	"strings"
	"sync"
	"time"
)

// Spec is a challenge's `flag` block from room.json.
type Spec struct {
	Type      string `json:"type"`       // "per_instance" | "static"
	Format    string `json:"format"`     // per_instance: contains {{nonce}}
	InjectEnv string `json:"inject_env"` // per_instance: env var name
	SHA256    string `json:"sha256"`     // static: hex digest of the flag
}

// NonceLen is the number of hex characters of the HMAC used as the nonce.
const NonceLen = 32

// ErrNoFlag means the spec cannot produce or check a flag.
var ErrNoFlag = errors.New("flag spec has nothing to check against")

// PerInstance returns the flag for one session's instance of a challenge:
// the format with {{nonce}} replaced by HMAC-SHA256(secret, session|challenge).
// The same inputs always give the same flag, so a restarted instance keeps it.
func PerInstance(secret []byte, sessionID, challengeID, format string) string {
	mac := hmac.New(sha256.New, secret)
	mac.Write([]byte(sessionID))
	mac.Write([]byte{0})
	mac.Write([]byte(challengeID))
	nonce := hex.EncodeToString(mac.Sum(nil))[:NonceLen]
	return strings.ReplaceAll(format, "{{nonce}}", nonce)
}

// Check reports whether `submitted` is the flag for this session and
// challenge. Comparisons are constant-time; surrounding whitespace is ignored
// (players paste).
func Check(spec Spec, secret []byte, sessionID, challengeID, submitted string) (bool, error) {
	submitted = strings.TrimSpace(submitted)
	switch spec.Type {
	case "per_instance":
		if spec.Format == "" {
			return false, ErrNoFlag
		}
		want := PerInstance(secret, sessionID, challengeID, spec.Format)
		return subtle.ConstantTimeCompare([]byte(want), []byte(submitted)) == 1, nil
	case "static":
		want, err := hex.DecodeString(spec.SHA256)
		if err != nil || len(want) != sha256.Size {
			return false, ErrNoFlag
		}
		got := sha256.Sum256([]byte(submitted))
		return subtle.ConstantTimeCompare(want, got[:]) == 1, nil
	}
	return false, ErrNoFlag
}

// Limiter enforces "10 wrong per rolling minute, then a doubling cooldown"
// per key (session + challenge). Safe for concurrent use.
type Limiter struct {
	Max    int
	Window time.Duration
	Base   time.Duration
	Now    func() time.Time

	mu    sync.Mutex
	state map[string]*limitState
}

type limitState struct {
	fails   []time.Time
	strikes int
	until   time.Time
}

// NewLimiter returns the platform's default limiter (ADR-0018).
func NewLimiter() *Limiter {
	return &Limiter{Max: 10, Window: time.Minute, Base: 30 * time.Second, Now: time.Now}
}

// Allow reports whether a submission may be checked now; if not, how long to wait.
func (l *Limiter) Allow(key string) (bool, time.Duration) {
	l.mu.Lock()
	defer l.mu.Unlock()
	s := l.get(key)
	now := l.Now()
	if now.Before(s.until) {
		return false, s.until.Sub(now)
	}
	return true, 0
}

// Wrong records a wrong submission and returns the cooldown it triggered (0 if none).
func (l *Limiter) Wrong(key string) time.Duration {
	l.mu.Lock()
	defer l.mu.Unlock()
	s := l.get(key)
	now := l.Now()
	kept := s.fails[:0]
	for _, t := range s.fails {
		if now.Sub(t) < l.Window {
			kept = append(kept, t)
		}
	}
	s.fails = append(kept, now)
	if len(s.fails) < l.Max {
		return 0
	}
	s.strikes++
	cool := l.Base << (s.strikes - 1)
	s.until = now.Add(cool)
	s.fails = nil
	return cool
}

func (l *Limiter) get(key string) *limitState {
	if l.state == nil {
		l.state = map[string]*limitState{}
	}
	s, ok := l.state[key]
	if !ok {
		s = &limitState{}
		l.state[key] = s
	}
	return s
}
