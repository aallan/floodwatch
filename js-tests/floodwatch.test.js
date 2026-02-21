/**
 * UI integration tests for js/floodwatch.js.
 *
 * These tests cover DOM interactions, event delegation, and canvas
 * rendering — the UI layer that had zero test coverage when two bugs
 * slipped through the v1.0.0 CSS/JS extraction refactor:
 *
 *   Bug 1: popupopen listener registered after the event already fired
 *   Bug 2: canvas text drawn at default 300×150 then CSS-stretched
 */
import { describe, test, expect, vi, beforeEach } from 'vitest';
import { createMockMarker, getMockCtx } from './setup-ui.js';


// ============================================================
// P0 — sizeCanvasToDisplay (would have caught Bug 2)
// ============================================================

describe('sizeCanvasToDisplay', () => {
    test('sets canvas intrinsic size to CSS display size × DPR', () => {
        const canvas = document.createElement('canvas');
        expect(canvas.width).toBe(300);  // default
        expect(canvas.height).toBe(150);

        canvas.getBoundingClientRect = () => ({
            width: 380, height: 220,
            top: 0, left: 0, right: 380, bottom: 220, x: 0, y: 0,
        });
        window.devicePixelRatio = 2;

        const ctx = window.sizeCanvasToDisplay(canvas);

        expect(canvas.width).toBe(760);   // 380 × 2
        expect(canvas.height).toBe(440);  // 220 × 2
        expect(ctx).toBeDefined();
        expect(ctx.setTransform).toHaveBeenCalledWith(2, 0, 0, 2, 0, 0);
    });

    test('applies identity transform at DPR 1', () => {
        const canvas = document.createElement('canvas');
        canvas.getBoundingClientRect = () => ({
            width: 400, height: 200,
            top: 0, left: 0, right: 400, bottom: 200, x: 0, y: 0,
        });
        window.devicePixelRatio = 1;

        const ctx = window.sizeCanvasToDisplay(canvas);
        expect(ctx.setTransform).toHaveBeenCalledWith(1, 0, 0, 1, 0, 0);
        expect(canvas.width).toBe(400);
        expect(canvas.height).toBe(200);
    });

    test('skips resize when already correctly sized', () => {
        const canvas = document.createElement('canvas');
        canvas.getBoundingClientRect = () => ({
            width: 380, height: 220,
            top: 0, left: 0, right: 380, bottom: 220, x: 0, y: 0,
        });
        window.devicePixelRatio = 1;

        // First call sizes the canvas
        window.sizeCanvasToDisplay(canvas);
        expect(canvas.width).toBe(380);

        // Second call should not re-assign (width already matches)
        canvas.width = 380;  // ensure it's already set
        canvas.height = 220;
        const ctx = window.sizeCanvasToDisplay(canvas);
        // setTransform is always called (resets the transform)
        expect(ctx.setTransform).toHaveBeenCalled();
    });
});


// ============================================================
// P0 — openPopup event delegation (would have caught Bug 1)
// ============================================================

describe('openPopup event delegation', () => {
    const station = {
        id: '50140', label: 'Umberleigh', lat: 50.99, lon: -3.98,
        river: 'River Taw', order: 4, typicalRangeHigh: 2.8,
    };

    beforeEach(() => {
        window.stationData['50140'] = {
            readings: [{ dateTime: new Date(), value: 1.5 }],
            latest: { dateTime: new Date(), value: 1.5 },
        };
        window.devicePixelRatio = 1;
    });

    test('popup buttons respond to clicks immediately after openPopup', () => {
        const marker = createMockMarker();
        window.openPopup(marker, station, 'level');

        const popupEl = marker.getPopup().getElement();
        // Append to document so setTimeRange can find elements by ID
        document.body.appendChild(popupEl);

        const btns = popupEl.querySelectorAll('button[data-action="setTimeRange"]');
        expect(btns.length).toBeGreaterThan(0);

        // The 24h button should not be active initially (5d is default)
        const btn24 = popupEl.querySelector('button[data-hours="24"]');
        expect(btn24).not.toBeNull();
        expect(btn24.classList.contains('active')).toBe(false);

        // Click it — the event delegation handler should fire synchronously
        btn24.dispatchEvent(new Event('click', { bubbles: true }));

        // After click, the 24h button should be active
        expect(btn24.classList.contains('active')).toBe(true);

        popupEl.remove();
    });

    test('click listener is attached directly, not via popupopen event', () => {
        const marker = createMockMarker();
        const popupAddEvent = vi.fn();

        // Wrap bindPopup to spy on the popup element's addEventListener
        const origBind = marker.bindPopup;
        marker.bindPopup = vi.fn(function (html) {
            origBind.call(this, html);
            const el = this.getPopup().getElement();
            const origAdd = el.addEventListener.bind(el);
            el.addEventListener = function (...args) {
                popupAddEvent(...args);
                return origAdd(...args);
            };
            return this;
        });

        window.openPopup(marker, station, 'level');

        // The click listener should have been added directly to the popup element
        expect(popupAddEvent).toHaveBeenCalledWith('click', expect.any(Function));

        // And NOT via marker.on('popupopen', ...)
        const popupOpenCalls = marker.on.mock.calls.filter(
            ([event]) => event === 'popupopen'
        );
        expect(popupOpenCalls.length).toBe(0);
    });
});


