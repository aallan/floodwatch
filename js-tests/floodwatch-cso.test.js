/**
 * Tests for the CSO (Combined Sewer Overflow) layer added to floodwatch.js.
 *
 * Covers the pure helpers (csoVisualState, csoIsTierA, titleCase,
 * computeCsoStats) and the marker render path (createCsoMarker — checks
 * the HTML class set on the icon, which drives colour and zoom-fade).
 *
 * The setup-ui harness eval's floodwatch.js into the global scope so all
 * top-level functions and globals are available as window.* — same trick
 * the existing floodwatch.test.js uses.
 */
import { describe, test, expect, beforeEach, afterEach } from 'vitest';
import './setup-ui.js';

// Common timestamp for tests — Tuesday 3 June 2026, 14:00 UTC.
const NOW = new Date('2026-06-03T14:00:00Z').getTime();


// ============================================================
// csoVisualState — pure mapping of status snapshot → visual state
// ============================================================

describe('csoVisualState', () => {
    beforeEach(() => {
        // Wipe and rebuild csoStatus for each test
        for (const k of Object.keys(window.csoStatus)) delete window.csoStatus[k];
    });

    test('returns "unknown" when no snapshot row exists', () => {
        expect(window.csoVisualState('UNKNOWN_SITE', NOW)).toBe('unknown');
    });

    test('returns "active" when status=1', () => {
        window.csoStatus.S1 = { status: 1 };
        expect(window.csoVisualState('S1', NOW)).toBe('active');
    });

    test('returns "offline" when status=-1', () => {
        window.csoStatus.S2 = { status: -1 };
        expect(window.csoVisualState('S2', NOW)).toBe('offline');
    });

    test('returns "recent" when status=0 and event ended within 48h', () => {
        // Spill ended 2 hours ago
        const twoHoursAgo = new Date(NOW - 2 * 3600 * 1000).toISOString();
        window.csoStatus.S3 = { status: 0, latestEventEnd: twoHoursAgo };
        expect(window.csoVisualState('S3', NOW)).toBe('recent');
    });

    test('returns "recent" right up to the 48h boundary', () => {
        const justUnder48h = new Date(NOW - (48 * 3600 - 1) * 1000).toISOString();
        window.csoStatus.S3b = { status: 0, latestEventEnd: justUnder48h };
        expect(window.csoVisualState('S3b', NOW)).toBe('recent');
    });

    test('returns "quiet" when last event ended >48h ago', () => {
        const threeDaysAgo = new Date(NOW - 3 * 86400 * 1000).toISOString();
        window.csoStatus.S4 = { status: 0, latestEventEnd: threeDaysAgo };
        expect(window.csoVisualState('S4', NOW)).toBe('quiet');
    });

    test('returns "quiet" when status=0 and no event end recorded', () => {
        window.csoStatus.S5 = { status: 0, latestEventEnd: '' };
        expect(window.csoVisualState('S5', NOW)).toBe('quiet');
    });
});


// ============================================================
// csoIsTierA — tier-A is "always visible regardless of zoom"
// ============================================================

describe('csoIsTierA', () => {
    test('active is tier-A', () => {
        expect(window.csoIsTierA('active')).toBe(true);
    });
    test('recent is tier-A', () => {
        expect(window.csoIsTierA('recent')).toBe(true);
    });
    test('quiet is NOT tier-A', () => {
        expect(window.csoIsTierA('quiet')).toBe(false);
    });
    test('offline is NOT tier-A', () => {
        expect(window.csoIsTierA('offline')).toBe(false);
    });
    test('unknown is NOT tier-A', () => {
        expect(window.csoIsTierA('unknown')).toBe(false);
    });
});


// ============================================================
// titleCase — preserves known acronyms uppercase
// ============================================================

describe('titleCase', () => {
    test('title-cases ordinary words', () => {
        expect(window.titleCase('CHULMLEIGH SEWAGE WORKS')).toBe('Chulmleigh Sewage Works');
    });
    test('keeps known acronyms uppercase', () => {
        expect(window.titleCase('CHULMLEIGH WWTW SSO')).toBe('Chulmleigh WWTW SSO');
    });
    test('handles mixed case input', () => {
        expect(window.titleCase('north molton WWTW')).toBe('North Molton WWTW');
    });
    test('returns empty string for empty input', () => {
        expect(window.titleCase('')).toBe('');
        expect(window.titleCase(null)).toBe('');
    });
});


