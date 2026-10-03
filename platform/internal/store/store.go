// Package store is the platform's SQLite persistence (PLAN.md 7.3, ADR-0018):
// sessions, players, join tokens, snapshots, events, flag attempts and
// challenge instances. Flag values are never stored.
package store

import (
	"context"
	"crypto/rand"
	"database/sql"
	"encoding/hex"
	"errors"
	"fmt"
	"strings"
	"time"

	_ "modernc.org/sqlite" // pure-Go driver, registers "sqlite"
)

// ErrNotFound is returned when a row does not exist.
var ErrNotFound = errors.New("not found")

// ErrTokenInvalid means a join token is unknown, used, expired, or for another session.
var ErrTokenInvalid = errors.New("join token invalid")

// JoinTokenTTL is how long a minted join token stays valid (docs/API.md).
const JoinTokenTTL = 60 * time.Second

// Session statuses.
const (
	StatusIdle     = "idle"
	StatusStarting = "starting"
	StatusRunning  = "running"
	StatusFinished = "finished"
)

// Session is one team playing one room once.
type Session struct {
	ID          string
	RoomID      string
	InviteCode  string
	ServerToken string
	Status      string
	CreatedAt   time.Time
	FinishedAt  time.Time
	Won         bool
	ElapsedS    int
	HintsUsed   int
	// Difficulty is the room difficulty id chosen at creation ("" = default).
	Difficulty string
}

// Instance is one running challenge for a session.
type Instance struct {
	SessionID   string
	ChallengeID string
	ContainerID string
	NetworkID   string
	HostPort    int
}

// Store wraps the database. Safe for concurrent use.
type Store struct {
	db  *sql.DB
	now func() time.Time
}

var migrations = []string{
	`CREATE TABLE sessions (
		id TEXT PRIMARY KEY,
		room_id TEXT NOT NULL,
		invite_code TEXT NOT NULL,
		server_token TEXT NOT NULL,
		status TEXT NOT NULL,
		created_at INTEGER NOT NULL,
		finished_at INTEGER NOT NULL DEFAULT 0,
		won INTEGER NOT NULL DEFAULT 0,
		elapsed_s INTEGER NOT NULL DEFAULT 0,
		hints_used INTEGER NOT NULL DEFAULT 0
	);
	CREATE TABLE players (
		session_id TEXT NOT NULL,
		player_id TEXT NOT NULL,
		display_name TEXT NOT NULL,
		PRIMARY KEY (session_id, player_id),
		UNIQUE (session_id, display_name)
	);
	CREATE TABLE join_tokens (
		token TEXT PRIMARY KEY,
		session_id TEXT NOT NULL,
		player_id TEXT NOT NULL,
		expires_at INTEGER NOT NULL,
		used INTEGER NOT NULL DEFAULT 0
	);
	CREATE TABLE snapshots (
		session_id TEXT PRIMARY KEY,
		saved_at INTEGER NOT NULL,
		body TEXT NOT NULL
	);
	CREATE TABLE events (
		id INTEGER PRIMARY KEY AUTOINCREMENT,
		session_id TEXT NOT NULL,
		at REAL NOT NULL,
		kind TEXT NOT NULL,
		player_id TEXT NOT NULL DEFAULT '',
		data TEXT NOT NULL DEFAULT '{}'
	);
	CREATE INDEX events_session ON events (session_id, id);
	CREATE TABLE flag_attempts (
		id INTEGER PRIMARY KEY AUTOINCREMENT,
		session_id TEXT NOT NULL,
		challenge_id TEXT NOT NULL,
		player_id TEXT NOT NULL,
		at INTEGER NOT NULL,
		accepted INTEGER NOT NULL
	);
	CREATE TABLE instances (
		session_id TEXT NOT NULL,
		challenge_id TEXT NOT NULL,
		container_id TEXT NOT NULL,
		network_id TEXT NOT NULL,
		host_port INTEGER NOT NULL,
		PRIMARY KEY (session_id, challenge_id)
	);`,
	`ALTER TABLE sessions ADD COLUMN difficulty TEXT NOT NULL DEFAULT ''`,
}

