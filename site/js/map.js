'use strict';

// The Taw catchment map: the gauges and their readings first, then storm
// overflows and flood warnings, over quiet waterways, roads and railways.
// Colours come from CSS variables so the map follows light/dark mode.

const FloodMap = (() => {
  const DATA = 'data/';

  // The opening view takes in the whole catchment, from Dartmoor to
  // Braunton, in the space beside the legend.
  const CATCHMENT_BOUNDS = [[50.65, -4.22], [51.19, -3.59]];
  // Devon and a wide margin round it, so its edges can be panned to the
  // middle of the screen.
  const MAX_BOUNDS = [[49.6, -5.9], [51.9, -1.8]];

  // Floodwatch's river colours, by name; other rivers are drawn in the
  // plain water colour. Each is a CSS variable, so it follows the theme.
  const RIVER_COLOURS = {
    'River Taw': '--river-taw',
    'River Mole': '--river-mole',
    'Little Dart River': '--river-little-dart',
    'River Yeo': '--river-yeo',
    'Lapford Yeo': '--river-lapford-yeo',
    'Crooked Oak': '--river-crooked-oak',
    'Hollocombe Water': '--river-hollocombe',
  };

  const MAJOR_RIVER_KM = 20;     // rivers at least this long are labelled first
  const MAJOR_LABEL_ZOOM = 9;    // long rivers labelled from here
  const RAIL_LABEL_ZOOM = 10;    // passenger line names from here
  const STREAM_MIN_ZOOM = 12;    // streams appear from here
  const CSO_QUIET_ZOOM = 11;     // quiet and offline storm overflows appear from here
  const MINOR_LABEL_ZOOM = 11;   // shorter rivers and freight lines get labels from here
  const ARROW_MIN_ZOOM = 12;     // flow arrows appear from here
  const ARROW_SPACING_KM = 2.5;

  const TILES = {
    light: ['Canvas/World_Light_Gray_Base', 'Canvas/World_Light_Gray_Reference'],
    dark: ['Canvas/World_Dark_Gray_Base', 'Canvas/World_Dark_Gray_Reference'],
  };
  const tileUrl = svc => `https://server.arcgisonline.com/ArcGIS/rest/services/${svc}/MapServer/tile/{z}/{y}/{x}`;

  let map;
  let tileTheme = null;
  let legendReady = false;
  let baseTiles = null;
  let refTiles = null;

  const PHONE = window.matchMedia('(max-width: 640px)');

  // Legend toggles. Each map part belongs to one toggle and may have a min zoom.
  const toggles = {
    catchment: { on: false },
    rivers:    { on: true },
    streams:   { on: false },
    passenger: { on: true },
    freight:   { on: true },
    stations:  { on: true },
    roads:     { on: true },
    levels:    { on: true },
    tidal:     { on: true },
    rain:      { on: true },
    // Only the overflows spilling now show when the page opens; spilled
    // recently, and quiet or offline (from CSO_QUIET_ZOOM), are switched on
    // from the legend.
    csoNow:    { on: true },
    csoRecent: { on: false },
    csoQuiet:  { on: false },
    floods:    { on: true },
    powercuts: { on: true },
  };
  // Legend sections whose heading switches the whole group.
  const GROUPS = {
    floods: ['floods'],
    power: ['powercuts'],
    live: ['levels', 'tidal', 'rain'],
    overflows: ['csoNow', 'csoRecent', 'csoQuiet'],
    waterways: ['rivers', 'streams'],
    railways: ['passenger', 'freight', 'stations'],
    roads: ['roads'],
  };
  const parts = [];       // { layer, toggle, minZoom, z }
  const restylers = [];   // functions re-applying colours/weights
  const renderers = {};

  // Draw order on the shared canvas, bottom to top. Labels and arrows are
  // DOM markers in their own pane, so their order doesn't matter.
  const Z = { mask: 0, streams: 1, rivers: 2, floods: 2.5, roads: 3, boundary: 4, catchment: 4.5, rail: 5, stations: 6, markers: 9 };

  function addPart(layer, toggle, z, minZoom = 0) {
    parts.push({ layer, toggle, z, minZoom });
  }

  // All interactive overlays share one canvas, which draws in the order layers
  // were added. So when the visible set changes, re-add everything in Z order
  // rather than appending, or a re-enabled layer would land on top.
  let shownKey = '';
  function updateVisibility() {
    const zoom = map.getZoom();
    const shown = parts
      .map((p, i) => ({ ...p, i }))
      .filter(p => toggles[p.toggle].on && zoom >= p.minZoom)
      .sort((a, b) => a.z - b.z || a.i - b.i);
    const key = shown.map(p => p.i).join(',');
    if (key !== shownKey) {
      shownKey = key;
      for (const p of parts) if (map.hasLayer(p.layer)) map.removeLayer(p.layer);
      for (const p of shown) p.layer.addTo(map);
    }
    const hint = $('#legend-streams-hint');
    if (hint) hint.textContent = zoom < STREAM_MIN_ZOOM ? 'zoom in' : '';
    const quiet = $('#legend-cso-quiet-hint');
    if (quiet) quiet.style.display = zoom < CSO_QUIET_ZOOM ? '' : 'none';
  }

  // ---------------------------------------------------------------- panes
  // One canvas for every interactive overlay. Separate canvases per pane look
  // tidier, but the topmost canvas swallows all mouse events, so nothing
  // beneath it gets a tooltip. The mask is not interactive, so it can have its
  // own canvas underneath, and place-name tiles sit above in a click-through pane.
  function makePanes() {
    map.createPane('mask').style.zIndex = 350;
    map.createPane('labels').style.zIndex = 450;
    // Storm overflows sit just beneath the gauges (the marker pane is 600).
    map.createPane('overflows').style.zIndex = 590;
    map.getPane('mask').style.pointerEvents = 'none';
    map.getPane('labels').style.pointerEvents = 'none';
    renderers.mask = L.canvas({ pane: 'mask' });
    const shared = L.canvas({ tolerance: 5 });
    for (const name of ['streams', 'rivers', 'roads', 'boundary', 'catchment', 'rail', 'stations']) renderers[name] = shared;
  }

  // ---------------------------------------------------------------- basemap
  function setTiles() {
    const theme = isDark() ? 'dark' : 'light';
    if (theme === tileTheme) return;
    tileTheme = theme;
    if (baseTiles) map.removeLayer(baseTiles);
    if (refTiles) map.removeLayer(refTiles);
    const [base, ref] = TILES[theme];
    baseTiles = L.tileLayer(tileUrl(base), {
      maxZoom: 16,
      attribution: 'Tiles &copy; <a href="https://www.esri.com/">Esri</a>',
    }).addTo(map);
    // Place names sit above the overlays so towns stay readable.
    refTiles = L.tileLayer(tileUrl(ref), { maxZoom: 16, pane: 'labels' }).addTo(map);
  }

  // ---------------------------------------------------------------- helpers
  const toLatLngs = ring => ring.map(([x, y]) => [y, x]);

  function kmBetween(a, b) {
    const kx = 111.32 * Math.cos(((a[1] + b[1]) / 2) * Math.PI / 180);
    return Math.hypot((b[0] - a[0]) * kx, (b[1] - a[1]) * 110.57);
  }

  function partLength(coords) {
    let km = 0;
    for (let i = 1; i < coords.length; i++) km += kmBetween(coords[i - 1], coords[i]);
    return km;
  }

  function longestPart(geom) {
    const lines = geom.type === 'MultiLineString' ? geom.coordinates : [geom.coordinates];
    let best = null, bestKm = -1;
    for (const l of lines) {
      const km = partLength(l);
      if (km > bestKm) { best = l; bestKm = km; }
    }
    return best;
  }

  // The [lat, lng] a given fraction of the way along a line.
  function pointAlong(coords, frac) {
    const target = partLength(coords) * frac;
    let acc = 0;
    for (let i = 1; i < coords.length; i++) {
      const seg = kmBetween(coords[i - 1], coords[i]);
      if (acc + seg >= target) {
        const t = seg ? (target - acc) / seg : 0;
        const [x1, y1] = coords[i - 1], [x2, y2] = coords[i];
        return [y1 + (y2 - y1) * t, x1 + (x2 - x1) * t];
      }
      acc += seg;
    }
    const [x, y] = coords[coords.length - 1];
    return [y, x];
  }

  function label(latlng, text, cls, colour = null) {
    const style = colour ? ` style="--label-colour: var(${colour})"` : '';
    return L.marker(latlng, {
      interactive: false,
      keyboard: false,
      icon: L.divIcon({ className: '', iconSize: [0, 0], html: `<div class="map-label ${cls}"${style}>${esc(text)}</div>` }),
    });
  }

  function tip(name, sub) {
    return `${esc(name)}${sub ? `<span class="tip-sub">${esc(sub)}</span>` : ''}`;
  }
  const TIP_OPTS = { sticky: true, className: 'map-tip', direction: 'top', offset: [0, -8] };

  // Marker size multiplier, read by the stylesheet as --mk: markers grow as
  // the map zooms in, where there are fewer of them on screen at once.
  const markerScale = z => (z >= 14 ? 2 : z >= 13 ? 1.75 : z >= 12 ? 1.5 : z >= 11 ? 1.3 : z >= 10 ? 1.15 : 1);
  // Gauges are a little smaller zoomed out, where they crowd each other.
  const gaugeScale = z => (z <= 9 ? 0.75 : z === 10 ? 0.9 : 1);
  function sizeMarkers() {
    map.getContainer().style.setProperty('--mk', markerScale(map.getZoom()));
    map.getContainer().style.setProperty('--gs', gaugeScale(map.getZoom()));
  }

  // Zoom-dependent line weight multiplier.
  const zoomScale = () => {
    const z = map.getZoom();
    return z >= 13 ? 1.7 : z >= 12 ? 1.45 : z >= 11 ? 1.2 : z >= 10 ? 1.05 : 0.9;
  };

  // ---------------------------------------------------------------- catchment
  // The Taw catchment's outline, off at first: the map is about the gauges.
  function addCatchment(fc) {
    const rings = fc.features.flatMap(f => f.geometry.coordinates.map(poly => toLatLngs(poly[0])));
    const area = L.polygon(rings, { renderer: renderers.catchment, interactive: false, fill: false });
    const style = () => area.setStyle({ color: cssVar('--accent'), weight: 1.5, opacity: 0.7, dashArray: '6 4' });
    style();
    restylers.push(style);
    addPart(area, 'catchment', Z.catchment);
  }

  // ---------------------------------------------------------------- waterways
  function addRivers(fc) {
    const named = fc.features.filter(f => f.properties.name);
    const unnamed = fc.features.filter(f => !f.properties.name);

    const style = f => {
      const km = f.properties.length_km || 0;
      const own = RIVER_COLOURS[f.properties.name];
      const base = own ? (km >= MAJOR_RIVER_KM ? 3.2 : 2.6) : f.properties.name ? 1.4 : 1.0;
      return {
        color: cssVar(own || '--water-minor'), weight: base * zoomScale(),
        opacity: own ? 0.95 : 0.8, lineCap: 'round', lineJoin: 'round',
      };
    };

    const namedLayer = L.geoJSON({ type: 'FeatureCollection', features: named }, {
      renderer: renderers.rivers, style,
      onEachFeature: (f, layer) => {
        const sub = [f.properties.kind === 'canal' ? 'canal' : null, f.properties.length_km ? fmtKm(f.properties.length_km) : null]
          .filter(Boolean).join(' · ');
        layer.bindTooltip(tip(f.properties.name, sub), TIP_OPTS);
      },
    });
    const unnamedLayer = L.geoJSON({ type: 'FeatureCollection', features: unnamed }, {
      renderer: renderers.rivers, style, interactive: false,
    });

    // Labels for the coloured rivers only; the rest are named on hover.
    const major = L.layerGroup(), minor = L.layerGroup();
    for (const f of named) {
      const own = RIVER_COLOURS[f.properties.name];
      const line = longestPart(f.geometry);
      if (!own || !line || line.length < 2) continue;
      label(pointAlong(line, 0.5), f.properties.name, 'river', own).addTo(major);
    }

    // Flow arrows: OSM waterways are drawn source to mouth.
    const arrows = L.layerGroup();
    for (const f of named) {
      if (f.properties.kind !== 'river') continue;
      for (const coords of f.geometry.coordinates) {
        let acc = 0, next = ARROW_SPACING_KM / 2;
        for (let i = 1; i < coords.length; i++) {
          const a = coords[i - 1], b = coords[i];
          const seg = kmBetween(a, b);
          while (seg > 0 && acc + seg >= next) {
            const t = (next - acc) / seg;
            const lat = a[1] + (b[1] - a[1]) * t, lng = a[0] + (b[0] - a[0]) * t;
            const bearing = Math.atan2((b[0] - a[0]) * Math.cos(lat * Math.PI / 180), b[1] - a[1]) * 180 / Math.PI;
            L.marker([lat, lng], {
              interactive: false, keyboard: false,
              icon: L.divIcon({
                className: '', iconSize: [10, 10], iconAnchor: [5, 5],
                html: `<div class="flow-arrow" style="transform: rotate(${bearing.toFixed(0)}deg)">&#x25B2;</div>`,
              }),
            }).addTo(arrows);
            next += ARROW_SPACING_KM;
          }
          acc += seg;
        }
      }
    }

    restylers.push(() => { namedLayer.setStyle(style); unnamedLayer.setStyle(style); });
    addPart(unnamedLayer, 'rivers', Z.rivers);
    addPart(namedLayer, 'rivers', Z.rivers);
    addPart(major, 'rivers', Z.markers, MAJOR_LABEL_ZOOM);
    addPart(minor, 'rivers', Z.markers, MINOR_LABEL_ZOOM);
    addPart(arrows, 'rivers', Z.markers, ARROW_MIN_ZOOM);
    return named.length;
  }

  function addStreams(fc) {
    const style = () => ({
      color: cssVar('--water-minor'), weight: 0.9 * zoomScale(), opacity: 0.85, lineCap: 'round', lineJoin: 'round',
    });
    const named = L.geoJSON({ type: 'FeatureCollection', features: fc.features.filter(f => f.properties.name) }, {
      renderer: renderers.streams, style,
      onEachFeature: (f, layer) => layer.bindTooltip(tip(f.properties.name, 'stream'), TIP_OPTS),
    });
    const unnamed = L.geoJSON({ type: 'FeatureCollection', features: fc.features.filter(f => !f.properties.name) }, {
      renderer: renderers.streams, style, interactive: false,
    });
    restylers.push(() => { named.setStyle(style); unnamed.setStyle(style); });
    addPart(unnamed, 'streams', Z.streams, STREAM_MIN_ZOOM);
    addPart(named, 'streams', Z.streams, STREAM_MIN_ZOOM);
  }

  // ---------------------------------------------------------------- railways
  const RAIL_KIND = {
    passenger: { colour: '--rail',          sub: 'passenger line' },
    freight:   { colour: '--rail-freight',  sub: 'freight branch' },
  };

  function addRailways(fc) {
    for (const kind of Object.keys(RAIL_KIND)) {
      const feats = { type: 'FeatureCollection', features: fc.features.filter(f => f.properties.kind === kind) };
      const group = L.layerGroup();
      const labels = L.layerGroup();

      // A thin dashed line, as Floodwatch has always drawn the railways.
      const cased = false;
      const base = L.geoJSON(feats, {
        renderer: renderers.rail,
        onEachFeature: (f, layer) => layer.bindTooltip(tip(f.properties.line || RAIL_KIND[kind].sub, f.properties.line ? RAIL_KIND[kind].sub : ''), TIP_OPTS),
      }).addTo(group);
      const inner = cased ? L.geoJSON(feats, { renderer: renderers.rail, interactive: false }).addTo(group) : null;

      const style = () => {
        const s = zoomScale();
        if (cased) {
          base.setStyle({ color: cssVar(RAIL_KIND[kind].colour), weight: 3.4 * s, opacity: 0.95, lineCap: 'butt', lineJoin: 'round' });
          inner.setStyle({ color: cssVar('--bg-card'), weight: 1.5 * s, opacity: 1, dashArray: `${5 * s} ${5 * s}`, lineCap: 'butt' });
        } else {
          base.setStyle({ color: cssVar(RAIL_KIND[kind].colour), weight: 1.5 * s, opacity: 0.75, dashArray: '6 4', lineCap: 'butt' });
        }
      };
      style();
      restylers.push(style);

      for (const f of feats.features) {
        if (!f.properties.line) continue;
        const line = longestPart(f.geometry);
        if (line && line.length > 1) label(pointAlong(line, 0.5), f.properties.line, `rail ${kind}`).addTo(labels);
      }
      addPart(group, kind, Z.rail);
      addPart(labels, kind, Z.markers, kind === 'freight' ? MINOR_LABEL_ZOOM + 1 : RAIL_LABEL_ZOOM);
    }
  }

  function addStations(fc) {
    const layer = L.geoJSON(fc, {
      pointToLayer: (f, latlng) => L.circleMarker(latlng, { renderer: renderers.stations }),
      onEachFeature: (f, l) => {
        const p = f.properties;
        const sub = p.crs ? `station · ${p.crs}` : 'station';
        l.bindTooltip(tip(p.name, sub), { ...TIP_OPTS, sticky: false });
      },
    });
    const style = () => layer.eachLayer(m => {
      m.setStyle({
        radius: 3 * zoomScale(),
        color: cssVar('--rail'), weight: 1.4,
        fillColor: cssVar('--hollow-fill'), fillOpacity: 1, opacity: 1,
      });
    });
    style();
    restylers.push(style);
    addPart(layer, 'stations', Z.stations, 9);
    return fc.features.length;
  }

  // ---------------------------------------------------------------- roads
  const ROAD_LABEL_SPACING_KM = 18;

  function addRoads(fc) {
    const group = L.layerGroup();
    const opts = {
      renderer: renderers.roads,
      onEachFeature: (f, layer) => layer.bindTooltip(tip(f.properties.ref, 'major road'), TIP_OPTS),
    };
    // A darker edge under a lighter fill, so the road reads against the
    // basemap without competing with the railways drawn above it.
    const edge = L.geoJSON(fc, opts).addTo(group);
    const fill = L.geoJSON(fc, { renderer: renderers.roads, interactive: false }).addTo(group);
    const style = () => {
      const s = zoomScale();
      edge.setStyle({ color: cssVar('--road-edge'), weight: 3.2 * s, opacity: 0.7, lineCap: 'round', lineJoin: 'round' });
      fill.setStyle({ color: cssVar('--road'), weight: 1.8 * s, opacity: 1, lineCap: 'round', lineJoin: 'round' });
    };
    style();
    restylers.push(style);

    // Number badges at the midpoints of the longer stretches, spaced out so
    // each road is labelled every ROAD_LABEL_SPACING_KM or so.
    const labels = L.layerGroup();
    for (const f of fc.features) {
      const placed = [];
      const stretches = f.geometry.coordinates
        .map(c => ({ c, km: partLength(c) }))
        .filter(p => p.km >= 2)
        .sort((a, b) => b.km - a.km);
      for (const { c } of stretches) {
        const at = pointAlong(c, 0.5);
        const pt = [at[1], at[0]];
        if (placed.some(q => kmBetween(q, pt) < ROAD_LABEL_SPACING_KM)) continue;
        placed.push(pt);
        label(at, f.properties.ref, 'road').addTo(labels);
      }
    }
    addPart(group, 'roads', Z.roads);
    addPart(labels, 'roads', Z.markers, 9);
  }

  // ---------------------------------------------------------------- live stations
  // DOM markers, so their shapes and colours come straight from the
  // stylesheet: circles for river levels, diamonds for tidal gauges, and
  // drops for rain gauges.
  const LIVE_REFRESH_MS = 5 * 60 * 1000;
  // ---------------------------------------------------------------- clusters
  // Markers that would overlap are gathered into one, showing how many it
  // holds and the most urgent state among them, until zoom CLUSTER_OFF_ZOOM.
  // Gauges and storm overflows cluster separately, so an overflow never hides
  // a gauge, and overflows sit in a pane beneath the gauges.
  const CLUSTER_OFF_ZOOM = 13;
  let gaugeCluster = null, csoCluster = null;

  // A legend layer whose markers live in a shared cluster group: switching
  // the layer on adds its markers to the group, and off takes them out.
  const ClusterPart = L.Layer.extend({
    initialize(getCluster) { this._getCluster = getCluster; this._markers = []; this._shown = false; },
    onAdd() { this._shown = true; this._getCluster().addLayers(this._markers); },
    onRemove() { this._shown = false; this._getCluster().removeLayers(this._markers); },
    addLayer(m) { this._markers.push(m); if (this._shown) this._getCluster().addLayer(m); return this; },
    clearLayers() { if (this._shown) this._getCluster().removeLayers(this._markers); this._markers = []; return this; },
  });

  const LEVEL_RANK = { high: 3, approach: 2 };
  function gaugeClusterIcon(cluster) {
    const stations = cluster.getAllChildMarkers().map(m => m.station).filter(Boolean);
    const worst = stations.reduce((w, s) => {
      const st = gaugeState(s);
      return (LEVEL_RANK[st] || 0) > (LEVEL_RANK[w] || 0) ? st : w;
    }, 'normal');
    const rising = stations.some(s => s.kind !== 'rain' && s.trend === 'rising' && s.state !== 'stale');
    const raining = stations.some(s => s.kind === 'rain' && s.h1 > 0);
    const size = parseFloat(cssVar('--gauge-size')) || 36;
    return L.divIcon({
      className: '', iconSize: [size, size], iconAnchor: [size / 2, size / 2],
      html: `<span class="gcluster is-${worst}${raining ? ' is-raining' : ''}"><span class="gcluster-n">${stations.length}</span></span>` +
        (rising ? '<span class="gauge-trend is-rising">↑</span>' : ''),
    });
  }

  function csoClusterIcon(cluster) {
    const overflows = cluster.getAllChildMarkers().map(m => m.overflow).filter(Boolean);
    const spilling = overflows.filter(o => o.state === 'spilling').length;
    return L.divIcon({
      className: '', iconSize: [32, 32], iconAnchor: [16, 16],
      html: `<span class="ccluster${spilling ? ' is-spilling' : ''}">${overflows.length}</span>`,
    });
  }

  // The cluster's tooltip lists what's in it, most urgent first.
  function clusterTip(e, describe) {
    const items = e.layer.getAllChildMarkers().map(describe).filter(Boolean);
    const shown = items.slice(0, 8).map(esc).join('<br>');
    const more = items.length > 8 ? `<br><span class="tip-sub">and ${items.length - 8} more</span>` : '';
    e.layer.bindTooltip(shown + more, { ...TIP_OPTS, sticky: false, offset: [0, -20] }).openTooltip();
  }

  function makeClusters() {
    const common = {
      showCoverageOnHover: false, zoomToBoundsOnClick: true, spiderfyOnMaxZoom: false,
      disableClusteringAtZoom: CLUSTER_OFF_ZOOM, removeOutsideVisibleBounds: true,
    };
    gaugeCluster = L.markerClusterGroup({ ...common, maxClusterRadius: 34, iconCreateFunction: gaugeClusterIcon }).addTo(map);
    csoCluster = L.markerClusterGroup({ ...common, maxClusterRadius: 28, clusterPane: 'overflows',
      iconCreateFunction: csoClusterIcon }).addTo(map);
    gaugeCluster.on('clustermouseover', e => clusterTip(e, m => m.station &&
      `${m.station.name}: ${gaugeText(m.station)}${m.station.kind === 'rain' ? ' mm' : ' m'}`));
    csoCluster.on('clustermouseover', e => clusterTip(e, m => m.overflow &&
      `${StationPopup.overflowName(m.overflow)}${m.overflow.state === 'spilling' ? ' (spilling)' : ''}`));
  }

  const liveGroups = { level: new ClusterPart(() => gaugeCluster), tidal: new ClusterPart(() => gaugeCluster),
    rain: new ClusterPart(() => gaugeCluster) };
  let liveRegistered = false;

  // A river level within 30% of the top of its typical range is getting
  // close, and its marker turns amber before it turns red.
  const APPROACH = 0.7;
  function gaugeState(s) {
    if (s.kind === 'rain') return s.state === 'stale' ? 'stale' : s.h1 > 0 ? 'raining' : 'dry';
    if (s.kind === 'level' && s.state !== 'high' && s.state !== 'stale' && s.typical && s.typical[1] != null
        && s.value >= APPROACH * s.typical[1]) return 'approach';
    return s.state;
  }

  function gaugeText(s) {
    if (s.kind === 'rain') return s.h1 == null ? '–' : s.h1.toFixed(1);
    return s.value == null ? '–' : s.value.toFixed(2);
  }

  function gaugeIcon(s) {
    const size = parseFloat(cssVar('--gauge-size')) || 36;
    const trend = s.trend && s.kind !== 'rain' && s.state !== 'stale'
      ? `<span class="gauge-trend is-${esc(s.trend)}">${{ rising: '↑', falling: '↓', steady: '→' }[s.trend] || ''}</span>` : '';
    return L.divIcon({
      className: '', iconSize: [size, size], iconAnchor: [size / 2, size / 2],
      html: `<span class="gauge gauge-${s.kind} is-${esc(gaugeState(s))}"><span class="gauge-value">${esc(gaugeText(s))}</span></span>${trend}`,
    });
  }

  function renderLive(live) {
    if (!liveRegistered) {
      addPart(liveGroups.level, 'levels', Z.markers);
      addPart(liveGroups.tidal, 'tidal', Z.markers);
      addPart(liveGroups.rain, 'rain', Z.markers);
      liveRegistered = true;
    }
    Object.values(liveGroups).forEach(g => g.clearLayers());
    const counts = { level: 0, tidal: 0, rain: 0 };
    for (const s of live.stations) {
      if (!liveGroups[s.kind]) continue;
      counts[s.kind]++;
      const marker = L.marker([s.lat, s.lon], { icon: gaugeIcon(s), title: s.name, riseOnHover: true, zIndexOffset: 500 });
      marker.station = s;
      marker
        .bindTooltip(tip(s.name, StationPopup.summary(s)), { ...TIP_OPTS, sticky: false, offset: [0, -20] })
        .on('click', () => StationPopup.open(map, s))
        .addTo(liveGroups[s.kind]);
    }
    setCount('levels', counts.level);
    setCount('tidal', counts.tidal);
    setCount('rain', counts.rain);
    StationPopup.invalidate();
    if (window.onLiveUpdate) window.onLiveUpdate(live);
  }

  // Storm overflows: spilling now or recently shows at every zoom; quiet and
  // offline overflows only once zoomed in, since there are hundreds of them.
  const csoGroups = { now: new ClusterPart(() => csoCluster), recent: new ClusterPart(() => csoCluster),
    quiet: new ClusterPart(() => csoCluster) };
  let csoRegistered = false;
  const CSO_GROUP = { spilling: 'now', recent: 'recent', quiet: 'quiet', offline: 'quiet' };

  function renderOverflows(data) {
    if (!csoRegistered) {
      addPart(csoGroups.quiet, 'csoQuiet', Z.markers, CSO_QUIET_ZOOM);
      addPart(csoGroups.recent, 'csoRecent', Z.markers);
      addPart(csoGroups.now, 'csoNow', Z.markers);
      csoRegistered = true;
    }
    Object.values(csoGroups).forEach(g => g.clearLayers());
    const counts = { now: 0, recent: 0, quiet: 0 };
    for (const o of data.overflows) {
      const group = CSO_GROUP[o.state];
      if (!group) continue;
      counts[group]++;
      // A 32 px tap target round the visible dot.
      const icon = L.divIcon({
        className: '', iconSize: [32, 32], iconAnchor: [16, 16],
        html: `<span class="cso is-${esc(o.state)}${o.works ? ' is-works' : ''}"></span>`,
      });
      const marker = L.marker([o.lat, o.lon], { icon, title: StationPopup.overflowName(o), riseOnHover: true, pane: 'overflows',
        zIndexOffset: group === 'now' ? 300 : group === 'recent' ? 200 : 100 });
      marker.overflow = o;
      marker
        .bindTooltip(tip(StationPopup.overflowName(o), StationPopup.overflowSummary(o)),
          { ...TIP_OPTS, sticky: false, offset: [0, -8] })
        .on('click', () => StationPopup.openOverflow(map, o))
        .addTo(csoGroups[group]);
    }
    setCount('csoNow', counts.now);
    setCount('csoRecent', counts.recent);
    setCount('csoQuiet', counts.quiet);
  }

  function loadOverflows() {
    return getJSON(DATA + 'overflows.json')
      .then(d => { renderOverflows(d); updateVisibility(); })
      .catch(e => console.warn('No storm overflow data:', e));
  }

  // ---------------------------------------------------------------- power cuts
  // NGED's live power cuts in the catchment: a dark disc with a bolt, larger for
  // more customers off.
  const powerGroup = L.layerGroup();
  let powerRegistered = false;
  const BOLT = '<svg viewBox="0 0 12 12" aria-hidden="true"><path d="M7.2 0.6 2.4 7h3.1l-0.9 4.4L9.6 5H6.4z"/></svg>';

  function renderPowerCuts(data) {
    if (!powerRegistered) { addPart(powerGroup, 'powercuts', Z.markers); powerRegistered = true; }
    powerGroup.clearLayers();
    const cuts = data.power_cuts || [];
    for (const c of cuts) {
      const size = Math.round(16 + Math.min(10, Math.sqrt(c.off)));
      const icon = L.divIcon({
        className: '', iconSize: [size, size], iconAnchor: [size / 2, size / 2],
        html: `<span class="pcut" style="--size: ${size}px">${BOLT}</span>`,
      });
      L.marker([c.lat, c.lon], { icon, title: PowerCuts.title(c), riseOnHover: true, zIndexOffset: 400 })
        .bindTooltip(tip(PowerCuts.title(c), PowerCuts.summary(c)), { ...TIP_OPTS, sticky: false, offset: [0, -10] })
        .on('click', () => PowerCuts.open(map, c, data.updated))
        .addTo(powerGroup);
    }
    setCount('powercuts', cuts.length);
  }

  function loadPowerCuts() {
    return getJSON(DATA + 'powercuts.json')
      .then(d => { renderPowerCuts(d); updateVisibility(); })
      .catch(e => console.warn('No power cut data:', e));
  }

  function loadLive() {
    return getJSON(DATA + 'live.json')
      .then(live => { renderLive(live); updateVisibility(); })
      .catch(e => console.warn('No live readings:', e));
  }

  // ---------------------------------------------------------------- flood warnings
  // Areas with an Environment Agency flood warning or alert in force, tinted
  // by severity. Warning areas are mostly narrow strips of floodplain, so they
  // draw above the rivers, which show through the fill. FloodWarnings (floods.js) loads
  // the data, which may arrive before or after the map starts.
  const FLOOD_CLASS = { 1: 'severe', 2: 'warning', 3: 'alert' };
  let floodWarnings = [];
  let floodLayer = null;
  const floodBounds = {};

  function floodStyle(w) {
    const colour = cssVar(`--flood-${FLOOD_CLASS[w.severity]}`);
    // An alert covers a wide area and says only that flooding is possible, so
    // its area is a faint tint; a warning's is outlined.
    return w.severity === 3
      ? { color: colour, fillColor: colour, weight: 0.8, opacity: 0.45, fillOpacity: 0.12, lineJoin: 'round' }
      : { color: colour, fillColor: colour, weight: 2 * zoomScale(), opacity: 0.95, fillOpacity: 0.3, lineJoin: 'round' };
  }

  function drawFloods() {
    if (!floodLayer) {
      floodLayer = L.layerGroup();
      addPart(floodLayer, 'floods', Z.floods);
      // Each warning is a GeoJSON group; its polygons carry the warning.
      restylers.push(() => floodLayer.eachLayer(group => group.eachLayer(l => l.setStyle(floodStyle(l.warning)))));
    }
    floodLayer.clearLayers();
    // Least severe first, so the most severe draws on top.
    for (const w of [...floodWarnings].sort((a, b) => b.severity - a.severity)) {
      if (!w.geometry) continue;
      const area = L.geoJSON({ type: 'Feature', geometry: w.geometry, properties: {} },
        { renderer: renderers.rivers, style: floodStyle(w) });
      area.eachLayer(l => { l.warning = w; });
      area.bindTooltip(tip(w.area || w.id, w.label), TIP_OPTS);
      area.on('click', e => L.popup({ className: 'stn-popup', maxWidth: 380, minWidth: 300, autoPanPadding: [24, 24] })
        .setLatLng(e.latlng).setContent(FloodWarnings.detail(w, false)).openOn(map));
      area.addTo(floodLayer);
      floodBounds[w.id] = area.getBounds();
    }
    setCount('floods', floodWarnings.length);
    updateVisibility();
  }

  function setFloodWarnings(list) {
    floodWarnings = list || [];
    if (map && legendReady) drawFloods();
  }

  function focusFlood(id) {
    if (!map || !floodBounds[id]) return;
    if (!toggles.floods.on) {
      toggles.floods.on = true;
      syncLegend($('.map-legend'));
      updateVisibility();
    }
    map.fitBounds(floodBounds[id], { padding: [40, 40], maxZoom: 13 });
  }

  // ---------------------------------------------------------------- legend
  function setCount(key, n) {
    const span = document.getElementById(`legend-count-${key}`);
    if (span) span.textContent = fmtInt(n);
  }

  function addLegend() {
    // Bottom left, over the land west of the catchment; collapsed at first
    // on phones.
    const ctl = L.control({ position: 'bottomleft' });
    ctl.onAdd = () => {
      const div = L.DomUtil.create('div', 'map-legend');
      const item = (key, swatch, colour, text, extra = '') =>
        `<button type="button" class="legend-item" data-key="${key}" aria-pressed="true">
           <span class="swatch ${swatch}" style="--c: var(${colour})"></span><span class="legend-label">${esc(text)}</span>${extra}
         </button>`;
      const title = (group, text) =>
        `<button type="button" class="legend-title legend-group" data-group="${group}"
           title="Show or hide all ${esc(text.toLowerCase())}">${esc(text)}</button>`;
      // Say how the legend works: rows and headings are switches.
      const verb = window.matchMedia('(hover: none)').matches ? 'Tap' : 'Click';
      const hint = `${verb} a layer to show or hide it, or a heading for its whole section.`;
      // Collapsed by default on phones, where the full legend hides the map.
      const collapsed = PHONE.matches;
      div.classList.toggle('collapsed', collapsed);
      div.innerHTML = `
        <button type="button" class="legend-head" aria-expanded="${!collapsed}" aria-controls="legend-body">
          Layers<span class="legend-chevron" aria-hidden="true"></span>
        </button>
        <div class="legend-body" id="legend-body">
        <p class="legend-hint">${hint}</p>
        <div class="legend-col">
        ${title('floods', 'Flood warnings')}
        ${item('floods', 'area flood-swatch', '--flood-warning', 'Warning and alert areas', '<span class="count" id="legend-count-floods"></span>')}
        ${title('power', 'Power cuts')}
        ${item('powercuts', 'pcut-swatch', '--power-bg', 'Live power cuts', '<span class="count" id="legend-count-powercuts"></span>')}
        ${title('live', 'Live readings')}
        ${item('levels', 'gauge-swatch level', '--gauge-normal', 'River level (m)', '<span class="count" id="legend-count-levels"></span>')}
        <div class="legend-key gauge-key">
          <span class="key-pair"><span class="swatch gauge-swatch level" style="--c: var(--gauge-approach)"></span>near top of range</span>
          <span class="key-pair"><span class="swatch gauge-swatch level" style="--c: var(--gauge-high)"></span>above range</span>
        </div>
        ${item('tidal', 'gauge-swatch tidal', '--gauge-tidal', 'Tidal level (m AOD)', '<span class="count" id="legend-count-tidal"></span>')}
        ${item('rain', 'gauge-swatch rain', '--gauge-rain', 'Rain in the last hour (mm)', '<span class="count" id="legend-count-rain"></span>')}
        <div class="legend-key"><span class="key-pair"><span class="cluster-key">3</span>gauges grouped together: zoom in</span></div>
        <div class="legend-key" aria-label="Trend badges on river and tidal gauges">
          <span class="key-pair"><span class="trend-key is-rising"></span>rising</span>
          <span class="key-pair"><span class="trend-key is-falling"></span>falling</span>
          <span class="key-pair"><span class="trend-key is-steady"></span>steady</span>
        </div>
        ${title('overflows', 'Storm overflows')}
        ${item('csoNow', 'cso-swatch is-spilling', '--cso', 'Spilling now', '<span class="count" id="legend-count-csoNow"></span>')}
        ${item('csoRecent', 'cso-swatch is-recent', '--cso-recent', 'Spilled in last 48 h', '<span class="count" id="legend-count-csoRecent"></span>')}
        ${item('csoQuiet', 'cso-swatch is-quiet', '--cso-quiet', 'Quiet or offline', '<span class="count"><span id="legend-cso-quiet-hint">zoom in · </span><span id="legend-count-csoQuiet"></span></span>')}
        <div class="legend-key">
          <span class="key-pair"><span class="works-key"></span>treatment works</span>
          <span class="key-pair"><span class="works-key is-network"></span>sewer network</span>
        </div>
        </div>
        <div class="legend-col">
        ${title('waterways', 'Waterways')}
        ${item('rivers', 'line', '--water', 'Rivers')}
        ${Object.entries(RIVER_COLOURS).map(([name, colour]) =>
          `<div class="legend-key river-key"><span class="river-swatch" style="--c: var(${colour})"></span>${esc(name)}</div>`).join('')}
        ${item('streams', 'line thin', '--water-minor', 'Streams', '<span class="count" id="legend-streams-hint"></span>')}
        ${title('railways', 'Railways')}
        ${item('passenger', 'line', '--rail', 'Passenger lines')}
        ${item('stations', 'dot', '--rail', 'Stations', '<span class="count" id="legend-count-stations"></span>')}
        ${title('roads', 'Roads')}
        ${item('roads', 'road', '--road', 'Major roads')}
        <div class="legend-title">Boundary</div>
        ${item('catchment', 'dash', '--accent', 'Taw catchment')}
        </div>
        </div>`;
      syncLegend(div);
      L.DomEvent.disableClickPropagation(div);
      L.DomEvent.disableScrollPropagation(div);
      div.addEventListener('click', e => {
        const head = e.target.closest('.legend-head');
        if (head) {
          const isCollapsed = div.classList.toggle('collapsed');
          head.setAttribute('aria-expanded', String(!isCollapsed));
          return;
        }
        // A group heading turns the whole group off if any of it is showing,
        // otherwise back on.
        const groupBtn = e.target.closest('.legend-group');
        if (groupBtn) {
          const keys = GROUPS[groupBtn.dataset.group];
          const on = !keys.some(k => toggles[k].on);
          keys.forEach(k => { toggles[k].on = on; });
        } else {
          const btn = e.target.closest('.legend-item');
          if (!btn) return;
          const t = toggles[btn.dataset.key];
          t.on = !t.on;
        }
        syncLegend(div);
        updateVisibility();
      });
      return div;
    };
    ctl.addTo(map);
  }

  function syncLegend(div) {
    div.querySelectorAll('.legend-item').forEach(btn => {
      const on = toggles[btn.dataset.key].on;
      btn.classList.toggle('off', !on);
      btn.setAttribute('aria-pressed', String(on));
    });
    div.querySelectorAll('.legend-group').forEach(btn => {
      btn.classList.toggle('off', !GROUPS[btn.dataset.group].some(k => toggles[k].on));
    });
  }

  // ---------------------------------------------------------------- public
  function init(id) {
    map = L.map(id, {
      // Whole zoom levels only: fractional zoom leaves seams between tiles.
      zoomSnap: 1, zoomDelta: 1, minZoom: 8, maxZoom: 16,
      // No tile fade: old tiles are only cleared once a fade completes, and
      // the label tiles are transparent, so a stalled fade shows doubled names.
      fadeAnimation: false,
      maxBounds: MAX_BOUNDS, maxBoundsViscosity: 0.8,
    });
    map.attributionControl.setPrefix('<a href="https://leafletjs.com">Leaflet</a>');
    map.attributionControl.addAttribution('&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors');
    map.attributionControl.addAttribution('Weather warnings: <a href="https://weather.metoffice.gov.uk/warnings-and-advice/uk-warnings">Met Office</a>');
    map.attributionControl.addAttribution('Readings: <a href="https://environment.data.gov.uk/flood-monitoring/doc/reference">Environment Agency</a>');
    map.attributionControl.addAttribution('Overflows: <a href="https://www.arcgis.com/home/item.html?id=cabfce76b72a4a278a33d737c0708d42">South West Water</a>');
    map.attributionControl.addAttribution('Forecasts: <a href="https://open-meteo.com/">Open-Meteo</a>, <a href="https://nrfa.ceh.ac.uk/">NRFA</a>');
    map.attributionControl.addAttribution('Power cuts: Supported by <a href="https://connecteddata.nationalgrid.co.uk/dataset/live-power-cuts">NGED Open Data</a>');
    map.attributionControl.addAttribution('Catchment: <a href="https://environment.data.gov.uk/catchment-planning/">Environment Agency</a>');
    map.setView([50.93, -3.90], 10, { animate: false });  // placeholder until the container has a size
    makePanes();
    makeClusters();
    setTiles();

    addLegend();
    fitLegend();     // keeps the legend inside the map
    fitIfVisible();
    legendReady = true;
    map.on('resize', fitLegend);
    if (document.fonts) document.fonts.ready.then(fitLegend);  // the credits rewrap once fonts load
    drawFloods();
    map.on('zoomend', () => { loadStreamsIfNeeded(); sizeMarkers(); updateVisibility(); restylers.forEach(fn => fn()); });
    sizeMarkers();

    // Each layer draws as soon as its file arrives; nothing waits for the
    // rest. Live readings are a single small file, so markers appear first.
    loadLive();
    loadOverflows();
    loadPowerCuts();
    setInterval(() => { loadLive(); loadOverflows(); loadPowerCuts(); }, LIVE_REFRESH_MS);
    const layer = (name, add) => getJSON(DATA + name)
      .then(fc => { add(fc); updateVisibility(); })
      .catch(e => console.warn(e));
    layer('catchment.geojson', addCatchment);
    layer('rivers.geojson', addRivers);
    layer('roads.geojson', addRoads);
    layer('railways.geojson', addRailways);
    layer('stations.geojson', fc => setCount('stations', addStations(fc)));
    loadStreamsIfNeeded();
  }

  // Streams are the largest overlay and only show from STREAM_MIN_ZOOM, so
  // they load the first time the map reaches that zoom.
  let streamsRequested = false;
  function loadStreamsIfNeeded() {
    if (streamsRequested || map.getZoom() < STREAM_MIN_ZOOM) return;
    streamsRequested = true;
    getJSON(DATA + 'streams.geojson')
      .then(fc => { addStreams(fc); updateVisibility(); })
      .catch(e => { streamsRequested = false; console.warn(e); });
  }

  function restyle() {
    if (!map) return;
    setTiles();
    restylers.forEach(fn => fn());
  }

  // Set the opening view the first time the map is visible: Leaflet sizes
  // itself from the container, which has no size while the view is hidden.
  // The whole catchment is fitted into the part of the map the legend leaves
  // clear, so none of it starts out hidden behind the legend.
  let fitted = false;
  function fitIfVisible() {
    if (fitted || !map || map.getSize().x === 0) return;
    const box = map.getContainer().getBoundingClientRect();
    const legend = map.getContainer().querySelector('.map-legend');
    const r = legend ? legend.getBoundingClientRect() : null;
    // Beside the legend if there's room for the catchment there, else above it.
    const beside = r && box.width - (r.right - box.left) > box.width * 0.45;
    const padTL = [beside ? r.right - box.left + 12 : 16, 16];
    const padBR = [16, !beside && r ? box.bottom - r.top + 12 : 16];
    map.fitBounds(CATCHMENT_BOUNDS, { paddingTopLeft: padTL, paddingBottomRight: padBR, animate: false });
    // On a phone the whole catchment only fits at zoom 9, where the gauges
    // crowd together; zoom 10 on the Taw reads better, with the edges just off.
    if (map.getZoom() < 10) map.setView(L.latLngBounds(CATCHMENT_BOUNDS).getCenter(), 10, { animate: false });
    fitted = true;
  }

  function resize() {
    if (!map) return;
    setTimeout(() => { map.invalidateSize(); fitIfVisible(); fitLegend(); }, 0);
  }

  // Keep the legend clear of the zoom buttons: no taller than the map, less
  // the zoom control and the margins around both.
  // Keep the legend inside the map: no taller than the map, less the margins
  // and, on the left, the zoom buttons above it.
  // On phones the legend sits at the bottom left, and the credits wrap across
  // the map's width beneath it, to as many lines as they need; the legend
  // sits just above them, however many that is.
  function fitLegend() {
    const legend = map && map.getContainer().querySelector('.map-legend');
    if (!legend) return;
    let clearance = 30;
    if (legend.closest('.leaflet-left')) {
      const box = map.getContainer().getBoundingClientRect();
      const credits = map.getContainer().querySelector('.leaflet-control-attribution');
      const zoom = map.getContainer().querySelector('.leaflet-control-zoom');
      const above = Math.ceil(credits ? credits.getBoundingClientRect().height : 0) + 8;
      const below = Math.ceil(zoom ? zoom.getBoundingClientRect().bottom - box.top : 0) + 8;
      legend.style.marginBottom = `${above}px`;
      clearance = above + below;
    }
    legend.style.setProperty('--legend-max', `${Math.max(120, map.getSize().y - clearance)}px`);
  }

  // `map` is exposed read-only for debugging from the console.
  return { init, restyle, resize, setFloodWarnings, focusFlood, get map() { return map; } };
})();
