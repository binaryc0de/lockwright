package flags

import (
	"crypto/sha256"
	"encoding/hex"
	"strings"
	"sync"
	"sync/atomic"
	"testing"
	"time"
)

var secret = []byte("test-secret-0123456789")

func TestPerInstanceIsStableAndDistinct(t *testing.T) {
	a := PerInstance(secret, "s1", "intranet", "FLAG{{{nonce}}}")
	if a != PerInstance(secret, "s1", "intranet", "FLAG{{{nonce}}}") {
		t.Fatal("same inputs gave different flags")
	}
	if !strings.HasPrefix(a, "FLAG{") || !strings.HasSuffix(a, "}") || len(a) != len("FLAG{}")+NonceLen {
		t.Fatalf("unexpected shape %q", a)
	}
	for _, other := range []string{
		PerInstance(secret, "s2", "intranet", "FLAG{{{nonce}}}"),
		PerInstance(secret, "s1", "other", "FLAG{{{nonce}}}"),
		PerInstance([]byte("another secret"), "s1", "intranet", "FLAG{{{nonce}}}"),
	} {
		if other == a {
			t.Fatal("flag did not change with session, challenge or secret")
		}
	}
	// Session/challenge boundary is unambiguous.
	if PerInstance(secret, "ab", "c", "{{nonce}}") == PerInstance(secret, "a", "bc", "{{nonce}}") {
		t.Fatal("session|challenge concatenation is ambiguous")
	}
}

func TestCheckPerInstance(t *testing.T) {
	spec := Spec{Type: "per_instance", Format: "FLAG{{{nonce}}}", InjectEnv: "FLAG"}
	flag := PerInstance(secret, "s1", "intranet", spec.Format)
	for _, c := range []struct {
		in   string
		want bool
	}{
		{flag, true},
		{"  " + flag + "\n", true},
		{strings.ToUpper(flag), false},
		{flag[:len(flag)-1], false},
		{"", false},
		{PerInstance(secret, "s2", "intranet", spec.Format), false},
	} {
		got, err := Check(spec, secret, "s1", "intranet", c.in)
		if err != nil || got != c.want {
			t.Errorf("Check(%q) = %v, %v; want %v", c.in, got, err, c.want)
		}
	}
}

func TestCheckStatic(t *testing.T) {
	sum := sha256.Sum256([]byte("FLAG{static_one}"))
	spec := Spec{Type: "static", SHA256: hex.EncodeToString(sum[:])}
	if ok, err := Check(spec, secret, "s", "c", "FLAG{static_one}"); !ok || err != nil {
		t.Fatalf("static flag rejected: %v %v", ok, err)
	}
	if ok, _ := Check(spec, secret, "s", "c", "FLAG{other}"); ok {
		t.Fatal("wrong static flag accepted")
	}
	if _, err := Check(Spec{Type: "static", SHA256: "zz"}, secret, "s", "c", "x"); err != ErrNoFlag {
		t.Fatalf("bad digest: err %v", err)
	}
	if _, err := Check(Spec{Type: "nope"}, secret, "s", "c", "x"); err != ErrNoFlag {
		t.Fatalf("unknown type: err %v", err)
	}
}

func TestLimiterCooldownDoubles(t *testing.T) {
	now := time.Unix(1000, 0)
	l := NewLimiter()
	l.Now = func() time.Time { return now }
	for i := 0; i < 9; i++ {
		if c := l.Wrong("k"); c != 0 {
			t.Fatalf("cooldown after %d wrong", i+1)
		}
		now = now.Add(time.Second)
	}
	if ok, _ := l.Allow("k"); !ok {
		t.Fatal("blocked before the 10th wrong attempt")
	}
	if c := l.Wrong("k"); c != 30*time.Second {
		t.Fatalf("10th wrong: cooldown %v, want 30s", c)
	}
	if ok, wait := l.Allow("k"); ok || wait != 30*time.Second {
		t.Fatalf("Allow during cooldown = %v, %v", ok, wait)
	}
	if ok, _ := l.Allow("other"); !ok {
		t.Fatal("cooldown leaked to another key")
	}
	now = now.Add(31 * time.Second)
	if ok, _ := l.Allow("k"); !ok {
		t.Fatal("still blocked after the cooldown")
	}
	for i := 0; i < 9; i++ {
		l.Wrong("k")
	}
	if c := l.Wrong("k"); c != time.Minute {
		t.Fatalf("second strike cooldown %v, want 1m", c)
	}
}

