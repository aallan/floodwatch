# Floodwatch — River Taw Catchment Monitoring

![Floodwatch screenshot](images/screenshot.png)

A real-time flood monitoring dashboard for the River Taw and its tributaries in Devon, UK. Displays river levels, tidal levels, rainfall data, and active flood warnings from Environment Agency monitoring stations on an interactive map with flow visualisation and time-series charts.

The service is currently deployed as a Digital Ocean App at [tawriver.watch](https://tawriver.watch).

## Prerequisites

**Python 3.12+** is the only requirement to run Floodwatch. The app uses only the Python standard library — no pip packages needed.

```bash
brew install python              # macOS (via Homebrew)
```

For development (tests, linting), you'll also need:

```bash
brew install node pre-commit ruff
pip install pytest
```

See [CONTRIBUTING.md](CONTRIBUTING.md) for the full development setup.

## Quick Start

Fetch historical data (first time only — takes a few minutes):

```bash
python fetch_data.py            # Full history
python fetch_data.py --recent   # Quick update (merges last 2 days)
```

Start the local server:

```bash
python serve.py
```

Open in your browser:

```bash
open http://localhost:8080
```

## Usage

### `serve.py` — Local Development Server

Serves the static site and handles data refresh requests. No PHP, Node, or other runtime needed — just Python 3.

```bash
python serve.py              # Start on port 8080 (localhost only)
python serve.py 3000         # Start on a custom port
python serve.py --bind ::    # Listen on all interfaces
python serve.py --stop       # Stop the running server
```

The server:

- Serves all static files (HTML, CSS, JS, CSV data, GeoJSON overlays)
- Handles `POST /refresh.php` by proxying to the EA Flood Monitoring API directly in Python
- Sets `Cache-Control: no-cache` headers on `.csv` and `.geojson` responses to prevent stale data
- Binds to `::1` (localhost) by default — use `--bind ::` to listen on all interfaces
- Tracks its own PID in `.server.pid` for clean start/stop lifecycle
- Auto-kills any stale server instance on the same port
- Rate-limits refresh requests to once per 5 minutes (returns HTTP 429)

Press `Ctrl+C` to stop, or use `python serve.py --stop` from another terminal.

### `fetch_data.py` — Data Fetcher

Downloads readings for all stations from the EA Flood Monitoring API and saves them as CSV files.

```bash
python fetch_data.py            # Full fetch — up to 2 years of history
python fetch_data.py --recent   # Quick update — last 2 days, merged with existing data
python fetch_data.py --recent 5 # Quick update — last 5 days
```

Run the full fetch once to seed the data directory, or again to backfill after a long gap. Use `--recent` for lightweight incremental updates — this is what the GitHub Actions workflow uses for hourly refreshes.

In `--recent` mode the script loads each station's existing CSV, fetches only the specified number of days from the API, merges and deduplicates by timestamp, and writes the combined result back. This keeps the full history intact while only making a handful of quick API calls.

This script:

- Fetches readings in 28-day chunks (full mode) or a single short request (`--recent` mode)
- Merges new readings with existing CSV data when using `--recent`
- Saves each station's data as a CSV in `data/`
- Writes `data/stations.csv` with metadata for all stations
- Deduplicates readings by timestamp
- Includes polite 300ms delays between API requests
- Stops fetching for a station after 3 consecutive empty chunks (full mode)

### `refresh.php` — LAMP Stack Backend (Optional)

If deploying to a LAMP server, this PHP script handles the same refresh logic as `serve.py`. The frontend's Refresh button POSTs to `/refresh.php` — whichever backend is available will respond.

## What the Map Shows

### Station Types

| Marker | Type | Unit | Colour | Shape |
|--------|------|------|--------|-------|
| River Level | Stage height | m | Teal | Circle |
| Tidal Level | Height above ordnance datum | mAOD | Amber | Diamond |
| Rainfall | Tipping bucket gauge total | mm | Blue | Teardrop |

Each marker displays the latest reading value. Click any marker to open a popup with:

- Current value and timestamp
- Trend indicator (for level and tidal stations — see below)
- Time-series chart with selectable ranges: **24h, 48h, 5d, 30d, All**
- **Forecast** button on rainfall stations — 48-hour predicted rainfall from Open-Meteo (see Rainfall Forecast below)
- "Top of normal range" reference line (dashed red) on level station charts
- Station name, type, and river

Active flood warnings and alerts for the Taw catchment are shown in a banner below the header (see Flood Warnings below).

### High Water Level Warning

River level station markers turn **red** when the current reading exceeds 70% of the station's typical range high (the EA's 95th-percentile historical value). When the level drops back below the 70% threshold, the marker returns to its normal teal colour on the next data load or refresh.

