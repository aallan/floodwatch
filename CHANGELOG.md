# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/), and this project adheres to [Semantic Versioning](https://semver.org/).

## [Unreleased]

## [1.5.0] — 2026-06-03

### Added
- Storm overflow (CSO) layer covering ~75 South West Water sites in the Taw catchment, sourced live from SWW's contribution to Water UK's National Storm Overflow Hub (open ArcGIS REST FeatureServer)
- Per-site event log accumulator: `process_cso()` in `fetch_data.py` polls the live feed each hour, detects state transitions, and appends new events to `data/cso_<permit_id>.csv`. Idempotent — re-running with no upstream changes is a no-op
- CSO frontend layer: purple-shaded circle markers (status-driven colours), Tier-A markers (active or recent <48h) visible at all zoom levels, Tier-B markers (quiet, offline) fade in at zoom ≥ 11 to avoid catchment-overview clutter
- CSO popups with current state, asset type, permit ID, EDM last-ping, "This month" + "Last 30 days" spill totals, an adaptive recent-activity panel (event list for ≤3 events, daily-totals histogram for >3), and a multi-year annual hours bar chart
- "(monitoring started 3rd Jun 2026)" subtitle next to the "Last 30 days" heading so users understand the chart fills out as polling accumulates history
- One-off historical backfill (`fetch_cso_history.py`): pulls 2021–2025 annual returns from Water UK's All-Years FeatureServer, joins old WaSC permit refs to new DEFRA IDs, writes `data/cso_sites_meta.csv` + `data/cso_annual_history.csv`
- Marker hierarchy by asset type: 22px circles for major facilities (wastewater treatment works sites — Inlet SO at WwTW, Storm tank at WwTW); 14px for minor (sewer-network overflows, pumping stations)
- Hover tooltips on every CSO marker with the expanded site name ("Chulmleigh Wastewater Treatment Works Settled Storm Overflow" rather than the compressed "Chulmleigh WWTW SSO") so users unfamiliar with water-industry acronyms can identify markers at a glance
- Hover tooltips on every EA station marker (river-level, tidal, rainfall) showing the station name — complements the value already shown in-marker
- `expandAcronyms` helper expands water-industry shorthand (WWTW, STW, SSO, CSO, PS, etc.) in popup titles and tooltips
- 27 new Python tests covering the CSO event-log state machine (`tests/test_fetch_cso.py`)
- 50 new JavaScript tests covering CSO marker rendering, visual-state mapping, asset-type classification, acronym expansion, stats computation, overlap detection, and zoom-fade behaviour (`js-tests/floodwatch-cso.test.js`)
- New CSS variable `--accent-cso: #b48ed4` (bright lavender, readable on the dark popup background)

### Changed
- Legend reorganised into two columns on desktop (Monitoring Stations + Trend + Storm Overflow on the left; Rivers + Railway on the right) — halves the legend height and stops it overlapping Leaflet's zoom controls
- Test count: 104 → 181 (91 Python + 90 JavaScript)
- README "Data Source" section renamed to "Data Sources" and expanded with SWW + Annual Returns endpoints
- README hero image updated to show the deployed CSO layer alongside the existing marker types

## [1.4.1] — 2026-03-04

### Fixed
- Red console errors on static deployment — switched `detectBackend()` from POST to GET and `fetchFloodWarnings()` from `fetch()` to XHR so CORS failures are silent
- CSV fallback warning disappearing too quickly — added persistent "No live data fetched" line to refresh summary, extended display time

## [1.4.0] — 2026-03-04

### Added
- CORS fallback for Refresh Data — tries EA API first, falls back to cached CSV data (updated hourly by GitHub Actions) if CORS-blocked, auto-recovers when EA restores headers
- Explicit log messages distinguishing live EA API data from cached data during refresh

### Fixed
- `detectBackend()` false positive on static deployments — `refresh.php` exists as a static file, HEAD returned 200; switched to POST + JSON parse check
- Flood status bar not shown when EA API is unreachable — now displays default green status dot

## [1.3.1] — 2026-02-22

### Fixed
- Version tag and GitHub link not left-aligned on mobile — compound padding from `.header-meta` and `.github-link` overrides

## [1.3.0] — 2026-02-22