// ============================================================
// computeCsoStats — overlap math on a sliding window
// ============================================================

describe('computeCsoStats', () => {
    test('counts zero hours / zero spills for empty event log', () => {
        const r = window.computeCsoStats([], new Date(NOW - 86400000), new Date(NOW));
        expect(r.hours).toBe(0);
        expect(r.spills).toBe(0);
    });

    test('sums duration of a single fully-contained event', () => {
        const events = [{
            start: new Date(NOW - 7200000),  // 2h before NOW
            end: new Date(NOW - 3600000),    // 1h before NOW
        }];
        const r = window.computeCsoStats(events, new Date(NOW - 86400000), new Date(NOW));
        expect(r.hours).toBeCloseTo(1, 5);
        expect(r.spills).toBe(1);
    });

    test('clamps duration to window when event spans the boundary', () => {
        // Event from 25h ago to 23h ago — but window starts 24h ago.
        // Only 1 hour of overlap should count.
        const events = [{
            start: new Date(NOW - 25 * 3600 * 1000),
            end: new Date(NOW - 23 * 3600 * 1000),
        }];
        const r = window.computeCsoStats(events, new Date(NOW - 24 * 3600 * 1000), new Date(NOW));
        expect(r.hours).toBeCloseTo(1, 5);
        expect(r.spills).toBe(1);
    });

    test('treats ongoing event (end=null) as ending at window end', () => {
        const events = [{
            start: new Date(NOW - 3 * 3600 * 1000),  // 3h before NOW
            end: null,                                // still going
            ongoing: true,
        }];
        const r = window.computeCsoStats(events, new Date(NOW - 86400000), new Date(NOW));
        expect(r.hours).toBeCloseTo(3, 5);
        expect(r.spills).toBe(1);
    });

    test('ignores events entirely outside the window', () => {
        const events = [{
            start: new Date(NOW - 100 * 86400000),  // 100 days ago
            end: new Date(NOW - 99 * 86400000),
        }];
        const r = window.computeCsoStats(events, new Date(NOW - 86400000), new Date(NOW));
        expect(r.hours).toBe(0);
        expect(r.spills).toBe(0);
    });

    test('sums multiple events correctly', () => {
        const events = [
            { start: new Date(NOW - 6 * 3600 * 1000), end: new Date(NOW - 5 * 3600 * 1000) },  // 1h
            { start: new Date(NOW - 3 * 3600 * 1000), end: new Date(NOW - 1 * 3600 * 1000) },  // 2h
        ];
        const r = window.computeCsoStats(events, new Date(NOW - 86400000), new Date(NOW));
        expect(r.hours).toBeCloseTo(3, 5);
        expect(r.spills).toBe(2);
    });
});


// ============================================================
// createCsoMarker — produces correct HTML class for status
// ============================================================

