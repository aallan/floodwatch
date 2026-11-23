# Floodwatch

![Floodwatch in a Safari window: the River Taw catchment in north Devon, with river level gauges as teal circles showing their readings in metres, rain gauges as drops, storm overflows spilling now as dark purple dots, clusters of gauges as white circles with a count, the Tarka and Dartmoor lines, a flood alert banner under the header and the layers legend open at the bottom left](docs/screenshot.png)

Floodwatch shows what the River Taw is doing: how high each gauge is and whether it's rising, how much rain has fallen in the last hour, which storm overflows are spilling, and what flood and weather warnings are in force across the catchment, from Dartmoor to Barnstaple. It runs at [tawriver.watch](https://tawriver.watch).

Everything on the map is public data, from the Environment Agency, South West Water, the Met Office, National Grid Electricity Distribution and others, read every five minutes. Floodwatch also keeps what those sources don't: the Environment Agency's API holds about four weeks of readings, and South West Water's feed only each overflow's latest spill, so Floodwatch has kept every reading since 13 January 2026 and every spill since 3 June 2026, and serves the lot.

The site is one page with no framework and no build step. The server, the poller and the map-data builder use only the Python standard library, with readings kept in SQLite.

- [What the map shows](#what-the-map-shows)
- [Data sources](#data-sources)
- [Running it](#running-it), locally and on a server
- [The archive](#the-archive)
- [How it works](#how-it-works)
- [Tests](#tests), [project layout](#project-layout), [contributing](#contributing) and [licence](#licence)

## What the map shows

### Gauges

The Environment Agency's gauges are the map's main layer, each with its latest reading printed on it.

| Marker | Reading | Colour |
|---|---|---|
| Circle | River level, in metres | Teal; amber once within 30% of the top of the gauge's typical range; red above it |
| Diamond | Tidal level at Barnstaple, in metres above Ordnance Datum | Orange |
| Drop | Rain in the last hour, in millimetres | Blue; a small pale drop with no number when it hasn't rained |

River and tidal gauges carry a badge with an arrow when the level is rising, falling or steady, from a straight line fitted to the last hour's readings; a change of less than 1 cm an hour counts as steady. A gauge that has sent nothing for three hours turns grey and smaller.

Gauges that would overlap on screen are gathered into a white circle with a count until zoom 13. Its edge takes the most urgent level among them, amber or red, and it carries a rising badge if any river among them is rising. Hovering lists each gauge and its reading, and clicking zooms in.

Clicking a gauge opens its chart for the last 24 hours, 7 days or 28 days, or all time. Over all time each point is the highest level, or the total rain, in an hour or more, so a flood isn't averaged away. River charts mark the top of the typical range and the record high. Rain gauges add the next 48 hours of forecast rain. The gauge at Umberleigh adds a fortnight's river flow forecast for the Taw, set against the flow measured there. Every gauge's popup links to a CSV of every reading it has.

The map shows the gauges inside the catchment, and the rain gauges up to 2 km over its watershed, such as Kinsford Gate on Exmoor, since rain falling there runs into the Taw.

### Storm overflows

South West Water's storm overflows in the catchment release storm sewage into the rivers and the estuary when heavy rain overloads the sewers. Each is a purple dot, larger at a sewage treatment works than on the sewer network or at a pumping station.

| Dot | Meaning | Shown |
|---|---|---|
| Dark purple, with a halo | Spilling now | When the page opens |
| Mid purple | Spilled in the last 48 hours | Once switched on in the legend |
| Pale purple | No spill in the last 48 hours | Once switched on, from zoom 11 |
| Hollow grey | Monitor offline | Once switched on, from zoom 11 |

An overflow's popup shows its spills over the last 30 days and its spill hours and count for each year from the regulatory annual returns. South West Water's names are spelt out: "Chulmleigh WWTW SSO" is Chulmleigh wastewater treatment works' settled storm overflow.

### Warnings

While the Environment Agency has a flood warning or alert in force in the catchment, a bar under the header says so, giving the area's name when there's one and a count by severity when there are more. Opening it lists each with the Agency's message and a "Show on map" button. A warning's area is outlined on the map; an alert covers a wide area, so its area is a faint tint. While nothing is in force, a green tag in the header says so.

The Met Office's yellow, amber and red warnings that name Devon get a bar of their own, in the warning's colour.

### Drought and power cuts

A tag in the header gives the Environment Agency's drought status for its Devon, Cornwall and Isles of Scilly area, from its weekly report, and South West Water's hosepipe ban when there is one. The report words some stages by reservoir, so the tag opens to show each one as written.

National Grid Electricity Distribution's power cuts in the catchment are dark discs with a yellow bolt, larger the more customers are off. Each popup gives the customers off and back on, when power is expected back, and the postcodes affected.

### Background

The rivers come from OpenStreetMap, the seven Floodwatch has always shown in their own colours and with their names: the Taw, the Mole, the Little Dart, the River Yeo through Barnstaple, the Lapford Yeo, the Crooked Oak and Hollocombe Water. The catchment's other rivers are pale blue and named on hover, and its streams can be switched on from zoom 12. Rivers end where they meet the estuary, rather than running down the middle of it.

The Tarka Line runs from Barnstaple into Exeter St Davids and Exeter Central, with the Dartmoor Line off it to Okehampton. The A377 and the A30 west of Exeter are the only roads drawn, and the catchment's outline can be switched on from the legend.

The page follows the system's light or dark setting, with a toggle to override it.

## Data sources

| Data | Source | Read | Licence |
|---|---|---|---|
| River, tidal and rain gauges | Environment Agency [real-time flood-monitoring API](https://environment.data.gov.uk/flood-monitoring/doc/reference) | Every 5 minutes | [Open Government Licence](https://www.nationalarchives.gov.uk/doc/open-government-licence/version/3/) |
| Flood warnings and alerts, and their areas | The same API | Every 5 minutes | Open Government Licence |
| Storm overflows | South West Water's [storm overflow activity feed](https://www.arcgis.com/home/item.html?id=cabfce76b72a4a278a33d737c0708d42) | Every 5 minutes | [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) |
| Storm overflow names, types and yearly totals | Event Duration Monitoring [annual returns](https://www.arcgis.com/home/item.html?id=66fef44a4aab438991d7ce08fbc1de64) | Daily | Open Government Licence |
| Weather warnings | Met Office [weather warnings](https://weather.metoffice.gov.uk/warnings-and-advice/uk-warnings) for South West England | Every 5 minutes | [Met Office terms](https://www.metoffice.gov.uk/policies/tandc) |
| Drought status and hosepipe bans | Environment Agency's weekly [Dry weather and drought in England](https://www.gov.uk/government/publications/dry-weather-and-drought-in-england-2026-summary-reports) report, through the [GOV.UK Content API](https://content-api.publishing.service.gov.uk/) | Every 6 hours | Open Government Licence |
| Power cuts | NGED's [live power cuts](https://connecteddata.nationalgrid.co.uk/dataset/live-power-cuts) | Every 5 minutes | [NGED Open Data Licence](https://www.nationalgrid.co.uk/open-data-licence) |
| Rain forecast | [Open-Meteo](https://open-meteo.com/) weather forecast API | When a popup asks, kept 15 minutes | CC BY 4.0 |
| River flow forecast | GloFAS, from the Copernicus Emergency Management Service, through Open-Meteo's [flood API](https://open-meteo.com/en/docs/flood-api) | When a popup asks, kept an hour | CC BY 4.0 |
| Measured river flow | Environment Agency [Hydrology API](https://environment.data.gov.uk/hydrology/doc/reference) | When a popup asks, kept 15 minutes | Open Government Licence |
| Mean river flow | UK [National River Flow Archive](https://nrfa.ceh.ac.uk/) | When needed, kept a week | [NRFA terms](https://nrfa.ceh.ac.uk/help/costs-terms-and-conditions) |
| Catchment boundary | Environment Agency [WFD operational catchments](https://services3.arcgis.com/Bb8lfThdhugyc4G3/ArcGIS/rest/services/WFD_Surface_Water_Operational_Catchments_Cycle3/FeatureServer) and the [Catchment Data Explorer](https://environment.data.gov.uk/catchment-planning/)'s river water bodies | Weekly | Open Government Licence |
| Rivers, streams, railways, stations, roads and place names | [OpenStreetMap](https://www.openstreetmap.org/), through the Overpass API | Weekly | [ODbL](https://www.openstreetmap.org/copyright) |
| Basemap | Esri World Light Gray and Dark Gray Canvas | Loaded by the page | [Esri terms](https://www.esri.com/en-us/legal/terms/full-master-agreement) |

## Running it

### Locally

You'll need Python 3.10 or later, `make`, `curl` and `shasum`, and Node 22 or later for the JavaScript tests.

```bash
git clone https://github.com/aallan/floodwatch.git
cd floodwatch
make libs     # download Leaflet and Leaflet.markercluster into site/lib, and check them against libs.sha256
make data     # build the map overlays in site/data
make serve    # serve the site at http://localhost:8090, polling every 5 minutes
```

The first poll lists the gauges and storm overflows, loads the history in `archive/`, then reads the warnings, power cuts and drought report and fills in each gauge's last four weeks from the Environment Agency, four gauges at a time. The gauges appear within a minute or two; the history fill takes a few minutes more.

`make data` takes a few minutes on a first run, most of it waiting on the public [Overpass API](https://wiki.openstreetmap.org/wiki/Overpass_API) servers. Downloads are cached in `.cache/overpass/` for a day:

```bash
python3 scripts/fetch_geodata.py --refresh   # ignore the cache and download everything again
python3 scripts/fetch_geodata.py --cached    # rebuild from the cache, however old
```

The other targets:

```bash
make poll     # run one poll of every feed, without the server
make test     # run the Python and JavaScript tests
make og       # redraw the link preview card, site/img/og-image.png (needs Google Chrome and make data)
make screenshot  # retake docs/screenshot.png, the map in a Safari window, from the running server (needs Google Chrome)
make clean    # remove the libraries, overlays and download cache; the database stays
```

### On a server

The public site runs as one process on an Ubuntu 24.04 server, with [Caddy](https://caddyserver.com/) in front for HTTPS, and pushes the archive back to this repository every night. `deploy/` holds the configuration:

```
deploy/floodwatch.service           the web server and poller
deploy/floodwatch-data.service      rebuilds the map overlays
deploy/floodwatch-data.timer        runs that rebuild early every Sunday
deploy/floodwatch-archive.service   exports the archive, commits it and pushes it
deploy/floodwatch-archive.timer     runs that at 02:30 every night
deploy/Caddyfile                    HTTPS for tawriver.watch, and the redirect from www
```

Point the domain's DNS at the server first, A and AAAA records for the bare name and `www`, so Caddy can get its certificates when it starts. Then, as root:

```bash
apt update && apt install -y git make curl gnupg python3 debian-keyring debian-archive-keyring apt-transport-https
curl -1sLf https://dl.cloudsmith.io/public/caddy/stable/gpg.key | gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
curl -1sLf https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt > /etc/apt/sources.list.d/caddy-stable.list
apt update && apt install -y caddy

useradd --system --home-dir /srv/floodwatch --shell /usr/sbin/nologin floodwatch
install -d -o floodwatch -g floodwatch -m 750 /srv/floodwatch /srv/floodwatch/.ssh
runuser -u floodwatch -- ssh-keygen -t ed25519 -N '' -C floodwatch-archive -f /srv/floodwatch/.ssh/id_ed25519
cat /srv/floodwatch/.ssh/id_ed25519.pub
```

Add that public key to the repository as a deploy key with write access. The nightly archive pushes to `main`, whose branch protection requires the `python-tests` and `js-tests` checks, so the deploy key also needs to be allowed to bypass that rule, with a repository ruleset that lists deploy keys as a bypass actor. Then:

```bash
runuser -u floodwatch -- ssh -o StrictHostKeyChecking=accept-new -T git@github.com   # records GitHub's host key
cd /srv/floodwatch
runuser -u floodwatch -- git clone git@github.com:aallan/floodwatch.git .
runuser -u floodwatch -- make libs
runuser -u floodwatch -- make data

cp deploy/*.service deploy/*.timer /etc/systemd/system/
systemctl daemon-reload
systemctl enable --now floodwatch floodwatch-data.timer floodwatch-archive.timer
cp deploy/Caddyfile /etc/caddy/Caddyfile
systemctl reload caddy

ufw allow OpenSSH && ufw allow 80/tcp && ufw allow 443 && ufw --force enable
```

The service runs as the unprivileged `floodwatch` user and can write only to `data/`, `site/data/` and `.cache/`; the archive service writes only to `data/` and `.git`. Its log is in the journal, `journalctl -u floodwatch -f`, and the archive's in `journalctl -u floodwatch-archive`.

To update, pull and restart. The first poll after a restart reads every feed straight away, whatever its schedule:

```bash
cd /srv/floodwatch && runuser -u floodwatch -- git pull && systemctl restart floodwatch
```

## The archive

`archive/` holds every reading and spill Floodwatch has, in the CSV format v1 published:

- `stations.csv`, one row per gauge, with the series its readings are from
- `level_<id>_<name>.csv` and `rainfall_<id>.csv`, one per gauge, with every 15-minute reading: `dateTime,value,unit,station_id,station_label`
- `cso_<id>.csv`, one per storm overflow, with every spill: `start_time,end_time,duration_min,is_ongoing`

Every night `scripts/archive.py push` writes the database out to `archive/`, and commits and pushes the files that changed. It works in a separate git worktree, `data/archive-worktree`, reset to the tip of `main` each night, so the checkout the server runs from is never touched and a deploy's `git pull` stays a fast-forward; if a push fails, the next night starts afresh. A gauge's existing file is reused and written exactly as v1 wrote it, so a night's commit adds that day's lines and nothing else. Files of gauges that are no longer listed are left alone.

On a new server the first poll loads `archive/` into the database, once the gauges and overflows are listed, so a fresh deploy starts with all the history there is. Readings and spills it already holds are kept, so the load is safe to repeat; `python3 scripts/archive.py restore` runs it by hand, and loads v1's own `data/` directory too.

## How it works

The poller, in `monitor/`, runs every 5 minutes, reading each feed in turn: the gauges, the storm overflows, the flood warnings, the weather warnings, the power cuts and the drought report, and then filling any gaps in the gauges' history. The feeds are independent, so one failing doesn't stop the others, and every request gives up after two minutes, however slowly an answer arrives.

### The catchment

Two Environment Agency datasets make the catchment's outline. The WFD operational catchment "Taw and North Devon Streams" covers all the land draining to the Taw, Barnstaple included, and stops at the estuary's banks; but it also takes in the Exmoor coast, from Croyde round to Lynmouth. The river water bodies inside it are numbered by hydrometric area, and those draining to the Taw are in area 50, the same as the gauging station at Umberleigh; but they leave out the land draining straight into the estuary. The outline is the operational catchment wherever it's in one of the Taw's water bodies or in a box round the estuary, about 1,200 km². The two datasets were digitised separately, so they're combined on a grid about 5 m square and the outline traced from it.

The same builder writes the catchments around the Taw's: the Torridge, Barnstaple Bay, the Exmoor coast and the rest. Gauges, storm overflows, power cuts and flood areas belong to the catchment when they're inside it, or near it and nearer to it than to any of those, which takes in the outfalls and the tidal gauge in the estuary, outside the outline, and leaves out those just over the watershed. Flood areas are judged by their centre, and any the Agency lists on the Taw are kept wherever their centre falls.

### Gauges

Once a day the poller lists the Environment Agency's level and rainfall stations within 45 km, keeps those that belong to the catchment, and reads each river gauge's typical range and record high. Every 5 minutes it makes one request per kind of reading for the latest value from every station in England, keeps the catchment's, and writes `site/data/live.json`, about 10 KB with every gauge's latest reading, trend and state, which is everything the map needs to draw its markers.

A gauge whose newest reading is more than 15 minutes past what the database holds has missed some, because the server was down or because the gauge uploads in batches, so its readings are fetched from the last one held. A gauge's history is fetched from `/api/stations/<id>/readings` only when its popup opens. Up to 28 days the chart gets every reading; over a longer range, or all time, the readings are put into buckets of an hour or more, enough that the chart has no more than 3,000 points, keeping each bucket's highest level or its total rain. `/api/stations/<id>/readings.csv` returns every reading at full resolution.

### Storm overflows

South West Water's feed reports each overflow's current state and only its latest spill, so the spill log is built up by polling. Every 5 minutes the poller reads all of South West Water's overflows in one request and, for each of the catchment's, compares the latest spill with the last one logged: a new start time is a new spill, and the same start time with the overflow now quiet closes the open one. A spill that starts and ends between two polls is still caught, because the feed keeps it as the latest until the next one, but if two spills happen between polls the earlier is missed. Once a day the poller reads names, asset types and yearly totals from the annual returns, matching rows to overflows by permit ID; rows before 2024 are matched through South West Water's own permit reference.

### Flow forecast

Flow forecasts come from [GloFAS](https://global-flood.emergency.copernicus.eu/), the Copernicus global flood model, through Open-Meteo's flood API. GloFAS routes rivers on a grid of cells about 5 km across, so `scripts/calibrate_flow.py` compares the model's 2015–2024 flows in the 25 cells around Umberleigh with the gauged record, and the forecast uses the cell just upstream of the gauge, which carries the Taw. Its flows are scaled so their long-run mean matches the gauged mean, 18.3 m³/s, read from the National River Flow Archive. The flow measured at Umberleigh every 15 minutes comes from the Hydrology API, and the forecast is scaled again by the ratio of measured to modelled flow on the last full day, so it starts from the river as it is: its lowest flow so far is multiplied by the ratio, and any rise from rain is added at the model's own size.

### The map's overlays

`scripts/fetch_geodata.py` builds the catchment's outline and its neighbours, and fetches the rivers, streams, railways, stations, roads and place names from Overpass, writing simplified GeoJSON to `site/data/`. Each river is drawn from its OpenStreetMap ways grouped by name, joined source to mouth so its flow arrows point downstream, and ended at its tidal limit, where it crosses the coastline. Three rivers in the catchment are named River Yeo, so each is named after where it runs: River Yeo, Lapford Yeo and Molland Yeo. Where OpenStreetMap leaves a stretch of a river unnamed, such as 3.5 km of the Little Dart above Witheridge, a chain of up to six unnamed ways running from the end of one stretch to the start of the next joins the river. The railways come from the Tarka and Dartmoor lines' route relations, which list all the track their trains run on.

## Tests

`make test` runs both suites, which use only Python's `unittest` and Node's built-in test runner, so there's nothing to install beyond Python and Node. The 194 Python tests cover the poller, the gauges, the spill log, the archive's export, restore and nightly push, the history buckets and CSV download, which positions belong to the catchment, the overlay builder's outline tracing, river naming and gap filling, the warnings, the drought report, power cuts, forecasts, and the server's endpoints and headers; each runs against a temporary database, with every outside service replaced by fixed responses, several of them trimmed copies of real ones in `tests/fixtures/`. The 26 JavaScript tests load the page's scripts into a sandbox and check the gauges' states and numbers, what a cluster shows, the chart arithmetic, the flow forecast's scaling, the spelt-out overflow names, the warning banner's wording and the power cut popups. GitHub Actions runs both on every push to `main` and every pull request.

## Project layout

```
serve.py                   HTTP server for site/ and /api/, and the poller thread
monitor/poll.py            the 5-minute poll cycle
monitor/ea.py              Environment Agency client: stations, latest readings, history
monitor/live.py            writes site/data/live.json
monitor/history.py         a gauge's history for its chart, in buckets over long ranges, and as CSV
monitor/archive.py         exports to archive/ and restores from it
monitor/region.py          which positions belong to the catchment
monitor/overflows.py       South West Water storm overflows: list, spill log, yearly totals
monitor/floods.py          Environment Agency flood warnings and alerts, and their areas
monitor/weather.py         Met Office weather warnings for Devon
monitor/drought.py         Environment Agency drought status and hosepipe bans
monitor/powercuts.py       NGED's live power cuts in the catchment
monitor/forecast.py        rain and river flow forecasts, and measured flow
monitor/net.py             HTTP requests with a time limit on the whole answer
monitor/cache.py           popup data fetched on demand, with an in-memory cache
monitor/db.py              SQLite schema and connection
monitor/geo.py             geometry shared with the overlay builder
scripts/fetch_geodata.py   the catchment, its neighbours and the map's overlays
scripts/archive.py         export, restore and push the archive
scripts/calibrate_flow.py  finds the GloFAS cell that carries a river past a gauge
scripts/og_image.py        draws site/img/og-image.png, the link preview card
scripts/screenshot.py      takes docs/screenshot.png, the map in a Safari window
archive/                   every reading and spill, in v1's CSV format
site/index.html            the page
site/css/style.css         layout and theme, light and dark
site/js/map.js             basemap, overlays, markers, clusters, legend and the opening view
site/js/stations.js        gauge and overflow popups and their charts
site/js/floods.js          the flood warning banner and header tag
site/js/weather.js         the Met Office warning banner
site/js/drought.js         the drought tag
site/js/powercuts.js       power cut popups
site/js/app.js             tab routing, the status line and the version
site/js/utils.js           escaping, formatting and the theme toggle
tests/                     Python tests, one file per module, and fixtures/
tests/js/                  JavaScript tests
deploy/                    systemd units and the Caddyfile
libs.sha256                checksums for the downloaded libraries
```

## Contributing

Bug reports, corrections and pull requests are welcome; [CONTRIBUTING.md](CONTRIBUTING.md) covers setting up and the conventions. Everyone taking part is expected to follow the [code of conduct](CODE_OF_CONDUCT.md), and security problems should be reported as [SECURITY.md](.github/SECURITY.md) describes. Changes are listed in the [changelog](CHANGELOG.md).

## Licence

The code is released under the [MIT licence](LICENSE).

The map data is © OpenStreetMap contributors, under the [Open Database Licence](https://www.openstreetmap.org/copyright). This uses Environment Agency flood and river level data from the real-time data API (Beta), under the [Open Government Licence](https://www.nationalarchives.gov.uk/doc/open-government-licence/version/3/), as are the catchment boundaries, the measured river flows from the Hydrology API, and the drought reports, which are Crown copyright. Storm overflow activity is © South West Water, under [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/), and the overflow annual returns are © Environment Agency copyright and/or database right, under the Open Government Licence. Weather and river flow forecasts are from [Open-Meteo](https://open-meteo.com/), under CC BY 4.0, with river flows generated using Copernicus Emergency Management Service information. Mean river flows are data from the UK National River Flow Archive. Weather warnings are the Met Office's, and contain public sector information licensed under the Open Government Licence v3.0. Power cut data is from National Grid Electricity Distribution, under the [NGED Open Data Licence](https://www.nationalgrid.co.uk/open-data-licence): Supported by NGED Open Data. Basemap tiles are © [Esri](https://www.esri.com/). [Leaflet](https://leafletjs.com/) is released under the BSD 2-Clause licence, and [Leaflet.markercluster](https://github.com/Leaflet/Leaflet.markercluster) under the MIT licence.
