'use strict';

// The Taw catchment map: basemap, catchment mask, waterways, railways, legend.
// Colours come from CSS variables so the map follows light/dark mode.

const FloodMap = (() => {
  const DATA = 'data/';

  // Points around the edge of the catchment, from scripts/fetch_geodata.py's
  // outline: the opening view keeps all of them on screen and clear of the
  // legend.
  const OUTLINE = [
    [50.65, -3.97], [50.72, -3.96], [50.78, -3.93], [50.83, -3.94], [50.85, -3.97], [50.86, -3.94], [50.86, -4.00],
    [50.89, -4.01], [50.90, -3.99], [50.91, -4.02], [50.94, -3.99], [50.98, -4.09], [51.00, -4.09], [51.01, -4.12],
    [51.03, -4.11], [51.04, -4.17], [51.07, -4.17], [51.07, -4.11], [51.09, -4.12], [51.08, -4.06], [51.09, -4.05],
    [51.08, -4.16], [51.10, -4.16], [51.08, -4.21], [51.12, -4.21], [51.13, -4.18], [51.16, -4.19], [51.18, -3.99],
    [51.17, -3.85], [51.15, -3.83], [51.12, -3.81], [51.11, -3.77], [51.07, -3.69], [51.04, -3.60], [51.00, -3.61],
    [50.99, -3.64], [50.94, -3.59], [50.90, -3.62], [50.87, -3.74], [50.84, -3.71], [50.81, -3.79], [50.76, -3.84],
    [50.74, -3.84], [50.71, -3.93],
  ];
  // Loose enough that the opening view can sit the catchment beside the legend.
  const MAX_BOUNDS = [[50.2, -4.9], [51.6, -2.9]];

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
    boundary:  { on: true },
    rivers:    { on: true },
    streams:   { on: true },
    passenger: { on: true },
    freight:   { on: true },
    stations:  { on: true },
    roads:     { on: true },
    levels:    { on: true },
    tidal:     { on: true },
    rain:      { on: true },
    // Spilling now and spilled recently show at every zoom; quiet and
    // offline overflows once zoomed in (CSO_QUIET_ZOOM).
    csoNow:    { on: true },
    csoRecent: { on: true },
    csoQuiet:  { on: true },
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
  const Z = { mask: 0, streams: 1, rivers: 2, floods: 2.5, roads: 3, boundary: 4, rail: 5, stations: 6, markers: 9 };

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
    map.getPane('mask').style.pointerEvents = 'none';
    map.getPane('labels').style.pointerEvents = 'none';
    renderers.mask = L.canvas({ pane: 'mask' });
    const shared = L.canvas({ tolerance: 5 });
    for (const name of ['streams', 'rivers', 'roads', 'boundary', 'rail', 'stations']) renderers[name] = shared;
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
  function sizeMarkers() {
    map.getContainer().style.setProperty('--mk', markerScale(map.getZoom()));
  }

  // Zoom-dependent line weight multiplier.
  const zoomScale = () => {
    const z = map.getZoom();
    return z >= 13 ? 1.7 : z >= 12 ? 1.45 : z >= 11 ? 1.2 : z >= 10 ? 1.05 : 0.9;
  };

  // ---------------------------------------------------------------- boundary
  function addBoundary(fc) {
    const rings = fc.features.flatMap(f => f.geometry.coordinates.map(poly => toLatLngs(poly[0])));
    const world = [[-89, -179], [-89, 179], [89, 179], [89, -179]];

    // Dim everything outside the catchment so it reads as the subject.
    const mask = L.polygon([world, ...rings], {
      renderer: renderers.mask, interactive: false, stroke: false, fillRule: 'evenodd',
    });
    const outline = L.polygon(rings, { renderer: renderers.boundary, interactive: false, fill: false });

    const style = () => {
      mask.setStyle({ fillColor: cssVar('--mask'), fillOpacity: parseFloat(cssVar('--mask-opacity')) || 0.5 });
      outline.setStyle({ color: cssVar('--accent'), weight: 1.4, opacity: 0.75 });
    };
    style();
    restylers.push(style);
    addPart(mask, 'boundary', Z.mask);
    addPart(outline, 'boundary', Z.boundary);
  }

  // ---------------------------------------------------------------- waterways
  function addRivers(fc) {
    const named = fc.features.filter(f => f.properties.name);
    const unnamed = fc.features.filter(f => !f.properties.name);

    const style = f => {
      const km = f.properties.length_km || 0;
      const own = RIVER_COLOURS[f.properties.name];
      const base = !f.properties.name ? 1.0 : own ? (km >= MAJOR_RIVER_KM ? 3.2 : 2.6) : km >= MAJOR_RIVER_KM ? 2.0 : 1.4;
      return {
        color: cssVar(own || '--water'), weight: base * zoomScale(),
        opacity: f.properties.name ? 0.95 : 0.65, lineCap: 'round', lineJoin: 'round',
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

    // Labels: long rivers always, short ones once zoomed in.
    const major = L.layerGroup(), minor = L.layerGroup();
    for (const f of named) {
      const line = longestPart(f.geometry);
      if (!line || line.length < 2) continue;
      const own = RIVER_COLOURS[f.properties.name];
      const isMajor = Boolean(own) || f.properties.length_km >= MAJOR_RIVER_KM;
      const mark = label(pointAlong(line, 0.5), f.properties.name, `river${isMajor ? ' major' : ''}`, own);
      mark.addTo(isMajor ? major : minor);
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

      // Passenger lines get the classic map casing: a solid line with a dashed
      // inner stripe. Freight branches are a plain thin dash.
      const cased = kind !== 'freight';
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
          base.setStyle({ color: cssVar(RAIL_KIND[kind].colour), weight: 1.6 * s, opacity: 0.9, dashArray: '4 4', lineCap: 'butt' });
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
        radius: 3.6 * zoomScale(),
        color: cssVar('--rail'), weight: 1.6,
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
      edge.setStyle({ color: cssVar('--road-edge'), weight: 4 * s, opacity: 0.9, lineCap: 'round', lineJoin: 'round' });
      fill.setStyle({ color: cssVar('--road'), weight: 2.2 * s, opacity: 1, lineCap: 'round', lineJoin: 'round' });
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
  const liveGroups = { level: L.layerGroup(), tidal: L.layerGroup(), rain: L.layerGroup() };
  let liveRegistered = false;

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
      const icon = L.divIcon({
        className: '', iconSize: [14, 14], iconAnchor: [7, 7],
        // River and tidal gauges carry a small badge for their trend.
        html: `<span class="stn stn-${s.kind} is-${esc(s.state)}"></span>` +
          (s.trend && s.state !== 'stale' ? `<span class="trend for-${s.kind} is-${esc(s.trend)}"></span>` : ''),
      });
      L.marker([s.lat, s.lon], { icon, title: s.name, riseOnHover: true })
        .bindTooltip(tip(s.name, StationPopup.summary(s)), { ...TIP_OPTS, sticky: false, offset: [0, -10] })
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
  const csoGroups = { now: L.layerGroup(), recent: L.layerGroup(), quiet: L.layerGroup() };
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
      const icon = L.divIcon({
        className: '', iconSize: [12, 12], iconAnchor: [6, 6],
        html: `<span class="cso is-${esc(o.state)}${o.works ? ' is-works' : ''}"></span>`,
      });
      L.marker([o.lat, o.lon], { icon, title: o.name || o.id, riseOnHover: true,
        zIndexOffset: group === 'now' ? 400 : group === 'recent' ? 200 : 0 })
        .bindTooltip(tip(o.name || `Storm overflow ${o.id}`, StationPopup.overflowSummary(o)),
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
    return { color: colour, fillColor: colour, weight: 2 * zoomScale(), opacity: 0.95,
      fillOpacity: w.severity === 3 ? 0.2 : 0.35, lineJoin: 'round' };
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
    // Bottom right on wider screens; bottom left on phones, where it starts
    // collapsed.
    const ctl = L.control({ position: PHONE.matches ? 'bottomleft' : 'bottomright' });
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
        ${item('levels', 'gauge level', '--level-normal', 'River levels', '<span class="count" id="legend-count-levels"></span>')}
        ${item('tidal', 'gauge tidal', '--tidal', 'Tidal levels', '<span class="count" id="legend-count-tidal"></span>')}
        ${item('rain', 'gauge rain', '--rain', 'Rain gauges', '<span class="count" id="legend-count-rain"></span>')}
        <div class="legend-key" aria-label="Trend badges on river and tidal gauges">
          <span class="trend-key is-rising"></span>rising
          <span class="trend-key is-falling"></span>falling
          <span class="trend-key is-steady"></span>steady
        </div>
        ${title('overflows', 'Storm overflows')}
        ${item('csoNow', 'cso-swatch is-spilling', '--cso', 'Spilling now', '<span class="count" id="legend-count-csoNow"></span>')}
        ${item('csoRecent', 'cso-swatch is-recent', '--cso-recent', 'Spilled in last 48 h', '<span class="count" id="legend-count-csoRecent"></span>')}
        ${item('csoQuiet', 'cso-swatch is-quiet', '--cso-quiet', 'Quiet or offline', '<span class="count"><span id="legend-cso-quiet-hint">zoom in · </span><span id="legend-count-csoQuiet"></span></span>')}
        <div class="legend-key"><span class="works-key"></span>at a treatment works</div>
        <div class="legend-key"><span class="works-key is-network"></span>on the sewer network</div>
        </div>
        <div class="legend-col">
        ${title('waterways', 'Waterways')}
        ${item('rivers', 'line', '--water', 'Rivers', '<span class="count" id="legend-count-rivers"></span>')}
        ${Object.entries(RIVER_COLOURS).map(([name, colour]) =>
          `<div class="legend-key river-key"><span class="river-swatch" style="--c: var(${colour})"></span>${esc(name)}</div>`).join('')}
        ${item('streams', 'line thin', '--water-minor', 'Streams', '<span class="count" id="legend-streams-hint"></span>')}
        ${title('railways', 'Railways')}
        ${item('passenger', 'line', '--rail', 'Passenger lines')}
        ${item('stations', 'dot', '--rail', 'Stations', '<span class="count" id="legend-count-stations"></span>')}
        ${title('roads', 'Roads')}
        ${item('roads', 'road', '--road', 'Major roads')}
        <div class="legend-title">Boundary</div>
        ${item('boundary', 'area', '--accent', 'Taw catchment')}
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
    setTiles();

    addLegend();
    fitLegend();     // places the legend, before the view is fitted around it
    fitIfVisible();  // after the legend, which it fits around
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
    layer('boundary.geojson', addBoundary);
    layer('rivers.geojson', fc => setCount('rivers', addRivers(fc)));
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

  // Fit the catchment the first time the map is visible. Fitting while the
  // view is hidden (zero size) would zoom all the way in.
  let fitted = false;

  // The opening view: the highest whole zoom level at which the outline is
  // all on screen and clear of the zoom buttons and attribution. The open
  // legend may sit over the dimmed land outside, and over a corner of the
  // catchment: no more than LEGEND_POINTS of its outline's points, and none
  // deeper than LEGEND_DEPTH of its width in from its edges. At each zoom the
  // placement covering least is used, the most central of those.
  const LEGEND_POINTS = 3;
  const LEGEND_DEPTH = 0.1;
  function openingView(outline, size, hard, soft, minZoom, maxZoom) {
    const M = 12;
    const inside = (x, y, r, m) => x > r.left - m && x < r.right + m && y > r.top - m && y < r.bottom + m;
    for (let z = maxZoom; z >= minZoom; z--) {
      const pts = outline.map(p => map.project(p, z));
      const minX = Math.min(...pts.map(p => p.x)), maxX = Math.max(...pts.map(p => p.x));
      const minY = Math.min(...pts.map(p => p.y)), maxY = Math.max(...pts.map(p => p.y));
      const w = maxX - minX, h = maxY - minY;
      if (w > size.x - 2 * M || h > size.y - 2 * M) continue;
      // Offsets from the centre back to the margin, ending on the margin itself.
      const steps = from => { const out = []; for (let v = from; v > M; v -= 8) out.push(v); out.push(M); return out; };
      let best = null;
      for (const ox of steps((size.x - w) / 2)) {
        for (const oy of steps((size.y - h) / 2)) {
          // How many points the legend covers, and how far in it reaches.
          let covered = 0, depth = 0, ok = true;
          pts.forEach(p => {
            const x = p.x - minX + ox, y = p.y - minY + oy;
            if (hard.some(r => inside(x, y, r, M))) ok = false;
            for (const r of soft) {
              if (!inside(x, y, r, 0)) continue;
              covered++;
              depth = Math.max(depth, Math.min(x - r.left, y - r.top));
            }
          });
          const better = !best || covered < best.covered || (covered === best.covered && depth < best.depth);
          if (ok && covered <= LEGEND_POINTS && depth <= LEGEND_DEPTH * w && better) best = { ox, oy, covered, depth };
          if (best && best.covered === 0) break;
        }
        if (best && best.covered === 0) break;
      }
      if (best) {
        const centre = L.point(minX - best.ox + size.x / 2, minY - best.oy + size.y / 2);
        return { centre: map.unproject(centre, z), zoom: z };
      }
    }
    return null;
  }

  function fitIfVisible() {
    if (fitted || !map || map.getSize().x === 0) return;
    const box = map.getContainer().getBoundingClientRect();
    const rect = el => {
      const r = el.getBoundingClientRect();
      return { left: r.left - box.left, right: r.right - box.left, top: r.top - box.top, bottom: r.bottom - box.top };
    };
    const c = map.getContainer();
    const hard = [...c.querySelectorAll('.map-legend.collapsed, .leaflet-control-zoom, .leaflet-control-attribution')].map(rect);
    const soft = [...c.querySelectorAll('.map-legend:not(.collapsed)')].map(rect);
    // Where the open legend can't be placed clear of the catchment, as on a
    // phone, the view is fitted ignoring it.
    const size = map.getSize(), min = map.getMinZoom();
    const view = openingView(OUTLINE, size, hard, soft, min, 12)
      || openingView(OUTLINE, size, [], [], min, 12);
    // The panning limit is set after the opening view, and takes it in, so it
    // never pulls the view back over the legend.
    map.setMaxBounds(null);
    if (view) map.setView(view.centre, view.zoom, { animate: false });
    else map.fitBounds(L.latLngBounds(OUTLINE), { animate: false });
    map.setMaxBounds(L.latLngBounds(MAX_BOUNDS).extend(map.getBounds()));
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