func TestLimiterForgetsOldFailures(t *testing.T) {
	now := time.Unix(1000, 0)
	l := NewLimiter()
	l.Now = func() time.Time { return now }
	for i := 0; i < 20; i++ {
		if c := l.Wrong("k"); c != 0 {
			t.Fatalf("cooldown at attempt %d although attempts are 7 s apart", i+1)
		}
		now = now.Add(7 * time.Second)
	}
}

func TestLimiterCooldownCapsAndNeverOverflows(t *testing.T) {
	now := time.Unix(1000, 0)
	l := NewLimiter()
	l.Now = func() time.Time { return now }
	// Trigger 80 strikes (well past the 64-bit shift overflow point).
	for strike := 1; strike <= 80; strike++ {
		var cool time.Duration
		for i := 0; i < l.Max; i++ {
			cool = l.Wrong("k")
		}
		if cool <= 0 || cool > DefaultMaxCooldown {
			t.Fatalf("strike %d: cooldown %v out of (0, %v]", strike, cool, DefaultMaxCooldown)
		}
		if strike >= 6 && cool != DefaultMaxCooldown {
			t.Fatalf("strike %d: cooldown %v, want cap %v", strike, cool, DefaultMaxCooldown)
		}
		if ok, wait := l.Allow("k"); ok || wait <= 0 {
			t.Fatalf("strike %d: Allow during cooldown = %v, %v", strike, ok, wait)
		}
		now = now.Add(cool + time.Second)
	}
}

func TestLimiterReserveIsAtomicUnderConcurrency(t *testing.T) {
	l := NewLimiter()
	const workers = 40
	start := make(chan struct{})
	var allowed atomic.Int32
	var wg sync.WaitGroup
	for i := 0; i < workers; i++ {
		wg.Add(1)
		go func() {
			defer wg.Done()
			<-start
			ok, wait, finish := l.Reserve("s1/intranet")
			if !ok {
				if wait <= 0 {
					t.Errorf("rejected attempt returned non-positive wait %v", wait)
				}
				return
			}
			allowed.Add(1)
			// Simulate slow DB write between check and record.
			time.Sleep(15 * time.Millisecond)
			finish(false)
		}()
	}
	close(start)
	wg.Wait()
	if got := allowed.Load(); got != int32(l.Max) {
		t.Fatalf("concurrent wrong attempts allowed = %d, want exactly %d", got, l.Max)
	}
	if ok, wait, _ := l.Reserve("s1/intranet"); ok || wait <= 0 {
		t.Fatalf("after burst, Reserve = %v, %v", ok, wait)
	}
}

func TestLimiterForgetSessionAndStaleSweep(t *testing.T) {
	now := time.Unix(1000, 0)
	l := NewLimiter()
	l.Now = func() time.Time { return now }
	l.Wrong("s1/intranet")
	l.Wrong("s1/other")
	l.Wrong("s2/intranet")
	l.ForgetSession("s1")
	if _, ok := l.state["s1/intranet"]; ok {
		t.Fatal("s1/intranet not evicted")
	}
	if _, ok := l.state["s1/other"]; ok {
		t.Fatal("s1/other not evicted")
	}
	if _, ok := l.state["s2/intranet"]; !ok {
		t.Fatal("s2/intranet evicted by ForgetSession(s1)")
	}
	// Stale sessions are swept automatically once idle past 2*MaxCooldown.
	now = now.Add(2*DefaultMaxCooldown + time.Second)
	ok, _, finish := l.Reserve("s3/intranet")
	if !ok {
		t.Fatal("s3/intranet unexpectedly blocked")
	}
	finish(true)
	if _, ok := l.state["s2/intranet"]; ok {
		t.Fatal("stale s2/intranet not swept")
	}
}
