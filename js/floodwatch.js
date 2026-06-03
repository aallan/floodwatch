// ============================================================
// Configuration
// ============================================================
const DATA_BASE = 'data/';
const API_BASE = 'https://environment.data.gov.uk/flood-monitoring';

// Station config matching our CSV data
const STATIONS = {
    level: [
        { id: '50149', label: 'Sticklepath', lat: 50.737824, lon: -3.917597, file: 'level_50149_sticklepath.csv', measureId: '50149-level-stage-i-15_min-m', river: 'River Taw', order: 1, typicalRangeHigh: 1.8 },
        { id: '50119', label: 'Taw Bridge', lat: 50.845457, lon: -3.886253, file: 'level_50119_taw_bridge.csv', measureId: '50119-level-stage-i-15_min-m', river: 'River Taw', order: 2, typicalRangeHigh: 1.9 },
        { id: '50132', label: 'Newnham Bridge', lat: 50.939901, lon: -3.907581, file: 'level_50132_newnham_bridge.csv', measureId: '50132-level-stage-i-15_min-m', river: 'River Taw', order: 3, typicalRangeHigh: 2.5 },
        { id: '50140', label: 'Umberleigh', lat: 50.99542, lon: -3.985089, file: 'level_50140_umberleigh.csv', measureId: '50140-level-stage-i-15_min-m', river: 'River Taw', order: 4, typicalRangeHigh: 2.8 },
        // River Mole tributary (upstream to downstream, joins Taw near Newnham Bridge)
        { id: '50135', label: 'North Molton', lat: 51.055152, lon: -3.795036, file: 'level_50135_north_molton.csv', measureId: '50135-level-stage-i-15_min-m', river: 'River Mole', order: 1, typicalRangeHigh: 1.1 },
        { id: '50153', label: 'Mole Mills', lat: 51.016893, lon: -3.822486, file: 'level_50153_mole_mills.csv', measureId: '50153-level-stage-i-15_min-m', river: 'River Mole', order: 2, typicalRangeHigh: 1.0 },
        { id: '50115', label: 'Woodleigh', lat: 50.973061, lon: -3.909695, file: 'level_50115_woodleigh.csv', measureId: '50115-level-stage-i-15_min-m', river: 'River Mole', order: 3, typicalRangeHigh: 1.7 },
        // Little Dart River tributary (joins Taw upstream of Newnham Bridge)
        { id: '50125', label: 'Chulmleigh', lat: 50.907767, lon: -3.863651, file: 'level_50125_chulmleigh.csv', measureId: '50125-level-stage-i-15_min-m', river: 'Little Dart River', order: 1, typicalRangeHigh: 1.5 },
        // Lapford Yeo tributary (joins Taw near Lapford)
        { id: '50151', label: 'Lapford', lat: 50.857808, lon: -3.810592, file: 'level_50151_lapford.csv', measureId: '50151-level-stage-i-15_min-m', river: 'Lapford Yeo', order: 1, typicalRangeHigh: 2.3 },
        // River Yeo tributary (joins Taw near Barnstaple)
        { id: '50114', label: 'Collard Bridge', lat: 51.099972, lon: -4.010005, file: 'level_50114_collard_bridge.csv', measureId: '50114-level-stage-i-15_min-m', river: 'River Yeo', order: 1, typicalRangeHigh: 1.1 },
    ],
    rainfall: [
        // East of Taw
        { id: '50199', label: 'Lapford Bowerthy', lat: 50.873373, lon: -3.798545, file: 'rainfall_50199.csv', measureId: '50199-rainfall-tipping_bucket_raingauge-t-15_min-mm' },
        { id: 'E85220', label: 'Molland Sindercombe', lat: 51.037989, lon: -3.736447, file: 'rainfall_E85220.csv', measureId: 'E85220-rainfall-tipping_bucket_raingauge-t-15_min-mm' },
        { id: 'E84360', label: 'Crediton Knowle', lat: 50.799653, lon: -3.737529, file: 'rainfall_E84360.csv', measureId: 'E84360-rainfall-tipping_bucket_raingauge-t-15_min-mm' },
        { id: '45183', label: 'Kinsford Gate', lat: 51.114443, lon: -3.795033, file: 'rainfall_45183.csv', measureId: '45183-rainfall-tipping_bucket_raingauge-t-15_min-mm' },
        // West of Taw
        { id: '50103', label: 'Allisland', lat: 50.880864, lon: -4.152815, file: 'rainfall_50103.csv', measureId: '50103-rainfall-tipping_bucket_raingauge-t-15_min-mm' },
        { id: '50194', label: 'Kenwith Castle', lat: 51.024089, lon: -4.236452, file: 'rainfall_50194.csv', measureId: '50194-rainfall-tipping_bucket_raingauge-t-15_min-mm' },
        { id: 'E82120', label: 'Bratton Fleming Haxton', lat: 51.116609, lon: -3.940857, file: 'rainfall_E82120.csv', measureId: 'E82120-rainfall-tipping_bucket_raingauge-t-15_min-mm' },
        { id: '47158', label: 'Halwill', lat: 50.771514, lon: -4.228634, file: 'rainfall_47158.csv', measureId: '47158-rainfall-tipping_bucket_raingauge-t-15_min-mm' },
    ],
    tidal: [
        { id: '50198', label: 'Barnstaple (Tidal)', lat: 51.080046, lon: -4.064537, file: 'level_50198_barnstaple_(tidal).csv', measureId: '50198-level-tidal_level-i-15_min-mAOD', river: 'River Taw' },
    ],
    // CSO (Combined Sewer Overflow) sites — populated at runtime from
    // data/cso_sites.csv by loadCsoData(). Static list is in the CSV
    // because there are ~75 sites and the fetcher maintains it.
    cso: [],
};

// CSO state — populated at startup, used by markers + popups.
const csoStatus = {};   // id -> {status, statusStart, latestEventStart, latestEventEnd, lastUpdated}
const csoMeta = {};     // id -> {name, asset_type, shellfish_water, bathing_water}
const csoHistory = {};  // id -> [{year, hours, spills}, ...]
let csoGeneratedAt = '';

// Zoom threshold below which tier-B CSO markers (quiet / offline) fade out.
// Tier A (currently spilling, or ended within 48h) stays visible at all zoom levels.
const CSO_FADE_ZOOM = 11;
const CSO_RECENT_WINDOW_MS = 48 * 3600 * 1000;


// Date polling began. Displayed in the "Last 30 days" popup subhead so
// users understand why the chart has limited history — the live SWW
// FeatureServer only exposes the most recent event per site, so 30-day
// history fills out hour-by-hour as the cron accumulates events.
const CSO_MONITORING_START = '3rd Jun 2026';

// Flood warning area IDs for the Taw catchment
const TAW_FLOOD_AREAS = [
    // Flood Warning Areas (River Taw specific)
    '113FWF2E1A',   // River Taw (Upper) Sticklepath to Taw Bridge
    '113FWF2E1D',   // River Taw (Upper) at North Tawton
    '113FWF2E1C',   // River Taw (Middle) Taw Bridge to Newnham Bridge
    '113FWF2E1B',   // River Taw (Lower) Newnham Bridge to Barnstaple
    '113FWF2E1E',   // River Taw (Lower) at Bishops Tawton
    '113FWT2T2A4',  // Tidal River Taw Bishops Tawton to Barnstaple
    // Flood Alert Areas (broader catchment)
    '113WAFTW12',   // North Dartmoor Rivers (upper Taw + Okement)
    '113WAFTW03',   // Lower Taw area
    // Okement areas
    '113FWF2D5A', '113FWF2D3A', '113FWF2D4A',
    // Landkey Stream
    '113FWFLANDKEY01',
    // Tidal estuary
    '113FWC2T2A2', '113FWT2T2A3', '113FWC2T2A1',
];

let forecastCache = {}; // stationId -> { data: [...], fetchedAt: Date }
const FORECAST_CACHE_TTL = 15 * 60 * 1000; // 15 minutes

let dischargeCache = {}; // stationId -> { data: {...}, fetchedAt: Date }
const DISCHARGE_CACHE_TTL = 60 * 60 * 1000; // 1 hour (daily data)

const FLOOD_SEVERITY = {
    1: { label: 'Severe Flood Warning', icon: '\u26A0\uFE0F', cssClass: 'sev-1' },
    2: { label: 'Flood Warning',        icon: '\u26A0\uFE0F', cssClass: 'sev-2' },
    3: { label: 'Flood Alert',          icon: '\u26A0',       cssClass: 'sev-3' },
    4: { label: 'No Longer In Force',   icon: '\u2713',       cssClass: 'sev-4' },
};

// ============================================================
// Globals
// ============================================================
let map;
let stationData = {}; // stationId -> { readings: [...], latest: {...} }
let activePopupChart = null;
let activePopupStation = null;
let hasBackend = false; // detected at startup

// ============================================================
// Canvas helpers
// ============================================================

/**
 * Sync a canvas's intrinsic pixel size with its CSS display size so
 * fillText / clearRect use the correct coordinate space.  Without
 * this the default 300×150 bitmap is stretched to fill the container,
 * distorting any text drawn before Chart.js takes over.
 */
function sizeCanvasToDisplay(canvas) {
    const dpr = window.devicePixelRatio || 1;
    const rect = canvas.getBoundingClientRect();
    const w = Math.round(rect.width * dpr);
    const h = Math.round(rect.height * dpr);
    if (canvas.width !== w || canvas.height !== h) {
        canvas.width = w;
        canvas.height = h;
    }
    const ctx = canvas.getContext('2d');
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    return ctx;
}

// ============================================================
// Map Setup
// ============================================================
function initMap() {
    const isMobile = window.innerWidth <= 480;
    map = L.map('map', {
        center: [50.92, -3.88],
        zoom: isMobile ? 10 : 10,
        zoomControl: true,
        tap: true
    });

    // CartoDB Positron (light, muted style as requested)
    L.tileLayer('https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png', {
        attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OSM</a> &copy; <a href="https://carto.com/">CARTO</a> | <a href="https://environment.data.gov.uk/flood-monitoring/doc/reference">EA</a> | <a href="https://open-meteo.com/">Open-Meteo</a>',
        subdomains: 'abcd',
        maxZoom: 19
    }).addTo(map);

    addLegend();

    // Recompute CSO tier-B opacity whenever the user changes zoom level.
    map.on('zoomend', applyCsoZoomFade);
}

// ============================================================
// River Overlay
// ============================================================
const RIVERS = [
    { file: 'river_taw.geojson', name: 'River Taw', color: '#1a8a7d', weight: 3.5, maxArrows: 25 },
    { file: 'river_mole.geojson', name: 'River Mole', color: '#2e7dab', weight: 2.8, maxArrows: 12 },
    { file: 'river_little_dart.geojson', name: 'Little Dart River', color: '#8a6e1a', weight: 2.8, maxArrows: 8 },
    { file: 'river_yeo.geojson', name: 'River Yeo', color: '#7a4a8a', weight: 2.8, maxArrows: 12 },
    { file: 'river_lapford_yeo.geojson', name: 'Lapford Yeo', color: '#ab5e2e', weight: 2.8, maxArrows: 8 },
    { file: 'river_crooked_oak.geojson', name: 'Crooked Oak', color: '#5a8a3a', weight: 2.8, maxArrows: 8 },
    { file: 'river_hollacombe_water.geojson', name: 'Hollocombe Water', color: '#6a7a3a', weight: 2.8, maxArrows: 6 },
];

function loadRiverOverlay() {
    for (const river of RIVERS) {
        fetch(DATA_BASE + river.file)
            .then(r => { if (!r.ok) throw new Error(r.status); return r.json(); })
            .then(geojson => {
                L.geoJSON(geojson, {
                    style: {
                        color: river.color,
                        weight: river.weight,
                        opacity: 0.55,
                        lineCap: 'round',
                        lineJoin: 'round'
                    }
                }).addTo(map);
                addFlowArrows(geojson, river.color, river.maxArrows);
                addRiverLabels(geojson, river);
            })
            .catch(e => console.warn(`Could not load ${river.name} overlay:`, e));
    }
}