// Open opens (creating if needed) the database at path and migrates it.
// Use ":memory:" for tests.
func Open(ctx context.Context, path string) (*Store, error) {
	dsn := path
	if path != ":memory:" {
		dsn = "file:" + path + "?_pragma=journal_mode(WAL)&_pragma=busy_timeout(5000)&_pragma=foreign_keys(1)"
	}
	db, err := sql.Open("sqlite", dsn)
	if err != nil {
		return nil, fmt.Errorf("open %s: %w", path, err)
	}
	// One connection: SQLite has a single writer anyway, and deferred
	// transactions racing for the write lock fail with SQLITE_BUSY under
	// concurrent joins (review M3-P2). Also keeps :memory: one database.
	db.SetMaxOpenConns(1)
	s := &Store{db: db, now: time.Now}
	if err := s.migrate(ctx); err != nil {
		db.Close()
		return nil, err
	}
	return s, nil
}

// Close closes the database.
func (s *Store) Close() error { return s.db.Close() }

func (s *Store) migrate(ctx context.Context) error {
	if _, err := s.db.ExecContext(ctx, `CREATE TABLE IF NOT EXISTS schema_version (v INTEGER NOT NULL)`); err != nil {
		return fmt.Errorf("migrate: %w", err)
	}
	var v int
	err := s.db.QueryRowContext(ctx, `SELECT v FROM schema_version`).Scan(&v)
	if errors.Is(err, sql.ErrNoRows) {
		if _, err := s.db.ExecContext(ctx, `INSERT INTO schema_version (v) VALUES (0)`); err != nil {
			return fmt.Errorf("migrate: %w", err)
		}
	} else if err != nil {
		return fmt.Errorf("migrate: %w", err)
	}
	for i := v; i < len(migrations); i++ {
		tx, err := s.db.BeginTx(ctx, nil)
		if err != nil {
			return fmt.Errorf("migrate %d: %w", i+1, err)
		}
		if _, err := tx.ExecContext(ctx, migrations[i]); err != nil {
			tx.Rollback()
			return fmt.Errorf("migrate %d: %w", i+1, err)
		}
		if _, err := tx.ExecContext(ctx, `UPDATE schema_version SET v = ?`, i+1); err != nil {
			tx.Rollback()
			return fmt.Errorf("migrate %d: %w", i+1, err)
		}
		if err := tx.Commit(); err != nil {
			return fmt.Errorf("migrate %d: %w", i+1, err)
		}
	}
	return nil
}

// --- Sessions -----------------------------------------------------------

// CreateSession makes a new idle session with a fresh id, invite code and server token.
func (s *Store) CreateSession(ctx context.Context, roomID string) (Session, error) {
	return s.CreateSessionWithDifficulty(ctx, roomID, "")
}

// CreateSessionWithDifficulty creates a session that plays the room at the
// given difficulty id ("" = the room's default).
func (s *Store) CreateSessionWithDifficulty(ctx context.Context, roomID, difficulty string) (Session, error) {
	code, err := s.freeInviteCode(ctx)
	if err != nil {
		return Session{}, err
	}
	sess := Session{
		ID:          RandomID(12),
		RoomID:      roomID,
		InviteCode:  code,
		ServerToken: RandomHex(32),
		Status:      StatusIdle,
		CreatedAt:   s.now().UTC().Truncate(time.Second),
		Difficulty:  difficulty,
	}
	_, err = s.db.ExecContext(ctx,
		`INSERT INTO sessions (id, room_id, invite_code, server_token, status, created_at, difficulty) VALUES (?, ?, ?, ?, ?, ?, ?)`,
		sess.ID, sess.RoomID, sess.InviteCode, sess.ServerToken, sess.Status, sess.CreatedAt.Unix(), sess.Difficulty)
	if err != nil {
		return Session{}, fmt.Errorf("create session: %w", err)
	}
	return sess, nil
}

