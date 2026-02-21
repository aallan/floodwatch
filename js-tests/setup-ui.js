/**
 * Test harness for js/floodwatch.js — provides the DOM scaffold and global
 * mocks (Leaflet, Chart.js, Papa Parse, fetch, canvas 2D) so the script
 * can be eval'd in a jsdom environment without real network or rendering.
 *
 * Usage: import from floodwatch.test.js before any test runs.
 */
import { vi } from 'vitest';
import fs from 'node:fs';
import path from 'node:path';

// ============================================================
// 1. DOM scaffold (mirrors the elements index.html provides)
// ============================================================
document.body.innerHTML = `
    <div id="header">
        <div class="header-left"><h1>Floodwatch</h1></div>
        <div class="header-right">
            <span class="flood-status" id="flood-status">
                <span class="flood-status-dot"></span>
                <span class="flood-status-label">No warnings</span>
            </span>
            <span class="last-updated" id="last-updated"></span>
            <button id="refresh-btn">
                <span class="spinner"></span>
                <span class="btn-text">Refresh Data</span>
            </button>
        </div>
    </div>
    <div id="content-area">
        <div id="flood-warnings" class="flood-warnings hidden">
            <div class="flood-warnings-summary">
                <span class="flood-warnings-icon"></span>
                <span class="flood-warnings-text" id="flood-warnings-text"></span>
                <span class="flood-warnings-chevron">&#x25BE;</span>
            </div>
            <div class="flood-warnings-details" id="flood-warnings-details"></div>
        </div>
        <div id="map"></div>
    </div>
    <div class="refresh-log hidden" id="refresh-log"></div>
`;

// ============================================================
// 2. Canvas 2D context mock
// ============================================================
const ctxStore = new WeakMap();

function createMockCtx() {
    return {
        fillText: vi.fn(),
        clearRect: vi.fn(),
        setTransform: vi.fn(),
        beginPath: vi.fn(),
        moveTo: vi.fn(),
        lineTo: vi.fn(),
        stroke: vi.fn(),
        save: vi.fn(),
        restore: vi.fn(),
        fillRect: vi.fn(),
        arc: vi.fn(),
        fill: vi.fn(),
        measureText: vi.fn(() => ({ width: 50 })),
        createLinearGradient: vi.fn(() => ({ addColorStop: vi.fn() })),
        setLineDash: vi.fn(),
        fillStyle: '',
        strokeStyle: '',
        font: '',
        textAlign: '',
        textBaseline: '',
        lineWidth: 1,
        globalAlpha: 1,
    };
}

// Patch canvas getContext globally for jsdom
const origGetContext = HTMLCanvasElement.prototype.getContext;
HTMLCanvasElement.prototype.getContext = function (type) {
    if (type === '2d') {
        if (!ctxStore.has(this)) ctxStore.set(this, createMockCtx());
        return ctxStore.get(this);
    }
    return origGetContext?.call(this, type) ?? null;
};

/** Retrieve the mock 2D context for a canvas element. */
export function getMockCtx(canvas) {
    return ctxStore.get(canvas);
}

// ============================================================
// 3. Leaflet mock
// ============================================================
function createMockPopup(html) {
    const el = document.createElement('div');
    el.innerHTML = typeof html === 'string' ? html : '';
    return { getElement: () => el, setContent: (h) => { el.innerHTML = h; } };
}

export function createMockMarker() {
    let popup = null;
    const marker = {
        addTo: vi.fn(function () { return this; }),
        bindPopup: vi.fn(function (html) {
            popup = createMockPopup(html);
            return this;
        }),
        unbindPopup: vi.fn(function () { popup = null; return this; }),
        openPopup: vi.fn(function () { return this; }),
        getPopup: vi.fn(() => popup),
        on: vi.fn(function () { return this; }),
        setIcon: vi.fn(function () { return this; }),
        options: { zIndexOffset: 500 },
    };
    return marker;
}

const mockMap = {
    addTo: vi.fn(),
    eachLayer: vi.fn(),
    removeLayer: vi.fn(),
    invalidateSize: vi.fn(),
    addLayer: vi.fn(),
    setView: vi.fn(),
    fitBounds: vi.fn(),
    on: vi.fn(),
    getZoom: vi.fn(() => 10),
};

const L = {
    map: vi.fn(() => mockMap),
    tileLayer: vi.fn(() => ({ addTo: vi.fn() })),
    marker: vi.fn(() => createMockMarker()),
    divIcon: vi.fn((opts) => opts),
    circleMarker: vi.fn(() => ({
        bindTooltip: vi.fn(),
    })),
    geoJSON: vi.fn(() => ({ addTo: vi.fn() })),
    control: vi.fn(() => {
        const ctrl = {
            onAdd: null,
            addTo: vi.fn(function () {
                if (this.onAdd) {
                    const el = this.onAdd(mockMap);
                    if (el) document.body.appendChild(el);
                }
            }),
        };
        return ctrl;
    }),
    DomUtil: {
        create: (tag, cls) => {
            const el = document.createElement(tag);
            if (cls) el.className = cls;
            return el;
        },
    },
    DomEvent: {
        disableClickPropagation: vi.fn(),
    },
};

globalThis.L = L;

// ============================================================
// 4. Chart.js mock
// ============================================================
globalThis.Chart = vi.fn(function (canvas, config) {
    this.canvas = canvas;
    this.config = config;
    this.chartArea = { top: 10, bottom: 200, left: 40, right: 380 };
    this.destroy = vi.fn();
    this.update = vi.fn();
});
globalThis.Chart.register = vi.fn();

// ============================================================
// 5. Papa Parse mock
// ============================================================
globalThis.Papa = {
    parse: vi.fn((url, opts) => {
        if (opts?.complete) opts.complete({ data: [] });
    }),
};

// ============================================================
// 6. fetch mock
// ============================================================
globalThis.fetch = vi.fn(() =>
    Promise.resolve({
        ok: true,
        json: () => Promise.resolve({ items: [], features: [] }),
        text: () => Promise.resolve(''),
        headers: new Headers(),
    })
);

// ============================================================
// 7. localStorage mock (jsdom provides one, but ensure it's clean)
// ============================================================
globalThis.localStorage.clear();

// ============================================================
// 8. Load FloodwatchCore (UMD module — works with require)
// ============================================================
globalThis.FloodwatchCore = require('../js/floodwatch-core.js');

// ============================================================
// 9. Load floodwatch.js via eval in the global scope
// ============================================================
// Using indirect eval — (0, eval)(...) — so that top-level function
// declarations land on the global object.  let/const are block-scoped
// even in indirect eval, so we rewrite them to var for testability.
const scriptPath = path.resolve(__dirname, '..', 'js', 'floodwatch.js');
let scriptSource = fs.readFileSync(scriptPath, 'utf-8');

// Convert top-level let/const to var so they become global properties.
// Only match declarations at the start of a line (top-level), not
// those inside functions/blocks (which are indented).
scriptSource = scriptSource.replace(/^(let|const) /gm, 'var ');

const indirectEval = eval;
indirectEval(scriptSource);

// Give init()'s async work a tick to settle
await new Promise((r) => setTimeout(r, 50));