function addFlowArrows(geojson, color, maxArrows) {
    // OSM waterway ways are digitized in flow direction (source to mouth).
    const candidates = [];
    for (const feature of geojson.features) {
        const coords = feature.geometry.coordinates;
        if (coords.length < 2) continue;
        const midIdx = Math.floor(coords.length / 2);
        const from = coords[Math.max(0, midIdx - 1)];
        const to = coords[Math.min(midIdx, coords.length - 1)];
        const midLat = (from[1] + to[1]) / 2;
        const midLon = (from[0] + to[0]) / 2;
        const angle = Math.atan2(to[0] - from[0], to[1] - from[1]) * 180 / Math.PI;
        candidates.push({ lat: midLat, lon: midLon, angle });
    }

    const step = Math.max(1, Math.floor(candidates.length / maxArrows));
    for (let i = 0; i < candidates.length; i += step) {
        const { lat, lon, angle } = candidates[i];
        const el = document.createElement('div');
        el.className = 'flow-arrow';
        el.style.setProperty('transform', `rotate(${-angle}deg)`);
        el.style.setProperty('color', color);
        el.innerHTML = '&#x25B2;';
        const arrowIcon = L.divIcon({
            html: el.outerHTML,
            className: '',
            iconSize: [14, 14],
            iconAnchor: [7, 7]
        });
        L.marker([lat, lon], { icon: arrowIcon, interactive: false }).addTo(map);
    }
}

function addRiverLabels(geojson, river) {
    // Find source (most upstream) and mouth (most downstream) points
    let minLat = Infinity, maxLat = -Infinity;
    let minLatCoord = null, maxLatCoord = null;
    for (const feature of geojson.features) {
        for (const coord of feature.geometry.coordinates) {
            if (coord[1] < minLat) { minLat = coord[1]; minLatCoord = coord; }
            if (coord[1] > maxLat) { maxLat = coord[1]; maxLatCoord = coord; }
        }
    }

    // All rivers get a name label near their midpoint
    const allCoords = geojson.features.flatMap(f => f.geometry.coordinates);
    if (allCoords.length > 0) {
        const mid = allCoords[Math.floor(allCoords.length / 2)];
        addLabel(mid[1] + 0.005, mid[0], river.name, river.color);
    }

    if (river.name === 'River Taw') {
        // Also label source and estuary for the main river
        if (minLatCoord) addLabel(minLatCoord[1] - 0.008, minLatCoord[0], 'UPSTREAM (Source)', river.color);
        if (maxLatCoord) addLabel(maxLatCoord[1] + 0.008, maxLatCoord[0], 'DOWNSTREAM (Estuary)', river.color);
    }
}

function addLabel(lat, lon, text, color) {
    const el = document.createElement('div');
    el.className = 'river-label';
    el.style.setProperty('background', color + '18');
    el.style.setProperty('color', color);
    el.style.setProperty('border-color', color + '33');
    el.textContent = text;
    const icon = L.divIcon({
        html: el.outerHTML,
        className: '',
        iconSize: [0, 0],
        iconAnchor: [0, 11]
    });
    L.marker([lat, lon], { icon, interactive: false }).addTo(map);
}

// ============================================================
// Tarka Line railway overlay
// ============================================================
function loadTarkaLine() {
    // Load track
    fetch(DATA_BASE + 'tarka_line.geojson')
        .then(r => r.json())
        .then(geojson => {
            L.geoJSON(geojson, {
                style: {
                    color: '#888',
                    weight: 2,
                    opacity: 0.4,
                    dashArray: '6,4',
                    lineCap: 'round'
                }
            }).addTo(map);
        })
        .catch(e => console.warn('Could not load Tarka Line track:', e));

    // Load stations
    fetch(DATA_BASE + 'tarka_stations.geojson')
        .then(r => r.json())
        .then(geojson => {
            L.geoJSON(geojson, {
                pointToLayer: (feature, latlng) => {
                    return L.circleMarker(latlng, {
                        radius: 4,
                        fillColor: '#666',
                        color: '#fff',
                        weight: 1.5,
                        opacity: 0.8,
                        fillOpacity: 0.7
                    });
                },
                onEachFeature: (feature, layer) => {
                    layer.bindTooltip(feature.properties.name, {
                        permanent: false,
                        direction: 'top',
                        offset: [0, -6],
                        className: 'tarka-tooltip'
                    });
                }
            }).addTo(map);
        })
        .catch(e => console.warn('Could not load Tarka Line stations:', e));

    // Label anchored to the track loop between St Davids and Central
    const tarkaEl = document.createElement('div');
    tarkaEl.className = 'railway-label';
    tarkaEl.textContent = 'Tarka Line';
    const tarkaIcon = L.divIcon({
        html: tarkaEl.outerHTML,
        className: '',
        iconSize: [0, 0],
        iconAnchor: [0, 8]
    });
    L.marker([50.7253, -3.537], { icon: tarkaIcon, interactive: false }).addTo(map);
}

// ============================================================
// Dartmoor Line railway overlay
// ============================================================
function loadDartmoorLine() {
    // Load track (only the unique section from Coleford Junction to Okehampton)
    fetch(DATA_BASE + 'dartmoor_line.geojson')
        .then(r => r.json())
        .then(geojson => {
            L.geoJSON(geojson, {
                style: {
                    color: '#888',
                    weight: 2,
                    opacity: 0.4,
                    dashArray: '6,4',
                    lineCap: 'round'
                }
            }).addTo(map);
        })
        .catch(e => console.warn('Could not load Dartmoor Line track:', e));

    // Load station (Okehampton only -- shared stations already on Tarka Line)
    fetch(DATA_BASE + 'dartmoor_stations.geojson')
        .then(r => r.json())
        .then(geojson => {
            L.geoJSON(geojson, {
                pointToLayer: (feature, latlng) => {
                    return L.circleMarker(latlng, {
                        radius: 4,
                        fillColor: '#666',
                        color: '#fff',
                        weight: 1.5,
                        opacity: 0.8,
                        fillOpacity: 0.7
                    });
                },
                onEachFeature: (feature, layer) => {
                    layer.bindTooltip(feature.properties.name, {
                        permanent: false,
                        direction: 'top',
                        offset: [0, -6],
                        className: 'tarka-tooltip'
                    });
                }
            }).addTo(map);
        })
        .catch(e => console.warn('Could not load Dartmoor Line stations:', e));

    // Label near Okehampton
    const dartmoorEl = document.createElement('div');
    dartmoorEl.className = 'railway-label';
    dartmoorEl.textContent = 'Dartmoor Line';
    const dartmoorIcon = L.divIcon({
        html: dartmoorEl.outerHTML,
        className: '',
        iconSize: [0, 0],
        iconAnchor: [0, 8]
    });
    L.marker([50.7324, -3.985], { icon: dartmoorIcon, interactive: false }).addTo(map);
}

// ============================================================
// Legend
// ============================================================
function addLegend() {
    const legend = L.control({ position: 'bottomleft' });
    legend.onAdd = () => {
        const div = L.DomUtil.create('div', 'legend');
        // Each section is wrapped in a .legend-section-block so CSS
        // multi-column layout can keep section titles paired with their
        // items via `break-inside: avoid`. Without the wrapper, columns
        // could split (say) the "Rivers" h4 from its first item.
        div.innerHTML = `
            <div class="legend-toggle">Legend</div>
            <div class="legend-body">
              <div class="legend-section-block">
                <h4>Monitoring Stations</h4>
                <div class="legend-item"><div class="legend-dot river"></div> River Level (m)</div>
                <div class="legend-item"><div class="legend-dot tidal"></div> Tidal Level (mAOD)</div>
                <div class="legend-item"><div class="legend-dot rain"></div> Rainfall (mm)</div>
              </div>
              <div class="legend-section-block">
                <h4 class="legend-section">Trend (1h)</h4>
                <div class="legend-item"><div class="legend-trend rising">&uarr;</div> Rising</div>
                <div class="legend-item"><div class="legend-trend falling">&darr;</div> Falling</div>
                <div class="legend-item"><div class="legend-trend steady">&rarr;</div> Steady</div>
              </div>
              <div class="legend-section-block">
                <h4 class="legend-section">Storm Overflow</h4>
                <div class="legend-item"><div class="legend-dot cso-active"></div> Discharging now</div>
                <div class="legend-item"><div class="legend-dot cso-recent"></div> Spilled within 48h</div>
                <div class="legend-item"><div class="legend-dot cso-quiet"></div> Quiet</div>
                <div class="legend-item"><div class="legend-dot cso-offline"></div> Monitor offline</div>
              </div>
              <div class="legend-section-block column-break">
                <h4 class="legend-section">Rivers</h4>
                <div class="legend-item"><div class="legend-line river-taw"></div> River Taw</div>
                <div class="legend-item"><div class="legend-line river-mole"></div> River Mole</div>
                <div class="legend-item"><div class="legend-line river-little-dart"></div> Little Dart River</div>
                <div class="legend-item"><div class="legend-line river-yeo"></div> River Yeo</div>
                <div class="legend-item"><div class="legend-line river-lapford-yeo"></div> Lapford Yeo</div>
                <div class="legend-item"><div class="legend-line river-crooked-oak"></div> Crooked Oak</div>
                <div class="legend-item"><div class="legend-line river-hollocombe"></div> Hollocombe Water</div>
                <div class="legend-item"><div class="legend-flow-arrow">&#x25B2;</div> Flow direction</div>
              </div>
              <div class="legend-section-block">
                <h4 class="legend-section">Railway</h4>
                <div class="legend-item"><div class="legend-line railway"></div> Tarka Line</div>
                <div class="legend-item"><div class="legend-line railway"></div> Dartmoor Line</div>
              </div>
            </div>
        `;
        div.querySelector('.legend-toggle').addEventListener('click', function() {
            this.parentElement.classList.toggle('expanded');
        });
        // Prevent map interaction when interacting with the legend
        L.DomEvent.disableClickPropagation(div);
        return div;
    };
    legend.addTo(map);
}

// ============================================================
// Data Loading
// ============================================================
function loadCSV(file) {
    return new Promise((resolve, reject) => {
        // Cache-bust: append timestamp so the browser always fetches fresh CSVs
        const url = DATA_BASE + file + '?t=' + Date.now();
        Papa.parse(url, {
            download: true,
            header: true,
            dynamicTyping: true,
            skipEmptyLines: true,
            complete: result => resolve(result.data),
            error: err => reject(err)
        });
    });
}

async function loadAllData() {
    const allStations = [...STATIONS.level, ...STATIONS.rainfall, ...STATIONS.tidal];

    const promises = allStations.map(async station => {
        try {
            const data = await loadCSV(station.file);
            const readings = data
                .filter(r => r.dateTime && r.value !== null && r.value !== '')
                .map(r => ({
                    dateTime: new Date(r.dateTime),
                    value: parseFloat(r.value)
                }))
                .filter(r => !isNaN(r.value))
                .sort((a, b) => a.dateTime - b.dateTime);

            stationData[station.id] = {
                readings,
                latest: readings.length > 0 ? readings[readings.length - 1] : null
            };
        } catch (e) {
            console.warn(`Could not load data for ${station.label}:`, e);
            stationData[station.id] = { readings: [], latest: null };
        }
    });

    await Promise.all(promises);
}