// freeInviteCode returns a code no unfinished session uses, so a code alone
// identifies the game to join.
func (s *Store) freeInviteCode(ctx context.Context) (string, error) {
	for i := 0; i < 20; i++ {
		code := InviteCode()
		var n int
		if err := s.db.QueryRowContext(ctx, `SELECT COUNT(*) FROM sessions WHERE invite_code = ? AND status != ?`, code, StatusFinished).Scan(&n); err != nil {
			return "", err
		}
		if n == 0 {
			return code, nil
		}
	}
	return "", errors.New("could not find a free invite code")
}

// SessionByInvite returns the newest session with this invite code
// (case-insensitive), or ErrNotFound.
func (s *Store) SessionByInvite(ctx context.Context, code string) (Session, error) {
	var id string
	err := s.db.QueryRowContext(ctx, `SELECT id FROM sessions WHERE invite_code = ? ORDER BY created_at DESC, rowid DESC LIMIT 1`,
		strings.ToUpper(strings.TrimSpace(code))).Scan(&id)
	if errors.Is(err, sql.ErrNoRows) {
		return Session{}, ErrNotFound
	}
	if err != nil {
		return Session{}, err
	}
	return s.Session(ctx, id)
}

// Session returns one session.
func (s *Store) Session(ctx context.Context, id string) (Session, error) {
	var sess Session
	var created, finished int64
	var won int
	err := s.db.QueryRowContext(ctx,
		`SELECT id, room_id, invite_code, server_token, status, created_at, finished_at, won, elapsed_s, hints_used, difficulty FROM sessions WHERE id = ?`, id).
		Scan(&sess.ID, &sess.RoomID, &sess.InviteCode, &sess.ServerToken, &sess.Status, &created, &finished, &won, &sess.ElapsedS, &sess.HintsUsed, &sess.Difficulty)
	if errors.Is(err, sql.ErrNoRows) {
		return Session{}, ErrNotFound
	}
	if err != nil {
		return Session{}, fmt.Errorf("session %s: %w", id, err)
	}
	sess.CreatedAt = time.Unix(created, 0).UTC()
	if finished > 0 {
		sess.FinishedAt = time.Unix(finished, 0).UTC()
	}
	sess.Won = won != 0
	return sess, nil
}

// SetStatus updates a session's status.
func (s *Store) SetStatus(ctx context.Context, id, status string) error {
	return s.exec1(ctx, `UPDATE sessions SET status = ? WHERE id = ?`, status, id)
}

// Finish marks a session finished with its result.
func (s *Store) Finish(ctx context.Context, id string, won bool, elapsedS, hintsUsed int) error {
	return s.exec1(ctx, `UPDATE sessions SET status = ?, finished_at = ?, won = ?, elapsed_s = ?, hints_used = ? WHERE id = ?`,
		StatusFinished, s.now().Unix(), boolInt(won), elapsedS, hintsUsed, id)
}

// Players returns the display names of everyone who has joined a session.
func (s *Store) Players(ctx context.Context, sessionID string) ([]string, error) {
	rows, err := s.db.QueryContext(ctx, `SELECT display_name FROM players WHERE session_id = ? ORDER BY rowid`, sessionID)
	if err != nil {
		return nil, fmt.Errorf("players: %w", err)
	}
	defer rows.Close()
	var out []string
	for rows.Next() {
		var n string
		if err := rows.Scan(&n); err != nil {
			return nil, err
		}
		out = append(out, n)
	}
	return out, rows.Err()
}

// --- Join tokens ----------------------------------------------------------

// MintJoinToken registers (or reuses) the player for this display name and
// returns a single-use token valid for JoinTokenTTL.
func (s *Store) MintJoinToken(ctx context.Context, sessionID, displayName string) (token, playerID string, err error) {
	displayName = strings.TrimSpace(displayName)
	tx, err := s.db.BeginTx(ctx, nil)
	if err != nil {
		return "", "", err
	}
	defer tx.Rollback()
	err = tx.QueryRowContext(ctx, `SELECT player_id FROM players WHERE session_id = ? AND display_name = ?`, sessionID, displayName).Scan(&playerID)
	if errors.Is(err, sql.ErrNoRows) {
		playerID = "p_" + RandomID(10)
		if _, err := tx.ExecContext(ctx, `INSERT INTO players (session_id, player_id, display_name) VALUES (?, ?, ?)`, sessionID, playerID, displayName); err != nil {
			return "", "", fmt.Errorf("add player: %w", err)
		}
	} else if err != nil {
		return "", "", fmt.Errorf("find player: %w", err)
	}
	token = RandomHex(24)
	if _, err := tx.ExecContext(ctx, `INSERT INTO join_tokens (token, session_id, player_id, expires_at) VALUES (?, ?, ?, ?)`,
		token, sessionID, playerID, s.now().Add(JoinTokenTTL).UnixMilli()); err != nil {
		return "", "", fmt.Errorf("mint token: %w", err)
	}
	return token, playerID, tx.Commit()
}

