import { test } from 'node:test';
import assert from 'node:assert/strict';
import { load } from './load.mjs';

const { esc, StationPopup } = load('utils.js', 'stations.js')('esc', 'StationPopup');
const { niceTicks, niceScale, levelAxis, timeTicks, tickLabel, rainBuckets, fmtValue, fmtFlow } =
  StationPopup._internals;

const ukHour = t => new Date(t * 1000).toLocaleTimeString('en-GB', { timeZone: 'Europe/London', hour: '2-digit' });
const utc = (...a) => Date.UTC(...a) / 1000;
// Arrays made in the sandbox have its own Array prototype; compare plain copies.
const plain = x => JSON.parse(JSON.stringify(x));

test('esc escapes markup', () => {
  assert.equal(esc(`<img src=x onerror="a('b')">&`), '&lt;img src=x onerror=&quot;a(&#39;b&#39;)&quot;&gt;&amp;');
  assert.equal(esc(null), '');
  assert.equal(esc(0), '0');
});

test('axis ticks fall on round numbers', () => {
  assert.deepEqual(plain(niceTicks(0, 7.3)), [0, 2.5, 5]);
  assert.deepEqual(plain(niceScale(0, 7.3)), { lo: 0, hi: 7.5, ticks: [0, 2.5, 5, 7.5] });
  const s = niceScale(0.37, 0.81);
  assert.ok(s.lo <= 0.37 && s.hi >= 0.81);
});

test('a river level axis runs from zero past the typical range', () => {
  const s = { kind: 'level' };
  const quiet = levelAxis(s, { typical: [0.2, 2], readings: [[0, 0.5], [1, 1.0]] });
  assert.equal(quiet.lo, 0);
  assert.ok(quiet.hi >= 2.5);
  const flood = levelAxis(s, { typical: [0.2, 2], readings: [[0, 0.5], [1, 4.0]] });
  assert.ok(flood.hi >= 4.4);
});

test('a tidal axis fits the tides', () => {
  const axis = levelAxis({ kind: 'tidal' }, { readings: [[0, -2.1], [1, 2.4]] });
  assert.deepEqual([axis.lo, axis.hi], [-4, 4]);   // padded, then rounded out to 2 m steps
});

test('week ticks land on UK midnights across the change from BST', () => {
  // British Summer Time ends at 01:00 UTC on Sunday 25 October 2026.
  const from = utc(2026, 9, 21, 12), to = utc(2026, 9, 28, 12);
  const ticks = timeTicks(from, to, 7);
  assert.equal(ticks.length, 7);
  for (const t of ticks) assert.equal(ukHour(t), '00');
  const labels = ticks.map(t => tickLabel(t, 7));
  assert.deepEqual(plain(labels), ['Thu', 'Fri', 'Sat', 'Sun', 'Mon', 'Tue', 'Wed']);
});

test('day ticks fall every 6 hours of UK time', () => {
  const ticks = timeTicks(utc(2026, 6, 1, 0), utc(2026, 6, 2, 0), 1);
  assert.deepEqual(plain(ticks.map(ukHour)), ['06', '12', '18', '00']);
});

test('28-day ticks fall on Monday midnights', () => {
  const ticks = timeTicks(utc(2026, 9, 2), utc(2026, 9, 30), 28);
  assert.equal(ticks.length, 4);
  for (const t of ticks) assert.equal(tickLabel(t, 7), 'Mon');
});

test('rain is summed into hours over a week', () => {
  const from = utc(2026, 9, 30, 0);
  const readings = [[from - 900, 9], [from + 900, 0.2], [from + 1800, 0.4], [from + 3600, 1.0]];
  const { size, bars } = rainBuckets(readings, 7, from);
  assert.equal(size, 3600);
  assert.deepEqual(plain(bars.map(([t, v]) => [t - from, Math.round(v * 10) / 10])), [[0, 0.6], [3600, 1.0]]);
});