describe('createCsoMarker icon classes', () => {
    beforeEach(() => {
        // Make sure tests are independent — reset Leaflet's mock call history
        for (const k of Object.keys(window.csoStatus)) delete window.csoStatus[k];
        window.L.divIcon.mockClear?.();
        window.L.marker.mockClear?.();
    });

    function lastDivIconHtml() {
        const calls = window.L.divIcon.mock.calls;
        return calls[calls.length - 1][0].html;
    }

    test('renders "active" class when status=1', () => {
        window.csoStatus.S1 = { status: 1 };
        window.createCsoMarker({ id: 'S1', lat: 50, lon: -3 });
        const html = lastDivIconHtml();
        expect(html).toContain('cso-marker');
        expect(html).toContain('active');
        expect(html).toContain('tier-a');
    });

    test('renders "recent" tier-A when status=0 and ended <48h ago', () => {
        const oneHourAgo = new Date(Date.now() - 3600000).toISOString();
        window.csoStatus.S2 = { status: 0, latestEventEnd: oneHourAgo };
        window.createCsoMarker({ id: 'S2', lat: 50, lon: -3 });
        const html = lastDivIconHtml();
        expect(html).toContain('recent');
        expect(html).toContain('tier-a');
    });

    test('renders "quiet" tier-B when status=0 and old event', () => {
        const fiveDaysAgo = new Date(Date.now() - 5 * 86400000).toISOString();
        window.csoStatus.S3 = { status: 0, latestEventEnd: fiveDaysAgo };
        window.createCsoMarker({ id: 'S3', lat: 50, lon: -3 });
        const html = lastDivIconHtml();
        expect(html).toContain('quiet');
        expect(html).toContain('tier-b');
    });

    test('renders "offline" tier-B when status=-1', () => {
        window.csoStatus.S4 = { status: -1 };
        window.createCsoMarker({ id: 'S4', lat: 50, lon: -3 });
        const html = lastDivIconHtml();
        expect(html).toContain('offline');
        expect(html).toContain('tier-b');
    });

    test('renders "unknown" tier-B when no status snapshot exists', () => {
        window.createCsoMarker({ id: 'NEVER_SEEN', lat: 50, lon: -3 });
        const html = lastDivIconHtml();
        expect(html).toContain('unknown');
        expect(html).toContain('tier-b');
    });

    test('uses "minor" size class for sites without WWTW asset type', () => {
        window.csoStatus.S6 = { status: 1 };
        window.createCsoMarker({ id: 'S6', lat: 50, lon: -3 });
        const html = lastDivIconHtml();
        expect(html).toContain('minor');
        expect(html).not.toContain('major');
    });

    test('uses "major" size class for sites with WWTW asset type', () => {
        window.csoStatus.S7 = { status: 1 };
        window.csoMeta.S7 = { assetType: 'Storm tank at WwTW' };
        window.createCsoMarker({ id: 'S7', lat: 50, lon: -3 });
        const html = lastDivIconHtml();
        expect(html).toContain('major');
    });

    test('uses zIndexOffset 100 to sit below EA markers (offset 500)', () => {
        window.csoStatus.S5 = { status: 0 };
        window.createCsoMarker({ id: 'S5', lat: 50, lon: -3 });
        const markerCall = window.L.marker.mock.calls[window.L.marker.mock.calls.length - 1];
        expect(markerCall[1].zIndexOffset).toBe(100);
    });
});


// ============================================================
// isCsoMajorFacility — asset-type → major/minor classification
// ============================================================

describe('isCsoMajorFacility', () => {
    test('storm tank at WwTW is major', () => {
        expect(window.isCsoMajorFacility('Storm tank at WwTW')).toBe(true);
    });
    test('inlet SO at WwTW is major', () => {
        expect(window.isCsoMajorFacility('Inlet SO at WwTW')).toBe(true);
    });
    test('SO on sewer network is NOT major', () => {
        expect(window.isCsoMajorFacility('SO on sewer network')).toBe(false);
    });
    test('storm discharge at pumping station is NOT major', () => {
        expect(window.isCsoMajorFacility('Storm discharge at pumping station')).toBe(false);
    });
    test('handles missing asset type', () => {
        expect(window.isCsoMajorFacility(undefined)).toBe(false);
        expect(window.isCsoMajorFacility('')).toBe(false);
    });
    test('handles mixed-case WWTW spelling', () => {
        expect(window.isCsoMajorFacility('Storm tank at WWTW')).toBe(true);
        expect(window.isCsoMajorFacility('Inlet SO at wwtw')).toBe(true);
    });
});

// ============================================================
// expandAcronyms — water-industry abbreviation expansion
// ============================================================

describe('expandAcronyms', () => {
    test('expands WWTW + SSO in the same string', () => {
        expect(window.expandAcronyms('Chulmleigh WWTW SSO'))
            .toBe('Chulmleigh wastewater treatment works settled storm overflow');
    });
    test('expands STW', () => {
        expect(window.expandAcronyms('Brayford STW'))
            .toBe('Brayford sewage treatment works');
    });
    test('expands PS (pumping station)', () => {
        expect(window.expandAcronyms('Anchorwood PS'))
            .toBe('Anchorwood pumping station');
    });
    test('handles SWW mixed-case WwTW spelling', () => {
        expect(window.expandAcronyms('Storm tank at WwTW'))
            .toBe('Storm tank at wastewater treatment works');
    });
    test('leaves non-acronym text unchanged', () => {
        expect(window.expandAcronyms('Chulmleigh')).toBe('Chulmleigh');
    });
    test('returns empty string for empty input', () => {
        expect(window.expandAcronyms('')).toBe('');
        expect(window.expandAcronyms(null)).toBe('');
    });
});

