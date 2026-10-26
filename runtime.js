/* Small compatibility layer for the Badbadak view, formerly mounted inside Pendar. */
const ALL = [];
const DATA = './data';
const MESHKI_ROOT = 'https://meshki.media/';

function esc(value) {
  return String(value ?? '').replace(/[&<>"']/g, ch => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[ch]));
}
function getJSON(path, timeoutMs = 12000) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  return fetch(path, { signal: controller.signal, cache: 'no-store' })
    .then(response => { if (!response.ok) throw new Error(`HTTP ${response.status}`); return response.json(); })
    .finally(() => clearTimeout(timer));
}
function routeURL(route) {
  const value = String(route || '').replace(/^#\/?/, '').replace(/^\/+|\/+$/g, '');
  if (value.startsWith('story/')) return `https://pendar.io/${value}/`;
  if (value.startsWith('figure/')) return `https://pendar.io/${value}/`;
  if (value.startsWith('entity/')) return `https://pendar.io/${value}/`;
  return `https://pendar.io/${value}/`;
}
function setHash(route) {
  const value = String(route || '').replace(/^#?/, '#');
  if (location.hash !== value) history.replaceState(null, '', `${location.pathname}${location.search}${value}`);
}
function setTab() {}
function show(view) {
  document.getElementById('badbadak-view').hidden = view !== 'badbadak';
}
async function loadMeshkiSeries() {
  try {
    const value = await getJSON(`${DATA}/series-showcase.json`, 8000);
    return { rows: Array.isArray(value) ? value : (value.rows || []) };
  } catch (_) { return { rows: [] }; }
}
