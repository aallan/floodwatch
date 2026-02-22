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
    ]
};

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
        div.innerHTML = `
            <div class="legend-toggle">Legend</div>
            <div class="legend-body">
            <h4>Monitoring Stations</h4>
            <div class="legend-item"><div class="legend-dot river"></div> River Level (m)</div>
            <div class="legend-item"><div class="legend-dot tidal"></div> Tidal Level (mAOD)</div>
            <div class="legend-item"><div class="legend-dot rain"></div> Rainfall (mm)</div>
            <h4 class="legend-section">Rivers</h4>
            <div class="legend-item"><div class="legend-line river-taw"></div> River Taw</div>
            <div class="legend-item"><div class="legend-line river-mole"></div> River Mole</div>
            <div class="legend-item"><div class="legend-line river-little-dart"></div> Little Dart River</div>
            <div class="legend-item"><div class="legend-line river-yeo"></div> River Yeo</div>
            <div class="legend-item"><div class="legend-line river-lapford-yeo"></div> Lapford Yeo</div>
            <div class="legend-item"><div class="legend-line river-crooked-oak"></div> Crooked Oak</div>
            <div class="legend-item"><div class="legend-line river-hollocombe"></div> Hollocombe Water</div>
            <div class="legend-item"><div class="legend-flow-arrow">&#x25B2;</div> Flow direction</div>
            <h4 class="legend-section">Railway</h4>
            <div class="legend-item"><div class="legend-line railway"></div> Tarka Line</div>
            <div class="legend-item"><div class="legend-line railway"></div> Dartmoor Line</div>
            <h4 class="legend-section">Trend (1h)</h4>
            <div class="legend-item"><div class="legend-trend rising">&uarr;</div> Rising</div>
            <div class="legend-item"><div class="legend-trend falling">&darr;</div> Falling</div>
            <div class="legend-item"><div class="legend-trend steady">&rarr;</div> Steady</div>
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
}

function createStationMarker(station, type) {
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

    marker.on('click', () => openPopup(marker, station, type));
}

// ============================================================
// Popup
// ============================================================
function openPopup(marker, station, type) {
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

        for (let i = 0; i < allStations.length; i++) {
            const station = allStations[i];
            setLogProgress(i + 1, total, 'stations');
            addLogEntry(`Fetching ${station.label}\u2026`, 'info');

            try {
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
                stationsFailed++;
                addLogEntry(`${station.label}: failed`, 'error');
                console.warn(`Refresh failed for ${station.label}:`, e);
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

        // Summary
        // Refresh flood warnings
        addLogEntry('Checking flood warnings\u2026', 'info');
        await fetchFloodWarnings();
        addLogEntry('Flood warnings updated', 'success');

        const summary = `Done: ${stationsUpdated} updated, +${totalNew} readings` + (stationsFailed > 0 ? `, ${stationsFailed} failed` : '');
        addLogEntry(summary, stationsFailed > 0 ? 'warn' : 'success');
        statusEl.textContent = `Updated ${new Date().toLocaleTimeString()}`;
        hideLog(4000);

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
    try {
        const resp = await fetch(API_BASE + '/id/floods?county=Devon');
        if (!resp.ok) throw new Error(`Flood warnings API error: ${resp.status}`);
        const data = await resp.json();
        const items = data.items || [];

        // Filter to Taw catchment areas with active severity (1-3)
        const tawWarnings = items.filter(item => {
            const areaId = item.floodAreaID || '';
            return TAW_FLOOD_AREAS.includes(areaId) &&
                   item.severityLevel >= 1 && item.severityLevel <= 3;
        });

        // Sort by severity (most severe first)
        tawWarnings.sort((a, b) => a.severityLevel - b.severityLevel);

        renderFloodWarnings(tawWarnings);
    } catch (e) {
        console.warn('Could not fetch flood warnings:', e);
    }
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
    // On static hosts this 404s — we test via XHR instead of fetch() because
    // fetch() logs non-2xx responses as console errors in Chrome, which looks
    // alarming even though they are handled.  XHR failures are silent.
    return new Promise(resolve => {
        const xhr = new XMLHttpRequest();
        xhr.open('HEAD', 'refresh.php');
        xhr.onload = () => resolve(xhr.status >= 200 && xhr.status < 300);
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
    await loadAllData();
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
