import { test } from 'node:test';
import assert from 'node:assert/strict';
import { load } from './load.mjs';

// Runs route() with a stand-in page and reports which view is showing.
function routeTo(hash) {
  const views = ['map', 'agents', 'about'].map(n => ({ id: `view-${n}`, active: false, classList: { toggle(_, on) { this.owner.active = on; } } }));
  views.forEach(v => { v.classList.owner = v; });
  const context = {
    location: { hash },
    $$: sel => (sel === '.view' ? views : []),
    document: { body: { classList: { toggle() {} } }, addEventListener() {} },
    FloodMap: { init() {}, resize() {} },
    window: { addEventListener() {} },
  };
  load(context, 'app.js')('route').route();
  return views.filter(v => v.active).map(v => v.id);
}

test('#/agents shows the agents view, and nothing else does', () => {
  assert.deepEqual(routeTo('#/agents'), ['view-agents']);
  assert.deepEqual(routeTo('#/about'), ['view-about']);
  assert.deepEqual(routeTo(''), ['view-map']);
});
