# Lobby site spec (M5, ADR-0028)

The platform's front door. Files live in `platform/internal/web/site/` and are embedded into the platform binary (`web.go`). The platform serves:

| URL | File |
|---|---|
| `/` | `site/index.html` (lobby) |
| `/g/{code}` | `site/game.html` (one game's page; JS reads the code from `location.pathname`) |
| `/site/<file>` | any other file in `site/` (CSS, JS, images) |

## Constraints
- **Plain HTML, CSS and JavaScript.** No framework, no build step, no npm, no CDN or other external requests (fonts included): it must work on a tailnet with no internet.
- **Untrusted text.** Everything shown from the API is set with `textContent` or DOM APIs, never `innerHTML`. That includes player names, which are chosen by players and are untrusted.
- **Layout and accessibility.** Works from 360 px wide (phones) to wide desktop monitors. Keyboard accessible, visible focus, sufficient contrast, `prefers-reduced-motion` respected.
- **Look.** Dark, moody, a little "night office / security console", matching the game: deep navy/charcoal background, off-white text, one accent (amber like a maglock LED) and green for "escaped". Readable system font stack.
- **Name.** The player's name is kept in `localStorage["escapebox.name"]` (wrapped in try/catch; the site must work without storage). Max 24 characters.

## API (same origin)
- `GET /api/catalog` -> `[{room_id, title, version, duration_minutes, players: [min, max], challenges, difficulties: [{id, title, description}], summary, pack?}]`
  - `challenges > 0` means a hacker room (CTF-enhanced, ADR-0023).
  - `difficulties` may be empty, meaning a single default level.
- `POST /api/sessions` body `{room_id, difficulty}` (difficulty: an id, or "" for the default) -> `201 {session_id, invite_code}`. Errors return `{error, message}`; show `message` to the player:
  - `429 too_many_games`
  - `503 games_full`
  - `400 unknown_difficulty`
  - `404 unknown_room`
- `GET /api/games/{code}` -> `{code, room_id, title, difficulty, difficulty_title, status, players: [names], players_max, duration_minutes, hacker_room, created_at, won, elapsed_s}`. `404 bad_invite` for unknown codes. `status` is one of:
  - `idle`: waiting for the first player;
  - `starting` or `running`: in progress;
  - `finished`: if `won`, escaped in `elapsed_s`; if `expired`, the platform closed it (nobody joined, or the team left); otherwise the time ran out. Expired games cannot be joined (`410 game_expired`).
- `GET /api/status` -> `{waiting, running, finished, max_games, free}` (`max_games` 0 and `free` -1 = no cap).
- Playing: the browser client is at `/play/?code=<CODE>&name=<url-encoded name>`. Open it in the same tab.

## Pages
**Lobby (`/`)**
- Header: "ESCAPEBOX" and one line of what it is (cooperative online escape rooms, play in your browser).
- Name field, shared with the game page.
- **Join a game:** a 6-character code input (uppercase, letters and digits) and a Join button that goes to `/g/<CODE>`. Show an inline error if the code is malformed.
- **Rooms:** one card per catalog room, with:
  - title, summary, duration, player range;
  - a "Hacker room" badge when `challenges > 0`, with a one-line note: the CTF parts use a second browser tab, and harder levels may expect your own tools;
  - a difficulty picker when there are difficulties, showing the selected level's description;
  - a "Start a game" button. It POSTs `/api/sessions` and on success goes to `/g/<invite_code>`; on error it shows the message on the card.
- Footer: a small status line from `/api/status` ("2 games running · 1 waiting · 4 slots").

**Game page (`/g/{code}`)**
- Room title, difficulty title, hacker-room badge.
- The join code shown large, the invite link (`location.origin + "/g/" + code`), and a "Copy invite link" button: `navigator.clipboard` with a select-the-text fallback, plus brief "Copied" feedback.
- Status line (waiting / in progress / escaped in mm:ss / ended), a players list ("3 / 4 players"), polled every 3 s while the page is visible. Stop polling once finished.
- Name field (shared, as above) and a big "Play" button to `/play/?code=...&name=...` (disabled with a hint if the name is empty or the game is finished).
- Unknown code: a friendly "No game has that code" with a link back to the lobby.
- A "Back to lobby" link.

## Verification
- Run the platform locally (`go run ./platform/cmd/platform -addr :8097 -data <tmpdir> -rooms game/rooms -game game -web build/client-web -packs build/packs -transport ws`) and exercise every state with curl and the browser.
- `go test ./platform/...` must pass.
- Screenshots via headless Chrome (`google-chrome --headless=new --screenshot=... --window-size=...`) of the lobby and of a game page, at 1440x900 and 390x844, in `docs/screenshots/m5-lobby/`.
