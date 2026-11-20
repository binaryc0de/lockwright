package store

import (
	"context"
	"errors"
	"path/filepath"
	"strconv"
	"strings"
	"sync"
	"testing"
	"time"
)

func open(t *testing.T) *Store {
	t.Helper()
	s, err := Open(context.Background(), ":memory:")
	if err != nil {
		t.Fatal(err)
	}
	t.Cleanup(func() { s.Close() })
	return s
}

func TestSessionLifecycle(t *testing.T) {
	ctx := context.Background()
	s := open(t)
	sess, err := s.CreateSession(ctx, "night_shift")
	if err != nil {
		t.Fatal(err)
	}
	if len(sess.ID) != 12 || len(sess.InviteCode) != 6 || len(sess.ServerToken) != 64 || sess.Status != StatusIdle {
		t.Fatalf("bad new session %+v", sess)
	}
	got, err := s.Session(ctx, sess.ID)
	if err != nil || got.RoomID != "night_shift" || got.InviteCode != sess.InviteCode {
		t.Fatalf("read back %+v %v", got, err)
	}
	if err := s.SetStatus(ctx, sess.ID, StatusRunning); err != nil {
		t.Fatal(err)
	}
	if err := s.Finish(ctx, sess.ID, true, 1830, 2); err != nil {
		t.Fatal(err)
	}
	got, _ = s.Session(ctx, sess.ID)
	if got.Status != StatusFinished || !got.Won || got.ElapsedS != 1830 || got.HintsUsed != 2 || got.FinishedAt.IsZero() {
		t.Fatalf("finish not stored: %+v", got)
	}
	if _, err := s.Session(ctx, "nope"); !errors.Is(err, ErrNotFound) {
		t.Fatalf("missing session err %v", err)
	}
	if err := s.SetStatus(ctx, "nope", StatusRunning); !errors.Is(err, ErrNotFound) {
		t.Fatalf("SetStatus on missing session err %v", err)
	}
}

func TestJoinTokensAreSingleUseExpiringAndPerSession(t *testing.T) {
	ctx := context.Background()
	s := open(t)
	now := time.Unix(10_000, 0)
	s.now = func() time.Time { return now }
	a, _ := s.CreateSession(ctx, "r")
	b, _ := s.CreateSession(ctx, "r")
	tok, pid, err := s.MintJoinToken(ctx, a.ID, " Alex ")
	if err != nil {
		t.Fatal(err)
	}
	if _, _, err := s.ConsumeJoinToken(ctx, b.ID, tok); !errors.Is(err, ErrTokenInvalid) {
		t.Fatalf("token accepted for another session: %v", err)
	}
	gotPID, name, err := s.ConsumeJoinToken(ctx, a.ID, tok)
	if err != nil || gotPID != pid || name != "Alex" {
		t.Fatalf("consume = %q %q %v", gotPID, name, err)
	}
	if _, _, err := s.ConsumeJoinToken(ctx, a.ID, tok); !errors.Is(err, ErrTokenInvalid) {
		t.Fatalf("token reused: %v", err)
	}
	// Rejoining keeps the player id.
	tok2, pid2, _ := s.MintJoinToken(ctx, a.ID, "Alex")
	if pid2 != pid {
		t.Fatalf("rejoin got a new player id %q != %q", pid2, pid)
	}
	now = now.Add(JoinTokenTTL + time.Second)
	if _, _, err := s.ConsumeJoinToken(ctx, a.ID, tok2); !errors.Is(err, ErrTokenInvalid) {
		t.Fatalf("expired token accepted: %v", err)
	}
	if names, _ := s.Players(ctx, a.ID); len(names) != 1 || names[0] != "Alex" {
		t.Fatalf("players %v", names)
	}
}