// ============================================================
// distanceMeters / csoOverlapsEAStation — overlap detection
// ============================================================

describe('distanceMeters', () => {
    test('returns 0 for identical points', () => {
        expect(window.distanceMeters(50.9, -3.9, 50.9, -3.9)).toBe(0);
    });

    test('approx Chulmleigh-EA-to-Chulmleigh-CSO ≈ 389m', () => {
        // Real coords from data files
        const d = window.distanceMeters(50.907767, -3.863651, 50.909868, -3.868095);
        expect(d).toBeGreaterThan(380);
        expect(d).toBeLessThan(400);
    });

    test('1 degree of latitude ≈ 111 km', () => {
        const d = window.distanceMeters(50, 0, 51, 0);
        expect(d).toBeGreaterThan(110000);
        expect(d).toBeLessThan(112000);
    });
});

describe('csoOverlapsEAStation', () => {
    let originalLevel;

    beforeEach(() => {
        // Stash and replace STATIONS.level with a known fixture so tests are independent
        originalLevel = window.STATIONS.level;
        window.STATIONS.level = [
            { id: '50125', label: 'Chulmleigh', lat: 50.907767, lon: -3.863651 },
        ];
        window.STATIONS.rainfall = [];
        window.STATIONS.tidal = [];
    });

    afterEach(() => {
        window.STATIONS.level = originalLevel;
    });

    test('detects overlap when CSO is within 500m of an EA station', () => {
        // 389m from EA Chulmleigh — the real SBB00257 location
        const overlapping = { lat: 50.909868, lon: -3.868095 };
        expect(window.csoOverlapsEAStation(overlapping)).toBe(true);
    });

    test('returns false for a CSO far from any EA station', () => {
        // ~5km away — out of overlap range
        const distant = { lat: 50.95, lon: -3.95 };
        expect(window.csoOverlapsEAStation(distant)).toBe(false);
    });

    test('returns false when no EA stations exist', () => {
        window.STATIONS.level = [];
        const anywhere = { lat: 50.9, lon: -3.9 };
        expect(window.csoOverlapsEAStation(anywhere)).toBe(false);
    });
});


// ============================================================
// applyCsoZoomFade — tier-B fades below zoom 11
// ============================================================

describe('applyCsoZoomFade', () => {
    let visited;

    beforeEach(() => {
        visited = [];
        // Replace map.eachLayer + getZoom for this test
        window.map = {
            getZoom: () => window._testZoom ?? 12,
            eachLayer: (cb) => visited.forEach(cb),
        };
    });

    function fakeMarker(tier) {
        // Looks like an L.Marker to instanceof check (we use the global L mock).
        // setOpacity records the value applied so tests can assert it.
        const m = Object.create(window.L.marker().constructor?.prototype ?? Object.prototype);
        Object.assign(m, {
            _csoTier: tier,
            _opacity: null,
            setOpacity(o) { this._opacity = o; },
        });
        return m;
    }

    test('does not crash when map is uninitialised', () => {
        window.map = null;
        expect(() => window.applyCsoZoomFade()).not.toThrow();
    });

    test('does nothing to tier-A markers regardless of zoom', () => {
        const a = fakeMarker('tier-a');
        // We can't easily make this pass the `instanceof L.Marker` check
        // through the mock chain; instead verify by manual call.
        // The function's tier-A skip is the explicit `=== 'tier-b'` filter,
        // so a tier-A marker with no setOpacity call is what we expect.
        visited = [a];
        // Force the instanceof guard true by replacing it
        const real = window.L.Marker;
        window.L.Marker = function () {};
        Object.setPrototypeOf(a, window.L.Marker.prototype);
        window._testZoom = 9;
        window.applyCsoZoomFade();
        expect(a._opacity).toBeNull(); // tier-A never gets opacity set
        window.L.Marker = real;
    });
});
