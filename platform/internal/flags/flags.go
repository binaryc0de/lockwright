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

// DefaultMaxCooldown bounds the doubling cooldown so repeated strikes cannot
// overflow time.Duration or lock a challenge out forever.
const DefaultMaxCooldown = 15 * time.Minute

// Limiter enforces "10 wrong per rolling minute, then a doubling cooldown"
// per key (session + challenge). Safe for concurrent use.
type Limiter struct {
	Max         int
	Window      time.Duration
	Base        time.Duration
	MaxCooldown time.Duration
	Now         func() time.Time

	mu    sync.Mutex
	state map[string]*limitState
}

type limitState struct {
	fails    []time.Time
	inFlight int
	strikes  int
	until    time.Time
	lastSeen time.Time
}

// NewLimiter returns the platform's default limiter (ADR-0018).
func NewLimiter() *Limiter {
	return &Limiter{
		Max:         10,
		Window:      time.Minute,
		Base:        30 * time.Second,
		MaxCooldown: DefaultMaxCooldown,
		Now:         time.Now,
	}
}

func (l *Limiter) nowLocked() time.Time {
	if l.Now != nil {
		return l.Now()
	}
	return time.Now()
}

func (l *Limiter) maxCooldownLocked() time.Duration {
	if l.MaxCooldown > 0 {
		return l.MaxCooldown
	}
	return DefaultMaxCooldown
}

// cooldownLocked computes min(Base * 2^(strikes-1), MaxCooldown) without
// shifting or overflowing time.Duration.
func (l *Limiter) cooldownLocked(strikes int) time.Duration {
	if l.Base <= 0 {
		return 0
	}
	maxCool := l.maxCooldownLocked()
	if l.Base >= maxCool {
		return maxCool
	}
	cool := l.Base
	for i := 1; i < strikes && cool < maxCool; i++ {
		if cool > maxCool/2 {
			return maxCool
		}
		cool *= 2
	}
	return cool
}

func (l *Limiter) pruneLocked(s *limitState, now time.Time) {
	kept := s.fails[:0]
	for _, t := range s.fails {
		if now.Sub(t) < l.Window {
			kept = append(kept, t)
		}
	}
	s.fails = kept
}

func (l *Limiter) recordWrongLocked(s *limitState, now time.Time) time.Duration {
	l.pruneLocked(s, now)
	s.fails = append(s.fails, now)
	if len(s.fails) < l.Max {
		return 0
	}
	s.strikes++
	cool := l.cooldownLocked(s.strikes)
	s.until = now.Add(cool)
	s.fails = nil
	return cool
}

func (l *Limiter) sweepStaleLocked(now time.Time) {
	staleAfter := l.maxCooldownLocked() * 2
	if w := l.Window * 2; w > staleAfter {
		staleAfter = w
	}
	for k, s := range l.state {
		if s.inFlight == 0 && !now.Before(s.until) && now.Sub(s.lastSeen) >= staleAfter {
			delete(l.state, k)
		}
	}
}

// Reserve atomically checks whether key may attempt a flag submission and
// reserves a slot so concurrent requests cannot race past Max. Call the
// returned finish(accepted) once the attempt completes; passing accepted=false
// records a failure and returns any triggered cooldown.
func (l *Limiter) Reserve(key string) (allowed bool, retryAfter time.Duration, finish func(accepted bool) time.Duration) {
	l.mu.Lock()
	defer l.mu.Unlock()
	now := l.nowLocked()
	l.sweepStaleLocked(now)
	s := l.get(key)
	s.lastSeen = now
	if now.Before(s.until) {
		return false, s.until.Sub(now), nil
	}
	l.pruneLocked(s, now)
	if l.Max > 0 && len(s.fails)+s.inFlight >= l.Max {
		return false, l.cooldownLocked(s.strikes + 1), nil
	}
	s.inFlight++
	var once sync.Once
	finish = func(accepted bool) time.Duration {
		var cool time.Duration
		once.Do(func() {
			l.mu.Lock()
			defer l.mu.Unlock()
			st, ok := l.state[key]
			if !ok {
				return
			}
			if st.inFlight > 0 {
				st.inFlight--
			}
			if accepted {
				return
			}
			t := l.nowLocked()
			st.lastSeen = t
			cool = l.recordWrongLocked(st, t)
		})
		return cool
	}
	return true, 0, finish
}

// Allow reports whether a submission may be checked now; if not, how long to wait.
// Prefer Reserve for concurrent callers so check-and-count is atomic.
func (l *Limiter) Allow(key string) (bool, time.Duration) {
	l.mu.Lock()
	defer l.mu.Unlock()
	s := l.get(key)
	now := l.nowLocked()
	if now.Before(s.until) {
		return false, s.until.Sub(now)
	}
	l.pruneLocked(s, now)
	if l.Max > 0 && len(s.fails)+s.inFlight >= l.Max {
		return false, l.cooldownLocked(s.strikes + 1)
	}
	return true, 0
}

// Wrong records a wrong submission and returns the cooldown it triggered (0 if none).
func (l *Limiter) Wrong(key string) time.Duration {
	l.mu.Lock()
	defer l.mu.Unlock()
	s := l.get(key)
	now := l.nowLocked()
	s.lastSeen = now
	return l.recordWrongLocked(s, now)
}

// ForgetSession removes all rate-limit state for a finished session.
func (l *Limiter) ForgetSession(sessionID string) {
	if sessionID == "" {
		return
	}
	l.mu.Lock()
	defer l.mu.Unlock()
	prefix := sessionID + "/"
	for k := range l.state {
		if k == sessionID || strings.HasPrefix(k, prefix) {
			delete(l.state, k)
		}
	}
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