// ============================================================
// CSO data loading (sites + status + metadata + annual history)
// ============================================================
// Four files, all produced by the Python fetchers in fetch_data.py +
// fetch_cso_history.py. Loaded once at startup — site list rarely changes
// and status JSON is small enough (~75 entries) that one fetch is fine.
async function loadCsoData() {
    // Site list — populates STATIONS.cso. Each row: id, river, lat, lon.
    try {
        const sitesRows = await loadCSV('cso_sites.csv');
        STATIONS.cso = sitesRows
            .filter(r => r.id && r.lat && r.lon)
            .map(r => ({
                id: r.id,
                lat: parseFloat(r.lat),
                lon: parseFloat(r.lon),
                river: r.river || '',
                // Label resolves later when csoMeta loads; fall back to permit ID.
                label: r.id,
            }));
    } catch (e) {
        console.warn('Could not load cso_sites.csv — CSO layer disabled:', e);
        STATIONS.cso = [];
        return;
    }

    // Status snapshot — JSON, keyed by site id.
    try {
        const resp = await fetch(DATA_BASE + 'cso_status.json', { cache: 'no-cache' });
        if (!resp.ok) throw new Error(`${resp.status} ${resp.url}`);
        const snap = await resp.json();
        csoGeneratedAt = snap.generated_at || '';
        for (const [id, status] of Object.entries(snap.sites || {})) {
            csoStatus[id] = status;
        }
    } catch (e) {
        console.warn('Could not load cso_status.json — markers will use unknown status:', e);
    }

    // Static site metadata — name, asset type, designation flags.
    // (One-off output of fetch_cso_history.py.)
    try {
        const metaRows = await loadCSV('cso_sites_meta.csv');
        for (const r of metaRows) {
            if (!r.id) continue;
            csoMeta[r.id] = {
                name: r.name || '',
                assetType: r.asset_type || '',
                shellfishWater: r.shellfish_water || '',
                bathingWater: r.bathing_water || '',
            };
        }
        // Patch the human-readable label onto each STATIONS.cso entry.
        for (const site of STATIONS.cso) {
            const meta = csoMeta[site.id];
            if (meta?.name) site.label = titleCase(meta.name);
        }
    } catch (e) {
        console.warn('Could not load cso_sites_meta.csv:', e);
    }

    // Annual history — popup chart data.
    try {
        const histRows = await loadCSV('cso_annual_history.csv');
        for (const r of histRows) {
            if (!r.id || !r.year) continue;
            (csoHistory[r.id] ??= []).push({
                year: r.year,
                hours: r.hours === '' ? null : parseFloat(r.hours),
                spills: r.spills === '' ? null : parseInt(r.spills, 10),
            });
        }
        // Sort each site's history ascending by year for chart axes.
        for (const id of Object.keys(csoHistory)) {
            csoHistory[id].sort((a, b) => String(a.year).localeCompare(String(b.year)));
        }
    } catch (e) {
        console.warn('Could not load cso_annual_history.csv:', e);
    }
}

