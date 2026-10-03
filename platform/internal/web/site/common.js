export const validCode = code => /^[A-Z0-9]{6}$/.test(code);

export function bindName(input, onChange = () => {}) {
  try { input.value = Array.from(localStorage.getItem('escapebox.name') || '').slice(0, 24).join(''); } catch { /* Storage is optional. */ }
  input.addEventListener('input', () => {
    input.value = Array.from(input.value).slice(0, 24).join('');
    try { localStorage.setItem('escapebox.name', input.value); } catch { /* Continue without storage. */ }
    onChange();
  });
}

export async function api(path, options = {}) {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 10000);
  try {
    const response = await fetch(path, { ...options, signal: controller.signal, cache: 'no-store' });
    const data = await response.json();
    if (!response.ok) {
      const error = new Error(typeof data.message === 'string' ? data.message : 'The platform could not complete that request. Try again.');
      error.status = response.status;
      throw error;
    }
    return data;
  } catch (error) {
    if (error.status) throw error;
    throw new Error('Cannot reach the platform. Check your connection and try again.');
  } finally { clearTimeout(timeout); }
}

export function elapsed(seconds) {
  const total = Math.max(0, Math.floor(Number(seconds) || 0));
  return `${String(Math.floor(total / 60)).padStart(2, '0')}:${String(total % 60).padStart(2, '0')}`;
}