### Added
- Version tag displayed in site header next to "View on GitHub" link — shows git tag on releases, commit hash between releases
- `version.json` auto-updated by pre-commit hook via `git describe --tags --always`
- Pre-commit hook (`version-json`) in `.pre-commit-config.yaml` to keep version in sync

### Fixed
- Dartmoor Line GeoJSON trim adjusted — previous cut was too aggressive, leaving a visible gap near Colebrooke

### Changed
- Atomic file writes for all CSV operations (`fetch_data.py`, `serve.py`, `refresh.php`) — write to temp file, fsync, rename
- API retry with exponential backoff and jitter in `serve.py` (3 attempts, `2^n + random` delay)
- Bind warning when dev server listens on all interfaces (`::` or `0.0.0.0`)
- Added jitter to `fetch_data.py` backoff for consistency
- Test count: 95 → 104 (64 Python + 40 JavaScript)

## [1.2.0] — 2026-02-21

### Added
- Ruff linting and format checks in CI (`ruff check .`, `ruff format --check .`)
- Expanded ruff lint rules: `UP` (pyupgrade), `B` (bugbear), `SIM` (simplify), `RUF`
- ARIA attributes: `aria-live="polite"` on flood status, `aria-busy` on refresh button, `role="button"` and `aria-expanded` on flood warnings summary
- `prefers-reduced-motion` media query — disables spinner, warning pulse, and log slide-in animations
- Response validation (`if (!resp.ok)`) on all `fetch()` calls (GeoJSON overlays, EA API, flood warnings, backend sync)

### Fixed
- Red console error (`OPTIONS 405`) on every page load from backend detection — switched to silent `XMLHttpRequest`
- Data freshness timestamp and flood status delayed ~2s on load — show timestamp immediately after markers, run network probes non-blocking

### Changed
- Synced `pyproject.toml` version to `1.2.0`
- Pre-commit hooks now filter to Python files only (skip JS/CSS/JSON/GeoJSON)
- Expanded `.gitignore` with standard exclusions (`.env`, `venv/`, IDE dirs, `*.log`)
- Applied ruff auto-fixes: `timezone.utc` → `UTC` alias, removed redundant `"r"` mode args

## [1.1.0] — 2026-02-21

### Fixed
- Popup buttons (time range, forecast, tidal/discharge tabs) not responding to clicks after the v1.0.0 refactor — event delegation listener was registered after the popup had already opened
- Canvas loading text ("Loading forecast…", "Loading discharge data…") stretched and distorted — intrinsic canvas size was not synced to CSS display size before drawing

### Added
- 15 UI integration tests for `floodwatch.js` covering event delegation, canvas coordinate handling, popup HTML generation, init() wiring, and marker construction
- `sizeCanvasToDisplay()` helper that syncs canvas resolution to CSS display size with DPR scaling
- Test harness (`setup-ui.js`) that loads `floodwatch.js` into jsdom with mocked Leaflet, Chart.js, and Papa Parse

### Changed
- Test count: 80 → 95 (55 Python + 40 JavaScript)
- Updated project structure in README.md and CONTRIBUTING.md to reflect external CSS/JS files

## [1.0.0] — 2026-02-21

### Changed
- Extracted inline `<style>` (1,105 lines) to `css/floodwatch.css`
- Extracted inline `<script>` (1,662 lines) to `js/floodwatch.js`
- Replaced all `onclick` handlers with `addEventListener` event delegation
- Replaced inline `style` attributes with CSS classes or CSSOM
- Tightened CSP: removed `'unsafe-inline'` from `script-src`
- Added CDN domains to `connect-src` for source map loading
- `index.html` reduced from 2,842 lines to 75 lines

## [0.6.0] — 2026-02-21

### Added
- Pre-commit hooks with ruff (linting and formatting on every commit)
- Content-Security-Policy headers on all `serve.py` responses
- Python type hints on all function signatures in `fetch_data.py` and `serve.py`
- Prerequisites section in README, CONTRIBUTING.md, and TESTING.md
- Governance files: CONTRIBUTING.md, CODE_OF_CONDUCT.md, SECURITY.md, CHANGELOG.md
- Issue templates (bug report, feature request) and pull request template
- `.editorconfig` for consistent formatting across editors
- `.github/dependabot.yml` for automated dependency updates (pip, npm, GitHub Actions)
- Branch protection on `main` requiring CI to pass before merge