// Convert an ALL CAPS source name like "CHULMLEIGH WWTW SSO" to "Chulmleigh
// WWTW SSO" — title-case but keep known acronyms uppercase. Used for
// tooltips (short, fits in a small badge) and the marker hover label.
function titleCase(s) {
    if (!s) return '';
    const acronyms = new Set(['STW', 'SSO', 'CSO', 'WWTW', 'WWTP', 'PS', 'STP']);
    return s.toLowerCase().split(/\s+/).map(w => {
        const up = w.toUpperCase();
        if (acronyms.has(up)) return up;
        // Preserve parenthesised content like "(tidal)" -> "(Tidal)"
        return w.replace(/^(\(?)([a-z])/, (_, p, c) => p + c.toUpperCase());
    }).join(' ');
}

// Expand water-industry acronyms to their long form. Used in popup titles
// and the asset-type meta line so the popup reads naturally for users
// unfamiliar with the abbreviations — matches the descriptive style used
// by sites like water-watch.co.uk.
//
// Input is the already-titleCased string; we expand acronyms in place.
// Case-insensitive match so both "WWTW" and "WwTW" (SWW's casing) work.
function expandAcronyms(s) {
    if (!s) return '';
    const expansions = [
        // Longest first so "WWTW" matches before any shorter accidental subset
        [/\bWWTW\b/gi, 'wastewater treatment works'],
        [/\bWWTP\b/gi, 'wastewater treatment plant'],
        [/\bWwTW\b/g,  'wastewater treatment works'],  // SWW's mixed-case form
        [/\bSTW\b/gi,  'sewage treatment works'],
        [/\bSTP\b/gi,  'sewage treatment plant'],
        [/\bSSO\b/gi,  'settled storm overflow'],
        [/\bCSO\b/gi,  'combined sewer overflow'],
        [/\bPS\b/gi,   'pumping station'],
    ];
    let out = s;
    for (const [re, long] of expansions) {
        out = out.replace(re, long);
    }
    return out;
}

// Resolve a CSO site's visual status from its current state snapshot.
// Returns one of: 'active' (status=1), 'recent' (status=0 AND ended <48h
// ago), 'quiet' (status=0, older), 'offline' (status=-1), 'unknown' (no
// snapshot row).
function csoVisualState(siteId, now) {
    const s = csoStatus[siteId];
    if (!s) return 'unknown';
    if (s.status === 1) return 'active';
    if (s.status === -1) return 'offline';
    // status === 0: distinguish recent vs quiet by event-end age
    if (s.latestEventEnd) {
        const endMs = new Date(s.latestEventEnd).getTime();
        if (!isNaN(endMs) && (now - endMs) < CSO_RECENT_WINDOW_MS) {
            return 'recent';
        }
    }
    return 'quiet';
}

// Tier A (always visible at any zoom): currently discharging OR recent <48h.
function csoIsTierA(visualState) {
    return visualState === 'active' || visualState === 'recent';
}

// ============================================================
// Station Markers
// ============================================================
function createMarkers() {
    // Level stations
    for (const station of STATIONS.level) {
        createStationMarker(station, 'level');
    }

    // Rainfall stations
    for (const station of STATIONS.rainfall) {
        createStationMarker(station, 'rainfall');
    }

    // Tidal stations
    for (const station of STATIONS.tidal) {
        createStationMarker(station, 'tidal');
    }

    // CSO sites — rendered last so they're under EA markers on the z-axis.
    for (const site of STATIONS.cso) {
        createStationMarker(site, 'cso');
    }

    // First-paint pass to apply the current zoom level's tier-B opacity.
    applyCsoZoomFade();
}

function createStationMarker(station, type) {
    // CSO sites have a distinct rendering pipeline — smaller, purple
    // shades by status, no inline value text, tap area larger than the
    // visible circle for mobile.
    if (type === 'cso') {
        return createCsoMarker(station);
    }

    const data = stationData[station.id];
    const latestValue = data?.latest ? data.latest.value : '?';
    const displayValue = typeof latestValue === 'number' ? latestValue.toFixed(type === 'rainfall' ? 1 : 2) : '?';

    const trend = getTrend(station.id, type);
    let trendHtml = '';
    if (trend) {
        trendHtml = `<span class="trend-badge ${trend.direction}">${trend.symbol}</span>`;
    }

    const isHighLevel = type === 'level' && station.typicalRangeHigh && typeof latestValue === 'number' && latestValue >= 0.7 * station.typicalRangeHigh;
    const highClass = isHighLevel ? ' high-level' : '';

    const size = 36;
    const icon = L.divIcon({
        html: `<div class="station-marker ${type}${highClass}"><span class="marker-value">${displayValue}</span>${trendHtml}</div>`,
        className: '',
        iconSize: [size, size],
        iconAnchor: [size / 2, size / 2],
        popupAnchor: [0, -size / 2]
    });

    const marker = L.marker([station.lat, station.lon], { icon, zIndexOffset: 500 }).addTo(map);

    // Hover tooltip with the station name — same pattern as CSO markers.
    // Helpful when the value alone (e.g. "0.4 m") doesn't identify the
    // station to a user scanning the map.
    marker.bindTooltip(station.label, {
        permanent: false,
        direction: 'top',
        offset: [0, -18],
        className: 'station-tooltip',
    });

    marker.on('click', () => openPopup(marker, station, type));
}

// Great-circle distance between two lat/lon points in metres (Haversine).
// Used to detect when a CSO marker would visually overlap with an EA
// station marker so we can offset the icon anchor.
function distanceMeters(lat1, lon1, lat2, lon2) {
    const R = 6371000;
    const toRad = (d) => d * Math.PI / 180;
    const dLat = toRad(lat2 - lat1);
    const dLon = toRad(lon2 - lon1);
    const a = Math.sin(dLat / 2) ** 2
            + Math.cos(toRad(lat1)) * Math.cos(toRad(lat2)) * Math.sin(dLon / 2) ** 2;
    return R * 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
}

// Classify a CSO site by asset type: "major" = at a wastewater treatment
// works (large facility serving a population centre), "minor" = pumping
// station or sewer-network overflow. Drives marker size and whether a
// permanent label is shown at high zoom — visual hierarchy that matches
// the actual infrastructure scale.
function isCsoMajorFacility(assetType) {
    if (!assetType) return false;
    // Catches "Storm tank at WwTW", "Inlet SO at WwTW", and their
    // "- with treatment" variants. SWW uses the mixed-case "WwTW" spelling.
    return /\bwwtw\b/i.test(assetType);
}

// True if `site` sits within CSO_OVERLAP_THRESHOLD_M of any EA station
// (level/rainfall/tidal). Kept as a utility for future use; the marker
// rendering itself doesn't offset based on this (offset was confusing).
const CSO_OVERLAP_THRESHOLD_M = 500;

function csoOverlapsEAStation(site) {
    const eaStations = [
        ...(STATIONS.level || []),
        ...(STATIONS.rainfall || []),
        ...(STATIONS.tidal || []),
    ];
    return eaStations.some(ea =>
        distanceMeters(site.lat, site.lon, ea.lat, ea.lon) < CSO_OVERLAP_THRESHOLD_M
    );
}

// CSO-specific marker rendering. 32px transparent hit area for mobile tap
// targets, visible circle 22px (major facility) or 14px (minor: pumping
// station / sewer-network overflow). The status class is set here at
// create time; tier-B opacity and permanent-label visibility are updated
// by applyCsoZoomFade() on zoom changes.
//
// Markers are drawn at their actual lat/lon — no offset. At zoom 10-11
// (catchment overview), markers near EA stations may be hidden under the
// larger EA marker; at zoom 12+ they separate naturally. Permanent labels
// appear next to major-facility markers at zoom ≥ CSO_LABEL_ZOOM so the
// significant sites are obvious without hovering.
function createCsoMarker(site) {
    const state = csoVisualState(site.id, Date.now());
    const tier = csoIsTierA(state) ? 'tier-a' : 'tier-b';
    const isMajor = isCsoMajorFacility(csoMeta[site.id]?.assetType);
    const sizeClass = isMajor ? 'major' : 'minor';

    // 32px outer hit area. Inner visible circle is sized via CSS based on
    // sizeClass — 22px for major, 14px for minor.
    const size = 32;
    const icon = L.divIcon({
        html: `<div class="cso-marker ${state} ${tier} ${sizeClass}"></div>`,
        className: '',
        iconSize: [size, size],
        iconAnchor: [size / 2, size / 2],
        popupAnchor: [0, -8],
    });

    const marker = L.marker([site.lat, site.lon], {
        icon,
        // zIndexOffset 100 < EA markers' 500 — CSO sits under EA when
        // markers stack at low zoom. Users zoom in to inspect individual
        // sites; tooltips work at any zoom for identification.
        zIndexOffset: 100,
    }).addTo(map);

    // Hover tooltip with the expanded (acronym-free) site name so users
    // unfamiliar with EA shorthand can read it naturally when they need
    // to identify a marker.
    marker.bindTooltip(expandAcronyms(site.label) || site.id, {
        permanent: false,
        direction: 'top',
        offset: [0, -10],
        className: 'cso-tooltip',
    });

    // Tag the leaflet marker so applyCsoZoomFade() can find it.
    marker._csoTier = tier;
    marker._csoId = site.id;
    marker._csoMajor = isMajor;

    marker.on('click', () => openPopup(marker, site, 'cso'));
    return marker;
}

// Apply zoom-based opacity to CSO markers. Tier A (active / recent <48h)
// stays at full opacity. Tier B (quiet / offline) fades to 0 at zoom
// below CSO_FADE_ZOOM, full opacity at or above it. Called on map
// zoomend and after createMarkers() for first paint.
function applyCsoZoomFade() {
    if (!map) return;
    const z = map.getZoom();
    const tierBOpacity = z >= CSO_FADE_ZOOM ? 1 : 0;
    map.eachLayer(layer => {
        if (layer instanceof L.Marker && layer._csoTier === 'tier-b') {
            layer.setOpacity(tierBOpacity);
        }
    });
}

// ============================================================
// Popup
// ============================================================
function openPopup(marker, station, type) {
    // CSO popups have a different shape (status + history, not value +
    // chart) — delegate to a dedicated builder. Full implementation
    // (stats + Gantt + annual chart) lives in openCsoPopup().
    if (type === 'cso') {
        return openCsoPopup(marker, station);
    }

    const data = stationData[station.id];
    const latest = data?.latest;
    const unit = type === 'tidal' ? 'mAOD' : (type === 'level' ? 'm' : 'mm');
    const latestStr = latest ? latest.value.toFixed(type === 'rainfall' ? 1 : 2) : '--';
    const timeStr = latest ? formatTime(latest.dateTime) : '--';
    const hasData = data?.readings?.length > 0;

    // Sanitise dynamic values for safe HTML insertion
    const safeId = station.id.replace(/[^a-zA-Z0-9_-]/g, '');
    const safeLabel = escapeHtml(station.label);
    const safeRiver = station.river ? escapeHtml(station.river) : '';
    const safeType = type.replace(/[^a-z]/g, '');

    const upstreamNote = type === 'level' && station.order
        ? `<span class="upstream-note">#${station.order} ${station.order === 1 ? '(most upstream)' : station.order === 4 ? '(most downstream)' : ''}</span>`
        : '';

    const trend = getTrend(station.id, type);
    const trendLabels = { rising: 'Rising', falling: 'Falling', steady: 'Steady' };
    const trendHtml = trend
        ? `<span class="popup-trend ${trend.direction}" title="${trendLabels[trend.direction]}">${trend.symbol}</span>`
        : '';

    const typeLabels = { level: 'River Level', rainfall: 'Rainfall', tidal: 'Tidal Level' };
    const chartId = `chart-${safeId}`;

    const html = `
        <div class="popup-header">
            <h3>${safeLabel}${upstreamNote}</h3>
            <div class="station-type ${safeType}">${typeLabels[type]}${safeRiver ? ' &mdash; ' + safeRiver : ''}</div>
        </div>
        <div class="popup-current" id="current-${safeId}" data-original-value="${latestStr}" data-original-unit="${unit}" data-original-trend="${trendHtml ? trendHtml.replace(/"/g, '&quot;') : ''}">
            <span class="value">${latestStr}</span>
            <span class="unit">${unit}</span>${trendHtml}
            <span class="timestamp" id="timestamp-${safeId}" data-original="${timeStr}">${timeStr}</span>
        </div>
        ${station.id === '50198' ? `
        <div class="popup-tabs" id="tabs-${safeId}">
            <button class="tab-tidal active" data-action="showTidalTab" data-station="${safeId}">Tidal Level</button>
            <button class="tab-discharge" data-action="showDischargeTab" data-station="${safeId}">River Discharge</button>
        </div>` : ''}
        ${hasData ? `
        <div class="popup-chart-area">
            <div class="popup-chart">
                <canvas id="${chartId}"></canvas>
            </div>
            <div class="popup-timerange" id="timerange-${safeId}">
                <button data-hours="24" data-action="setTimeRange" data-station="${safeId}" data-type="${safeType}">24h</button>
                <button data-hours="48" data-action="setTimeRange" data-station="${safeId}" data-type="${safeType}">48h</button>
                <button class="active" data-hours="${5*24}" data-action="setTimeRange" data-station="${safeId}" data-type="${safeType}">5d</button>
                <button data-hours="${30*24}" data-action="setTimeRange" data-station="${safeId}" data-type="${safeType}">30d</button>
                <button data-hours="0" data-action="setTimeRange" data-station="${safeId}" data-type="${safeType}">All</button>
                ${type === 'rainfall' ? `<button class="forecast-btn" data-action="showForecast" data-station="${safeId}">&#9729; Fcst</button>` : ''}
            </div>
        </div>
        ` : `
        <div class="popup-nodata">No data available for this station</div>
        `}
    `;

    const isMobile = window.innerWidth <= 480;
    const isTablet = window.innerWidth <= 768;
    const popupMinWidth = isMobile ? 260 : isTablet ? 300 : 380;
    const popupMaxWidth = isMobile ? 320 : isTablet ? 360 : 400;
    marker.unbindPopup();
    marker.bindPopup(html, { maxWidth: popupMaxWidth, minWidth: popupMinWidth, className: '' }).openPopup();

    // Event delegation for popup buttons (replaces inline onclick handlers).
    // Attach directly to the popup element after openPopup() so the listener
    // is live immediately — a 'popupopen' handler would fire too late because
    // the event is emitted during openPopup() above, before we could register.
    const popupEl = marker.getPopup().getElement();
    if (popupEl) {
        popupEl.addEventListener('click', function(e) {
            const btn = e.target.closest('button[data-action]');
            if (!btn) return;
            const action = btn.dataset.action;
            const sid = btn.dataset.station;
            if (action === 'setTimeRange') {
                setTimeRange(sid, parseInt(btn.dataset.hours), btn.dataset.type, btn);
            } else if (action === 'showForecast') {
                showForecast(sid, btn);
            } else if (action === 'showTidalTab') {
                showTidalTab(sid, btn);
            } else if (action === 'showDischargeTab') {
                showDischargeTab(sid, btn);
            }
        });
    }

    if (hasData) {
        activePopupStation = station.id;
        // Wait for popup DOM to render
        setTimeout(() => renderChart(station.id, 5 * 24, type), 50);
    }
}

// ============================================================
// CSO popup — current state, lazy-loaded event log, two charts
// ============================================================

// Tracks Chart.js instances inside the active CSO popup so we can destroy
// them on popup close. Separate from `activePopupChart` which the EA
// markers use — they render only one chart at a time, we render two.
let activeCsoCharts = [];

// In-memory cache of per-site event logs. Each is the contents of
// data/cso_<id>.csv parsed into {start: Date, end: Date|null, ongoing: bool}.
// Loaded lazily on first popup open for that site.
const csoEventCache = {};

async function loadCsoEventLog(siteId) {
    if (csoEventCache[siteId]) return csoEventCache[siteId];
    try {
        const rows = await loadCSV(`cso_${siteId}.csv`);
        const events = rows.map(r => ({
            start: r.start_time ? new Date(r.start_time) : null,
            end: r.end_time ? new Date(r.end_time) : null,
            ongoing: r.is_ongoing === 'true',
        })).filter(e => e.start && !isNaN(e.start));
        csoEventCache[siteId] = events;
        return events;
    } catch (e) {
        console.warn(`No event log for ${siteId} yet:`, e);
        csoEventCache[siteId] = [];
        return [];
    }
}

// Compute spill stats over a [windowStart, windowEnd] interval. Hours sums
// the portion of each event's duration that falls inside the window; spills
// counts events overlapping it. Ongoing events are treated as ending at
// windowEnd (i.e. "still going as of now").
function computeCsoStats(events, windowStart, windowEnd) {
    let hours = 0;
    let spills = 0;
    for (const e of events) {
        const eEnd = e.end || windowEnd;
        const oStart = Math.max(e.start.getTime(), windowStart.getTime());
        const oEnd = Math.min(eEnd.getTime(), windowEnd.getTime());
        if (oEnd > oStart) {
            hours += (oEnd - oStart) / 3600000;
            spills += 1;
        }
    }
    return { hours, spills };
}

// Build the stats panel using DOM construction (textContent only — no
// innerHTML, no string interpolation into HTML). Numeric values from
// computeCsoStats are safe inputs but DOM construction keeps the XSS
// surface explicitly zero.
function renderCsoStats(container, monthStats, slidingStats) {
    while (container.firstChild) container.removeChild(container.firstChild);
    const grid = document.createElement('div');
    grid.className = 'cso-stat-grid';

    const buildStat = (labelText, hours, spills) => {
        const wrap = document.createElement('div');
        wrap.className = 'cso-stat';
        const label = document.createElement('div');
        label.className = 'cso-stat-label';
        label.textContent = labelText;
        const value = document.createElement('div');
        value.className = 'cso-stat-value';
        value.textContent = `${hours.toFixed(1)}h`;
        const sub = document.createElement('div');
        sub.className = 'cso-stat-sub';
        sub.textContent = `${spills} ${spills === 1 ? 'spill' : 'spills'}`;
        wrap.append(label, value, sub);
        return wrap;
    };

    grid.append(
        buildStat('This month', monthStats.hours, monthStats.spills),
        buildStat('Last 30 days', slidingStats.hours, slidingStats.spills),
    );
    container.appendChild(grid);
}

function openCsoPopup(marker, site) {
    const status = csoStatus[site.id] || {};
    const meta = csoMeta[site.id] || {};
    const history = csoHistory[site.id] || [];

    const state = csoVisualState(site.id, Date.now());
    const stateLabel = {
        active: 'Discharging now',
        recent: 'Spilled within 48h',
        quiet: 'Quiet',
        offline: 'Monitor offline',
        unknown: 'Status unknown',
    }[state];

    const safeId = site.id.replace(/[^a-zA-Z0-9_-]/g, '');
    // Popup title uses the expanded EA permit name (acronyms spelled out)
    // so users unfamiliar with WWTW/SSO/etc. can read it naturally — matches
    // the descriptive style of sites like water-watch.co.uk.
    const safeLabel = escapeHtml(expandAcronyms(site.label) || site.id);
    const safeRiver = site.river ? escapeHtml(site.river) : '';
    const safeAsset = meta.assetType ? escapeHtml(meta.assetType) : '';

    const sinceStart = status.statusStart ? formatTime(new Date(status.statusStart)) : '';
    const lastPing = status.lastUpdated ? formatTime(new Date(status.lastUpdated)) : '';

    // All template values are escapeHtml()'d, status state is a known-safe
    // literal, IDs are sanitised — same XSS posture as the existing EA popups.
    // Compact meta line: only render parts that exist, joined with " · ".
    // Avoids three separate rows for Asset / Permit / EDM.
    const metaParts = [];
    if (safeAsset) metaParts.push(safeAsset);
    metaParts.push(escapeHtml(site.id));
    if (lastPing) metaParts.push(`EDM ${escapeHtml(lastPing)}`);

    const html = `
        <div class="popup-header cso">
            <h3>${safeLabel}</h3>
            <div class="station-type cso">Storm Overflow${safeRiver ? ' &mdash; ' + safeRiver : ''}</div>
        </div>
        <div class="cso-current ${state}">
            <span class="cso-state-badge ${state}">${stateLabel}</span>
            ${sinceStart ? `<span class="timestamp">since ${escapeHtml(sinceStart)}</span>` : ''}
        </div>
        <div class="cso-meta">${metaParts.join(' &middot; ')}</div>
        <div class="cso-stats" id="cso-stats-${safeId}">
            <div class="cso-stat-loading">Loading…</div>
        </div>
        <div class="cso-chart-block">
            <h4>Last 30 days <span class="cso-monitoring-since">(monitoring started ${CSO_MONITORING_START})</span></h4>
            <div class="cso-chart-container"><canvas id="cso-gantt-${safeId}"></canvas></div>
        </div>
        <div class="cso-chart-block">
            <h4>Annual spill hours</h4>
            <div class="cso-chart-container annual"><canvas id="cso-annual-${safeId}"></canvas></div>
        </div>
    `;

    // unbindPopup + bindPopup pattern: matches the EA popup behaviour
    // (see openPopup line ~773). Without the explicit unbind, Leaflet
    // retains a stale popup binding after the user closes the popup once,
    // and the second click silently fails to reopen it.
    marker.unbindPopup();
    marker.bindPopup(html, { className: 'cso-popup', maxWidth: 380 }).openPopup();

    // Tear down any charts left over from a previous CSO popup. Wrapped
    // in try/catch because Chart.js can throw if the canvas was already
    // detached when its containing popup closed.
    for (const c of activeCsoCharts) {
        try { c.destroy(); } catch (_) { /* canvas already gone */ }
    }
    activeCsoCharts = [];

    // Render charts after Leaflet has attached the popup DOM.
    setTimeout(() => renderCsoPopupCharts(site.id, history), 50);
}

async function renderCsoPopupCharts(siteId, history) {
    const safeId = siteId.replace(/[^a-zA-Z0-9_-]/g, '');
    const events = await loadCsoEventLog(siteId);

    // Two stat windows: calendar month + last-30-days sliding.
    const now = new Date();
    const monthStart = new Date(Date.UTC(now.getUTCFullYear(), now.getUTCMonth(), 1));
    const thirtyDaysAgo = new Date(now.getTime() - 30 * 86400 * 1000);

    const statsEl = document.getElementById(`cso-stats-${safeId}`);
    if (statsEl) {
        renderCsoStats(
            statsEl,
            computeCsoStats(events, monthStart, now),
            computeCsoStats(events, thirtyDaysAgo, now),
        );
    }

    renderCsoRecentActivity(safeId, events, thirtyDaysAgo, now);
    renderCsoAnnualChart(safeId, history);
}

// Recent-activity panel — adapts the visualisation to data density.
//   N == 0  → "no spills" message painted on canvas
//   N ≤ THRESHOLD → textual event list (each row: date, duration)
//   N >  THRESHOLD → daily-totals histogram
//
// Sparse data (1-3 events) reads better as a list — a histogram with one
// 6-minute bar in 30 days of empty space is a lot of chart for very
// little information. Once polling has accumulated more events the
// histogram surfaces patterns the list can't (e.g. clusters during
// storms).
const CSO_HISTOGRAM_THRESHOLD = 3;

function renderCsoRecentActivity(safeId, events, windowStart, windowEnd) {
    const canvas = document.getElementById(`cso-gantt-${safeId}`);
    if (!canvas) return;
    const container = canvas.parentElement;

    const inWindow = events.filter(e => {
        const eEnd = e.end || windowEnd;
        return eEnd.getTime() >= windowStart.getTime() && e.start.getTime() <= windowEnd.getTime();
    });

    if (inWindow.length === 0) {
        renderCsoNoSpills(container);
        return;
    }

    if (inWindow.length <= CSO_HISTOGRAM_THRESHOLD) {
        renderCsoEventList(container, inWindow, windowEnd);
        return;
    }

    renderCsoHistogram(canvas, events, windowStart, windowEnd);
}

// Replace the canvas with a one-line "no spills" message. Same compact
// container treatment as the event-list mode (height: auto, no 70px
// canvas reserve) so the empty state takes about the same vertical
// space as a single list row.
function renderCsoNoSpills(container) {
    while (container.firstChild) container.removeChild(container.firstChild);
    container.classList.add('as-list');

    const msg = document.createElement('div');
    msg.className = 'cso-no-events';
    msg.textContent = 'No spills in the last 30 days';
    container.appendChild(msg);
}

// Compact event list — replaces the canvas with a <ul> when there are
// only a few events to show. Newest first. DOM construction (no innerHTML)
// keeps the XSS surface zero — all interpolated values come from Date
// methods or pre-computed numbers.
function renderCsoEventList(container, eventsInWindow, windowEnd) {
    while (container.firstChild) container.removeChild(container.firstChild);
    container.classList.add('as-list');

    const ul = document.createElement('ul');
    ul.className = 'cso-event-list';

    // Newest event first.
    const sorted = [...eventsInWindow].sort((a, b) => b.start - a.start);

    for (const e of sorted) {
        const li = document.createElement('li');

        const whenSpan = document.createElement('span');
        whenSpan.className = 'cso-event-when';
        whenSpan.textContent = e.start.toLocaleString('en-GB', {
            day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit', timeZone: 'UTC',
        }) + ' UTC';

        const durSpan = document.createElement('span');
        durSpan.className = 'cso-event-dur';
        durSpan.textContent = formatCsoEventDuration(e, windowEnd);

        li.append(whenSpan, durSpan);
        ul.appendChild(li);
    }

    container.appendChild(ul);
}

function formatCsoEventDuration(event, windowEnd) {
    const eEnd = event.end || windowEnd;
    const mins = Math.round((eEnd.getTime() - event.start.getTime()) / 60000);
    const tag = event.ongoing ? ' (ongoing)' : '';
    if (mins < 60) return `${mins} min${tag}`;
    const h = Math.floor(mins / 60);
    const m = mins % 60;
    return (m === 0 ? `${h}h` : `${h}h ${m}m`) + tag;
}

// Daily-totals bar chart. One bar per calendar day, height = total
// minutes of spill that day. Only used when there are >3 events in
// window (per renderCsoRecentActivity dispatch).
function renderCsoHistogram(canvas, events, windowStart, windowEnd) {
    // Bucket each event's duration into the calendar days it overlaps.
    const dayMs = 86400 * 1000;
    const startDay = new Date(Date.UTC(windowStart.getUTCFullYear(), windowStart.getUTCMonth(), windowStart.getUTCDate()));
    const numDays = Math.ceil((windowEnd.getTime() - startDay.getTime()) / dayMs);

    const dailyMinutes = new Array(numDays).fill(0);
    const labels = [];
    for (let i = 0; i < numDays; i++) {
        const d = new Date(startDay.getTime() + i * dayMs);
        labels.push(d.toLocaleDateString('en-GB', { day: 'numeric', month: 'short' }));
    }

    for (const e of events) {
        const eEnd = e.end || windowEnd;
        const oStart = Math.max(e.start.getTime(), windowStart.getTime());
        const oEnd = Math.min(eEnd.getTime(), windowEnd.getTime());
        if (oEnd <= oStart) continue;

        // Distribute event minutes across the days it overlaps.
        let cursor = oStart;
        while (cursor < oEnd) {
            const dayIndex = Math.floor((cursor - startDay.getTime()) / dayMs);
            const dayEnd = startDay.getTime() + (dayIndex + 1) * dayMs;
            const segEnd = Math.min(dayEnd, oEnd);
            if (dayIndex >= 0 && dayIndex < numDays) {
                dailyMinutes[dayIndex] += (segEnd - cursor) / 60000;
            }
            cursor = segEnd;
        }
    }

    // Convert minutes to hours for display.
    const dailyHours = dailyMinutes.map(m => +(m / 60).toFixed(2));

    const chart = new Chart(canvas, {
        type: 'bar',
        data: {
            labels,
            datasets: [{
                data: dailyHours,
                backgroundColor: '#9b6cc4',
                borderColor: '#5b2a8a',
                borderWidth: 1,
                barPercentage: 1.0,
                categoryPercentage: 0.9,
            }],
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            animation: false,
            plugins: {
                legend: { display: false },
                tooltip: {
                    callbacks: {
                        title: (items) => labels[items[0].dataIndex],
                        label: (item) => {
                            const h = item.parsed.y;
                            if (h < 1) return `${Math.round(h * 60)} min`;
                            return `${h.toFixed(1)}h`;
                        },
                    },
                },
            },
            scales: {
                x: {
                    ticks: {
                        color: '#8890a8',
                        font: { size: 9 },
                        maxRotation: 0,
                        autoSkipPadding: 12,
                    },
                    grid: { display: false },
                },
                y: {
                    beginAtZero: true,
                    ticks: {
                        color: '#8890a8',
                        font: { size: 9 },
                        callback: v => v + 'h',
                    },
                    grid: { color: 'rgba(144,152,176,0.15)' },
                },
            },
        },
    });
    activeCsoCharts.push(chart);
}

function renderCsoAnnualChart(safeId, history) {
    const canvas = document.getElementById(`cso-annual-${safeId}`);
    if (!canvas) return;

    if (history.length === 0) {
        const ctx = sizeCanvasToDisplay(canvas);
        const rect = canvas.getBoundingClientRect();
        ctx.fillStyle = '#888';
        ctx.font = '13px sans-serif';
        ctx.textAlign = 'center';
        ctx.fillText('No annual returns recorded', rect.width / 2, rect.height / 2);
        return;
    }

    const chart = new Chart(canvas, {
        type: 'bar',
        data: {
            labels: history.map(h => String(h.year)),
            datasets: [{
                label: 'Hours discharging',
                data: history.map(h => h.hours),
                backgroundColor: '#9b6cc4',
                borderColor: '#5b2a8a',
                borderWidth: 1,
            }],
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            animation: false,
            plugins: {
                legend: { display: false },
                tooltip: {
                    callbacks: {
                        label: (item) => {
                            const h = history[item.dataIndex];
                            const parts = [h.hours == null ? '?' : h.hours.toFixed(1) + 'h'];
                            if (h.spills != null) parts.push(`${h.spills} spills`);
                            return parts.join(' · ');
                        },
                    },
                },
            },
            scales: {
                x: {
                    ticks: { color: '#8890a8', font: { size: 10 } },
                    grid: { display: false },
                },
                y: {
                    beginAtZero: true,
                    ticks: {
                        color: '#8890a8',
                        font: { size: 10 },
                        callback: v => v + 'h',
                    },
                    grid: { color: '#3a406022' },
                },
            },
        },
    });
    activeCsoCharts.push(chart);
}

function setTimeRange(stationId, hours, type, btn) {
    // Update active button
    const container = document.getElementById(`timerange-${stationId}`);
    if (container) {
        container.querySelectorAll('button').forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
    }
    // Restore original timestamp (in case we were in forecast mode)
    const tsEl = document.getElementById(`timestamp-${stationId}`);
    if (tsEl) tsEl.textContent = tsEl.dataset.original;
    renderChart(stationId, hours, type);
}

// ============================================================
// Open-Meteo Rainfall Forecast
// ============================================================

async function fetchForecast(stationId) {
    const cached = forecastCache[stationId];
    if (cached && (Date.now() - cached.fetchedAt) < FORECAST_CACHE_TTL) {
        return cached.data;
    }

    const station = getStation(stationId);
    if (!station) throw new Error('Station not found');

    const url = `https://api.open-meteo.com/v1/forecast?latitude=${station.lat}&longitude=${station.lon}&hourly=precipitation&forecast_days=2&timezone=Europe/London`;
    const resp = await fetch(url);
    if (!resp.ok) throw new Error(`Open-Meteo API error: ${resp.status}`);

    const json = await resp.json();
    const times = json.hourly?.time || [];
    const precip = json.hourly?.precipitation || [];

    const data = times.map((t, i) => ({
        dateTime: new Date(t),
        value: precip[i] ?? 0
    }));

    forecastCache[stationId] = { data, fetchedAt: Date.now() };
    return data;
}

async function showForecast(stationId, btn) {
    const container = document.getElementById(`timerange-${stationId}`);

    // Toggle off: if forecast button is already active, return to default historical view
    if (btn.classList.contains('active')) {
        if (container) {
            container.querySelectorAll('button').forEach(b => b.classList.remove('active'));
            const defaultBtn = container.querySelector('button[data-hours="120"]');
            if (defaultBtn) defaultBtn.classList.add('active');
        }
        // Restore original timestamp
        const tsEl = document.getElementById(`timestamp-${stationId}`);
        if (tsEl) tsEl.textContent = tsEl.dataset.original;
        renderChart(stationId, 5 * 24, 'rainfall');
        return;
    }

    // Deactivate all buttons, activate forecast button
    if (container) {
        container.querySelectorAll('button').forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
    }

    // Destroy existing chart
    if (activePopupChart) {
        activePopupChart.destroy();
        activePopupChart = null;
    }

    // Show loading state on canvas
    const canvas = document.getElementById(`chart-${stationId}`);
    if (!canvas) return;
    const ctx = sizeCanvasToDisplay(canvas);
    const rect = canvas.getBoundingClientRect();
    ctx.clearRect(0, 0, rect.width, rect.height);
    ctx.fillStyle = '#8890a8';
    ctx.font = '13px sans-serif';
    ctx.textAlign = 'center';
    ctx.fillText('Loading forecast\u2026', rect.width / 2, rect.height / 2);

    // Update timestamp to show forecast range
    const tsEl = document.getElementById(`timestamp-${stationId}`);
    if (tsEl) tsEl.textContent = 'Loading\u2026';

    try {
        const data = await fetchForecast(stationId);
        // Update timestamp with forecast date range
        if (tsEl && data.length > 0) {
            const from = data[0].dateTime;
            const to = data[data.length - 1].dateTime;
            const fmt = d => d.toLocaleDateString('en-GB', { day: 'numeric', month: 'short' });
            tsEl.textContent = `Forecast: ${fmt(from)}\u2013${fmt(to)}`;
        }
        renderForecastChart(stationId, data);
    } catch (e) {
        console.error('Forecast error:', e);
        if (tsEl) tsEl.textContent = tsEl.dataset.original;
        const errCtx = sizeCanvasToDisplay(canvas);
        const errRect = canvas.getBoundingClientRect();
        errCtx.clearRect(0, 0, errRect.width, errRect.height);
        errCtx.fillStyle = '#e05555';
        errCtx.font = '13px sans-serif';
        errCtx.textAlign = 'center';
        errCtx.fillText('Forecast unavailable', errRect.width / 2, errRect.height / 2);
    }
}

function renderForecastChart(stationId, forecastData) {
    if (activePopupChart) {
        activePopupChart.destroy();
        activePopupChart = null;
    }

    const canvas = document.getElementById(`chart-${stationId}`);
    if (!canvas) return;

    activePopupChart = new Chart(canvas, {
        type: 'bar',
        data: {
            labels: forecastData.map(r => r.dateTime),
            datasets: [{
                label: 'Predicted rainfall',
                data: forecastData.map(r => r.value),
                backgroundColor: 'rgba(212, 160, 55, 0.6)',
                borderColor: '#d4a037',
                borderWidth: 1,
                borderRadius: 2
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    display: true,
                    labels: {
                        color: '#8890a8',
                        font: { size: 9 },
                        boxWidth: 12,
                        boxHeight: 10,
                        padding: 6
                    },
                    position: 'bottom'
                },
                tooltip: {
                    backgroundColor: '#2a3050',
                    titleColor: '#e0e4f0',
                    bodyColor: '#e0e4f0',
                    borderColor: '#3a4060',
                    borderWidth: 1,
                    callbacks: {
                        title: items => {
                            const d = new Date(items[0].parsed.x);
                            return d.toLocaleString();
                        },
                        label: item => `${item.parsed.y.toFixed(1)} mm`
                    }
                }
            },
            scales: {
                x: {
                    type: 'time',
                    time: {
                        tooltipFormat: 'PPpp',
                        displayFormats: {
                            hour: 'HH:mm',
                            day: 'dd MMM'
                        }
                    },
                    ticks: { color: '#8890a8', maxTicksLimit: 8, font: { size: 10 } },
                    grid: { color: '#3a406033' }
                },
                y: {
                    min: 0,
                    ticks: {
                        color: '#8890a8',
                        font: { size: 10 },
                        callback: v => v.toFixed(0) + ' mm'
                    },
                    grid: { color: '#3a406033' }
                }
            }
        }
    });
}

// ============================================================
// GloFAS River Discharge Forecast (Barnstaple tidal only)
// ============================================================

async function fetchDischarge(stationId) {
    const cached = dischargeCache[stationId];
    if (cached && (Date.now() - cached.fetchedAt) < DISCHARGE_CACHE_TTL) {
        return cached.data;
    }

    const station = getStation(stationId);
    if (!station) throw new Error('Station not found');

    // Use Umberleigh coordinates (NRFA 50001) -- the main Taw gauging point.
    // Barnstaple's own coords resolve to a minor stream in the GloFAS 5km grid.
    const dischargeLat = 50.99542;
    const dischargeLon = -3.985089;
    const url = `https://flood-api.open-meteo.com/v1/flood?latitude=${dischargeLat}&longitude=${dischargeLon}&daily=river_discharge_mean,river_discharge_max,river_discharge_min&forecast_days=14&past_days=7&cell_selection=land`;
    const resp = await fetch(url);
    if (!resp.ok) throw new Error(`Flood API error: ${resp.status}`);

    const json = await resp.json();
    const times = json.daily?.time || [];
    const mean = json.daily?.river_discharge_mean || [];
    const max = json.daily?.river_discharge_max || [];
    const min = json.daily?.river_discharge_min || [];

    const data = {
        time: times.map(t => new Date(t)),
        mean, max, min
    };

    dischargeCache[stationId] = { data, fetchedAt: Date.now() };
    return data;
}

function showTidalTab(stationId, btn) {
    // Update tab active states
    const tabs = document.getElementById(`tabs-${stationId}`);
    if (tabs) {
        tabs.querySelectorAll('button').forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
    }

    // Restore original tidal value/unit/timestamp
    const currentEl = document.getElementById(`current-${stationId}`);
    if (currentEl) {
        const origValue = currentEl.dataset.originalValue;
        const origUnit = currentEl.dataset.originalUnit;
        const origTrend = currentEl.dataset.originalTrend || '';
        const tsEl = document.getElementById(`timestamp-${stationId}`);
        const origTime = tsEl?.dataset.original || '';
        currentEl.innerHTML = `
            <span class="value">${origValue}</span>
            <span class="unit">${origUnit}</span>${origTrend}
            <span class="timestamp" id="timestamp-${stationId}" data-original="${origTime}">${origTime}</span>
        `;
    }

    // Show timerange buttons, remove chart right padding, remove discharge legend
    const timerange = document.getElementById(`timerange-${stationId}`);
    if (timerange) timerange.style.display = '';
    const chartDiv = document.getElementById(`chart-${stationId}`)?.parentElement;
    if (chartDiv) {
        chartDiv.style.paddingRight = '';
        const legend = chartDiv.parentElement?.parentElement?.querySelector('.discharge-legend');
        if (legend) legend.remove();
    }

    // Restore default tidal chart
    renderChart(stationId, 5 * 24, 'tidal');
}

async function showDischargeTab(stationId, btn) {
    // Update tab active states
    const tabs = document.getElementById(`tabs-${stationId}`);
    if (tabs) {
        tabs.querySelectorAll('button').forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
    }

    // Hide timerange buttons, add right padding to chart to match left
    const timerange = document.getElementById(`timerange-${stationId}`);
    if (timerange) timerange.style.display = 'none';
    const chartDiv = document.getElementById(`chart-${stationId}`)?.parentElement;
    if (chartDiv) chartDiv.style.paddingRight = '12px';

    // Destroy existing chart
    if (activePopupChart) {
        activePopupChart.destroy();
        activePopupChart = null;
    }

    // Show loading on canvas
    const canvas = document.getElementById(`chart-${stationId}`);
    if (!canvas) return;
    const ctx = sizeCanvasToDisplay(canvas);
    const rect = canvas.getBoundingClientRect();
    ctx.clearRect(0, 0, rect.width, rect.height);
    ctx.fillStyle = '#8890a8';
    ctx.font = '13px sans-serif';
    ctx.textAlign = 'center';
    ctx.fillText('Loading discharge data\u2026', rect.width / 2, rect.height / 2);

    // Update current value area to show loading
    const currentEl = document.getElementById(`current-${stationId}`);
    if (currentEl) {
        currentEl.innerHTML = `
            <span class="value">\u2014</span>
            <span class="unit">m\u00b3/s</span>
            <span class="timestamp" id="timestamp-${stationId}">Loading\u2026</span>
        `;
    }

    try {
        const data = await fetchDischarge(stationId);

        // Find today's value
        const today = new Date();
        today.setHours(0, 0, 0, 0);
        let todayIdx = data.time.findIndex(t => t >= today);
        if (todayIdx < 0) todayIdx = data.time.length - 1;
        const todayMean = data.mean[todayIdx];

        // Update current value area with discharge info
        if (currentEl) {
            const from = data.time[0];
            const to = data.time[data.time.length - 1];
            const fmt = d => d.toLocaleDateString('en-GB', { day: 'numeric', month: 'short' });
            currentEl.innerHTML = `
                <span class="value">${todayMean != null ? todayMean.toFixed(1) : '\u2014'}</span>
                <span class="unit">m\u00b3/s</span>
                <span class="timestamp" id="timestamp-${stationId}">${fmt(from)}\u2013${fmt(to)}</span>
            `;
        }

        renderDischargeChart(stationId, data);
    } catch (e) {
        console.error('Discharge error:', e);
        if (currentEl) {
            currentEl.innerHTML = `
                <span class="value">\u2014</span>
                <span class="unit">m\u00b3/s</span>
                <span class="timestamp" id="timestamp-${stationId}">Unavailable</span>
            `;
        }
        const errCtx = sizeCanvasToDisplay(canvas);
        const errRect = canvas.getBoundingClientRect();
        errCtx.clearRect(0, 0, errRect.width, errRect.height);
        errCtx.fillStyle = '#e05555';
        errCtx.font = '13px sans-serif';
        errCtx.textAlign = 'center';
        errCtx.fillText('Discharge data unavailable', errRect.width / 2, errRect.height / 2);
    }
}

function renderDischargeChart(stationId, data) {
    if (activePopupChart) {
        activePopupChart.destroy();
        activePopupChart = null;
    }

    const canvas = document.getElementById(`chart-${stationId}`);
    if (!canvas) return;

    // Build datasets: min-max range as filled band (forecast only), mean as solid line
    const labels = data.time;

    // Only show min-max range from today onward (forecast days)
    const today = new Date();
    today.setHours(0, 0, 0, 0);
    const forecastMax = data.max.map((v, i) => data.time[i] >= today ? v : null);
    const forecastMin = data.min.map((v, i) => data.time[i] >= today ? v : null);

    activePopupChart = new Chart(canvas, {
        type: 'line',
        data: {
            labels,
            datasets: [
                {
                    label: 'Forecast range',
                    data: forecastMax,
                    borderColor: 'transparent',
                    backgroundColor: 'rgba(212, 160, 55, 0.15)',
                    fill: '+1',
                    pointRadius: 0,
                    pointHoverRadius: 0,
                    spanGaps: false
                },
                {
                    label: 'Forecast range',
                    data: forecastMin,
                    borderColor: 'transparent',
                    backgroundColor: 'rgba(212, 160, 55, 0.15)',
                    fill: false,
                    pointRadius: 0,
                    pointHoverRadius: 0,
                    spanGaps: false
                },
                {
                    label: 'Mean discharge',
                    data: data.mean,
                    borderColor: '#d4a037',
                    backgroundColor: 'rgba(212, 160, 55, 0.3)',
                    borderWidth: 2,
                    pointRadius: 0,
                    pointHoverRadius: 4,
                    fill: false,
                    tension: 0.3
                },
                {
                    label: 'Normal flow (Mean)',
                    data: data.time.map(() => 18.3),
                    borderColor: 'rgba(74, 173, 74, 0.6)',
                    borderWidth: 1,
                    borderDash: [6, 4],
                    pointRadius: 0,
                    pointHoverRadius: 0,
                    fill: false
                },
                {
                    label: 'High flow (Q10)',
                    data: data.time.map(() => 48.3),
                    borderColor: 'rgba(224, 85, 85, 0.6)',
                    borderWidth: 1,
                    borderDash: [6, 4],
                    pointRadius: 0,
                    pointHoverRadius: 0,
                    fill: false
                }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    display: false
                },
                tooltip: {
                    backgroundColor: '#2a3050',
                    titleColor: '#e0e4f0',
                    bodyColor: '#e0e4f0',
                    borderColor: '#3a4060',
                    borderWidth: 1,
                    filter: item => item.datasetIndex === 2,
                    callbacks: {
                        title: items => {
                            const d = new Date(items[0].parsed.x);
                            return d.toLocaleDateString('en-GB', { weekday: 'short', day: 'numeric', month: 'short' });
                        },
                        label: item => {
                            const idx = item.dataIndex;
                            const mean = data.mean[idx];
                            const isForecast = data.time[idx] >= today;
                            if (isForecast) {
                                const min = data.min[idx];
                                const max = data.max[idx];
                                return `${mean?.toFixed(1)} m\u00b3/s (${min?.toFixed(1)}\u2013${max?.toFixed(1)})`;
                            }
                            return `${mean?.toFixed(1)} m\u00b3/s`;
                        }
                    }
                },
                todayLine: {
                    id: 'todayLine',
                    afterDraw(chart) {
                        const xScale = chart.scales.x;
                        const today = new Date();
                        today.setHours(0, 0, 0, 0);
                        const x = xScale.getPixelForValue(today.getTime());
                        if (x < xScale.left || x > xScale.right) return;
                        const ctx = chart.ctx;
                        ctx.save();
                        ctx.strokeStyle = '#8890a8';
                        ctx.lineWidth = 1;
                        ctx.setLineDash([4, 4]);
                        ctx.beginPath();
                        ctx.moveTo(x, chart.chartArea.top);
                        ctx.lineTo(x, chart.chartArea.bottom);
                        ctx.stroke();
                        ctx.setLineDash([]);
                        ctx.fillStyle = '#8890a8';
                        ctx.font = '9px sans-serif';
                        ctx.textAlign = 'center';
                        ctx.fillText('Today', x, chart.chartArea.top - 3);
                        ctx.restore();
                    }
                }
            },
            scales: {
                x: {
                    type: 'time',
                    time: {
                        unit: 'day',
                        tooltipFormat: 'PP',
                        displayFormats: {
                            day: 'dd MMM'
                        }
                    },
                    ticks: { color: '#8890a8', maxTicksLimit: 7, font: { size: 10 } },
                    grid: { color: '#3a406033' }
                },
                y: {
                    min: 0,
                    ticks: {
                        color: '#8890a8',
                        font: { size: 10 },
                        callback: v => v.toFixed(0) + ' m\u00b3/s'
                    },
                    grid: { color: '#3a406033' }
                }
            },
            interaction: {
                intersect: false,
                mode: 'index'
            }
        }
    });

    // Add HTML legend below chart area (two rows for clean layout)
    const chartArea = canvas.closest('.popup-chart-area');
    let legendEl = chartArea?.parentElement.querySelector('.discharge-legend');
    if (!legendEl && chartArea) {
        legendEl = document.createElement('div');
        legendEl.className = 'discharge-legend';
        chartArea.after(legendEl);
    }
    legendEl.innerHTML = `
        <div class="discharge-legend-row">
            <span class="discharge-legend-item"><span class="legend-swatch forecast-range"></span>Forecast range</span>
            <span class="discharge-legend-item"><span class="legend-line discharge-mean"></span>Mean discharge</span>
        </div>
        <div class="discharge-legend-row">
            <span class="discharge-legend-item"><span class="legend-line dashed normal-flow"></span>Normal flow (Mean)</span>
            <span class="discharge-legend-item"><span class="legend-line dashed high-flow"></span>High flow (Q10)</span>
        </div>`;
}