// ConsumeJoinToken checks and burns a join token for this session.
func (s *Store) ConsumeJoinToken(ctx context.Context, sessionID, token string) (playerID, displayName string, err error) {
	res, err := s.db.ExecContext(ctx,
		`UPDATE join_tokens SET used = 1 WHERE token = ? AND session_id = ? AND used = 0 AND expires_at > ?`,
		token, sessionID, s.now().UnixMilli())
	if err != nil {
		return "", "", fmt.Errorf("consume token: %w", err)
	}
	if n, _ := res.RowsAffected(); n != 1 {
		return "", "", ErrTokenInvalid
	}
	err = s.db.QueryRowContext(ctx,
		`SELECT p.player_id, p.display_name FROM join_tokens t JOIN players p ON p.session_id = t.session_id AND p.player_id = t.player_id WHERE t.token = ?`,
		token).Scan(&playerID, &displayName)
	if err != nil {
		return "", "", fmt.Errorf("token player: %w", err)
	}
	return playerID, displayName, nil
}

// --- Snapshots and events ---------------------------------------------------

// PutSnapshot stores the latest snapshot (opaque JSON) for a session.
func (s *Store) PutSnapshot(ctx context.Context, sessionID string, body []byte) error {
	_, err := s.db.ExecContext(ctx,
		`INSERT INTO snapshots (session_id, saved_at, body) VALUES (?, ?, ?)
		 ON CONFLICT (session_id) DO UPDATE SET saved_at = excluded.saved_at, body = excluded.body`,
		sessionID, s.now().Unix(), string(body))
	if err != nil {
		return fmt.Errorf("put snapshot: %w", err)
	}
	return nil
}

// Snapshot returns the latest snapshot or ErrNotFound.
func (s *Store) Snapshot(ctx context.Context, sessionID string) ([]byte, error) {
	var body string
	err := s.db.QueryRowContext(ctx, `SELECT body FROM snapshots WHERE session_id = ?`, sessionID).Scan(&body)
	if errors.Is(err, sql.ErrNoRows) {
		return nil, ErrNotFound
	}
	if err != nil {
		return nil, fmt.Errorf("snapshot: %w", err)
	}
	return []byte(body), nil
}

// Event is one session_events row.
type Event struct {
	At       float64 `json:"at"`
	Kind     string  `json:"kind"`
	PlayerID string  `json:"player_id,omitempty"`
	Data     string  `json:"-"` // raw JSON object
}

// AppendEvents appends events in order.
func (s *Store) AppendEvents(ctx context.Context, sessionID string, evs []Event) error {
	tx, err := s.db.BeginTx(ctx, nil)
	if err != nil {
		return err
	}
	defer tx.Rollback()
	for _, e := range evs {
		data := e.Data
		if data == "" {
			data = "{}"
		}
		if _, err := tx.ExecContext(ctx, `INSERT INTO events (session_id, at, kind, player_id, data) VALUES (?, ?, ?, ?, ?)`,
			sessionID, e.At, e.Kind, e.PlayerID, data); err != nil {
			return fmt.Errorf("append event: %w", err)
		}
	}
	return tx.Commit()
}

// Events returns a session's events in order.
func (s *Store) Events(ctx context.Context, sessionID string) ([]Event, error) {
	rows, err := s.db.QueryContext(ctx, `SELECT at, kind, player_id, data FROM events WHERE session_id = ? ORDER BY id`, sessionID)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	var out []Event
	for rows.Next() {
		var e Event
		if err := rows.Scan(&e.At, &e.Kind, &e.PlayerID, &e.Data); err != nil {
			return nil, err
		}
		out = append(out, e)
	}
	return out, rows.Err()
}