### Changed
- Python code reformatted by ruff (consistent style across all `.py` files)
- Removed 19 unused imports across Python source and test files
- `pyproject.toml` now includes ruff configuration (line length, lint rules, quote style)

## [0.5.0] — 2026-02-21

### Added
- Test suite with 80 tests: 55 Python (pytest) and 25 JavaScript (Vitest)
- CI workflow running Python and JS tests on push and pull request
- TESTING.md with full test documentation
- INSTALL.md with deployment guides for all four methods

### Changed
- README.md restructured — deployment and test documentation split into dedicated files

## [0.4.0] — 2026-02-20

### Added
- Security audit fixes: HTML escaping, input validation, Content-Security-Policy considerations
- Linked back to live site from README

### Fixed
- Tidal data corrected — all historical CSV rows now use mAOD instead of m

## [0.3.0] — 2026-02-13

### Added
- Open-Meteo rainfall forecast (48-hour) in station popups with Fcst toggle button
- River discharge forecast tab on Barnstaple (Tidal) popup — 7 days hindcast + 14 days forecast from GloFAS v4
- Normal flow and high flow (Q10) reference lines on discharge chart from NRFA 66-year record
- Catchment area display for discharge context

### Fixed
- Bug in catchment area calculation for river discharge

## [0.2.0] — 2026-02-12

### Added
- EA flood warnings and alerts banner — monitors 15 flood area IDs across the Taw catchment
- Tarka Line and Dartmoor Line railway overlays with station markers
- Dartmoor Line spur and Hollocombe Water tributary
- Warnings vs Alerts documentation in README

### Fixed
- Trend indicator calculation
- CSS popover styling

## [0.1.0] — 2026-02-11

### Added
- Interactive flood monitoring dashboard for the River Taw catchment
- 19 monitoring stations: 11 river level, 1 tidal, 8 rainfall (all from the EA Flood Monitoring API)
- Leaflet map with CartoDB Positron basemap and Chart.js time-series popups
- River overlays (Taw, Mole, Little Dart, Yeo, Lapford Yeo, Crooked Oak) with flow direction arrows
- Trend indicators (rising/falling/steady) via linear regression over last hour of readings
- High water level warning — markers turn red above 70% of typical range
- Mobile-responsive layout with two breakpoints (768px tablets, 480px phones)
- `fetch_data.py` — bulk historical data fetcher with 28-day chunking
- `serve.py` — local Python dev server with refresh proxy and rate limiting
- `refresh.php` — PHP refresh endpoint for LAMP deployments
- GitHub Actions workflow for hourly CSV data updates
- Digital Ocean App Platform deployment config (`.do/app.yaml`)
- Open Graph social media preview image

### Fixed
- Legend positioning on mobile (multiple iterations)
- Safari address bar overlap after refresh
- Text overflow in popup boxes
- GitHub Actions deprecation warning

[Unreleased]: https://github.com/aallan/floodwatch/compare/v1.5.0...HEAD
[1.5.0]: https://github.com/aallan/floodwatch/compare/v1.4.1...v1.5.0
[1.4.1]: https://github.com/aallan/floodwatch/compare/v1.4.0...v1.4.1
[1.4.0]: https://github.com/aallan/floodwatch/compare/v1.3.1...v1.4.0
[1.3.1]: https://github.com/aallan/floodwatch/compare/v1.3.0...v1.3.1
[1.3.0]: https://github.com/aallan/floodwatch/compare/v1.2.0...v1.3.0
[1.2.0]: https://github.com/aallan/floodwatch/compare/v1.1.0...v1.2.0
[1.1.0]: https://github.com/aallan/floodwatch/compare/v1.0.0...v1.1.0
[1.0.0]: https://github.com/aallan/floodwatch/compare/v0.6.0...v1.0.0
[0.6.0]: https://github.com/aallan/floodwatch/compare/v0.5.0...v0.6.0
[0.5.0]: https://github.com/aallan/floodwatch/compare/v0.4.0...v0.5.0
[0.4.0]: https://github.com/aallan/floodwatch/compare/v0.3.0...v0.4.0
[0.3.0]: https://github.com/aallan/floodwatch/compare/v0.2.0...v0.3.0
[0.2.0]: https://github.com/aallan/floodwatch/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/aallan/floodwatch/releases/tag/v0.1.0