func TestSnapshotsEventsAttemptsInstances(t *testing.T) {
	ctx := context.Background()
	s := open(t)
	if _, err := s.Snapshot(ctx, "s1"); !errors.Is(err, ErrNotFound) {
		t.Fatalf("empty snapshot err %v", err)
	}
	s.PutSnapshot(ctx, "s1", []byte(`{"version":1,"a":1}`))
	s.PutSnapshot(ctx, "s1", []byte(`{"version":1,"a":2}`))
	if b, _ := s.Snapshot(ctx, "s1"); string(b) != `{"version":1,"a":2}` {
		t.Fatalf("snapshot %s", b)
	}
	if err := s.AppendEvents(ctx, "s1", []Event{{At: 1, Kind: "puzzle_solved", Data: `{"puzzle":"x"}`}, {At: 2, Kind: "hint_revealed", PlayerID: "p1"}}); err != nil {
		t.Fatal(err)
	}
	evs, _ := s.Events(ctx, "s1")
	if len(evs) != 2 || evs[0].Kind != "puzzle_solved" || evs[1].PlayerID != "p1" || evs[1].Data != "{}" {
		t.Fatalf("events %+v", evs)
	}
	s.RecordFlagAttempt(ctx, "s1", "intranet", "p1", false)
	s.RecordFlagAttempt(ctx, "s1", "intranet", "p1", true)
	if total, ok, _ := s.FlagAttempts(ctx, "s1", "intranet"); total != 2 || ok != 1 {
		t.Fatalf("attempts %d %d", total, ok)
	}
	s.PutInstance(ctx, Instance{SessionID: "s1", ChallengeID: "intranet", ContainerID: "c1", NetworkID: "n1", HostPort: 20001})
	s.PutInstance(ctx, Instance{SessionID: "s1", ChallengeID: "intranet", ContainerID: "c2", NetworkID: "n1", HostPort: 20002})
	ins, _ := s.Instances(ctx, "s1")
	if len(ins) != 1 || ins[0].ContainerID != "c2" || ins[0].HostPort != 20002 {
		t.Fatalf("instances %+v", ins)
	}
	s.DeleteInstances(ctx, "s1")
	if ins, _ := s.Instances(ctx, "s1"); len(ins) != 0 {
		t.Fatalf("instances not deleted %+v", ins)
	}
}

func TestReopenKeepsDataAndSchema(t *testing.T) {
	ctx := context.Background()
	path := filepath.Join(t.TempDir(), "platform.db")
	s, err := Open(ctx, path)
	if err != nil {
		t.Fatal(err)
	}
	sess, _ := s.CreateSession(ctx, "r")
	s.Close()
	s2, err := Open(ctx, path)
	if err != nil {
		t.Fatal(err)
	}
	defer s2.Close()
	if _, err := s2.Session(ctx, sess.ID); err != nil {
		t.Fatalf("session lost after reopen: %v", err)
	}
}

func TestInviteCodesAvoidAmbiguousCharacters(t *testing.T) {
	for i := 0; i < 500; i++ {
		code := InviteCode()
		if len(code) != 6 {
			t.Fatalf("invite code %q has len %d, want 6", code, len(code))
		}
		for _, c := range code {
			if !strings.ContainsRune(inviteAlphabet, c) {
				t.Fatalf("invite code %q contains character %q outside alphabet", code, c)
			}
			if c == '0' || c == 'O' || c == '1' || c == 'I' || c == 'L' {
				t.Fatalf("ambiguous character %q", c)
			}
		}
	}
}

func TestSessionByInvite(t *testing.T) {
	ctx := context.Background()
	s := open(t)
	a, _ := s.CreateSession(ctx, "r")
	got, err := s.SessionByInvite(ctx, " "+strings.ToLower(a.InviteCode)+" ")
	if err != nil || got.ID != a.ID {
		t.Fatalf("by invite: %+v %v", got, err)
	}
	if _, err := s.SessionByInvite(ctx, "ZZZZZZ"); !errors.Is(err, ErrNotFound) {
		t.Fatalf("unknown code err %v", err)
	}
}