Tidal and rainfall stations are not affected — their markers always use their standard colours.

### Chart Reference Line and Fixed Y-Axis

Level station popup charts display a dashed red horizontal line at the "top of normal range" (`typicalRangeHigh` from the EA API — the 95th percentile of historical readings). The Y-axis is fixed from **0** to **typicalRangeHigh × 1.25** (rounded up to the next 0.5m) so the scale stays consistent when switching between 24h, 48h, 5d, and 30d views.

Tidal and rainfall station charts start at 0 but auto-scale the Y-axis maximum since they don't have a meaningful typical range value.

### Trend Indicators

River level and tidal stations display a small coloured badge on the bottom-right corner of the marker showing whether the water level is rising, falling, or steady:

| Badge | Meaning | Colour |
|-------|---------|--------|
| ↑ | Rising | Red |
| ↓ | Falling | Green |
| → | Steady | Grey |

The trend is calculated by fitting a linear-regression slope over the last 1 hour of readings. A slope steeper than ±1 cm/hour (0.01 m/hr) counts as rising or falling; anything within that threshold is steady. This approach tracks the actual direction of the graph line, so the badge always matches what the user sees on the chart.

The trend badge also appears in the popup next to the current value. Rainfall stations do not show a trend indicator.

If there isn't enough recent data (fewer than 3 readings in the last hour), no badge is shown.

### Flood Warnings and Alerts

The EA issues two distinct types of notification through the same API endpoint (`/id/floods`):

- **Flood Warnings** (severity 1–2) are issued for specific locations — e.g. "River Taw (Lower) from Newnham Bridge to Barnstaple, including Umberleigh". These mean flooding is expected or severe.
- **Flood Alerts** (severity 3) are issued for broader catchment areas — e.g. "North Dartmoor Rivers" or "Lower Taw area". These mean flooding is possible and to be prepared.

The dashboard monitors 15 EA flood area IDs covering both types:

| Type | Areas monitored | Example |
|------|----------------|---------|
| Flood Warning Areas | 13 (River Taw upper/middle/lower, tidal, Okement, Landkey, tidal estuary) | `113FWF2E1B` — River Taw (Lower) |
| Flood Alert Areas | 2 (North Dartmoor Rivers, Lower Taw area) | `113WAFTW12` — North Dartmoor Rivers |

Warnings and alerts are fetched from the EA API on page load and on each refresh. When active warnings or alerts exist, a coloured banner appears below the header:

| Severity | Label | Banner colour |
|----------|-------|---------------|
| 1 | Severe Flood Warning | Red (pulsing icon) |
| 2 | Flood Warning | Amber |
| 3 | Flood Alert | Yellow |

Click the banner to expand and see details for each warning or alert, including the EA's situation message, the affected river, and when it was raised.

When no warnings or alerts are in force, a small green "No warnings" indicator appears in the header alongside the last-updated timestamp. On phones, only the green dot is shown to save space.

Severity level 4 ("Warning no longer in force") is filtered out — only active warnings and alerts appear.

### Rainfall Forecast

