import { api, bindName, validCode } from './common.js';

bindName(document.querySelector('[data-player-name]'));
const codeInput = document.querySelector('#join-code');
const joinError = document.querySelector('#join-error');
codeInput.addEventListener('input', () => {
  codeInput.value = codeInput.value.toUpperCase();
  codeInput.removeAttribute('aria-invalid');
  joinError.textContent = '';
});
document.querySelector('#join-form').addEventListener('submit', event => {
  event.preventDefault();
  const code = codeInput.value.trim().toUpperCase();
  if (!validCode(code)) {
    joinError.textContent = 'Enter a 6-character code using letters and digits.';
    codeInput.setAttribute('aria-invalid', 'true');
    codeInput.focus();
    return;
  }
  location.assign(`/g/${encodeURIComponent(code)}`);
});

const list = document.querySelector('#room-list');
const message = document.querySelector('#catalog-message');
const retry = document.querySelector('#catalog-retry');
async function loadRooms() {
  retry.hidden = true;
  message.textContent = 'Loading rooms…';
  try {
    const rooms = await api('/api/catalog');
    list.replaceChildren();
    for (const room of rooms) {
      const card = document.querySelector('#room-template').content.cloneNode(true);
      card.querySelector('h3').textContent = room.title;
      card.querySelector('.case-id').textContent = `Room · ${room.room_id} · v${room.version}`;
      card.querySelector('.room-summary').textContent = room.summary;
      showIntro(card.querySelector('.intro-video'), room.intro, room.title);
      const [min, max] = room.players;
      card.querySelector('.room-facts').textContent = `${room.duration_minutes} minutes · ${min === max ? min : `${min}–${max}`} players`;
      card.querySelectorAll('[data-hacker]').forEach(element => { element.hidden = !(room.challenges > 0); });
      const select = card.querySelector('select');
      const levels = room.difficulties || [];
      if (levels.length) {
        card.querySelector('.difficulty').hidden = false;
        for (const level of levels) {
          const option = document.createElement('option');
          option.value = level.id;
          option.textContent = level.title;
          select.append(option);
        }
        const description = card.querySelector('.difficulty-description');
        const describe = () => { description.textContent = levels.find(level => level.id === select.value)?.description || ''; };
        select.addEventListener('change', describe);
        describe();
      }
      const button = card.querySelector('.start-button');
      const errorText = card.querySelector('.card-error');
      button.addEventListener('click', async () => {
        button.disabled = true;
        select.disabled = true;
        button.textContent = 'Starting…';
        errorText.textContent = '';
        try {
          const game = await api('/api/sessions', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ room_id: room.room_id, difficulty: levels.length ? select.value : '' }) });
          if (!validCode(game.invite_code)) throw new Error('The platform returned an invalid invitation. Try again.');
          location.assign(`/g/${encodeURIComponent(game.invite_code)}`);
        } catch (error) {
          errorText.textContent = error.message;
          button.disabled = false;
          select.disabled = false;
          button.textContent = 'Start a game';
        }
      });
      list.append(card);
    }
    message.textContent = rooms.length ? '' : 'No rooms are installed yet. Check back soon.';
  } catch (error) {
    message.textContent = error.message;
    retry.hidden = false;
  }
}
retry.addEventListener('click', loadRooms);
loadRooms();

async function loadStatus() {
  const line = document.querySelector('#platform-status');
  try {
    const status = await api('/api/status');
    const free = status.free < 0 ? null : status.free;
    line.textContent = `${status.running} running · ${status.waiting} waiting${free === null ? '' : ` · ${free} free`}`;
  } catch { line.textContent = 'Platform status unavailable'; }
}
loadStatus();

// showIntro sets up a room's intro video (click to play, sound on) when the
// platform lists one. preload="none" keeps the page light until it is played.
function showIntro(video, intro, title) {
  if (!intro || !intro.video) return;
  video.src = intro.video;
  if (intro.poster) video.poster = intro.poster;
  video.setAttribute('aria-label', `Intro video: ${title}`);
  video.hidden = false;
}