function getStation(stationId) {
    return FloodwatchCore.getStation(stationId, STATIONS);
}

function renderChart(stationId, hours, type) {
    if (activePopupChart) {
        activePopupChart.destroy();
        activePopupChart = null;
    }

    const canvas = document.getElementById(`chart-${stationId}`);
    if (!canvas) return;

    const data = stationData[stationId];
    if (!data?.readings?.length) return;

    let readings = data.readings;
    if (hours > 0) {
        const cutoff = new Date(Date.now() - hours * 3600 * 1000);
        readings = readings.filter(r => r.dateTime >= cutoff);
    }

    // Downsample large datasets to keep charts responsive.
    // Target ~3000 points -- plenty of visual detail for a 400px-wide chart.
    const MAX_CHART_POINTS = 3000;
    if (readings.length > MAX_CHART_POINTS) {
        const step = readings.length / (MAX_CHART_POINTS - 1);
        const sampled = [readings[0]];
        for (let i = 1; i < MAX_CHART_POINTS - 1; i++) {
            sampled.push(readings[Math.round(i * step)]);
        }
        sampled.push(readings[readings.length - 1]);
        readings = sampled;
    }

    if (readings.length === 0) {
        // Show message
        const ctx = sizeCanvasToDisplay(canvas);
        const msgRect = canvas.getBoundingClientRect();
        ctx.fillStyle = '#8890a8';
        ctx.font = '13px sans-serif';
        ctx.textAlign = 'center';
        ctx.fillText('No data for this time range', msgRect.width / 2, msgRect.height / 2);
        return;
    }

    const unit = type === 'tidal' ? 'mAOD' : (type === 'level' ? 'm' : 'mm');
    const colors = { level: '#1a8a7d', rainfall: '#5574b8', tidal: '#c47a2a' };
    const bgColors = { level: 'rgba(26, 138, 125, 0.15)', rainfall: 'rgba(85, 116, 184, 0.15)', tidal: 'rgba(196, 122, 42, 0.15)' };
    const color = colors[type];
    const bgColor = bgColors[type];

    // Look up station for typicalRangeHigh (level stations only)
    const station = getStation(stationId);
    const rangeHigh = station?.typicalRangeHigh;

    // Build datasets -- main readings line + optional "top of normal range" reference line
    const datasets = [{
        data: readings.map(r => r.value),
        borderColor: color,
        backgroundColor: bgColor,
        borderWidth: 1.5,
        pointRadius: readings.length > 200 ? 0 : 1,
        pointHoverRadius: 3,
        fill: true,
        tension: 0.3
    }];

    if (rangeHigh) {
        datasets.push({
            label: 'Top of normal range',
            data: readings.map(() => rangeHigh),
            borderColor: 'rgba(224, 85, 85, 0.6)',
            borderWidth: 1,
            borderDash: [6, 4],
            pointRadius: 0,
            pointHoverRadius: 0,
            fill: false,
            tension: 0
        });
    }

    // Y-axis: fixed scale for stations with typicalRangeHigh, auto for others
    const yScale = {
        min: 0,
        ticks: {
            color: '#8890a8',
            font: { size: 10 },
            stepSize: type === 'rainfall' ? undefined : 0.5,
            callback: v => v.toFixed(type === 'rainfall' ? 0 : 1) + ' ' + unit
        },
        grid: { color: '#3a406033' }
    };
    if (rangeHigh) {
        yScale.max = Math.ceil(rangeHigh * 1.25 * 2) / 2;
    }

    activePopupChart = new Chart(canvas, {
        type: 'line',
        data: {
            labels: readings.map(r => r.dateTime),
            datasets
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    display: !!rangeHigh,
                    labels: {
                        filter: item => item.text === 'Top of normal range',
                        color: '#8890a8',
                        font: { size: 9 },
                        boxWidth: 20,
                        boxHeight: 1,
                        padding: 6,
                        usePointStyle: false
                    },
                    position: 'bottom'
                },
                tooltip: {
                    backgroundColor: '#2a3050',
                    titleColor: '#e0e4f0',
                    bodyColor: '#e0e4f0',
                    borderColor: '#3a4060',
                    borderWidth: 1,
                    filter: item => item.datasetIndex === 0,
                    callbacks: {
                        title: items => {
                            const d = new Date(items[0].parsed.x);
                            return d.toLocaleString();
                        },
                        label: item => `${item.parsed.y.toFixed(type === 'rainfall' ? 1 : 2)} ${unit}`
                    }
                }
            },
            scales: {
                x: {
                    type: 'time',
                    time: {
                        tooltipFormat: 'PPpp',
                        displayFormats: {
                            hour: 'HH:mm',
                            day: 'dd MMM',
                            week: 'dd MMM',
                            month: 'MMM yyyy'
                        }
                    },
                    ticks: { color: '#8890a8', maxTicksLimit: 6, font: { size: 10 } },
                    grid: { color: '#3a406033' }
                },
                y: yScale
            },
            interaction: {
                intersect: false,
                mode: 'index'
            }
        }
    });
}

