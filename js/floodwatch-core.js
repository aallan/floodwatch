/**
 * Floodwatch core utility functions.
 *
 * Extracted from index.html for testability. These functions accept their
 * dependencies as parameters instead of reading globals.
 *
 * UMD module: works in Node (require/import) and browser (window.FloodwatchCore).
 */
(function (exports) {
    'use strict';

    /**
     * Format a Date as a relative or absolute time string.
     * @param {Date} date - The date to format.
     * @param {Date} [now=new Date()] - The reference "now" time (for testability).
     * @returns {string} Human-readable time string.
     */
    function formatTime(date, now) {
        if (!now) now = new Date();
        const diff = now - date;
        if (diff < 3600000) return Math.floor(diff / 60000) + ' min ago';
        if (diff < 86400000) return Math.floor(diff / 3600000) + 'h ago';
        return date.toLocaleDateString('en-GB', { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' });
    }

    /**
     * HTML-escape a string to prevent XSS.
     * Uses the DOM textContent/innerHTML trick (requires document).
     * @param {string} str - The string to escape.
     * @returns {string} The escaped string.
     */
    function escapeHtml(str) {
        const div = document.createElement('div');
        div.textContent = str;
        return div.innerHTML;
    }

    /**
     * Look up a station by ID across all station types.
     * @param {string} stationId - The station ID to find.
     * @param {Object} stations - The STATIONS object with level, rainfall, tidal arrays.
     * @returns {Object|undefined} The station object, or undefined if not found.
     */
    function getStation(stationId, stations) {
        const all = [...(stations.level || []), ...(stations.rainfall || []), ...(stations.tidal || [])];
        return all.find(s => s.id === stationId);
    }

    /**
     * Calculate trend (rising / falling / steady) from recent readings.
     * Fits a linear-regression slope over the last ~1 hour of data.
     * Threshold: +/-0.01 m/hr (1 cm/hr) to filter noise.
     *
     * @param {Array} readings - Array of {dateTime: Date, value: number} sorted chronologically.
     * @param {string} type - Station type: 'level', 'tidal', or 'rainfall'.
     * @returns {{direction: string, symbol: string}|null} Trend object or null.
     */
    function getTrend(readings, type) {
        if (type === 'rainfall') return null;

        if (!readings || readings.length < 4) return null;

        const now = readings[readings.length - 1].dateTime;
        const oneHourAgo = new Date(now - 1 * 3600000);

        const recent = readings.filter(r => r.dateTime >= oneHourAgo);
        if (recent.length < 3) return null;

        const n = recent.length;
        const t0 = recent[0].dateTime.getTime();
        let sumX = 0, sumY = 0, sumXY = 0, sumX2 = 0;
        for (const r of recent) {
            const x = (r.dateTime.getTime() - t0) / 3600000;
            const y = r.value;
            sumX += x; sumY += y; sumXY += x * y; sumX2 += x * x;
        }
        const slope = (n * sumXY - sumX * sumY) / (n * sumX2 - sumX * sumX);

        const threshold = 0.01;

        if (slope > threshold) return { direction: 'rising', symbol: '\u2191' };
        if (slope < -threshold) return { direction: 'falling', symbol: '\u2193' };
        return { direction: 'steady', symbol: '\u2192' };
    }

    /**
     * Compute a djb2-style hash fingerprint from station IDs.
     * Used to auto-invalidate localStorage cache when stations change.
     *
     * @param {Object} stations - The STATIONS object with level, rainfall, tidal arrays.
     * @returns {string} A base-36 hash string.
     */
    function computeCacheFingerprint(stations) {
        const allIds = [
            ...(stations.level || []),
            ...(stations.rainfall || []),
            ...(stations.tidal || [])
        ].map(s => s.id).sort().join(',');

        return allIds.split('').reduce(
            (h, c) => ((h << 5) - h + c.charCodeAt(0)) | 0, 0
        ).toString(36);
    }

    // Export all functions
    exports.formatTime = formatTime;
    exports.escapeHtml = escapeHtml;
    exports.getStation = getStation;
    exports.getTrend = getTrend;
    exports.computeCacheFingerprint = computeCacheFingerprint;

})(typeof module !== 'undefined' ? module.exports : (window.FloodwatchCore = {}));
