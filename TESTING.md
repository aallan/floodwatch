# Testing

80 tests cover the data pipeline, server logic, and frontend utility functions. The focus is on areas where bugs are most consequential: data merge/dedup logic (where errors silently corrupt charts), API retry behaviour (where failures lose data), filename sanitisation (where unsanitised input could create path traversal issues), and HTML escaping (where station names could inject scripts). No production dependencies are added — all test tooling is dev-only.

## Prerequisites

- **Python 3.12+** and **pytest** — `brew install python && pip install pytest`
- **Node.js 22+** — `brew install node` (for JavaScript tests only)

## Running Tests

**Python** (55 tests via pytest):

```bash
pytest tests/ -v
```

**JavaScript** (25 tests via Vitest + jsdom):

```bash
cd js-tests
npm install          # first time only
npm test
```

Both suites run in CI on every push to `main` via `.github/workflows/tests.yml`.

## Python Tests — `test_fetch_data.py` (37 tests)

Tests the data pipeline that downloads readings from the EA API and writes them as CSV files. All HTTP calls are mocked — no real API requests are made. Filesystem tests use pytest's `tmp_path` for isolation.

**`get_measure_id`** (5 tests) — The EA API identifies each station's data stream with a compound measure ID like `50140-level-stage-i-15_min-m`. If the format is wrong for a station type, the fetcher silently gets no data back. Tests verify:
- Level stations produce the standard `{id}-level-stage-i-15_min-m` format
- Rainfall stations produce the tipping bucket format (`{id}-rainfall-tipping_bucket_raingauge-t-15_min-mm`)
- The Barnstaple tidal station uses its custom `measure_id` override (`50198-level-tidal_level-i-15_min-mAOD`) rather than deriving one from the type
- Stations without a custom `measure_id` key fall through to the default format for their type

