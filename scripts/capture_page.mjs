// Capture a page at an exact size, for scripts/screenshot.py.
//
//   node scripts/capture_page.mjs PORT URL OUT.png WIDTH HEIGHT SCALE WAIT_MS
//
// Chrome's own --screenshot lays a page out 87 px short of the window and
// then grows it, and Leaflet leaves tiles undrawn across the late resize.
// Here the viewport is fixed through the DevTools protocol before the page
// loads, so it never changes size. Chrome must already be running with
// --remote-debugging-port=PORT. Node 22 or later (for its WebSocket).

import { writeFileSync } from 'node:fs';

const [port, url, out, width, height, scale, waitMs] = process.argv.slice(2);
const targets = await (await fetch(`http://127.0.0.1:${port}/json/list`)).json();
const page = targets.find(t => t.type === 'page');
if (!page) throw new Error('no page target in Chrome');

const ws = new WebSocket(page.webSocketDebuggerUrl);
await new Promise((resolve, reject) => { ws.onopen = resolve; ws.onerror = reject; });

let id = 0;
const pending = new Map();
const events = [];
ws.onmessage = ({ data }) => {
  const msg = JSON.parse(data);
  if (msg.id && pending.has(msg.id)) {
    const { resolve, reject } = pending.get(msg.id);
    pending.delete(msg.id);
    msg.error ? reject(new Error(msg.error.message)) : resolve(msg.result);
  } else if (msg.method) {
    events.push(msg.method);
  }
};
const send = (method, params = {}) => new Promise((resolve, reject) => {
  pending.set(++id, { resolve, reject });
  ws.send(JSON.stringify({ id, method, params }));
});
const sleep = ms => new Promise(r => setTimeout(r, ms));

await send('Emulation.setDeviceMetricsOverride',
  { width: +width, height: +height, deviceScaleFactor: 0, mobile: false });
await send('Page.enable');
await send('Page.navigate', { url });
for (let t = 0; t < 30000 && !events.includes('Page.loadEventFired'); t += 100) await sleep(100);
// Time for live.json, the overlays and the basemap tiles to arrive.
await sleep(+waitMs);
const { data } = await send('Page.captureScreenshot', { format: 'png' });
writeFileSync(out, Buffer.from(data, 'base64'));
await send('Browser.close').catch(() => {});
ws.close();
