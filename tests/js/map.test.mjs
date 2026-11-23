import { test } from 'node:test';
import assert from 'node:assert/strict';
import { load } from './load.mjs';

// map.js builds a few Leaflet objects as it loads; these stand in for them.
const L = {
  Layer: { extend: proto => function (...a) { Object.assign(this, proto); if (this.initialize) this.initialize(...a); } },
  layerGroup: () => ({}),
};
const window = { matchMedia: () => ({ matches: false }) };
const { FloodMap } = load({ L, window }, 'utils.js', 'map.js')('FloodMap');
const { gaugeState, gaugeText, clusterSummary, gaugeScale, APPROACH } = FloodMap._internals;

const level = (value, extra = {}) => ({ kind: 'level', value, state: 'normal', typical: [0.2, 2.0], ...extra });

test('a river level turns amber near the top of its typical range, and red above it', () => {
  assert.equal(APPROACH, 0.7);
  assert.equal(gaugeState(level(1.39)), 'normal');
  assert.equal(gaugeState(level(1.4)), 'approach');          // 70% of 2.0
  assert.equal(gaugeState(level(2.3, { state: 'high' })), 'high');
  assert.equal(gaugeState(level(1.9, { state: 'stale' })), 'stale');
  assert.equal(gaugeState(level(1.9, { typical: [null, null], state: 'unknown' })), 'unknown');
});

test('rain gauges are raining, dry or stale by the last hour', () => {
  assert.equal(gaugeState({ kind: 'rain', h1: 0.4, state: 'raining' }), 'raining');
  assert.equal(gaugeState({ kind: 'rain', h1: 0, state: 'dry' }), 'dry');
  assert.equal(gaugeState({ kind: 'rain', h1: 0.4, state: 'stale' }), 'stale');
  assert.equal(gaugeState({ kind: 'tidal', value: 2.6, state: 'tidal' }), 'tidal');
});

test('the number on a gauge', () => {
  assert.equal(gaugeText(level(1.2867)), '1.29');
  assert.equal(gaugeText({ kind: 'rain', h1: 0.25 }), '0.3');
  assert.equal(gaugeText({ kind: 'rain', h1: null }), '–');
  assert.equal(gaugeText({ kind: 'level', value: null }), '–');
});

test('a cluster shows its most urgent level, and any rising river or rain', () => {
  const c = clusterSummary([
    level(0.5), level(1.6, { trend: 'rising' }), { kind: 'rain', h1: 0, state: 'dry' },
  ]);
  assert.equal(c.count, 3);
  assert.equal(c.worst, 'approach');
  assert.equal(c.rising, true);
  assert.equal(c.raining, false);
  const high = clusterSummary([level(2.4, { state: 'high' }), level(1.6), { kind: 'rain', h1: 1.2, state: 'raining' }]);
  assert.equal(high.worst, 'high');
  assert.equal(high.raining, true);
  // A stale gauge's old trend doesn't count as rising.
  assert.equal(clusterSummary([level(0.5, { state: 'stale', trend: 'rising' })]).rising, false);
  assert.equal(clusterSummary([level(0.5)]).worst, 'normal');
});

test('gauges are smaller zoomed out', () => {
  assert.equal(gaugeScale(9), 0.75);
  assert.equal(gaugeScale(10), 0.9);
  assert.equal(gaugeScale(13), 1);
});