func TestConcurrentJoinsOnAFileDatabase(t *testing.T) {
	ctx := context.Background()
	s, err := Open(ctx, filepath.Join(t.TempDir(), "p.db"))
	if err != nil {
		t.Fatal(err)
	}
	defer s.Close()
	sess, _ := s.CreateSession(ctx, "r")
	var wg sync.WaitGroup
	errs := make(chan error, 16)
	for i := 0; i < 16; i++ {
		wg.Add(1)
		go func(i int) {
			defer wg.Done()
			if _, _, err := s.MintJoinToken(ctx, sess.ID, "player"+strconv.Itoa(i%4)); err != nil {
				errs <- err
			}
		}(i)
	}
	wg.Wait()
	close(errs)
	for err := range errs {
		t.Fatalf("concurrent join failed: %v", err)
	}
	if names, _ := s.Players(ctx, sess.ID); len(names) != 4 {
		t.Fatalf("players %v", names)
	}
}

func TestExpireUnjoinedAndCounts(t *testing.T) {
	ctx := context.Background()
	s, _ := Open(ctx, ":memory:")
	defer s.Close()
	base := time.Unix(1_800_000_000, 0)
	now := base
	s.now = func() time.Time { return now }
	old, _ := s.CreateSession(ctx, "r")
	joined, _ := s.CreateSession(ctx, "r")
	if _, _, err := s.MintJoinToken(ctx, joined.ID, "Ann"); err != nil {
		t.Fatal(err)
	}
	if _, _, err := s.ConsumeJoinToken(ctx, joined.ID, mustToken(t, s, joined.ID)); err != nil {
		t.Fatal(err)
	}
	now = base.Add(45 * time.Minute)
	fresh, _ := s.CreateSession(ctx, "r")
	// Two waiting for their first player hold slots; the joined idle one is
	// restorable and holds none.
	if n, _ := s.CountActive(ctx); n != 2 {
		t.Fatalf("active %d", n)
	}
	ids, err := s.ExpireUnjoined(ctx, now.Add(-30*time.Minute))
	if err != nil || len(ids) != 1 || ids[0] != old.ID {
		t.Fatalf("expired %v %v (want only %s)", ids, err, old.ID)
	}
	if st, _ := s.Session(ctx, fresh.ID); st.Status != StatusIdle {
		t.Fatal("fresh session expired")
	}
	counts, _ := s.CountByStatus(ctx)
	if counts[StatusFinished] != 1 || counts[StatusIdle] != 2 {
		t.Fatalf("counts %v", counts)
	}
}

func mustToken(t *testing.T, s *Store, sessionID string) string {
	t.Helper()
	tok, _, err := s.MintJoinToken(context.Background(), sessionID, "Ann2")
	if err != nil {
		t.Fatal(err)
	}
	return tok
}

func TestRestartResetsLiveGamesAndCapCountsHolders(t *testing.T) {
	ctx := context.Background()
	s, _ := Open(ctx, ":memory:")
	defer s.Close()
	base := time.Unix(1_800_000_000, 0)
	now := base
	s.now = func() time.Time { return now }
	played, _ := s.CreateSession(ctx, "r")
	tok, _, _ := s.MintJoinToken(ctx, played.ID, "Ann")
	if _, _, err := s.ConsumeJoinToken(ctx, played.ID, tok); err != nil {
		t.Fatal(err)
	}
	_ = s.SetStatus(ctx, played.ID, StatusRunning)
	waiting, _ := s.CreateSession(ctx, "r")
	if n, _ := s.CountActive(ctx); n != 2 {
		t.Fatalf("active before restart %d", n)
	}
	if n, _ := s.ResetLiveStatuses(ctx); n != 1 {
		t.Fatalf("reset %d", n)
	}
	// The played game is restorable but holds nothing; the waiting one counts.
	if n, _ := s.CountActive(ctx); n != 1 {
		t.Fatalf("active after restart %d", n)
	}
	now = base.Add(13 * time.Hour)
	if n, _ := s.ExpireAbandoned(ctx, now.Add(-12*time.Hour)); n != 2 {
		t.Fatalf("abandoned %d", n)
	}
	for _, id := range []string{played.ID, waiting.ID} {
		if st, _ := s.Session(ctx, id); st.Status != StatusFinished {
			t.Fatalf("%s still %s", id, st.Status)
		}
	}
}