// ============================================================
// P1 — openPopup HTML correctness
// ============================================================

describe('openPopup HTML', () => {
    beforeEach(() => {
        window.devicePixelRatio = 1;
    });

    test('time-range buttons have data-action attributes', () => {
        const marker = createMockMarker();
        const station = { id: '50199', label: 'Lapford Bowerthy', lat: 50.87, lon: -3.79 };
        window.stationData['50199'] = {
            readings: [{ dateTime: new Date(), value: 1.0 }],
            latest: { dateTime: new Date(), value: 1.0 },
        };

        window.openPopup(marker, station, 'rainfall');

        const html = marker.bindPopup.mock.calls[0][0];
        expect(html).toContain('data-action="setTimeRange"');
        expect(html).toContain('data-action="showForecast"');
    });

    test('tidal station 50198 gets tab buttons', () => {
        const marker = createMockMarker();
        const station = {
            id: '50198', label: 'Barnstaple (Tidal)', lat: 51.08, lon: -4.06,
            river: 'River Taw',
        };
        window.stationData['50198'] = {
            readings: [{ dateTime: new Date(), value: 3.0 }],
            latest: { dateTime: new Date(), value: 3.0 },
        };

        window.openPopup(marker, station, 'tidal');

        const html = marker.bindPopup.mock.calls[0][0];
        expect(html).toContain('data-action="showTidalTab"');
        expect(html).toContain('data-action="showDischargeTab"');
    });

    test('station labels are HTML-escaped to prevent XSS', () => {
        const marker = createMockMarker();
        const station = { id: 'xss', label: '<img onerror=alert(1)>', lat: 50, lon: -3 };
        window.stationData['xss'] = { readings: [], latest: null };

        window.openPopup(marker, station, 'level');

        const html = marker.bindPopup.mock.calls[0][0];
        expect(html).not.toContain('<img onerror');
        expect(html).toContain('&lt;img');
    });
});


// ============================================================
// P1 — init() event wiring
// ============================================================

describe('init event wiring', () => {
    test('refresh-btn has a click listener (adds loading class)', () => {
        // refreshData() adds 'loading' class to the button as its first action.
        // If the addEventListener wiring is correct, clicking triggers that.
        const btn = document.getElementById('refresh-btn');
        btn.classList.remove('loading');

        btn.click();

        expect(btn.classList.contains('loading')).toBe(true);
        // Clean up
        btn.classList.remove('loading');
    });

    test('flood-warnings-summary has a click listener (toggles details)', () => {
        // toggleFloodWarnings() toggles the 'expanded' class on #flood-warnings.
        const warnings = document.getElementById('flood-warnings');
        warnings.classList.remove('expanded');

        document.querySelector('.flood-warnings-summary').click();

        expect(warnings.classList.contains('expanded')).toBe(true);
        // Clean up — toggle back
        document.querySelector('.flood-warnings-summary').click();
    });

    test('no inline onclick attributes exist in the DOM', () => {
        const elements = document.querySelectorAll('[onclick]');
        expect(elements.length).toBe(0);
    });
});


// ============================================================
// P1 — createStationMarker
// ============================================================