// ============================================================
// Refresh Activity Log
// ============================================================
const MAX_LOG_ENTRIES = 6;

function showLog() {
    const log = document.getElementById('refresh-log');
    log.classList.remove('hidden');
    log.innerHTML = '';
}

function hideLog(delay = 3000) {
    setTimeout(() => {
        const log = document.getElementById('refresh-log');
        log.classList.add('hidden');
        setTimeout(() => { log.innerHTML = ''; }, 600);
    }, delay);
}

function addLogEntry(text, type = 'info') {
    const log = document.getElementById('refresh-log');
    const entry = document.createElement('div');
    entry.className = `refresh-log-entry ${type}`;
    entry.textContent = text;
    log.appendChild(entry);

    // Keep only the last N entries plus the progress bar
    const entries = log.querySelectorAll('.refresh-log-entry');
    while (entries.length > MAX_LOG_ENTRIES) {
        entries[0].remove();
        break;
    }
}

function setLogProgress(current, total, label) {
    const log = document.getElementById('refresh-log');
    let bar = log.querySelector('.refresh-log-progress');
    if (!bar) {
        bar = document.createElement('div');
        bar.className = 'refresh-log-progress';
        log.prepend(bar);
    }
    const pct = Math.round((current / total) * 100);
    bar.textContent = '';
    const barBg = document.createElement('div');
    barBg.className = 'bar-bg';
    const barFill = document.createElement('div');
    barFill.className = 'bar-fill';
    barFill.style.width = pct + '%';
    barBg.appendChild(barFill);
    bar.appendChild(barBg);
    bar.appendChild(document.createTextNode(` ${current}/${total} ${escapeHtml(label)}`));
}