test('values are formatted with their units', () => {
  assert.equal(fmtValue({ kind: 'level', unit: 'mASD' }, 0.5), '0.50 m');
  assert.equal(fmtValue({ kind: 'tidal', unit: 'mAOD' }, 2.345), '2.35 m AOD');
  assert.equal(fmtValue({ kind: 'rain' }, 1.25), '1.3 mm');
  assert.equal(fmtValue({ kind: 'rain' }, null), '—');
  assert.equal(fmtFlow(4.75), '4.8 m³/s');
  assert.equal(fmtFlow(53.8), '54 m³/s');
});

test('tooltip summaries', () => {
  const { summary, overflowSummary } = StationPopup;
  assert.equal(summary({ kind: 'level', unit: 'm', state: 'normal', value: 0.8, trend: 'rising' }), '0.80 m · ↑ rising');
  assert.equal(summary({ kind: 'rain', state: 'dry', h1: 0, h24: 1.2 }), '0 mm in the last hour · 1.2 mm in 24 h');
  assert.equal(summary({ state: 'no-data' }), 'no readings yet');
  assert.equal(overflowSummary({ state: 'offline' }), 'monitor offline');
  assert.equal(overflowSummary({ state: 'quiet' }), 'no spills recorded');
  assert.equal(overflowSummary({ state: 'spilling' }), 'spilling now');
});

test('measured flow is averaged by day, for days with enough readings', () => {
  const { dailyMeans } = StationPopup._internals;
  const day = utc(2026, 10, 1);
  const full = Array.from({ length: 96 }, (_, i) => [day + i * 900, i < 48 ? 2 : 4]);
  const sparse = Array.from({ length: 10 }, (_, i) => [day + 86400 + i * 900, 9]);
  const means = dailyMeans([...full, ...sparse], [[day, 1], [day + 86400, 1], [day + 2 * 86400, 1]]);
  assert.equal(means.get(day), 3);
  assert.equal(means.has(day + 86400), false);   // ten readings aren't a day
  assert.equal(means.has(day + 2 * 86400), false);
});

test('all-time charts tick on the first of the month, more sparsely on a long record', () => {
  const { monthTicks, tickLabel } = StationPopup._internals;
  const t = (y, m, d = 1) => Date.UTC(y, m, d) / 1000;
  assert.deepEqual(plain(monthTicks(t(2026, 0, 13), t(2026, 4, 20))), [t(2026, 1), t(2026, 2), t(2026, 3), t(2026, 4)]);
  // Ten months: every other month, on even months (Jan, Mar, May...)
  assert.deepEqual(plain(monthTicks(t(2026, 0, 13), t(2026, 10, 23))),
    [t(2026, 2), t(2026, 4), t(2026, 6), t(2026, 8), t(2026, 10)]);
  assert.equal(tickLabel(t(2026, 2), 'all'), 'Mar');
  assert.equal(tickLabel(t(2027, 0), 'all'), 'Jan 2027');
});

test('storm overflow names and asset types are spelt out', () => {
  const { spellOut } = StationPopup._internals;
  assert.equal(spellOut('Chulmleigh WWTW SSO'), 'Chulmleigh wastewater treatment works settled storm overflow');
  assert.equal(spellOut('Barnstaple (ashford) STW'), 'Barnstaple (Ashford) sewage treatment works');
  assert.equal(spellOut('Rock Park CSO'), 'Rock Park combined sewer overflow');
  assert.equal(spellOut('WWTW at Lapford'), 'Wastewater treatment works at Lapford');
  assert.equal(spellOut('Inlet SO at WwTW'), 'Inlet storm overflow at wastewater treatment works');
  assert.equal(spellOut('SO on sewer network'), 'Storm overflow on sewer network');
  assert.equal(StationPopup.overflowName({ id: 'SBB1' }), 'Storm overflow SBB1');
});