describe('createStationMarker', () => {
    beforeEach(() => {
        window.devicePixelRatio = 1;
    });

    test('divIcon HTML uses CSS class, not inline style attribute', () => {
        const station = {
            id: '50140', label: 'Umberleigh', lat: 50.99, lon: -3.98,
            river: 'River Taw', order: 4, typicalRangeHigh: 2.8,
        };
        window.stationData['50140'] = {
            readings: [], latest: { dateTime: new Date(), value: 1.5 },
        };

        window.createStationMarker(station, 'level');

        const lastDivIcon = L.divIcon.mock.calls[L.divIcon.mock.calls.length - 1][0];
        expect(lastDivIcon.html).toContain('class="station-marker');
        expect(lastDivIcon.html).not.toMatch(/style\s*=/);
    });

    test('marker receives a click handler', () => {
        const station = { id: '50140', label: 'Umberleigh', lat: 50.99, lon: -3.98 };
        window.stationData['50140'] = { readings: [], latest: null };

        window.createStationMarker(station, 'level');

        const marker = L.marker.mock.results[L.marker.mock.results.length - 1].value;
        const clickCalls = marker.on.mock.calls.filter(([event]) => event === 'click');
        expect(clickCalls.length).toBe(1);
    });
});


// ============================================================
// P2 — Canvas loading states (fillText coordinates)
// ============================================================

describe('canvas loading states', () => {
    beforeEach(() => {
        window.devicePixelRatio = 1;
    });

    test('showForecast draws loading text at CSS-based coordinates', async () => {
        const canvas = document.createElement('canvas');
        canvas.id = 'chart-50199';
        document.body.appendChild(canvas);

        canvas.getBoundingClientRect = () => ({
            width: 380, height: 220,
            top: 0, left: 0, right: 380, bottom: 220, x: 0, y: 0,
        });

        window.stationData['50199'] = {
            readings: [{ dateTime: new Date(), value: 0 }],
            latest: { dateTime: new Date(), value: 0 },
        };

        // Ensure timestamp element exists for showForecast
        const tsEl = document.createElement('span');
        tsEl.id = 'timestamp-50199';
        tsEl.dataset.original = 'test';
        document.body.appendChild(tsEl);

        // Ensure timerange element exists for btn.classList
        const trEl = document.createElement('div');
        trEl.id = 'timerange-50199';
        trEl.innerHTML = '<button class="forecast-btn">Fcst</button>';
        document.body.appendChild(trEl);

        const btn = trEl.querySelector('button');
        window.activePopupChart = null;

        // showForecast is async — just test the synchronous loading text
        const promise = window.showForecast('50199', btn);

        const ctx = getMockCtx(canvas);
        expect(ctx.fillText).toHaveBeenCalledWith(
            'Loading forecast\u2026',
            190,  // rect.width / 2 = 380 / 2
            110,  // rect.height / 2 = 220 / 2
        );

        // Let the async work settle (fetch will resolve with mock)
        await promise.catch(() => {});

        // Clean up
        canvas.remove();
        tsEl.remove();
        trEl.remove();
    });

    test('showDischargeTab draws loading text at CSS-based coordinates', async () => {
        const canvas = document.createElement('canvas');
        canvas.id = 'chart-50198';
        document.body.appendChild(canvas);

        canvas.getBoundingClientRect = () => ({
            width: 380, height: 220,
            top: 0, left: 0, right: 380, bottom: 220, x: 0, y: 0,
        });

        window.stationData['50198'] = {
            readings: [{ dateTime: new Date(), value: 3.0 }],
            latest: { dateTime: new Date(), value: 3.0 },
        };

        // Provide required DOM elements
        const currentEl = document.createElement('div');
        currentEl.id = 'current-50198';
        document.body.appendChild(currentEl);

        const tabsEl = document.createElement('div');
        tabsEl.id = 'tabs-50198';
        tabsEl.innerHTML = '<button class="tab-discharge">Discharge</button>';
        document.body.appendChild(tabsEl);

        const trEl = document.createElement('div');
        trEl.id = 'timerange-50198';
        document.body.appendChild(trEl);

        const btn = tabsEl.querySelector('button');
        window.activePopupChart = null;

        const promise = window.showDischargeTab('50198', btn);

        const ctx = getMockCtx(canvas);
        expect(ctx.fillText).toHaveBeenCalledWith(
            'Loading discharge data\u2026',
            190,  // rect.width / 2
            110,  // rect.height / 2
        );

        await promise.catch(() => {});

        // Clean up
        canvas.remove();
        currentEl.remove();
        tabsEl.remove();
        trEl.remove();
    });
});
