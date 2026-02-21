# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/), and this project adheres to [Semantic Versioning](https://semver.org/).

## [Unreleased]

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

[Unreleased]: https://github.com/aallan/floodwatch/compare/v1.0.0...HEAD
[1.0.0]: https://github.com/aallan/floodwatch/compare/v0.6.0...v1.0.0
[0.6.0]: https://github.com/aallan/floodwatch/compare/v0.5.0...v0.6.0
[0.5.0]: https://github.com/aallan/floodwatch/compare/v0.4.0...v0.5.0
[0.4.0]: https://github.com/aallan/floodwatch/compare/v0.3.0...v0.4.0
[0.3.0]: https://github.com/aallan/floodwatch/compare/v0.2.0...v0.3.0
[0.2.0]: https://github.com/aallan/floodwatch/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/aallan/floodwatch/releases/tag/v0.1.0