function removeLogProgress() {
    const bar = document.querySelector('.refresh-log-progress');
    if (bar) bar.remove();
}

// ============================================================
// Data Refresh
// ============================================================
async function refreshData() {
    forecastCache = {};
    dischargeCache = {};

    const btn = document.getElementById('refresh-btn');
    btn.classList.add('loading');
    btn.setAttribute('aria-busy', 'true');
    btn.disabled = true;

    const statusEl = document.getElementById('last-updated');
    statusEl.textContent = 'Refreshing...';
    showLog();
    addLogEntry('Starting data refresh\u2026', 'info');

    try {
        const allStations = [...STATIONS.level, ...STATIONS.rainfall, ...STATIONS.tidal];
        const total = allStations.length;
        let totalNew = 0;
        let stationsUpdated = 0;
        let stationsFailed = 0;

        let useCSVFallback = false;

        for (let i = 0; i < allStations.length; i++) {
            const station = allStations[i];
            setLogProgress(i + 1, total, 'stations');
            addLogEntry(`Fetching ${station.label}\u2026`, 'info');

            try {
                if (useCSVFallback) throw new Error('CSV fallback');

                const existing = stationData[station.id]?.readings || [];
                const latestTime = existing.length > 0 ? existing[existing.length - 1].dateTime : null;
                const now = new Date();
                let allItems = [];

                if (latestTime) {
                    const gapMs = now - latestTime;
                    const gapDays = gapMs / (1000 * 60 * 60 * 24);

                    if (gapDays <= 5) {
                        const url = `${API_BASE}/id/measures/${station.measureId}/readings?since=${latestTime.toISOString()}&_sorted&_limit=10000`;
                        const resp = await fetch(url);
                        if (!resp.ok) throw new Error(`EA API error: ${resp.status}`);
                        const data = await resp.json();
                        allItems = data.items || [];
                    } else {
                        // Large gap: fetch in 28-day chunks
                        addLogEntry(`  ${Math.round(gapDays)}d gap \u2014 chunked fetch`, 'warn');
                        let chunkEnd = now;
                        const chunkDays = 28;
                        const startLimit = latestTime;
                        let chunkNum = 0;

                        while (chunkEnd > startLimit) {
                            chunkNum++;
                            const chunkStart = new Date(chunkEnd - chunkDays * 86400000);
                            const effectiveStart = chunkStart < startLimit ? startLimit : chunkStart;
                            const startStr = effectiveStart.toISOString().split('T')[0];
                            const endStr = chunkEnd.toISOString().split('T')[0];

                            const url = `${API_BASE}/id/measures/${station.measureId}/readings?startdate=${startStr}&enddate=${endStr}&_sorted&_limit=100000`;
                            try {
                                const resp = await fetch(url);
                                if (!resp.ok) throw new Error(`EA API error: ${resp.status}`);
                                const data = await resp.json();
                                const chunkItems = data.items || [];
                                allItems = allItems.concat(chunkItems);
                                addLogEntry(`  chunk ${chunkNum}: ${startStr} \u2192 ${endStr} (${chunkItems.length})`, 'info');
                            } catch (e) {
                                addLogEntry(`  chunk ${chunkNum} failed`, 'error');
                            }

                            chunkEnd = new Date(effectiveStart - 86400000);
                            await new Promise(r => setTimeout(r, 300));
                        }
                    }
                } else {
                    addLogEntry(`  No existing data \u2014 fetching 28d`, 'warn');
                    const startDate = new Date(now - 28 * 86400000).toISOString().split('T')[0];
                    const endDate = now.toISOString().split('T')[0];
                    const url = `${API_BASE}/id/measures/${station.measureId}/readings?startdate=${startDate}&enddate=${endDate}&_sorted&_limit=100000`;
                    const resp = await fetch(url);
                    if (!resp.ok) throw new Error(`EA API error: ${resp.status}`);
                    const data = await resp.json();
                    allItems = data.items || [];
                }

                if (allItems.length > 0) {
                    const newReadings = allItems
                        .map(r => ({ dateTime: new Date(r.dateTime), value: parseFloat(r.value) }))
                        .filter(r => !isNaN(r.value));

                    const existingTimes = new Set(existing.map(r => r.dateTime.toISOString()));
                    const merged = [...existing];
                    let newCount = 0;

                    for (const r of newReadings) {
                        if (!existingTimes.has(r.dateTime.toISOString())) {
                            merged.push(r);
                            newCount++;
                        }
                    }

                    merged.sort((a, b) => a.dateTime - b.dateTime);
                    stationData[station.id] = { readings: merged, latest: merged[merged.length - 1] };

                    if (newCount > 0) {
                        totalNew += newCount;
                        stationsUpdated++;
                        addLogEntry(`${station.label}: +${newCount} readings`, 'success');
                    } else {
                        addLogEntry(`${station.label}: up to date`, 'success');
                    }
                } else {
                    addLogEntry(`${station.label}: no new data`, 'success');
                }
            } catch (e) {
                // EA API failed (likely CORS) — fall back to reloading CSV
                if (!useCSVFallback) {
                    useCSVFallback = true;
                    addLogEntry('EA API unavailable \u2014 using cached data (updated hourly)', 'warn');
                }
                try {
                    const data = await loadCSV(station.file);
                    const readings = data
                        .filter(r => r.dateTime && r.value !== null && r.value !== '')
                        .map(r => ({ dateTime: new Date(r.dateTime), value: parseFloat(r.value) }))
                        .filter(r => !isNaN(r.value))
                        .sort((a, b) => a.dateTime - b.dateTime);

                    const oldCount = stationData[station.id]?.readings?.length || 0;
                    stationData[station.id] = {
                        readings,
                        latest: readings.length > 0 ? readings[readings.length - 1] : null
                    };
                    const diff = readings.length - oldCount;
                    if (diff > 0) { totalNew += diff; stationsUpdated++; }
                    addLogEntry(`${station.label}: loaded cached data`, 'success');
                } catch {
                    stationsFailed++;
                    addLogEntry(`${station.label}: failed`, 'error');
                    console.warn(`Refresh failed for ${station.label}:`, e);
                }
            }
        }

        removeLogProgress();

        // Re-create markers with updated values
        map.eachLayer(layer => {
            if (layer instanceof L.Marker && layer.options.zIndexOffset === 500) {
                map.removeLayer(layer);
            }
        });
        createMarkers();

        // Persist updated data
        // Always cache to localStorage so fresh data survives a reload,
        // even if the browser serves stale CSVs from its HTTP cache.
        cacheToLocalStorage();

        if (hasBackend) {
            addLogEntry('Syncing to backend\u2026', 'info');
            try {
                const syncResp = await fetch('refresh.php', { method: 'POST' });
                if (!syncResp.ok) throw new Error(`Backend sync: ${syncResp.status}`);
                addLogEntry('Backend sync done', 'success');
            } catch (e) {
                addLogEntry('Backend sync failed \u2014 cached locally', 'warn');
            }
        } else {
            addLogEntry('Cached to browser storage', 'success');
        }

        // Refresh flood warnings (may silently fail if EA API is CORS-blocked)
        addLogEntry('Checking flood warnings\u2026', 'info');
        await fetchFloodWarnings();

        const source = useCSVFallback ? ' (cached data)' : '';
        const summary = `Done: ${stationsUpdated} updated, +${totalNew} readings${source}` + (stationsFailed > 0 ? `, ${stationsFailed} failed` : '');
        addLogEntry(summary, stationsFailed > 0 ? 'warn' : (useCSVFallback ? 'warn' : 'success'));
        if (useCSVFallback) {
            addLogEntry('No live data fetched \u2014 EA API is currently unavailable', 'warn');
        }
        statusEl.textContent = `Updated ${new Date().toLocaleTimeString()}`;
        hideLog(useCSVFallback ? 6000 : 4000);

    } catch (e) {
        addLogEntry(`Refresh failed: ${e.message}`, 'error');
        statusEl.textContent = 'Refresh failed';
        console.error('Refresh error:', e);
        hideLog(6000);
    } finally {
        btn.classList.remove('loading');
        btn.setAttribute('aria-busy', 'false');
        btn.disabled = false;
    }
}

