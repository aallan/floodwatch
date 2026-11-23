'use strict';

// Environment Agency flood warnings and alerts: the header indicator, the
// banner under the header, and the warning areas handed to the map.

const FloodWarnings = (() => {
  const REFRESH_MS = 5 * 60 * 1000;
  const TZ = 'Europe/London';
  const CLASS = { 1: 'severe', 2: 'warning', 3: 'alert' };
  const CHECK_FOR_FLOODING = 'https://check-for-flooding.service.gov.uk/';
  let warnings = [];
  let generated = null;

  const fmtWhen = ts => new Date(ts * 1000).toLocaleString('en-GB', {
    timeZone: TZ, weekday: 'short', day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit',
  });

  function plural(n, one, many) { return `${n} ${n === 1 ? one : many}`; }

  // One warning gives its kind and area, as Floodwatch has always shown it:
  // 'Flood alert: North Dartmoor Rivers'. More are counted by kind: '1 severe
  // flood warning, 2 flood warnings and 3 flood alerts in force'.
  const KIND = { 1: 'Severe flood warning', 2: 'Flood warning', 3: 'Flood alert' };
  function summaryText(list) {
    if (list.length === 1 && list[0].area) return `${KIND[list[0].severity] || 'Flood warning'}: ${list[0].area}`;
    const n = level => list.filter(w => w.severity === level).length;
    const parts = [];
    if (n(1)) parts.push(plural(n(1), 'severe flood warning', 'severe flood warnings'));
    if (n(2)) parts.push(plural(n(2), 'flood warning', 'flood warnings'));
    if (n(3)) parts.push(plural(n(3), 'flood alert', 'flood alerts'));
    const text = parts.length > 1 ? `${parts.slice(0, -1).join(', ')} and ${parts[parts.length - 1]}` : parts[0];
    return `${text} in force in the Taw catchment`;
  }

  function el(tag, cls, text) {
    const e = document.createElement(tag);
    if (cls) e.className = cls;
    if (text != null) e.textContent = text;
    return e;
  }

  // One warning, as shown in the banner and in its map popup.
  function detail(w, withMapButton) {
    const box = el('div', `flood-item is-${CLASS[w.severity]}`);
    const head = el('div', 'flood-item-head');
    head.appendChild(el('span', 'flood-chip', w.label));
    head.appendChild(el('span', 'flood-item-area', w.area || w.description || w.id));
    box.appendChild(head);
    const meta = [w.river, w.since ? `in force since ${fmtWhen(w.since)}` : null,
      w.updated && w.updated !== w.since ? `updated ${fmtWhen(w.updated)}` : null].filter(Boolean).join(' · ');
    if (meta) box.appendChild(el('div', 'flood-item-meta', meta));
    if (w.message) box.appendChild(el('div', 'flood-item-message', w.message));
    if (withMapButton && w.geometry) {
      const b = el('button', 'btn-toggle flood-show', 'Show on map');
      b.type = 'button';
      b.addEventListener('click', () => {
        const summary = $('#flood-banner .flood-summary');
        summary.setAttribute('aria-expanded', 'false');
        $('#flood-details').hidden = true;
        if (!location.hash.startsWith('#/map')) location.hash = '#/map';
        setTimeout(() => FloodMap.focusFlood(w.id), 50);
      });
      box.appendChild(b);
    }
    box.appendChild(el('div', 'flood-item-source', `Environment Agency flood area ${w.id}`));
    return box;
  }

  // The pill in the header while nothing is in force, which opens to say so.
  function renderClear() {
    const pill = $('#flood-pill');
    pill.title = 'No Environment Agency flood warnings or alerts in force in the Taw catchment';
    $('.flood-pill-text', pill).textContent = 'No flood warnings';
    const checked = generated ? new Date(generated * 1000).toLocaleTimeString('en-GB', { timeZone: TZ, hour: '2-digit', minute: '2-digit' }) : null;
    PillMenus.fill($('#flood-pill-panel'), 'No flood warnings on the Taw', [
      'The Environment Agency has no flood warnings or flood alerts in force in the Taw catchment.',
      `If any are issued, a banner appears under the header and the areas are outlined on the map. ${checked ? `Last checked at ${checked}; ` : ''}checked every 5 minutes.`,
    ], 'Environment Agency · ', { text: 'Check for flooding', href: CHECK_FOR_FLOODING });
  }

  function render() {
    const status = $('#flood-status');
    const banner = $('#flood-banner');
    const details = $('#flood-details');
    // The banner changes the header's height, and so the map's.
    if (banner.hidden !== !warnings.length) setTimeout(() => FloodMap.resize(), 0);
    if (!warnings.length) {
      banner.hidden = true;
      status.hidden = false;
      renderClear();
      return;
    }
    status.hidden = true;
    $('#flood-pill').setAttribute('aria-expanded', 'false');
    $('#flood-pill-panel').hidden = true;
    const worst = Math.min(...warnings.map(w => w.severity));
    banner.className = `flood-banner is-${CLASS[worst]}`;
    banner.hidden = false;
    $('.flood-summary-text', banner).textContent = summaryText(warnings);
    details.textContent = '';
    warnings.forEach(w => details.appendChild(detail(w, true)));
  }

  function load() {
    return getJSON('data/warnings.json')
      .then(d => {
        warnings = d.warnings || [];
        generated = d.generated || null;
        render();
        FloodMap.setFloodWarnings(warnings);
      })
      .catch(e => console.warn('No flood warning data:', e));
  }

  function init() {
    PillMenus.add($('#flood-status'));
    const summary = $('#flood-banner .flood-summary');
    summary.addEventListener('click', () => {
      const open = summary.getAttribute('aria-expanded') !== 'true';
      summary.setAttribute('aria-expanded', String(open));
      $('#flood-details').hidden = !open;
    });
    load();
    setInterval(load, REFRESH_MS);
  }

  return { init, detail, _internals: { summaryText } };
})();
