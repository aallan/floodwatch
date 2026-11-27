'use strict';

// Hash router: #/map (default), #/agents and #/about.
const VIEWS = ['map', 'agents', 'about'];
let mapStarted = false;

function route() {
  const name = (location.hash.replace(/^#\//, '') || 'map').split('/')[0];
  const view = VIEWS.includes(name) ? name : 'map';
  $$('.view').forEach(v => v.classList.toggle('active', v.id === `view-${view}`));
  $$('#nav .nav-btn').forEach(a => a.classList.toggle('active', a.getAttribute('href') === `#/${view}`));
  document.body.classList.toggle('map-mode', view === 'map');
  if (view === 'map') {
    // Start the map the first time it is visible: Leaflet sizes and fits
    // itself from the container, which has no size while the view is hidden.
    if (!mapStarted) { mapStarted = true; FloodMap.init('map'); }
    else FloodMap.resize();
  }
}

async function loadMeta() {
  try {
    const meta = await getJSON('data/meta.json');
    $('#data-generated').textContent = `Map data downloaded from OpenStreetMap on ${fmtDate(meta.generated)}.`;
  } catch (e) {
    $('#status').textContent = 'No map data yet. Run make data.';
  }
}

// The version running, under the title.
async function loadVersion() {
  try {
    const { version } = await getJSON('/api/version');
    if (version) $('#version').textContent = `(${version})`;
  } catch (e) { /* the version is a nicety; leave it out */ }
}

// The status line reports how fresh the live readings are.
function showLiveStatus(live) {
  const newest = Math.max(0, ...live.stations.map(s => s.ts || 0));
  if (!newest) {
    $('#status').textContent = 'No live readings yet';
    return;
  }
  const when = new Date(newest * 1000).toLocaleString('en-GB', {
    timeZone: 'Europe/London', weekday: 'short', day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit',
  });
  const delayed = Date.now() / 1000 - newest > 3600 ? ' (delayed)' : '';
  $('#status').textContent = `Latest readings ${when}${delayed}`;
}

// The Copy button on the Agents tab. navigator.clipboard needs https or localhost.
function initCopyButtons() {
  $$('.copy-btn').forEach(btn => btn.addEventListener('click', async () => {
    try {
      await navigator.clipboard.writeText($(`#${btn.dataset.copy}`).textContent);
      btn.textContent = 'Copied';
      setTimeout(() => { btn.textContent = 'Copy'; }, 2000);
    } catch (e) { /* no clipboard here; the address can still be selected */ }
  }));
}

document.addEventListener('DOMContentLoaded', () => {
  initCopyButtons();
  initTheme();
  window.onThemeChange = () => FloodMap.restyle();
  window.onLiveUpdate = showLiveStatus;
  window.addEventListener('hashchange', route);
  route();
  loadMeta();
  loadVersion();
  FloodWarnings.init();
  WeatherWarnings.init();
  Drought.init();
});
