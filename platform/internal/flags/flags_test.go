package flags

import (
	"crypto/sha256"
	"encoding/hex"
	"strings"
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