// RecordFlagAttempt logs a submission (never its value).
func (s *Store) RecordFlagAttempt(ctx context.Context, sessionID, challengeID, playerID string, accepted bool) error {
	_, err := s.db.ExecContext(ctx, `INSERT INTO flag_attempts (session_id, challenge_id, player_id, at, accepted) VALUES (?, ?, ?, ?, ?)`,
		sessionID, challengeID, playerID, s.now().Unix(), boolInt(accepted))
	return err
}

// FlagAttempts counts attempts for a session and challenge: (total, accepted).
func (s *Store) FlagAttempts(ctx context.Context, sessionID, challengeID string) (total, accepted int, err error) {
	err = s.db.QueryRowContext(ctx, `SELECT COUNT(*), COALESCE(SUM(accepted), 0) FROM flag_attempts WHERE session_id = ? AND challenge_id = ?`,
		sessionID, challengeID).Scan(&total, &accepted)
	return total, accepted, err
}

// --- Challenge instances ----------------------------------------------------

// PutInstance records a running challenge instance.
func (s *Store) PutInstance(ctx context.Context, in Instance) error {
	_, err := s.db.ExecContext(ctx,
		`INSERT INTO instances (session_id, challenge_id, container_id, network_id, host_port) VALUES (?, ?, ?, ?, ?)
		 ON CONFLICT (session_id, challenge_id) DO UPDATE SET container_id = excluded.container_id, network_id = excluded.network_id, host_port = excluded.host_port`,
		in.SessionID, in.ChallengeID, in.ContainerID, in.NetworkID, in.HostPort)
	return err
}

// Instances lists a session's challenge instances.
func (s *Store) Instances(ctx context.Context, sessionID string) ([]Instance, error) {
	rows, err := s.db.QueryContext(ctx, `SELECT session_id, challenge_id, container_id, network_id, host_port FROM instances WHERE session_id = ? ORDER BY challenge_id`, sessionID)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	var out []Instance
	for rows.Next() {
		var in Instance
		if err := rows.Scan(&in.SessionID, &in.ChallengeID, &in.ContainerID, &in.NetworkID, &in.HostPort); err != nil {
			return nil, err
		}
		out = append(out, in)
	}
	return out, rows.Err()
}

// DeleteInstances forgets a session's instances (after teardown).
func (s *Store) DeleteInstances(ctx context.Context, sessionID string) error {
	_, err := s.db.ExecContext(ctx, `DELETE FROM instances WHERE session_id = ?`, sessionID)
	return err
}

// --- helpers ------------------------------------------------------------------

func (s *Store) exec1(ctx context.Context, q string, args ...any) error {
	res, err := s.db.ExecContext(ctx, q, args...)
	if err != nil {
		return err
	}
	if n, _ := res.RowsAffected(); n == 0 {
		return ErrNotFound
	}
	return nil
}

func boolInt(b bool) int {
	if b {
		return 1
	}
	return 0
}

const idAlphabet = "abcdefghijkmnpqrstuvwxyz23456789"

// RandomID returns n random characters from an unambiguous lowercase alphabet.
func RandomID(n int) string { return randomFrom(idAlphabet, n) }

// InviteCode returns a 6-character code that is easy to read out loud.
func InviteCode() string { return strings.ToUpper(randomFrom("abcdefghjkmnpqrstuvwxyz23456789", 6)) }

// RandomHex returns 2n hex characters from n random bytes.
func RandomHex(n int) string {
	b := make([]byte, n)
	if _, err := rand.Read(b); err != nil {
		panic(err)
	}
	return hex.EncodeToString(b)
}

func randomFrom(alphabet string, n int) string {
	b := make([]byte, n)
	if _, err := rand.Read(b); err != nil {
		panic(err)
	}
	for i := range b {
		b[i] = alphabet[int(b[i])%len(alphabet)]
	}
	return string(b)
}
