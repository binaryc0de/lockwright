import { api, bindName, validCode, elapsed } from './common.js';

const code = location.pathname.split('/')[2].toUpperCase();
const nameInput = document.querySelector('[data-player-name]');
const play = document.querySelector('#play-button');
const hint = document.querySelector('#play-hint');
const message = document.querySelector('#page-message');
const retry = document.querySelector('#game-retry');
let game = null;
let available = false;
let finished = false;
let loading = false;
let timer;
function updatePlay() {
  const hasName = nameInput.value.trim().length > 0;
  play.disabled = !available || finished || !hasName;
  hint.textContent = finished ? 'This game has finished. Start another from the lobby.' : !available ? 'Waiting for the platform to confirm this game.' : !hasName ? 'Enter your name to play. Up to 24 characters.' : game?.status === 'idle' ? 'You can enter first: the others join you inside.' : 'Your team is inside. Join them.';
}
bindName(nameInput, updatePlay);
updatePlay();
document.querySelector('#play-form').addEventListener('submit', event => {
  event.preventDefault();
  if (play.disabled) return;
  const params = new URLSearchParams({ code: game.code, name: nameInput.value.trim() });
  location.assign(`/play/?${params}`);
});

function render(data) {
  game = data;
  available = true;
  finished = data.status === 'finished';
  document.querySelector('#game-details').hidden = false;
  document.querySelector('#room-title').textContent = data.title;
  document.title = `${data.title} · ESCAPEBOX`;
  const difficulty = document.querySelector('#difficulty-title');
  difficulty.textContent = data.difficulty_title;
  difficulty.hidden = !data.difficulty_title;
  document.querySelector('#hacker-badge').hidden = !data.hacker_room;
  document.querySelector('#game-hacker-note').hidden = !data.hacker_room;
  document.querySelector('#game-duration').textContent = `${data.duration_minutes} minutes`;
  const intro = document.querySelector('#intro-video');
  if (data.intro && data.intro.video && !intro.getAttribute('src')) {
    intro.src = data.intro.video;
    if (data.intro.poster) intro.poster = data.intro.poster;
    intro.setAttribute('aria-label', `Intro video: ${data.title}`);
    intro.hidden = false;
  }
  const codeBox = document.querySelector('#game-code');
  if (codeBox.dataset.code !== data.code) {
    codeBox.replaceChildren(...Array.from(data.code).map(ch => { const s = document.createElement('span'); s.textContent = ch; return s; }));
    codeBox.setAttribute('aria-label', `Join code ${Array.from(data.code).join(' ')}`);
    codeBox.dataset.code = data.code;
  }
  const invite = `${location.origin}/g/${encodeURIComponent(data.code)}`;
  const link = document.querySelector('#invite-link');
  if (link.value !== invite) link.value = invite;
  const status = document.querySelector('#game-status');
  status.parentElement.classList.toggle('escaped', finished && data.won);
  document.querySelector('#status-led').className = `led ${data.status === 'idle' ? 'wait' : finished ? (data.won ? 'on' : 'off') : 'on'}`;
  status.textContent = data.status === 'idle' ? 'Waiting for the team: the room opens when the first player enters' : !finished ? 'In progress' : data.won ? `Escaped in ${elapsed(data.elapsed_s)}` : data.expired ? (data.players.length === 0 ? 'Expired · nobody joined in time.' : 'Expired · the team left it unfinished.') : 'Ended · Time ran out or the game ended.';
  const players = document.querySelector('#players');
  // Avoid rebuilding the list on every poll, including while a reader uses it.
  if (JSON.stringify(data.players) !== players.dataset.names) {
    players.replaceChildren();
    for (const name of data.players) {
      const item = document.createElement('li');
      item.textContent = name;
      players.append(item);
    }
    players.dataset.names = JSON.stringify(data.players);
  }
  document.querySelector('#player-count').textContent = `${data.players.length} / ${data.players_max} players`;
  document.querySelector('#players-empty').hidden = data.players.length > 0;
  document.querySelector('#players-empty').textContent = finished ? 'No players joined this game.' : 'Nobody has badged in yet.';
  updatePlay();
}
function schedule() {
  clearTimeout(timer);
  if (!finished && !document.hidden) timer = setTimeout(loadGame, 3000);
}
// The first load always runs (an invite opened in a background tab must not
// stay blank); after that, polling pauses while the tab is hidden.
async function loadGame(first = false) {
  if (loading || finished || (document.hidden && !first)) return;
  loading = true;
  retry.hidden = true;
  try {
    if (!validCode(code)) { const error = new Error(); error.status = 404; throw error; }
    render(await api(`/api/games/${encodeURIComponent(code)}`));
    message.textContent = '';
  } catch (error) {
    available = false;
    if (error.status === 404) {
      finished = true;
      document.querySelector('#game-details').hidden = true;
      document.querySelector('#unknown-game').hidden = false;
      message.textContent = '';
    } else {
      message.textContent = `${error.message} ${game ? 'Game updates are paused until we reconnect.' : ''}`;
      retry.hidden = false;
    }
    updatePlay();
  } finally {
    loading = false;
    schedule();
  }
}
retry.addEventListener('click', () => { clearTimeout(timer); loadGame(); });
document.addEventListener('visibilitychange', () => {
  clearTimeout(timer);
  if (!document.hidden) loadGame();
});
window.addEventListener('pagehide', () => { clearTimeout(timer); });
loadGame(true);

const link = document.querySelector('#invite-link');
let feedbackTimer;
document.querySelector('#copy-invite').addEventListener('click', async () => {
  const feedback = document.querySelector('#copy-feedback');
  clearTimeout(feedbackTimer);
  try {
    if (!navigator.clipboard?.writeText) throw new Error('Clipboard unavailable');
    await navigator.clipboard.writeText(link.value);
    feedback.textContent = 'Copied';
    feedbackTimer = setTimeout(() => { feedback.textContent = ''; }, 3000);
  } catch {
    link.focus();
    link.select();
    feedback.textContent = 'Link selected. Copy it with Ctrl+C, ⌘C, or your phone’s Copy menu.';
  }
});
