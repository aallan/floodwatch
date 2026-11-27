'use strict';

// Station popups: the latest reading, and a chart of recent history fetched
// from /api/stations/<id>/readings when the popup opens.

const StationPopup = (() => {
  const TZ = 'Europe/London';
  const ALL = 'all';            // every reading the station has, from /api/ in buckets
  const RANGES = [[1, '24 hours'], [7, '7 days'], [28, '28 days'], [ALL, 'All time']];
  const FORECAST = 'forecast';  // the rain gauges' extra range: the next 48 hours
  const FLOW = 'flow';          // some level gauges' extra range: modelled river flow
  const HISTORY_DAYS = 28;
  const history = new Map();  // station id and range -> Promise of the API response

  // Formatting ---------------------------------------------------------------
  const unitLabel = u => (u === 'mAOD' ? 'm AOD' : u === 'mASD' ? 'm' : u || '');

  function fmtValue(s, v) {
    if (v == null) return '—';
    if (s.kind === 'rain') return `${Number(v).toLocaleString('en-GB', { maximumFractionDigits: 1 })} mm`;
    return `${Number(v).toLocaleString('en-GB', { minimumFractionDigits: 2, maximumFractionDigits: 2 })} ${unitLabel(s.unit)}`;
  }

  function fmtTime(ts, withDay = true) {
    const opts = { timeZone: TZ, hour: '2-digit', minute: '2-digit' };
    if (withDay) Object.assign(opts, { weekday: 'short', day: 'numeric', month: 'short' });
    return new Date(ts * 1000).toLocaleString('en-GB', opts);
  }

  function fmtAgo(ts) {
    const mins = Math.round((Date.now() / 1000 - ts) / 60);
    if (mins < 2) return 'just now';
    if (mins < 60) return `${mins} min ago`;
    const hours = Math.round(mins / 60);
    if (hours < 48) return `${hours} h ago`;
    return `${Math.round(hours / 24)} days ago`;
  }

  const STATE_TEXT = {
    high: 'Above its typical range', normal: 'Within its typical range', low: 'Below its typical range',
    unknown: 'No typical range published', stale: 'No recent reading', 'no-data': 'No readings yet',
    tidal: 'Tidal', raining: 'Raining', dry: 'Dry',
  };

  const TREND_ARROW = { rising: '↑', falling: '↓', steady: '→' };

  // One line for tooltips: the reading and what it means.
  function summary(s) {
    if (s.state === 'no-data') return 'no readings yet';
    if (s.kind === 'rain') {
      return s.state === 'stale' ? `no reading since ${fmtTime(s.ts)}`
        : `${fmtValue(s, s.h1)} in the last hour · ${fmtValue(s, s.h24)} in 24 h`;
    }
    const trend = s.trend ? ` · ${TREND_ARROW[s.trend]} ${s.trend}` : '';
    return s.state === 'stale' ? `${fmtValue(s, s.value)} at ${fmtTime(s.ts)}` : `${fmtValue(s, s.value)}${trend}`;
  }

  // Chart ----------------------------------------------------------------------
  const W = 320, H = 150, M = { l: 40, r: 8, t: 10, b: 22 };
  const NS = 'http://www.w3.org/2000/svg';

  function el(name, attrs = {}, parent) {
    const e = document.createElementNS(NS, name);
    for (const [k, v] of Object.entries(attrs)) e.setAttribute(k, v);
    if (parent) parent.appendChild(e);
    return e;
  }

  // Rain is drawn as totals per bucket: 15 minutes, an hour or a day.
  function rainBuckets(readings, days, from) {
    const size = days <= 1 ? 900 : days <= 7 ? 3600 : 86400;
    const sums = new Map();
    for (const [t, v] of readings) {
      if (t <= from) continue;
      const b = Math.floor(t / size) * size;
      sums.set(b, (sums.get(b) || 0) + v);
    }
    return { size, bars: [...sums.entries()].sort((a, b) => a[0] - b[0]) };
  }

  function niceTicks(lo, hi, count = 3) {
    const span = hi - lo || 1;
    const step0 = span / count;
    const mag = Math.pow(10, Math.floor(Math.log10(step0)));
    const step = [1, 2, 2.5, 5, 10].map(m => m * mag).find(s => s >= step0);
    const ticks = [];
    for (let v = Math.ceil(lo / step) * step; v <= hi + 1e-9; v += step) ticks.push(Number(v.toFixed(6)));
    return ticks;
  }

  // Round an axis out to whole tick steps, so its ends carry labels.
  function niceScale(lo, hi) {
    const ticks = niceTicks(lo, hi);
    const step = ticks.length > 1 ? ticks[1] - ticks[0] : (hi - lo) || 1;
    const nlo = Math.floor(lo / step + 1e-9) * step;
    const nhi = Math.ceil(hi / step - 1e-9) * step;
    return { lo: nlo, hi: nhi, ticks: niceTicks(nlo, nhi) };
  }

  // The level axis for a station, fixed across the 24-hour, 7-day and
  // 28-day views so they compare by eye. River levels start at zero and run
  // to 1.25 times the top of the typical range, or higher if the river has
  // been higher; tidal gauges fit the tides they've recorded.
  function levelAxis(s, data) {
    const vals = data.readings.map(r => r[1]);
    const dataLo = Math.min(...vals), dataHi = Math.max(...vals);
    if (s.kind === 'tidal') {
      const pad = (dataHi - dataLo) * 0.08 || 0.1;
      return niceScale(dataLo - pad, dataHi + pad);
    }
    const high = data.typical ? data.typical[1] : null;
    return niceScale(Math.min(0, dataLo), Math.max(high != null ? high * 1.25 : 0, dataHi * 1.1, 0.1));
  }

  // Ticks at UK local hours, found hour by hour so that the change between
  // GMT and BST never shifts them: every 6 hours over a day, midnights over a
  // week, and Monday midnights over four weeks.
  const hourParts = new Intl.DateTimeFormat('en-GB', { timeZone: TZ, hour: 'numeric', hourCycle: 'h23', weekday: 'short' });
  function timeTicks(from, to, days) {
    const ticks = [];
    for (let t = Math.ceil(from / 3600) * 3600; t <= to; t += 3600) {
      const parts = hourParts.formatToParts(new Date(t * 1000));
      const hour = Number(parts.find(p => p.type === 'hour').value);
      const weekday = parts.find(p => p.type === 'weekday').value;
      if (days <= 1 ? hour % 6 === 0 : hour === 0 && (days <= 7 || weekday === 'Mon')) ticks.push(t);
    }
    return ticks;
  }

  // Over all time, the first of each month, or every few months on a long
  // record. Months are found in UTC: an hour's difference doesn't show at
  // this scale.
  function monthTicks(from, to) {
    const months = (to - from) / (30.4 * 86400);
    const step = months > 36 ? 6 : months > 18 ? 3 : months > 8 ? 2 : 1;
    const d = new Date(from * 1000);
    let y = d.getUTCFullYear(), m = d.getUTCMonth() + 1;
    const ticks = [];
    for (;;) {
      if (m > 11) { y += Math.floor(m / 12); m %= 12; }
      const t = Date.UTC(y, m, 1) / 1000;
      if (t > to) break;
      if (m % step === 0) ticks.push(t);
      m++;
    }
    return ticks;
  }

  function tickLabel(t, days) {
    const d = new Date(t * 1000);
    if (days === ALL) {
      return d.toLocaleDateString('en-GB', { timeZone: 'UTC', month: 'short', ...(d.getUTCMonth() === 0 ? { year: 'numeric' } : {}) });
    }
    if (days <= 1) return d.toLocaleTimeString('en-GB', { timeZone: TZ, hour: '2-digit', minute: '2-digit' });
    if (days <= 7) return d.toLocaleDateString('en-GB', { timeZone: TZ, weekday: 'short' });
    return d.toLocaleDateString('en-GB', { timeZone: TZ, day: 'numeric', month: 'short' });
  }

  function drawChart(host, readout, key, s, data, days) {
    host.textContent = '';
    const now = Math.floor(Date.now() / 1000);
    const all = days === ALL;
    const first = data.first || (data.readings.length ? data.readings[0][0] : now - 86400);
    const from = all ? Math.min(first, now - 86400) - 1 : now - days * 86400;
    const svg = el('svg', { viewBox: `0 0 ${W} ${H}`, class: 'stn-chart', role: 'img',
      'aria-label': `${s.name}: readings ${all ? 'since ' + fmtDate(first) : 'over the last ' + (days === 1 ? '24 hours' : days + ' days')}` });
    host.appendChild(svg);
    const x = t => M.l + (t - from) / (now - from) * (W - M.l - M.r);

    let points, axis, barWidth = 0;
    if (s.kind === 'rain') {
      // Over all time the server has already totalled the rain into buckets.
      const { size, bars } = all ? { size: data.bucket, bars: data.readings } : rainBuckets(data.readings, days, from);
      points = bars;
      axis = niceScale(0, Math.max(1, ...bars.map(b => b[1])));
      barWidth = Math.max(1, (x(from + size) - x(from)) - 1);
    } else {
      points = data.readings.filter(r => r[0] > from);
      if (data.readings.length) axis = levelAxis(s, data);
    }
    key.textContent = chartKey(s, data, days);
    if (!points.length) {
      el('text', { x: W / 2, y: H / 2, 'text-anchor': 'middle', class: 'stn-chart-empty' }, svg)
        .textContent = 'No readings in this period';
      return;
    }
    const { lo, hi } = axis;
    const y = v => M.t + (1 - (v - lo) / (hi - lo)) * (H - M.t - M.b);

    // Grid and axes
    for (const v of axis.ticks) {
      el('line', { x1: M.l, x2: W - M.r, y1: y(v), y2: y(v), class: 'stn-grid' }, svg);
      el('text', { x: M.l - 5, y: y(v) + 3, 'text-anchor': 'end', class: 'stn-axis' }, svg).textContent =
        v.toLocaleString('en-GB', { maximumFractionDigits: 2 });
    }
    for (const t of all ? monthTicks(from, now) : timeTicks(from, now, days)) {
      el('line', { x1: x(t), x2: x(t), y1: M.t, y2: H - M.b, class: 'stn-grid' }, svg);
      el('text', { x: x(t), y: H - 6, 'text-anchor': 'middle', class: 'stn-axis' }, svg).textContent = tickLabel(t, days);
    }

    // Reference lines for river levels: the top of the typical range, and
    // the record high when it falls within the axis.
    const refLine = (v, cls) => {
      if (v != null && v >= lo && v <= hi) el('line', { x1: M.l, x2: W - M.r, y1: y(v), y2: y(v), class: cls }, svg);
    };
    if (s.kind === 'level') {
      refLine(data.record, 'stn-ref stn-ref-record');
      refLine(data.typical && data.typical[1], 'stn-ref stn-ref-high');
    }

    if (s.kind === 'rain') {
      for (const [t, v] of points) {
        if (v <= 0) continue;
        el('rect', { x: x(t), y: y(v), width: barWidth, height: y(0) - y(v), class: 'stn-bar' }, svg);
      }
    } else {
      // Break the line where readings are missing for more than an hour, or
      // over all time, for more than two of the server's buckets.
      const gap = all ? 2 * data.bucket : 3600;
      let d = '';
      let prev = null;
      for (const [t, v] of points) {
        d += `${prev === null || t - prev > gap ? 'M' : 'L'}${x(t).toFixed(1)},${y(v).toFixed(1)}`;
        prev = t;
      }
      el('path', { d, class: `stn-line stn-line-${s.kind}` }, svg);
    }

    // Hover readout
    const cursor = el('line', { y1: M.t, y2: H - M.b, class: 'stn-cursor', visibility: 'hidden' }, svg);
    const caption = s.kind === 'rain' ? rainBucketText(days, data.bucket) : all ? `(highest ${bucketText(data.bucket)})` : '';
    readout.textContent = '';
    svg.addEventListener('mousemove', e => {
      const box = svg.getBoundingClientRect();
      const t = from + ((e.clientX - box.left) * W / box.width - M.l) / (W - M.l - M.r) * (now - from);
      let best = null;
      for (const p of points) if (!best || Math.abs(p[0] - t) < Math.abs(best[0] - t)) best = p;
      if (!best) return;
      cursor.setAttribute('x1', x(best[0]));
      cursor.setAttribute('x2', x(best[0]));
      cursor.setAttribute('visibility', 'visible');
      readout.textContent = `${fmtTime(best[0])} · ${fmtValue(s, best[1])}${caption ? ' ' + caption : ''}`;
    });
    svg.addEventListener('mouseleave', () => {
      cursor.setAttribute('visibility', 'hidden');
      readout.textContent = '';
    });
  }

  const bucketText = size => ({ 3600: 'each hour', 10800: 'every 3 hours', 21600: 'every 6 hours',
    43200: 'every 12 hours', 86400: 'each day', 604800: 'each week' }[size] || '');
  const rainBucketText = (days, size) => (days === ALL
    ? { 3600: 'per hour', 10800: 'per 3 hours', 21600: 'per 6 hours', 43200: 'per 12 hours', 86400: 'per day', 604800: 'per week' }[size] || ''
    : days <= 1 ? 'per 15 minutes' : days <= 7 ? 'per hour' : 'per day');

  function fmtDate(ts) {
    return new Date(ts * 1000).toLocaleDateString('en-GB', { timeZone: TZ, day: 'numeric', month: 'short', year: 'numeric' });
  }

  // The line under each chart that says what it shows.
  function chartKey(s, data, days) {
    const since = days === ALL && data.first ? `Since ${fmtDate(data.first)}. ` : '';
    if (s.kind === 'rain') return `${since}Rainfall ${rainBucketText(days, data.bucket)}`;
    const highest = days === ALL ? `The highest reading ${bucketText(data.bucket)}. ` : '';
    if (s.kind === 'tidal') return `${since}${highest}${s.unit === 'mAOD' ? 'Height above Ordnance Datum' : 'Height at the gauge'}`;
    const high = data.typical ? data.typical[1] : null;
    if (high == null) return `${since}${highest}No typical range published for this gauge`;
    const record = data.record != null ? ` · record ${fmtValue(s, data.record)}` : '';
    return `${since}${highest}Dashed line: top of typical range, ${fmtValue(s, high)}${record}`;
  }

  // Rain forecast ----------------------------------------------------------------
  const forecasts = new Map();  // station id -> Promise of the API response

  function loadForecast(id) {
    if (!forecasts.has(id)) {
      const p = getJSON(`/api/forecast/rain/${encodeURIComponent(id)}`);
      p.catch(() => forecasts.delete(id));
      forecasts.set(id, p);
    }
    return forecasts.get(id);
  }

  // The next 48 hours as amber bars, one per hour, as on Floodwatch.
  function drawForecast(host, readout, key, d) {
    host.textContent = '';
    readout.textContent = '';
    const hours = d.hours || [];
    if (!hours.length) {
      host.textContent = 'No forecast is available right now.';
      key.textContent = '';
      return;
    }
    const from = hours[0][0], to = from + 48 * 3600;
    const total = hours.reduce((sum, h) => sum + h[1], 0);
    key.textContent = total > 0
      ? `Forecast rain per hour, from Open-Meteo · ${total.toLocaleString('en-GB', { maximumFractionDigits: 1 })} mm in all`
      : 'No rain forecast in the next 48 hours, from Open-Meteo';
    const svg = el('svg', { viewBox: `0 0 ${W} ${H}`, class: 'stn-chart', role: 'img',
      'aria-label': `Rain forecast for the next 48 hours: ${total.toFixed(1)} mm in all` });
    host.appendChild(svg);
    const x = t => M.l + (t - from) / (to - from) * (W - M.l - M.r);
    const axis = niceScale(0, Math.max(1, ...hours.map(h => h[1])));
    const y = v => M.t + (1 - (v - axis.lo) / (axis.hi - axis.lo)) * (H - M.t - M.b);
    for (const v of axis.ticks) {
      el('line', { x1: M.l, x2: W - M.r, y1: y(v), y2: y(v), class: 'stn-grid' }, svg);
      el('text', { x: M.l - 5, y: y(v) + 3, 'text-anchor': 'end', class: 'stn-axis' }, svg).textContent =
        v.toLocaleString('en-GB', { maximumFractionDigits: 2 });
    }
    for (const t of timeTicks(from, to, 1)) {
      el('line', { x1: x(t), x2: x(t), y1: M.t, y2: H - M.b, class: 'stn-grid' }, svg);
      const midnight = new Date(t * 1000).toLocaleTimeString('en-GB', { timeZone: TZ, hour: '2-digit' }) === '00';
      el('text', { x: x(t), y: H - 6, 'text-anchor': 'middle', class: 'stn-axis' }, svg).textContent =
        midnight ? tickLabel(t, 7) : tickLabel(t, 1);
    }
    const bw = Math.max(1, x(from + 3600) - x(from) - 1);
    for (const [t, mm] of hours) {
      if (mm > 0) el('rect', { x: x(t), y: y(mm), width: bw, height: y(0) - y(mm), class: 'stn-bar stn-bar-forecast' }, svg);
    }
    const cursor = el('line', { y1: M.t, y2: H - M.b, class: 'stn-cursor', visibility: 'hidden' }, svg);
    svg.addEventListener('mousemove', e => {
      const box = svg.getBoundingClientRect();
      const t = from + ((e.clientX - box.left) * W / box.width - M.l) / (W - M.l - M.r) * (to - from);
      const h = hours.find(r => t >= r[0] && t < r[0] + 3600);
      if (!h) return;
      cursor.setAttribute('x1', x(h[0] + 1800));
      cursor.setAttribute('x2', x(h[0] + 1800));
      cursor.setAttribute('visibility', 'visible');
      const chance = h[2] != null ? ` (${h[2]}% chance of rain)` : '';
      readout.textContent = `${fmtTime(h[0])} · ${h[1].toLocaleString('en-GB', { maximumFractionDigits: 1 })} mm${chance}`;
    });
    svg.addEventListener('mouseleave', () => { cursor.setAttribute('visibility', 'hidden'); readout.textContent = ''; });
  }

  // River flow forecast ----------------------------------------------------------
  const flows = new Map();  // station id -> Promise of the API response

  function loadFlow(id) {
    if (!flows.has(id)) {
      const p = getJSON(`/api/forecast/flow/${encodeURIComponent(id)}`);
      p.catch(() => flows.delete(id));
      flows.set(id, p);
    }
    return flows.get(id);
  }

  const fmtFlowNum = v => Number(v).toLocaleString('en-GB', { maximumFractionDigits: v < 10 ? 1 : 0 });
  const fmtFlow = v => `${fmtFlowNum(v)} m³/s`;

  // The mean of the measured flow on each day, keyed by the day's start, for
  // days with at least half their readings.
  function dailyMeans(measured, days) {
    const means = new Map();
    for (const [start] of days) {
      const v = measured.filter(r => r[0] >= start && r[0] < start + 86400).map(r => r[1]);
      if (v.length >= 48) means.set(start, v.reduce((a, b) => a + b, 0) / v.length);
    }
    return means;
  }

  // Daily modelled flow, the fortnight ahead in amber with the spread of the
  // forecast ensemble, against normal and high flow. The past week shows the
  // flow measured at the gauge, with the model's flow for the same days
  // fainter behind it, or the model's alone where the flow isn't measured.
  // Where the flow is measured, the forecast is scaled to start from it.
  function drawFlow(host, readout, key, d) {
    host.textContent = '';
    readout.textContent = '';
    const days = d.days || [];
    if (!days.length) {
      host.textContent = 'No flow forecast is available right now.';
      key.textContent = '';
      return;
    }
    const now = Math.floor(Date.now() / 1000);
    const from = days[0][0], to = days[days.length - 1][0] + 86400;
    const measured = (d.measured || []).filter(r => r[0] >= from && r[0] <= now);
    const hasMeasured = measured.length > 1;
    const means = dailyMeans(measured, days);
    const k = hasMeasured && d.anchor && d.anchor.ratio > 0 ? d.anchor.ratio : 1;
    const ratio = k.toLocaleString('en-GB', { maximumFractionDigits: 1 });
    key.textContent = (k !== 1
      ? `Blue: flow measured at NRFA gauge ${d.nrfa}, provisional. Amber: the GloFAS forecast, its falling flow multiplied by ${ratio} ` +
        'to start from the measured flow, with any rise from rain added at the model\'s own size. Faint blue: the model\'s own flow. '
      : hasMeasured
        ? `Blue: flow measured at NRFA gauge ${d.nrfa}, provisional. Faint blue and amber: daily flow modelled by GloFAS, scaled to that gauge's mean. `
        : `Daily flow modelled by GloFAS, scaled to NRFA gauge ${d.nrfa}. `) +
      `Dashed line: high flow, ${fmtFlow(d.high)} · dotted: normal, ${fmtFlow(d.normal)}`;
    const shown = d.scaled || days;
    const svg = el('svg', { viewBox: `0 0 ${W} ${H}`, class: 'stn-chart', role: 'img',
      'aria-label': `${d.river}: ${hasMeasured ? 'measured and ' : ''}modelled flow for the past week, and the forecast for the next fortnight` });
    host.appendChild(svg);
    const x = t => M.l + (t - from) / (to - from) * (W - M.l - M.r);
    const axis = niceScale(0, Math.max(d.high * 1.15, ...shown.map(r => r[3] ?? r[1]), ...measured.map(r => r[1])));
    const y = v => M.t + (1 - (v - axis.lo) / (axis.hi - axis.lo)) * (H - M.t - M.b);

    for (const v of axis.ticks) {
      el('line', { x1: M.l, x2: W - M.r, y1: y(v), y2: y(v), class: 'stn-grid' }, svg);
      el('text', { x: M.l - 5, y: y(v) + 3, 'text-anchor': 'end', class: 'stn-axis' }, svg).textContent =
        v.toLocaleString('en-GB', { maximumFractionDigits: 2 });
    }
    for (const t of timeTicks(from, to, 28)) {
      el('line', { x1: x(t), x2: x(t), y1: M.t, y2: H - M.b, class: 'stn-grid' }, svg);
      el('text', { x: x(t), y: H - 6, 'text-anchor': 'middle', class: 'stn-axis' }, svg).textContent = tickLabel(t, 28);
    }
    for (const [v, cls] of [[d.normal, 'stn-ref stn-ref-normal'], [d.high, 'stn-ref stn-ref-high']]) {
      el('line', { x1: M.l, x2: W - M.r, y1: y(v), y2: y(v), class: cls }, svg);
    }

    // Each day is plotted at its middle. The forecast starts with today.
    const mid = r => x(r[0] + 43200);
    const ahead = shown.filter(r => r[0] + 86400 > now);
    const past = shown.filter(r => r[0] + 86400 <= now);
    const spread = ahead.filter(r => r[2] != null && r[3] != null);
    if (spread.length > 1) {
      const top = spread.map(r => `${mid(r).toFixed(1)},${y(r[3]).toFixed(1)}`);
      const bottom = spread.slice().reverse().map(r => `${mid(r).toFixed(1)},${y(r[2]).toFixed(1)}`);
      el('path', { d: `M${top.join('L')}L${bottom.join('L')}Z`, class: 'stn-band' }, svg);
    }
    const line = (rows, cls) => {
      if (rows.length > 1) el('path', { d: 'M' + rows.map(r => `${mid(r).toFixed(1)},${y(r[1]).toFixed(1)}`).join('L'), class: cls }, svg);
    };
    if (k !== 1) {
      // The scaled forecast runs on from the latest measured flow.
      const last = measured[measured.length - 1];
      line(past, 'stn-line stn-line-model');
      const next = ahead.filter(r => r[0] + 43200 > last[0]);
      if (next.length) {
        el('path', { d: `M${x(last[0]).toFixed(1)},${y(last[1]).toFixed(1)}` +
          next.map(r => `L${mid(r).toFixed(1)},${y(r[1]).toFixed(1)}`).join(''), class: 'stn-line stn-line-forecast' }, svg);
      }
    } else {
      // The past line runs on into today, so the two halves join.
      line(ahead.length ? [...past, ahead[0]] : past, hasMeasured ? 'stn-line stn-line-model' : 'stn-line stn-line-level');
      line(ahead, 'stn-line stn-line-forecast');
    }
    if (hasMeasured) {
      // A gap of more than an hour in the readings is left as a gap in the line.
      const d0 = measured.map((r, i) => `${i && r[0] - measured[i - 1][0] <= 3600 ? 'L' : 'M'}${x(r[0]).toFixed(1)},${y(r[1]).toFixed(1)}`).join('');
      el('path', { d: d0, class: 'stn-line stn-line-level' }, svg);
    }
    if (now > from && now < to) {
      el('line', { x1: x(now), x2: x(now), y1: M.t, y2: H - M.b, class: 'stn-today' }, svg);
      el('text', { x: x(now) + 3, y: M.t + 8, class: 'stn-today-label' }, svg).textContent = 'Today';
    }

    const cursor = el('line', { y1: M.t, y2: H - M.b, class: 'stn-cursor', visibility: 'hidden' }, svg);
    svg.addEventListener('mousemove', e => {
      const box = svg.getBoundingClientRect();
      const t = from + ((e.clientX - box.left) * W / box.width - M.l) / (W - M.l - M.r) * (to - from);
      const r = shown.find(row => t >= row[0] && t < row[0] + 86400);
      if (!r) return;
      cursor.setAttribute('x1', mid(r));
      cursor.setAttribute('x2', mid(r));
      cursor.setAttribute('visibility', 'visible');
      const day = new Date(r[0] * 1000).toLocaleDateString('en-GB', { timeZone: TZ, weekday: 'short', day: 'numeric', month: 'short' });
      const range = r[2] != null && r[3] != null && r[3] - r[2] >= 0.05 ? `, range ${fmtFlowNum(r[2])}–${fmtFlow(r[3])}` : '';
      const mean = means.get(r[0]);
      readout.textContent = r[0] + 86400 > now ? `${day} · ${fmtFlow(r[1])} forecast${range}`
        : mean != null ? `${day} · ${fmtFlow(mean)} measured, ${fmtFlow(r[1])} modelled`
          : `${day} · ${fmtFlow(r[1])}${hasMeasured ? ' modelled' : ''}`;
    });
    svg.addEventListener('mouseleave', () => { cursor.setAttribute('visibility', 'hidden'); readout.textContent = ''; });
  }

  // Popup ----------------------------------------------------------------------
  function node(tag, cls, text) {
    const e = document.createElement(tag);
    if (cls) e.className = cls;
    if (text != null) e.textContent = text;
    return e;
  }

  function content(s) {
    const box = node('div', 'stn-pop');
    box.appendChild(node('div', 'stn-pop-title', s.name));
    const kindText = { level: 'River level', tidal: 'Tidal level', rain: 'Rain gauge' }[s.kind];
    box.appendChild(node('div', 'stn-pop-sub', [s.river, kindText].filter(Boolean).join(' · ')));

    const now = node('div', 'stn-pop-now');
    if (s.kind === 'rain') {
      now.appendChild(node('span', 'stn-pop-value', fmtValue(s, s.h24)));
      now.appendChild(node('span', 'stn-pop-note', 'in the last 24 hours'));
    } else {
      now.appendChild(node('span', 'stn-pop-value', fmtValue(s, s.value)));
      if (s.trend) now.appendChild(node('span', `stn-pop-trend is-${s.trend}`, `${TREND_ARROW[s.trend]} ${s.trend}`));
    }
    box.appendChild(now);
    const state = node('div', `stn-pop-state is-${s.state}`);
    state.appendChild(node('span', 'stn-pop-dot'));
    state.appendChild(document.createTextNode(STATE_TEXT[s.state] || ''));
    if (s.ts) state.appendChild(node('span', 'stn-pop-when', ` · ${fmtAgo(s.ts)}`));
    box.appendChild(state);

    const tabs = node('div', 'stn-pop-ranges');
    const chartHost = node('div', 'stn-pop-chart');
    const key = node('div', 'stn-pop-key');
    const readout = node('div', 'stn-pop-readout');
    box.append(tabs, chartHost, key, readout);
    const source = node('div', 'stn-pop-source', `Environment Agency station ${s.id} · `);
    const download = node('a', 'stn-pop-link', 'Download as CSV');
    download.href = `/api/stations/${encodeURIComponent(s.id)}/readings.csv`;
    download.setAttribute('download', '');
    source.appendChild(download);
    box.appendChild(source);

    let current = 7;
    const render = () => {
      chartHost.classList.add('loading');
      if (current === FORECAST || current === FLOW) {
        const [get, draw] = current === FLOW ? [loadFlow, drawFlow] : [loadForecast, drawForecast];
        get(s.id).then(d => {
          chartHost.classList.remove('loading');
          draw(chartHost, readout, key, d);
        }).catch(() => {
          chartHost.classList.remove('loading');
          chartHost.textContent = 'The forecast is unavailable right now.';
          key.textContent = '';
        });
        return;
      }
      load(s.id, current === ALL).then(data => {
        chartHost.classList.remove('loading');
        drawChart(chartHost, readout, key, s, data, current);
      }).catch(() => {
        chartHost.classList.remove('loading');
        chartHost.textContent = 'History is unavailable right now.';
      });
    };
    const ranges = s.kind === 'rain' ? [...RANGES, [FORECAST, 'Next 48 h']]
      : s.flow ? [...RANGES, [FLOW, 'River flow']] : RANGES;
    for (const [days, text] of ranges) {
      const b = node('button', 'btn-toggle' + (days === current ? ' active' : ''), text);
      b.type = 'button';
      b.addEventListener('click', () => {
        current = days;
        tabs.querySelectorAll('button').forEach(x => x.classList.toggle('active', x === b));
        render();
      });
      tabs.appendChild(b);
    }
    render();
    return box;
  }

  // The last four weeks serve the 24-hour, 7-day and 28-day charts; all time
  // is a separate, bucketed request.
  function load(id, all = false) {
    const k = `${id}|${all ? ALL : HISTORY_DAYS}`;
    if (!history.has(k)) {
      const p = getJSON(`/api/stations/${encodeURIComponent(id)}/readings?days=${all ? ALL : HISTORY_DAYS}`);
      p.catch(() => history.delete(k));
      history.set(k, p);
    }
    return history.get(k);
  }

  // Forget cached history when new readings arrive.
  function invalidate() { history.clear(); }

  function open(map, s) {
    L.popup({ className: 'stn-popup', maxWidth: 360, minWidth: 320, autoPanPadding: [24, 24] })
      .setLatLng([s.lat, s.lon])
      .setContent(content(s))
      .openOn(map);
  }

  // Storm overflows ------------------------------------------------------------
  const OVERFLOW_STATE = {
    spilling: 'Spilling now', recent: 'Spilled in the last 48 hours',
    quiet: 'Not spilling', offline: 'Monitor offline',
  };

  function fmtDay(ts) {
    return new Date(ts * 1000).toLocaleDateString('en-GB', { timeZone: TZ, day: 'numeric', month: 'short', year: 'numeric' });
  }

  function fmtHours(h) {
    if (h == null) return '—';
    if (h < 1) return `${Math.round(h * 60)} min`;
    return `${h.toLocaleString('en-GB', { maximumFractionDigits: h < 10 ? 1 : 0 })} h`;
  }

  // One line for tooltips.
  function overflowSummary(o) {
    if (o.state === 'spilling') return o.since ? `spilling since ${fmtTime(o.since)}` : 'spilling now';
    if (o.state === 'offline') return 'monitor offline';
    if (o.last_end) return `last spill ended ${fmtAgo(o.last_end)}`;
    return 'no spills recorded';
  }

  // The last 30 days as a strip, one bar per spill.
  function spillStrip(host, events, now) {
    const from = now - 30 * 86400;
    const SW = 320, SH = 46, L = 4, R = 4, T = 6, B = 16;
    const svg = el('svg', { viewBox: `0 0 ${SW} ${SH}`, class: 'stn-chart', role: 'img',
      'aria-label': `${events.length} spills recorded in the last 30 days` });
    const x = t => L + (Math.max(t, from) - from) / (now - from) * (SW - L - R);
    el('rect', { x: L, y: T, width: SW - L - R, height: SH - T - B, class: 'cso-strip-bg' }, svg);
    for (const t of timeTicks(from, now, 28)) {
      el('line', { x1: x(t), x2: x(t), y1: T, y2: SH - B, class: 'stn-grid' }, svg);
      el('text', { x: x(t), y: SH - 4, 'text-anchor': 'middle', class: 'stn-axis' }, svg).textContent = tickLabel(t, 28);
    }
    for (const [start, end] of events) {
      const x1 = x(start), x2 = x(end || now);
      el('rect', { x: x1, y: T, width: Math.max(1.5, x2 - x1), height: SH - T - B, class: 'cso-strip-bar' }, svg);
    }
    host.appendChild(svg);
  }

  function annualBars(host, annual) {
    const rows = annual.filter(a => a[1] != null);
    if (!rows.length) return;
    const SW = 320, SH = 92, L = 4, R = 4, T = 14, B = 16;
    const max = Math.max(...rows.map(a => a[1]), 1);
    const svg = el('svg', { viewBox: `0 0 ${SW} ${SH}`, class: 'stn-chart', role: 'img', 'aria-label': 'Spill hours per year' });
    const slot = (SW - L - R) / rows.length;
    rows.forEach(([year, hours, spills], i) => {
      const h = (SH - T - B) * hours / max;
      const cx = L + slot * i + slot / 2;
      el('rect', { x: cx - slot * 0.3, y: SH - B - h, width: slot * 0.6, height: Math.max(h, 0.5), class: 'cso-year-bar' }, svg);
      el('text', { x: cx, y: SH - B - h - 3, 'text-anchor': 'middle', class: 'stn-axis' }, svg).textContent = fmtHours(hours);
      el('text', { x: cx, y: SH - 4, 'text-anchor': 'middle', class: 'stn-axis' }, svg).textContent =
        spills != null ? `${year} · ${spills}` : String(year);
    });
    host.appendChild(svg);
  }

  // South West Water's names and asset types are full of abbreviations:
  // 'Chulmleigh WWTW SSO' is a wastewater treatment works' settled storm
  // overflow. They're spelt out, as Floodwatch has always shown them.
  const ABBREVIATIONS = [
    [/\bWWTW\b/gi, 'wastewater treatment works'],
    [/\bWWTP\b/gi, 'wastewater treatment plant'],
    [/\bSTW\b/gi, 'sewage treatment works'],
    [/\bSTP\b/gi, 'sewage treatment plant'],
    [/\bSSO\b/g, 'settled storm overflow'],
    [/\bCSO\b/g, 'combined sewer overflow'],
    [/\bSO\b/g, 'storm overflow'],
    [/\bPS\b/g, 'pumping station'],
  ];
  function spellOut(text) {
    if (!text) return '';
    let out = String(text);
    for (const [re, long] of ABBREVIATIONS) out = out.replace(re, long);
    // 'Barnstaple (ashford)' -> 'Barnstaple (Ashford)', and a capital to start.
    out = out.replace(/\((\p{Ll})/gu, (_, c) => `(${c.toUpperCase()}`);
    return out.charAt(0).toUpperCase() + out.slice(1);
  }
  const overflowName = o => (o.name ? spellOut(o.name) : `Storm overflow ${o.id}`);

  function overflowContent(o) {
    const box = node('div', 'stn-pop');
    box.appendChild(node('div', 'stn-pop-title', overflowName(o)));
    const sub = node('div', 'stn-pop-sub', [o.water, 'Storm overflow'].filter(Boolean).join(' · '));
    box.appendChild(sub);
    const state = node('div', `stn-pop-state cso-state is-${o.state}`);
    state.appendChild(node('span', 'stn-pop-dot'));
    state.appendChild(document.createTextNode(OVERFLOW_STATE[o.state] || ''));
    const when = o.state === 'spilling' || o.state === 'offline'
      ? (o.since ? ` · since ${fmtTime(o.since)}` : '')
      : (o.last_end ? ` · last spill ended ${fmtAgo(o.last_end)}` : '');
    if (when) state.appendChild(node('span', 'stn-pop-when', when));
    box.appendChild(state);

    const body = node('div', 'cso-body loading');
    box.appendChild(body);
    const source = node('div', 'stn-pop-source', `South West Water monitor · permit ${o.id}`);
    box.appendChild(source);

    getJSON(`/api/overflows/${encodeURIComponent(o.id)}`).then(d => {
      body.classList.remove('loading');
      if (d.asset_type) sub.textContent = [o.water, spellOut(d.asset_type)].filter(Boolean).join(' · ');
      const now = Math.floor(Date.now() / 1000);
      const from = now - 30 * 86400;
      const hours = d.events.reduce((sum, [s, e]) => sum + (Math.min(e || now, now) - Math.max(s, from)) / 3600, 0);

      body.appendChild(node('div', 'cso-head', 'Last 30 days'));
      const stats = node('div', 'cso-stats');
      stats.appendChild(node('span', 'stn-pop-value', String(d.events.length)));
      stats.appendChild(node('span', 'stn-pop-note', d.events.length === 1 ? 'spill' : 'spills'));
      stats.appendChild(node('span', 'stn-pop-value', fmtHours(hours)));
      stats.appendChild(node('span', 'stn-pop-note', 'spilling'));
      body.appendChild(stats);
      spillStrip(body, d.events, now);
      if (d.log_started && d.log_started > from) {
        body.appendChild(node('div', 'stn-pop-key', `Spills recorded here since ${fmtDay(d.log_started)}; earlier ones in this window aren't included.`));
      }
      if (d.annual.length) {
        body.appendChild(node('div', 'cso-head', 'Spill hours per year, and number of spills'));
        annualBars(body, d.annual);
        body.appendChild(node('div', 'stn-pop-key', 'From the regulatory annual returns'));
      }
      if (d.last_seen) source.textContent = `South West Water monitor · permit ${o.id} · last report ${fmtAgo(d.last_seen)}`;
    }).catch(() => {
      body.classList.remove('loading');
      body.textContent = 'Spill history is unavailable right now.';
    });
    return box;
  }

  function openOverflow(map, o) {
    L.popup({ className: 'stn-popup', maxWidth: 360, minWidth: 320, autoPanPadding: [24, 24] })
      .setLatLng([o.lat, o.lon])
      .setContent(overflowContent(o))
      .openOn(map);
  }

  return {
    open, summary, invalidate, openOverflow, overflowSummary, overflowName,
    // The chart arithmetic and formatting, for tests/js.
    _internals: { niceTicks, niceScale, levelAxis, timeTicks, monthTicks, tickLabel, rainBuckets, fmtValue, fmtFlow,
      dailyMeans, spellOut },
  };
})();
