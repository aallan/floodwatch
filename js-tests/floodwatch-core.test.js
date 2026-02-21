/**
 * Tests for js/floodwatch-core.js — extracted utility functions.
 */
import { describe, test, expect } from 'vitest';

const {
    formatTime,
    escapeHtml,
    getStation,
    getTrend,
    computeCacheFingerprint,
} = require('../js/floodwatch-core.js');


// ============================================================
// formatTime
// ============================================================

describe('formatTime', () => {
    test('returns "X min ago" for times less than 1 hour ago', () => {
        const now = new Date('2026-01-15T12:00:00Z');
        const date = new Date('2026-01-15T11:45:00Z');
        expect(formatTime(date, now)).toBe('15 min ago');
    });

    test('returns "Xh ago" for times less than 24 hours ago', () => {
        const now = new Date('2026-01-15T12:00:00Z');
        const date = new Date('2026-01-15T06:00:00Z');
        expect(formatTime(date, now)).toBe('6h ago');
    });

    test('returns formatted date for times more than 24 hours ago', () => {
        const now = new Date('2026-01-15T12:00:00Z');
        const date = new Date('2026-01-13T14:30:00Z');
        const result = formatTime(date, now);
        // Should contain the day and month
        expect(result).toMatch(/13/);
        expect(result).toMatch(/Jan/);
    });

    test('returns "0 min ago" for identical times', () => {
        const now = new Date('2026-01-15T12:00:00Z');
        expect(formatTime(now, now)).toBe('0 min ago');
    });
});


// ============================================================
// escapeHtml
// ============================================================

describe('escapeHtml', () => {
    test('escapes angle brackets', () => {
        const result = escapeHtml('<script>alert("xss")</script>');
        expect(result).toContain('&lt;');
        expect(result).toContain('&gt;');
        expect(result).not.toContain('<script>');
    });

    test('escapes ampersands', () => {
        expect(escapeHtml('foo & bar')).toBe('foo &amp; bar');
    });

    test('passes through safe strings unchanged', () => {
        expect(escapeHtml('Umberleigh')).toBe('Umberleigh');
    });

    test('handles empty string', () => {
        expect(escapeHtml('')).toBe('');
    });
});


// ============================================================
// getStation
// ============================================================

describe('getStation', () => {
    const mockStations = {
        level: [
            { id: '50140', label: 'Umberleigh' },
            { id: '50149', label: 'Sticklepath' },
        ],
        rainfall: [
            { id: '50199', label: 'Lapford Bowerthy' },
        ],
        tidal: [
            { id: '50198', label: 'Barnstaple (Tidal)' },
        ],
    };

    test('finds level station by ID', () => {
        expect(getStation('50140', mockStations).label).toBe('Umberleigh');
    });

    test('finds rainfall station by ID', () => {
        expect(getStation('50199', mockStations).label).toBe('Lapford Bowerthy');
    });

    test('finds tidal station by ID', () => {
        expect(getStation('50198', mockStations).label).toBe('Barnstaple (Tidal)');
    });

    test('returns undefined for non-existent ID', () => {
        expect(getStation('99999', mockStations)).toBeUndefined();
    });

    test('handles missing station type arrays', () => {
        const partial = { level: [{ id: '1', label: 'A' }] };
        expect(getStation('1', partial).label).toBe('A');
    });
});


// ============================================================
// getTrend
// ============================================================

describe('getTrend', () => {
    /**
     * Helper: create readings at 15-min intervals within the last hour.
     * Values are linearly interpolated from start to end.
     */
    function makeReadings(values) {
        const intervalMs = 15 * 60000; // 15 minutes
        const endTime = new Date('2026-01-15T12:00:00Z').getTime();
        const startTime = endTime - (values.length - 1) * intervalMs;
        return values.map((v, i) => ({
            dateTime: new Date(startTime + i * intervalMs),
            value: v,
        }));
    }

    test('returns rising for increasing values', () => {
        // 5 readings over 1 hour, rising 0.1m (slope = 0.1 m/hr >> 0.01)
        const readings = makeReadings([1.0, 1.025, 1.05, 1.075, 1.1]);
        const result = getTrend(readings, 'level');
        expect(result).not.toBeNull();
        expect(result.direction).toBe('rising');
        expect(result.symbol).toBe('\u2191');
    });

    test('returns falling for decreasing values', () => {
        const readings = makeReadings([1.1, 1.075, 1.05, 1.025, 1.0]);
        const result = getTrend(readings, 'level');
        expect(result).not.toBeNull();
        expect(result.direction).toBe('falling');
        expect(result.symbol).toBe('\u2193');
    });

    test('returns steady for flat values', () => {
        const readings = makeReadings([1.0, 1.001, 0.999, 1.002, 1.0]);
        const result = getTrend(readings, 'level');
        expect(result).not.toBeNull();
        expect(result.direction).toBe('steady');
        expect(result.symbol).toBe('\u2192');
    });

    test('returns null for rainfall type', () => {
        const readings = makeReadings([0, 0.2, 0.4, 0.6, 0.8]);
        expect(getTrend(readings, 'rainfall')).toBeNull();
    });

    test('returns null for fewer than 4 readings', () => {
        const readings = makeReadings([1.0, 1.1, 1.2]);
        expect(getTrend(readings, 'level')).toBeNull();
    });

    test('returns null for null/undefined readings', () => {
        expect(getTrend(null, 'level')).toBeNull();
        expect(getTrend(undefined, 'level')).toBeNull();
    });

    test('works for tidal type (not rainfall)', () => {
        const readings = makeReadings([1.0, 1.025, 1.05, 1.075, 1.1]);
        const result = getTrend(readings, 'tidal');
        expect(result).not.toBeNull();
        expect(result.direction).toBe('rising');
    });
});


// ============================================================
// computeCacheFingerprint
// ============================================================

describe('computeCacheFingerprint', () => {
    test('returns a non-empty string', () => {
        const stations = {
            level: [{ id: 'A' }],
            rainfall: [{ id: 'B' }],
            tidal: [{ id: 'C' }],
        };
        const fp = computeCacheFingerprint(stations);
        expect(typeof fp).toBe('string');
        expect(fp.length).toBeGreaterThan(0);
    });

    test('is deterministic for same input', () => {
        const stations = {
            level: [{ id: '50140' }, { id: '50149' }],
            rainfall: [{ id: '50199' }],
            tidal: [{ id: '50198' }],
        };
        const fp1 = computeCacheFingerprint(stations);
        const fp2 = computeCacheFingerprint(stations);
        expect(fp1).toBe(fp2);
    });

    test('changes when stations change', () => {
        const s1 = { level: [{ id: 'A' }], rainfall: [], tidal: [] };
        const s2 = { level: [{ id: 'B' }], rainfall: [], tidal: [] };
        expect(computeCacheFingerprint(s1)).not.toBe(computeCacheFingerprint(s2));
    });

    test('order of stations does not affect result (sorted internally)', () => {
        const s1 = { level: [{ id: 'B' }, { id: 'A' }], rainfall: [], tidal: [] };
        const s2 = { level: [{ id: 'A' }, { id: 'B' }], rainfall: [], tidal: [] };
        expect(computeCacheFingerprint(s1)).toBe(computeCacheFingerprint(s2));
    });

    test('handles missing type arrays gracefully', () => {
        const stations = { level: [{ id: 'X' }] };
        expect(() => computeCacheFingerprint(stations)).not.toThrow();
    });
});