Rainfall station popups include a **Fcst** button that fetches a 48-hour hourly precipitation forecast from the [Open-Meteo API](https://open-meteo.com/) using each station's own latitude and longitude.

- The forecast is shown as an **amber bar chart** to visually distinguish it from the blue historical line chart
- The popup timestamp updates to show the forecast date range (e.g. "Forecast: 13 Feb–15 Feb")
- Clicking the Fcst button again toggles back to the default 5-day historical view
- Clicking any historical time range button (24h, 48h, etc.) also returns to the historical chart
- Forecasts are cached in memory for 15 minutes per station to avoid unnecessary API calls
- No API calls are made on page load — the Open-Meteo fetch only fires when the user clicks the Fcst button
- Level and tidal stations do not show the Forecast button

### River Discharge Forecast

The Barnstaple (Tidal) station popup has a **tab UI** with two views: "Tidal Level" (the default historical chart) and "River Discharge". The discharge tab fetches a river discharge forecast from the [Open-Meteo Flood API](https://open-meteo.com/en/docs/flood-api) powered by the GloFAS v4 model.

- Shows **7 days of hindcast** and **14 days of forecast** — 21 days total
- The chart displays the **ensemble mean** as a solid amber line with a **min–max range band** showing forecast uncertainty (forecast days only)
- Two reference lines from the NRFA 66-year record at Umberleigh (station 50001): **Normal flow (Mean)** at 18.3 m³/s and **High flow (Q10)** at 48.3 m³/s
- A dashed vertical "Today" line separates observed from predicted data
- Uses Umberleigh coordinates (NRFA 50001) for the GloFAS API call — Barnstaple's own coordinates resolve to a minor stream in the 5 km grid
- The current value area updates to show today's mean discharge in **m³/s**
- Discharge data is cached for 1 hour per station
- No API call on page load — only fetches when the user clicks the "River Discharge" tab
- Only available on the Barnstaple tidal popup, since it sits at the outlet of the full Taw catchment (1,346 km²) where the GloFAS model is most reliable
- Uses `cell_selection=land` to ensure the model picks a land-based grid cell near the estuary

### River Overlays

Seven rivers are displayed as coloured GeoJSON overlays with flow direction arrows:

| River | Colour | Role |
|-------|--------|------|
| River Taw | Teal (#1a8a7d) | Main stem — source to estuary |
| River Mole | Blue (#2e7dab) | Tributary, joins near Newnham Bridge |
| Little Dart River | Brown (#8a6e1a) | Tributary, joins upstream of Newnham Bridge |
| River Yeo | Purple (#7a4a8a) | Tributary, joins near Barnstaple |
| Lapford Yeo | Burnt orange (#ab5e2e) | Tributary, joins the Taw near Lapford |
| Crooked Oak | Green (#5a8a3a) | Tributary, flows into the River Mole near South Molton |
| Hollocombe Water | Olive (#6a7a3a) | Tributary, joins the Taw between Eggesford and Kings Nympton |

Flow arrows (triangles) point downstream. The River Taw also has "UPSTREAM (Source)" and "DOWNSTREAM (Estuary)" labels. All rivers have a name label at their midpoint.

The GeoJSON data comes from OpenStreetMap via the Overpass API. OSM waterway ways are digitised in flow direction (source to mouth), so the arrows follow the natural direction of the data.

### Railway Overlays

Two railway lines are displayed as dashed grey overlays with station markers:

| Line | Route | Stations |
|------|-------|----------|
| Tarka Line | Exeter Central to Barnstaple | 14 stations (Exeter Central, Exeter St Davids, Newton St Cyres, Crediton, Yeoford, Copplestone, Morchard Road, Lapford, Eggesford, Kings Nympton, Portsmouth Arms, Umberleigh, Chapelton, Barnstaple) |
| Dartmoor Line | Coleford Junction to Okehampton | 1 station (Okehampton) — shared stations shown on the Tarka Line |

The Tarka and Dartmoor lines share track from Exeter to Coleford Junction (near Yeoford). Only the unique Dartmoor Line section from the junction to Okehampton is drawn separately to avoid duplication. Station markers show the station name on hover. Track data comes from OpenStreetMap (OSM relations 275887 and 276920).

### Map Tiles

Uses [CartoDB Positron](https://carto.com/basemaps/) — a light, muted basemap that keeps the focus on the data overlays.

### Mobile Responsiveness

The dashboard adapts to smaller screens with two CSS breakpoints:

| Breakpoint | Target | Key changes |
|------------|--------|-------------|
| ≤ 768px | Tablets | Compact header, smaller popups (320px), scrollable legend, compact chart height |
| ≤ 480px | Phones | Hidden subtitle, compact "last updated" text below refresh button, collapsible legend toggle (top-right), 280px popups, larger zoom controls, initial zoom level 10 |

On phones, the legend collapses to a single "Legend ▸" button in the top-right corner — tap to expand. The "last updated" timestamp is shown in a smaller font stacked below the Refresh button. The map starts at a wider zoom level to show all stations at a glance.

## Monitoring Stations

### River Taw (main stem, upstream to downstream)

| # | Station | ID | Lat/Lon |
|---|---------|-----|---------|
| 1 | Sticklepath | 50149 | 50.738, -3.918 |
| 2 | Taw Bridge | 50119 | 50.845, -3.886 |
| 3 | Newnham Bridge | 50132 | 50.940, -3.908 |
| 4 | Umberleigh | 50140 | 50.995, -3.985 |

### Barnstaple Tidal

| Station | ID | Lat/Lon | Unit |
|---------|-----|---------|------|
| Barnstaple (Tidal) | 50198 | 51.080, -4.065 | mAOD |

### River Mole (tributary, upstream to downstream)

| # | Station | ID | Lat/Lon |
|---|---------|-----|---------|
| 1 | North Molton | 50135 | 51.055, -3.795 |
| 2 | Mole Mills | 50153 | 51.017, -3.822 |
| 3 | Woodleigh | 50115 | 50.973, -3.910 |

### Little Dart River (tributary)

| Station | ID | Lat/Lon |
|---------|-----|---------|
| Chulmleigh | 50125 | 50.908, -3.864 |

### River Yeo (tributary, joins near Barnstaple)

| Station | ID | Lat/Lon |
|---------|-----|---------|
| Collard Bridge | 50114 | 51.100, -4.010 |

### Lapford Yeo (tributary, joins the Taw near Lapford)

| Station | ID | Lat/Lon |
|---------|-----|---------|
| Lapford | 50151 | 50.858, -3.811 |

### Crooked Oak (tributary, flows into the River Mole)

No monitoring stations on this river.

### Hollocombe Water (tributary, joins the Taw between Eggesford and Kings Nympton)

No monitoring stations on this river.

### Rainfall Stations

**East of the Taw:**

| Station | ID | Lat/Lon |
|---------|-----|---------|
| Lapford Bowerthy | 50199 | 50.873, -3.799 |
| Molland Sindercombe | E85220 | 51.038, -3.736 |
| Crediton Knowle | E84360 | 50.800, -3.738 |
| Kinsford Gate | 45183 | 51.114, -3.795 |

**West of the Taw:**

| Station | ID | Lat/Lon |
|---------|-----|---------|
| Allisland | 50103 | 50.881, -4.153 |
| Kenwith Castle | 50194 | 51.024, -4.236 |
| Bratton Fleming Haxton | E82120 | 51.117, -3.941 |
| Halwill | 47158 | 50.772, -4.229 |

## Data Source

All hydrological data comes from the **Environment Agency Flood Monitoring API**:

```
https://environment.data.gov.uk/flood-monitoring
```

This is the same data that powers the government's [Check for Flooding](https://check-for-flooding.service.gov.uk/) service. Readings are taken every 15 minutes.

### Measure ID Format

Each station has a unique measure identifier that encodes the station, parameter, qualifier, interval, and unit:

```
{stationId}-{parameter}-{qualifier}-{type}-{interval}-{unit}
```

Examples:
- `50132-level-stage-i-15_min-m` — Newnham Bridge river level (instantaneous, metres)
- `50198-level-tidal_level-i-15_min-mAOD` — Barnstaple tidal level (metres above ordnance datum)
- `50199-rainfall-tipping_bucket_raingauge-t-15_min-mm` — Lapford Bowerthy rainfall (total, mm)

### API Endpoints Used

| Purpose | Endpoint |
|---------|----------|
| Recent readings | `GET /id/measures/{measureId}/readings?since={ISO8601}&_sorted&_limit=10000` |
| Date range | `GET /id/measures/{measureId}/readings?startdate={YYYY-MM-DD}&enddate={YYYY-MM-DD}&_sorted&_limit=100000` |
| Flood warnings | `GET /id/floods?county=Devon` |
| Rainfall forecast | `GET https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&hourly=precipitation&forecast_days=2&timezone=Europe/London` |
| River discharge | `GET https://flood-api.open-meteo.com/v1/flood?latitude={lat}&longitude={lon}&daily=river_discharge_mean,river_discharge_max,river_discharge_min&forecast_days=14&past_days=7&cell_selection=land` |
| Station lookup | `GET /id/stations?RLOIid={id}` |

### Refresh Logic

When you click **Refresh Data**, the app determines the gap between the last known reading and now for each station:

- **Gap ≤ 5 days:** Single API request using `?since=` — fast and efficient
- **Gap > 5 days:** Fetches in 28-day chunks working backwards to the last known timestamp — fills the entire gap without missing data
- **No existing data:** Fetches the last 28 days as a starting point

This gap-fill logic applies identically across the frontend (JavaScript), `serve.py` (Python), and `refresh.php` (PHP).

#### Activity Log

An activity log appears in the bottom-right corner of the map during refresh, showing:

- A progress bar (e.g. "7/19 stations")
- Per-station status: fetching, success with reading count, errors, and warnings for large gaps
- A summary line on completion

The log fades away a few seconds after the refresh completes.

#### Backend Detection and Caching

On page load, the app probes for a backend by sending an `OPTIONS` request to `/refresh`. If the response includes `Access-Control-Allow-Methods: POST`, a backend is present (LAMP or serve.py). Otherwise the app assumes it's running as a static site.

| Deployment | After fetching from EA API |
|------------|---------------------------|
| **LAMP / serve.py** | Caches to `localStorage`, then POSTs to backend to persist updated CSVs server-side |
| **Static (App Platform, etc.)** | Caches the last 7 days of readings in `localStorage` so they survive page reloads |

All deployments cache refreshed data to `localStorage` — this means a page reload always shows the most recent data you've fetched, even if the browser's HTTP cache serves stale CSV files. On LAMP/serve.py, the backend sync happens after the local cache, so data is persisted in both places.

On page load, any cached readings from `localStorage` are merged on top of the CSV data, so the map immediately reflects the most recent data — even before hitting Refresh. CSV requests include a cache-busting parameter to bypass browser HTTP caching.

After a refresh, station markers are re-created with updated values and trend badges.

## Data Files

All data lives in the `data/` directory:

```
data/
  stations.csv                          # Station metadata (all 19 stations)
  level_50149_sticklepath.csv           # River level CSVs (11 files)
  level_50119_taw_bridge.csv
  level_50132_newnham_bridge.csv
  level_50140_umberleigh.csv
  level_50198_barnstaple_(tidal).csv
  level_50135_north_molton.csv
  level_50153_mole_mills.csv
  level_50115_woodleigh.csv
  level_50125_chulmleigh.csv
  level_50151_lapford.csv
  level_50114_collard_bridge.csv
  rainfall_50199.csv                    # Rainfall CSVs (8 files)
  rainfall_E85220.csv
  rainfall_E84360.csv
  rainfall_45183.csv
  rainfall_50103.csv
  rainfall_50194.csv
  rainfall_E82120.csv
  rainfall_47158.csv
  river_taw.geojson                     # River geometry (7 files)
  river_mole.geojson
  river_little_dart.geojson
  river_yeo.geojson
  river_lapford_yeo.geojson
  river_crooked_oak.geojson
  river_hollacombe_water.geojson
  tarka_line.geojson                    # Railway track geometry (2 files)
  dartmoor_line.geojson
  tarka_stations.geojson                # Railway station points (2 files)
  dartmoor_stations.geojson
```

### CSV Format

All station CSVs share the same structure:

```csv
dateTime,value,unit,station_id,station_label
2026-02-10T10:15:00Z,0.523,m,50149,Sticklepath
2026-02-10T10:30:00Z,0.521,m,50149,Sticklepath
```

| Column | Description |
|--------|-------------|
| `dateTime` | ISO 8601 timestamp in UTC |
| `value` | Reading value (float) |
| `unit` | `m`, `mAOD`, or `mm` |
| `station_id` | EA station reference |
| `station_label` | Human-readable name |

## Deployment

Floodwatch can be deployed four ways, from simplest to most involved. See **[INSTALL.md](INSTALL.md)** for full step-by-step instructions, costs, and data transfer estimates for each option.

| Method | Backend | Cost | Best for |
|--------|---------|------|----------|
| **Local** (`python serve.py`) | Python dev server | Free | Development and testing |
| **App Platform** (recommended) | Static site — no backend needed | Free tier ($0/mo) | Production — zero maintenance, automatic SSL and CDN |
| **LAMP Droplet** | Apache + PHP | $6/mo | Full server-side control with persistent CSV refresh |
| **Generic LAMP** | Any Apache/Nginx + PHP stack | Varies | Existing hosting infrastructure |

All deployments serve the same `index.html` single-page app. The difference is how the Refresh button works: on LAMP/serve.py it persists updated CSVs server-side, while on App Platform it caches to `localStorage` and relies on hourly GitHub Actions commits to keep the CSV baseline fresh.

## Tests

104 tests (64 Python + 40 JavaScript) cover the data pipeline, server logic, frontend utility functions, and UI interactions. See **[TESTING.md](TESTING.md)** for full details of what each test covers and why.

## Project Structure

```
floodwatch/
  index.html                          # Single-page app (HTML shell, ~75 lines)
  fetch_data.py                       # Data fetcher (full or --recent incremental)
  serve.py                            # Local Python dev server with refresh proxy
  refresh.php                         # PHP refresh endpoint for LAMP deployment
  README.md                           # This file
  INSTALL.md                          # Deployment guide (4 methods)
  TESTING.md                          # Test suite documentation
  CONTRIBUTING.md                     # How to contribute
  CODE_OF_CONDUCT.md                  # Contributor Covenant
  CHANGELOG.md                        # Version history
  LICENSE                             # MIT licence
  .editorconfig                       # Consistent formatting across editors
  .pre-commit-config.yaml             # Pre-commit hooks (ruff lint + format)
  .gitignore                          # Excludes .server.pid, __pycache__, .DS_Store, .claude, node_modules, .pytest_cache
  .do/app.yaml                        # Digital Ocean App Platform spec
  .github/workflows/update-data.yml   # Hourly GitHub Actions data refresh
  .github/workflows/tests.yml         # CI: Python + JS tests on push/PR
  .github/dependabot.yml              # Automated dependency update PRs
  .github/SECURITY.md                 # Security vulnerability reporting
  .github/ISSUE_TEMPLATE/             # Bug report and feature request templates
  .github/pull_request_template.md    # PR template
  css/
    floodwatch.css                    # All application styles
  js/
    floodwatch.js                     # Main application logic
    floodwatch-core.js                # Extracted utility functions (UMD module)
  js-tests/
    package.json                      # Vitest + jsdom devDependencies
    package-lock.json                 # Lockfile for reproducible installs
    vitest.config.js                  # jsdom environment config
    floodwatch-core.test.js           # 25 JavaScript tests
  tests/
    conftest.py                       # Shared pytest fixtures
    test_fetch_data.py                # 37 tests for fetch_data.py
    test_serve.py                     # 12 tests for serve.py logic
    test_serve_handler.py             # 5 tests for HTTP handler behaviour
    fixtures/
      sample_readings.json            # Mock EA API response
      sample_level.csv                # Sample CSV for load/merge tests
  pyproject.toml                      # pytest config (no production deps)
  images/                             # Static images
    screenshot.png                    # README screenshot
    opengraph.png                     # Social media preview (1200×630)
  data/                               # CSV data files and GeoJSON river overlays
  .server.pid                         # Auto-managed server PID file (gitignored)
```

## Technology

| Component | Technology |
|-----------|-----------|
| Map | [Leaflet.js](https://leafletjs.com/) 1.9.4 |
| Basemap tiles | [CartoDB Positron](https://carto.com/basemaps/) |
| Charts | [Chart.js](https://www.chartjs.org/) 4.4.1 with date-fns adapter |
| CSV parsing | [PapaParse](https://www.papaparse.com/) 5.4.1 |
| River geometry | [OpenStreetMap](https://www.openstreetmap.org/) via [Overpass API](https://overpass-api.de/) |
| Data source | [EA Flood Monitoring API](https://environment.data.gov.uk/flood-monitoring/doc/reference) |
| Rainfall forecast | [Open-Meteo API](https://open-meteo.com/) |
| Discharge forecast | [Open-Meteo Flood API](https://open-meteo.com/en/docs/flood-api) (GloFAS v4) |
| Dev server | Python 3 standard library (`http.server`) |
| Production backend | PHP (`refresh.php`) |
| Python tests | [pytest](https://docs.pytest.org/) 8+ |
| JavaScript tests | [Vitest](https://vitest.dev/) 3 + [jsdom](https://github.com/jsdom/jsdom) |

## Licence

The code in this repository is licensed under the MIT licence.

Copyright &copy; 2026 Alasdair Allan

Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated documentation files (the "Software"), to deal in the Software without restriction, including without limitation the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and to permit persons to whom the Software is furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