**`get_station_filename`** (6 tests) — CSV filenames are derived from station names and IDs. Unsanitised names could create files in unexpected directories or overwrite other data. Tests verify:
- Level stations produce `level_{id}_{label}.csv` with lowercase labels and underscored spaces
- Rainfall stations use the simpler `rainfall_{id}.csv` format (no label, since some have long names)
- Parentheses in labels like "Barnstaple (Tidal)" are preserved (they're safe in filenames)
- Slashes, exclamation marks, and other special characters are stripped or replaced with underscores
- Non-alphanumeric characters in station IDs are sanitised

**`merge_readings`** (7 tests) — The core of the `--recent` incremental update that runs hourly via GitHub Actions. Bugs here cause duplicate rows (inflating chart values) or lost readings (gaps in charts). Tests verify:
- New readings merge correctly into an empty existing set
- Duplicate timestamps are deduplicated (the EA API sometimes returns overlapping data between fetches)
- The merged result is always sorted chronologically (charts depend on this)
- Readings with empty `dateTime` fields are silently dropped (the API occasionally returns these)
- Both inputs empty produces an empty result without errors
- All fields beyond `dateTime`/`value` (like `unit`, `station_id`) are preserved through the merge
- Large sets (hundreds of readings with overlapping ranges) merge correctly

**`load_existing_csv` / `save_readings_csv` / `save_stations_csv`** (10 tests) — CSV round-trip correctness matters because the frontend parses these files directly. Tests verify:
- Loading a valid CSV returns a list of dicts with the correct field names and values
- Loading a missing file returns an empty list (not an error — a station may not have data yet)
- Loading a header-only file returns an empty list (fresh CSVs start this way)
- Saved CSVs have the correct header row (`dateTime,value,unit,station_id,station_label`)
- Level stations write `m` as the unit, rainfall writes `mm`, and tidal writes `mAOD` — getting these wrong would confuse anyone reading the raw data
- Readings with empty `dateTime` are excluded from the saved file
- `stations.csv` contains all 19 stations with the correct metadata headers

**`api_get`** (4 tests) — The EA API occasionally times out or returns 5xx errors, especially during flood events when traffic spikes. `api_get` retries with exponential backoff to handle transient failures without losing an entire fetch run. Tests verify:
- A successful first attempt returns the parsed JSON
- After two failures, a third successful attempt returns the data (resilience)
- After exhausting all retries, the original error is raised (doesn't silently swallow failures)
- The backoff delays are correct — sleeps 1s then 2s between retries (exponential), confirmed by capturing `time.sleep` calls

**`fetch_readings_batch` / `fetch_all_readings`** (5 tests) — The full-history fetcher works backwards in 28-day chunks, which means chunks can overlap and the same reading may appear twice. Tests verify:
- A successful batch returns the API's `items` array
- A failed batch returns an empty list (allows the fetcher to skip one bad chunk and continue)
- Overlapping chunks are deduplicated in the final result
- The fetcher stops after 3 consecutive empty chunks rather than iterating all 13+ chunks for a full year — avoids hammering the API for stations that have limited historical data
- The combined result is sorted chronologically regardless of which chunk each reading came from

## Python Tests — `test_serve.py` (12 tests)

Tests the dev server's refresh logic and lifecycle management. HTTP calls to the EA API are mocked; filesystem operations use `tmp_path`.

**`api_get`** (3 tests) — The server's version of `api_get` deliberately has no retry — if one station's refresh fails, the server moves on to the next rather than blocking. Tests verify:
- Successful requests return parsed JSON
- Network errors (`URLError`) return `None` instead of crashing the server
- Malformed JSON responses return `None` instead of raising an exception

**`refresh_station`** (5 tests) — When the frontend's Refresh button is clicked, the server decides how to fetch based on the gap since the last reading. The strategy affects both speed and completeness. Tests verify:
- **No existing data** — fetches the last 28 days as a starting point and writes a new CSV
- **Small gap (≤5 days)** — uses a single `?since=` API request, which is fast and efficient
- **Large gap (>5 days)** — switches to chunked date-range fetches to fill the entire gap without missing data
- **Deduplication** — when the API returns readings that already exist in the CSV, the count correctly reports zero new readings
- **Tidal unit** — the Barnstaple tidal station's CSV rows use `mAOD` (metres above ordnance datum), not `m`

**PID file** (3 tests) — The server tracks its own PID in `.server.pid` so `--stop` can find and kill it cleanly. Tests verify:
- Write then read returns the current process ID
- Reading a missing PID file returns `None` (server wasn't running)
- Reading a corrupt PID file returns `None` instead of crashing

**`handle_refresh`** (2 tests) — Integration test for the JSON response that the frontend's activity log parses. Tests verify:
- The response contains `success`, `timestamp`, and a `details` array with one entry per station
- The `stations_updated` count correctly reflects how many stations received new data

## Python Tests — `test_serve_handler.py` (5 tests)

These tests start a real `FloodwatchHandler` HTTP server on a random port in a daemon thread and make actual HTTP requests with `urllib.request`. This tests the full request/response cycle including headers, status codes, and content negotiation — not just the logic functions.

- **POST `/refresh.php` → 200** — Verifies the refresh endpoint returns valid JSON with `"success": true`. This is the endpoint the frontend's Refresh button hits.
- **Rate limiting → 429** — A second POST within 5 minutes returns HTTP 429 with a JSON body containing `retry_after` seconds. Prevents accidental API abuse if someone clicks Refresh repeatedly.
- **OPTIONS CORS headers** — The frontend sends an `OPTIONS` preflight to detect whether a backend is present. The response must include `Access-Control-Allow-Methods: POST` or the frontend falls back to client-side-only mode.
- **CSV `Cache-Control: no-cache`** — CSV and GeoJSON responses include `Cache-Control: no-cache` so the browser always fetches fresh data after a refresh. Without this, the browser's HTTP cache serves stale readings.
- **Unknown path → 404** — POSTing to a path other than `/refresh.php` or `/refresh` returns 404. Ensures the server doesn't accidentally handle arbitrary POST requests.

## JavaScript Tests (25 tests)

Five functions are extracted from the inline `<script>` in `index.html` into `js/floodwatch-core.js` — a UMD module that works in both the browser (`window.FloodwatchCore`) and Node (`require`). The originals in `index.html` become thin wrappers that pass globals to the extracted versions. This makes the core logic testable without loading Leaflet, Chart.js, or the full DOM.

Tests use Vitest with jsdom (needed because `escapeHtml` uses `document.createElement`).

**`formatTime`** (4 tests) — Displayed in every marker popup as the "last updated" timestamp. Uses relative times for recent readings and absolute dates for older ones.
- Less than 1 hour ago → `"15 min ago"` (shows minutes)
- Less than 24 hours ago → `"6h ago"` (shows hours)
- More than 24 hours ago → formatted date like `"13 Jan, 14:30"` (shows day and time)
- Identical timestamps → `"0 min ago"` (edge case when a reading just arrived)

**`escapeHtml`** (4 tests) — Station names are inserted into popup HTML via `innerHTML`. Without escaping, a station name containing `<` or `&` could inject arbitrary HTML or scripts. The function uses the `textContent`/`innerHTML` DOM trick for escaping.
- `<script>alert("xss")</script>` → angle brackets become `&lt;` and `&gt;`
- `foo & bar` → ampersand becomes `&amp;`
- Safe strings like `"Umberleigh"` pass through unchanged
- Empty string returns empty string

**`getStation`** (5 tests) — Called on every marker click to look up station metadata across the three type arrays (level, rainfall, tidal). Tests verify:
- Finds stations in each of the three arrays by ID
- Returns `undefined` for a non-existent ID (the popup code checks for this)
- Handles a partial stations object where some type arrays are missing (defensive — avoids `TypeError` if the data structure changes)

**`getTrend`** (7 tests) — Calculates the trend badge (↑ rising, ↓ falling, → steady) shown on every level and tidal marker. Fits a linear-regression slope over the last hour of readings with a ±1 cm/hr threshold to filter sensor noise.
- Readings increasing by 0.1 m/hr → `{direction: 'rising', symbol: '↑'}`
- Readings decreasing by 0.1 m/hr → `{direction: 'falling', symbol: '↓'}`
- Readings fluctuating within ±1 mm → `{direction: 'steady', symbol: '→'}`
- Rainfall stations → `null` (trend is meaningless for cumulative rain totals)
- Fewer than 4 readings → `null` (not enough data for reliable regression)
- `null` or `undefined` input → `null` (station may not have loaded yet)
- Tidal stations → works the same as level stations (both measure water height)

**`computeCacheFingerprint`** (5 tests) — Generates a hash of all station IDs used to auto-invalidate `localStorage` when stations are added or removed. Without this, cached data from a previous station configuration would persist.
- Returns a non-empty string for a valid stations object
- Deterministic — same input always produces the same hash
- Sensitive — changing one station ID produces a different hash
- Order-independent — station arrays can be in any order (IDs are sorted internally before hashing)
- Tolerates missing type arrays — `{level: [...]}` without `rainfall` or `tidal` doesn't throw

## Test Architecture

- **Python:** pytest with shared fixtures in `conftest.py`. `monkeypatch` replaces `urlopen` and `time.sleep` so HTTP and backoff tests run instantly without network access. `tmp_path` provides an isolated filesystem per test — each test gets its own empty `data/` directory. All 55 tests run in ~2 seconds.
- **JavaScript:** Vitest with jsdom environment. jsdom is needed because `escapeHtml` uses `document.createElement` — pure Node has no DOM. The extracted functions accept dependencies as parameters (e.g. `getStation(id, stations)` instead of reading a global `STATIONS`) so tests can pass mock data without setting up the full app state.
- **CI:** Two parallel jobs in `.github/workflows/tests.yml` — Python (pytest on 3.12) and JavaScript (Vitest on Node 22). Actions are SHA-pinned to match the project's existing `update-data.yml` workflow. Tests run on push to `main` and on pull requests, with path filters so unrelated changes (like editing GeoJSON files) don't trigger unnecessary test runs.