// ============================================================
// Helpers
// ============================================================
function formatTime(date) {
    return FloodwatchCore.formatTime(date);
}

function getTrend(stationId, type) {
    if (type === 'rainfall') return null;
    const data = stationData[stationId];
    if (!data?.readings?.length) return null;
    return FloodwatchCore.getTrend(data.readings, type);
}

// ============================================================
// Flood Warnings (EA Flood Monitoring API)
// ============================================================

function escapeHtml(str) {
    return FloodwatchCore.escapeHtml(str);
}

async function fetchFloodWarnings() {
    // Uses XHR to keep CORS failures silent in the console (fetch() logs
    // a red error that can't be suppressed from JavaScript).
    return new Promise(resolve => {
        const xhr = new XMLHttpRequest();
        xhr.open('GET', API_BASE + '/id/floods?county=Devon');
        xhr.onload = () => {
            try {
                if (xhr.status < 200 || xhr.status >= 300) throw new Error(`Flood warnings API error: ${xhr.status}`);
                const data = JSON.parse(xhr.responseText);
                const items = data.items || [];

                const tawWarnings = items.filter(item => {
                    const areaId = item.floodAreaID || '';
                    return TAW_FLOOD_AREAS.includes(areaId) &&
                           item.severityLevel >= 1 && item.severityLevel <= 3;
                });

                tawWarnings.sort((a, b) => a.severityLevel - b.severityLevel);
                renderFloodWarnings(tawWarnings);
            } catch (e) {
                console.warn('Could not fetch flood warnings:', e);
                const statusEl = document.getElementById('flood-status');
                statusEl.classList.add('visible');
            }
            resolve();
        };
        xhr.onerror = () => {
            console.warn('Could not fetch flood warnings (network error)');
            const statusEl = document.getElementById('flood-status');
            statusEl.classList.add('visible');
            resolve();
        };
        xhr.send();
    });
}

function renderFloodWarnings(warnings) {
    const banner = document.getElementById('flood-warnings');
    const textEl = document.getElementById('flood-warnings-text');
    const detailsEl = document.getElementById('flood-warnings-details');
    const statusEl = document.getElementById('flood-status');

    if (warnings.length === 0) {
        banner.classList.add('hidden');
        banner.classList.remove('expanded', 'severity-1', 'severity-2', 'severity-3');
        const summary = banner.querySelector('.flood-warnings-summary');
        if (summary) summary.setAttribute('aria-expanded', 'false');
        if (statusEl) statusEl.classList.add('visible');
        if (map) map.invalidateSize();
        return;
    }

    // Hide the green "no warnings" status
    if (statusEl) statusEl.classList.remove('visible');

    // Determine highest severity (lowest number)
    const highestSeverity = Math.min(...warnings.map(w => w.severityLevel));
    const sevInfo = FLOOD_SEVERITY[highestSeverity];

    // Update severity class on banner
    banner.classList.remove('severity-1', 'severity-2', 'severity-3');
    banner.classList.add(`severity-${highestSeverity}`);

    // Build summary text
    const iconEl = banner.querySelector('.flood-warnings-icon');
    iconEl.textContent = sevInfo.icon;

    if (warnings.length === 1) {
        textEl.textContent = `${sevInfo.label}: ${warnings[0].description}`;
    } else {
        const counts = {};
        for (const w of warnings) {
            const label = FLOOD_SEVERITY[w.severityLevel].label;
            counts[label] = (counts[label] || 0) + 1;
        }
        const parts = Object.entries(counts).map(([label, count]) =>
            `${count} ${label}${count > 1 ? 's' : ''}`
        );
        textEl.textContent = parts.join(', ') + ' in the Taw catchment';
    }

    // Build details panel
    let detailsHtml = '';
    for (const w of warnings) {
        const sev = FLOOD_SEVERITY[w.severityLevel];
        const raised = w.timeRaised ? formatTime(new Date(w.timeRaised)) : '';
        const changed = w.timeSeverityChanged ? formatTime(new Date(w.timeSeverityChanged)) : '';
        const river = w.floodArea?.riverOrSea || '';

        detailsHtml += `
            <div class="flood-warning-item">
                <div class="flood-warning-item-header">
                    <span class="flood-warning-severity ${sev.cssClass}">${sev.label}</span>
                </div>
                <div class="flood-warning-description">${escapeHtml(w.description || '')}</div>
                ${w.message ? `<div class="flood-warning-message">${escapeHtml(w.message)}</div>` : ''}
                <div class="flood-warning-meta">
                    ${river ? `<span>${escapeHtml(river)}</span>` : ''}
                    ${raised ? `<span>Raised: ${raised}</span>` : ''}
                    ${changed ? `<span>Updated: ${changed}</span>` : ''}
                </div>
            </div>
        `;
    }
    detailsEl.innerHTML = detailsHtml;

    // Show banner
    banner.classList.remove('hidden');
    if (map) map.invalidateSize();
}

function toggleFloodWarnings() {
    const banner = document.getElementById('flood-warnings');
    banner.classList.toggle('expanded');
    const summary = banner.querySelector('.flood-warnings-summary');
    if (summary) summary.setAttribute('aria-expanded', banner.classList.contains('expanded'));
    setTimeout(() => { if (map) map.invalidateSize(); }, 320);
}

// ============================================================
// LocalStorage Cache (for static deployments without a backend)
// ============================================================
const CACHE_KEY = 'floodwatch_cache';
const CACHE_VERSION = 1;
const CACHE_FINGERPRINT = FloodwatchCore.computeCacheFingerprint(STATIONS);

function cacheToLocalStorage() {
    try {
        const cache = { version: CACHE_VERSION, fingerprint: CACHE_FINGERPRINT, timestamp: new Date().toISOString(), stations: {} };
        for (const [id, data] of Object.entries(stationData)) {
            if (!data.readings?.length) continue;
            // Only store readings newer than the CSV data would have
            // to keep localStorage small. Store the last 7 days max.
            const cutoff = new Date(Date.now() - 7 * 86400000);
            const recent = data.readings.filter(r => r.dateTime >= cutoff);
            cache.stations[id] = recent.map(r => ({
                t: r.dateTime.toISOString(),
                v: r.value
            }));
        }
        localStorage.setItem(CACHE_KEY, JSON.stringify(cache));
    } catch (e) {
        console.warn('LocalStorage cache write failed:', e);
    }
}

function loadFromLocalStorage() {
    try {
        const raw = localStorage.getItem(CACHE_KEY);
        if (!raw) return;
        const cache = JSON.parse(raw);
        if (cache.version !== CACHE_VERSION || cache.fingerprint !== CACHE_FINGERPRINT) return;

        let merged = 0;
        for (const [id, entries] of Object.entries(cache.stations)) {
            if (!entries?.length) continue;
            const existing = stationData[id];
            if (!existing) continue;

            const existingTimes = new Set(existing.readings.map(r => r.dateTime.toISOString()));
            let added = 0;

            for (const entry of entries) {
                if (!existingTimes.has(entry.t)) {
                    existing.readings.push({ dateTime: new Date(entry.t), value: entry.v });
                    added++;
                }
            }

            if (added > 0) {
                existing.readings.sort((a, b) => a.dateTime - b.dateTime);
                existing.latest = existing.readings[existing.readings.length - 1];
                merged += added;
            }
        }
        if (merged > 0) {
            console.log(`Merged ${merged} cached readings from localStorage`);
        }
    } catch (e) {
        console.warn('LocalStorage cache read failed:', e);
    }
}

async function detectBackend() {
    // Check whether a refresh backend (serve.py or refresh.php) is available.
    // GET + JSON-parse check: a real backend executes the PHP and returns
    // JSON; a static file server returns the raw PHP source (which isn't
    // JSON).  Uses XHR to keep probe failures silent in the console.
    return new Promise(resolve => {
        const xhr = new XMLHttpRequest();
        xhr.open('GET', 'refresh.php?probe=1');
        xhr.onload = () => {
            if (xhr.status < 200 || xhr.status >= 300) return resolve(false);
            try { JSON.parse(xhr.responseText); resolve(true); }
            catch { resolve(false); }
        };
        xhr.onerror = () => resolve(false);
        xhr.send();
    });
}

// ============================================================
// Init
// ============================================================
async function init() {
    initMap();
    loadRiverOverlay();
    loadTarkaLine();
    loadDartmoorLine();
    // EA station data + CSO data load in parallel — they touch disjoint
    // file sets so there's no ordering dependency.
    await Promise.all([loadAllData(), loadCsoData()]);
    loadFromLocalStorage(); // merge any cached data on top of CSVs
    createMarkers();

    // Show data freshness immediately — don't wait for network probes
    const latestTimes = Object.values(stationData)
        .map(d => d.latest?.dateTime)
        .filter(Boolean)
        .sort((a, b) => b - a);

    if (latestTimes.length > 0) {
        document.getElementById('last-updated').textContent =
            `Data from ${formatTime(latestTimes[0])}`;
    }

    // Wire up event listeners (replaces inline onclick= in HTML)
    document.getElementById('refresh-btn').addEventListener('click', refreshData);
    document.querySelector('.flood-warnings-summary').addEventListener('click', toggleFloodWarnings);

    // Flood warnings, backend detection, version tag run in parallel — non-blocking
    fetchFloodWarnings();
    detectBackend().then(result => { hasBackend = result; });
    fetch('version.json')
        .then(r => r.json())
        .then(data => {
            const el = document.getElementById('version-tag');
            if (el && data.version) el.textContent = '(' + data.version + ')';
        })
        .catch(() => {}); // non-critical
}

init();
