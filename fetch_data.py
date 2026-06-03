#!/usr/bin/env python3
"""
Fetch flood monitoring and rainfall data from the Environment Agency API.
Saves data as CSV files for the static site.
"""

import argparse
import csv
import json
import os
import random
import re
import tempfile
import time
from datetime import UTC, datetime, timedelta
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

DATA_DIR: str = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")

# Station dict type — level stations have extra keys (rloi, river, measure_id)
# but all have at least these.
type StationInfo = dict[str, Any]

# River Taw level stations (upstream to downstream order by lat)
LEVEL_STATIONS = [
    {"id": "50149", "label": "Sticklepath", "rloi": "3100", "lat": 50.737824, "lon": -3.917597, "river": "River Taw", "type": "level"},
    {"id": "50119", "label": "Taw Bridge", "rloi": "3123", "lat": 50.845457, "lon": -3.886253, "river": "River Taw", "type": "level"},
    {"id": "50132", "label": "Newnham Bridge", "rloi": "3113", "lat": 50.939901, "lon": -3.907581, "river": "River Taw", "type": "level"},
    {"id": "50140", "label": "Umberleigh", "rloi": "3106", "lat": 50.99542, "lon": -3.985089, "river": "River Taw", "type": "level"},
    {
        "id": "50198",
        "label": "Barnstaple (Tidal)",
        "rloi": "9013",
        "lat": 51.080046,
        "lon": -4.064537,
        "river": "River Taw",
        "type": "tidal",
        "measure_id": "50198-level-tidal_level-i-15_min-mAOD",
    },
    # River Mole tributary stations (upstream to downstream)
    {"id": "50135", "label": "North Molton", "rloi": "3110", "lat": 51.055152, "lon": -3.795036, "river": "River Mole", "type": "level"},
    {"id": "50153", "label": "Mole Mills", "rloi": "3096", "lat": 51.016893, "lon": -3.822486, "river": "River Mole", "type": "level"},
    {"id": "50115", "label": "Woodleigh", "rloi": "3127", "lat": 50.973061, "lon": -3.909695, "river": "River Mole", "type": "level"},
    # Little Dart River tributary station
    {
        "id": "50125",
        "label": "Chulmleigh",
        "rloi": "3118",
        "lat": 50.907767,
        "lon": -3.863651,
        "river": "Little Dart River",
        "type": "level",
    },
    # River Yeo tributary stations (upstream to downstream)
    {"id": "50151", "label": "Lapford", "rloi": "3098", "lat": 50.857808, "lon": -3.810592, "river": "River Yeo", "type": "level"},
    {"id": "50114", "label": "Collard Bridge", "rloi": "3128", "lat": 51.099972, "lon": -4.010005, "river": "River Yeo", "type": "level"},
]

# Nearby rainfall stations
RAINFALL_STATIONS = [
    # East of Taw
    {"id": "50199", "label": "Lapford Bowerthy", "lat": 50.873373, "lon": -3.798545, "type": "rainfall"},
    {"id": "E85220", "label": "Molland Sindercombe", "lat": 51.037989, "lon": -3.736447, "type": "rainfall"},
    {"id": "E84360", "label": "Crediton Knowle", "lat": 50.799653, "lon": -3.737529, "type": "rainfall"},
    {"id": "45183", "label": "Kinsford Gate", "lat": 51.114443, "lon": -3.795033, "type": "rainfall"},
    # West of Taw
    {"id": "50103", "label": "Allisland", "lat": 50.880864, "lon": -4.152815, "type": "rainfall"},
    {"id": "50194", "label": "Kenwith Castle", "lat": 51.024089, "lon": -4.236452, "type": "rainfall"},
    {"id": "E82120", "label": "Bratton Fleming Haxton", "lat": 51.116609, "lon": -3.940857, "type": "rainfall"},
    {"id": "47158", "label": "Halwill", "lat": 50.771514, "lon": -4.228634, "type": "rainfall"},
]

API_BASE: str = "https://environment.data.gov.uk/flood-monitoring"

# Reading type — a single measurement from the API or loaded from CSV
type Reading = dict[str, Any]


# ============================================================
# CSO (Combined Sewer Overflow) — South West Water EDM feed
# ============================================================
# Near-real-time spill status from South West Water's contribution to Water
# UK's National Storm Overflow Hub. Open ArcGIS REST API — no auth, hit
# directly. Updated within ~1h of an EDM sensor reporting state change.
#
# The feed only exposes the MOST RECENT event per site (latestEventStart /
# latestEventEnd), so we accumulate a per-site event log by polling hourly
# and detecting state transitions.

# Layer 0 of the SWW Storm Overflow Activity FeatureServer (1,374 sites SWW-wide).
CSO_LIVE_URL: str = "https://services-eu1.arcgis.com/OMdMOtfhATJPcHe3/arcgis/rest/services/NEH_outlets_PROD/FeatureServer/0/query"

# Rivers in the Taw catchment that we monitor. Substring-matched against
# the FeatureServer's `receivingWaterCourse` field, case-insensitive.
# (Server-side filtering — keeps the response to ~75 sites.)
CSO_RIVER_ALLOWLIST: list[str] = [
    "TAW",
    "MOLE",
    "YEO",
    "LITTLE DART",
    "DALCH",
    "BRAY",
    "CROOKED OAK",
    "NADRID",
    "CASTLE HILL",
    "MULLY",
    "HAWKRIDGE",
    "HAWKBRIDGE",
    "BRYN BROOK",
    "COMMON LAKE",
    "GOODLEIGH",
]
# Substrings that EXCLUDE a site even if it matched above. Example: the
# Bideford Yeo is a Torridge tributary, not part of our Taw catchment,
# but shares the "YEO" substring with our Barnstaple Yeo.
CSO_RIVER_EXCLUDE: list[str] = ["TORRIDGE", "VENN", "DODSCOTT", "BIDEFORD"]

# CSO live-feed status values. -1 (offline) is treated as a distinct
# visual state, not collapsed with "not discharging".
CSO_STATUS_ACTIVE: int = 1
CSO_STATUS_QUIET: int = 0
CSO_STATUS_OFFLINE: int = -1


def _atomic_write_csv(filepath: str, write_fn) -> None:
    """Write a CSV atomically: temp file, fsync, rename over target."""
    dir_path = os.path.dirname(filepath) or "."
    fd, tmp_path = tempfile.mkstemp(dir=dir_path, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", newline="") as f:
            write_fn(f)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_path, filepath)
    except BaseException:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise


def api_get(url: str, retries: int = 3) -> dict[str, Any]:
    """Fetch JSON from the API with retries."""
    for attempt in range(retries):
        try:
            req = Request(url, headers={"Accept": "application/json"})
            with urlopen(req, timeout=60) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except (HTTPError, URLError, TimeoutError) as e:
            print(f"  Attempt {attempt + 1}/{retries} failed for {url}: {e}")
            if attempt < retries - 1:
                time.sleep(2**attempt + random.uniform(0, 1))
            else:
                raise


def get_measure_id(station: StationInfo) -> str:
    """Get the measure ID for a station."""
    if "measure_id" in station:
        return station["measure_id"]
    if station["type"] in ("level", "tidal"):
        return f"{station['id']}-level-stage-i-15_min-m"
    else:
        return f"{station['id']}-rainfall-tipping_bucket_raingauge-t-15_min-mm"


def fetch_readings_batch(measure_id: str, start_date: str, end_date: str) -> list[Reading]:
    """Fetch readings for a date range (API handles up to ~1 month well)."""
    url = f"{API_BASE}/id/measures/{measure_id}/readings?startdate={start_date}&enddate={end_date}&_sorted&_limit=100000"
    try:
        data = api_get(url)
        return data.get("items", [])
    except Exception as e:
        print(f"  Warning: Could not fetch {start_date} to {end_date}: {e}")
        return []


def fetch_all_readings(station: StationInfo, going_back_days: int = 365 * 2) -> list[Reading]:
    """Fetch all available readings for a station, going back as far as possible."""
    measure_id = get_measure_id(station)

    all_readings = []
    end_date = datetime.now(UTC).date()

    # The API provides recent data (up to ~4 weeks) directly
    # For older data, we use date ranges which the API supports
    # We'll try going back in monthly chunks

    current_end = end_date
    chunk_days = 28  # ~1 month chunks
    start_limit = end_date - timedelta(days=going_back_days)

    print(f"  Fetching data from {start_limit} to {current_end}...")

    empty_chunks = 0
    while current_end > start_limit and empty_chunks < 3:
        current_start = current_end - timedelta(days=chunk_days)
        if current_start < start_limit:
            current_start = start_limit

        readings = fetch_readings_batch(measure_id, current_start.isoformat(), current_end.isoformat())

        if readings:
            all_readings.extend(readings)
            empty_chunks = 0
            print(f"    {current_start} to {current_end}: {len(readings)} readings")
        else:
            empty_chunks += 1
            print(f"    {current_start} to {current_end}: no data (empty streak: {empty_chunks})")

        current_end = current_start - timedelta(days=1)
        time.sleep(0.3)  # Be polite to the API

    # Deduplicate by dateTime
    seen = set()
    unique = []
    for r in all_readings:
        dt = r.get("dateTime", "")
        if dt and dt not in seen:
            seen.add(dt)
            unique.append(r)

    # Sort by dateTime
    unique.sort(key=lambda x: x.get("dateTime", ""))

    return unique


def load_existing_csv(filename: str) -> list[Reading]:
    """Load existing readings from a CSV file as a list of dicts."""
    filepath = os.path.join(DATA_DIR, filename)
    if not os.path.exists(filepath):
        return []
    readings = []
    with open(filepath) as f:
        reader = csv.DictReader(f)
        for row in reader:
            readings.append({"dateTime": row["dateTime"], "value": row["value"]})
    return readings


def merge_readings(existing: list[Reading], new_readings: list[Reading]) -> list[Reading]:
    """Merge existing and new readings, deduplicate, and sort."""
    combined = existing + new_readings
    seen = set()
    unique = []
    for r in combined:
        dt = r.get("dateTime", "")
        if dt and dt not in seen:
            seen.add(dt)
            unique.append(r)
    unique.sort(key=lambda x: x.get("dateTime", ""))
    return unique


def save_readings_csv(station: StationInfo, readings: list[Reading], filename: str) -> None:
    """Save readings to a CSV file (atomic write)."""
    filepath = os.path.join(DATA_DIR, filename)
    unit = "mm" if station["type"] == "rainfall" else ("mAOD" if station["type"] == "tidal" else "m")

    def write_fn(f):
        writer = csv.writer(f)
        writer.writerow(["dateTime", "value", "unit", "station_id", "station_label"])
        for r in readings:
            val = r.get("value", "")
            dt = r.get("dateTime", "")
            if dt and val != "":
                writer.writerow([dt, val, unit, station["id"], station["label"]])

    _atomic_write_csv(filepath, write_fn)
    print(f"  Saved {len(readings)} readings to {filepath}")


def save_stations_csv() -> None:
    """Save station metadata to CSV (atomic write)."""
    filepath = os.path.join(DATA_DIR, "stations.csv")

    def write_fn(f):
        writer = csv.writer(f)
        writer.writerow(["id", "label", "lat", "lon", "river", "type", "rloi", "measure_id"])
        for s in LEVEL_STATIONS:
            writer.writerow([s["id"], s["label"], s["lat"], s["lon"], s.get("river", ""), s["type"], s.get("rloi", ""), get_measure_id(s)])
        for s in RAINFALL_STATIONS:
            writer.writerow([s["id"], s["label"], s["lat"], s["lon"], "", s["type"], "", get_measure_id(s)])

    _atomic_write_csv(filepath, write_fn)
    print(f"Saved station metadata to {filepath}")


def get_station_filename(station: StationInfo) -> str:
    """Get the CSV filename for a station."""
    if station["type"] == "rainfall":
        return f"rainfall_{station['id']}.csv"
    safe_label = re.sub(r'[^a-z0-9_()-]', '_', station['label'].lower().replace(' ', '_'))
    safe_id = re.sub(r'[^a-zA-Z0-9_-]', '', station['id'])
    return f"level_{safe_id}_{safe_label}.csv"


# ============================================================
# CSO helpers
# ============================================================


def _epoch_ms_to_iso(ms: int | None) -> str:
    """Convert ArcGIS epoch milliseconds to ISO 8601 UTC, or '' if None."""
    if ms is None:
        return ""
    return datetime.fromtimestamp(ms / 1000, tz=UTC).isoformat().replace("+00:00", "Z")


def _build_cso_where_clause() -> str:
    """Build a server-side SQL WHERE filtering to South West Water sites in
    the Taw catchment, matched by the receivingWaterCourse field."""
    field = "receivingWaterCourse"
    likes = " OR ".join(f"UPPER({field}) LIKE '%{r}%'" for r in CSO_RIVER_ALLOWLIST)
    nots = " AND ".join(f"UPPER({field}) NOT LIKE '%{e}%'" for e in CSO_RIVER_EXCLUDE)
    return f"company='South West Water' AND ({likes}) AND ({nots})"


def api_post(url: str, params: dict[str, str], retries: int = 3) -> dict[str, Any]:
    """POST form-encoded params to an ArcGIS REST endpoint.

    Use POST (not GET) when the WHERE clause may exceed ~2KB — ArcGIS
    silently returns 404 on URLs above its undocumented limit rather than
    a clean 414, which is genuinely confusing to debug.
    """
    body = urlencode(params).encode()
    for attempt in range(retries):
        try:
            req = Request(url, data=body, headers={"Content-Type": "application/x-www-form-urlencoded", "Accept": "application/json"})
            with urlopen(req, timeout=60) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except (HTTPError, URLError, TimeoutError) as e:
            print(f"  Attempt {attempt + 1}/{retries} failed for {url}: {e}")
            if attempt < retries - 1:
                time.sleep(2**attempt + random.uniform(0, 1))
            else:
                raise


def fetch_cso_catchment_sites() -> list[dict[str, Any]]:
    """Fetch all SWW CSO sites in the Taw catchment with current status.

    Returns a list of attribute dicts as returned by the FeatureServer, with
    one extra normalised field: `_river_title` (title-cased river name).
    """
    params = {
        "where": _build_cso_where_clause(),
        "outFields": "Id,company,receivingWaterCourse,status,statusStart,latestEventStart,latestEventEnd,lastUpdated,latitude,longitude",
        "returnGeometry": "false",
        "resultRecordCount": "2000",
        "f": "json",
    }
    data = api_post(CSO_LIVE_URL, params)
    sites = []
    for feat in data.get("features", []):
        attrs = feat.get("attributes", {})
        attrs["_river_title"] = (attrs.get("receivingWaterCourse") or "").title()
        sites.append(attrs)
    sites.sort(key=lambda s: s.get("Id") or "")
    return sites


# CSO event log: per-site CSV recording each spill episode.
# Columns: start_time (ISO-Z), end_time (ISO-Z or ''), duration_min (or ''), is_ongoing (true|false)
CSO_EVENT_COLUMNS: list[str] = ["start_time", "end_time", "duration_min", "is_ongoing"]


def _cso_events_path(site_id: str) -> str:
    return os.path.join(DATA_DIR, f"cso_{site_id}.csv")


def read_cso_events(site_id: str) -> list[dict[str, str]]:
    """Load the existing event log for a site (empty list if absent)."""
    path = _cso_events_path(site_id)
    if not os.path.exists(path):
        return []
    with open(path) as f:
        return list(csv.DictReader(f))


def update_cso_events(site: dict[str, Any], existing: list[dict[str, str]]) -> list[dict[str, str]]:
    """Apply a new live-feed observation to the per-site event log.

    The live feed exposes only the MOST RECENT event (latestEventStart /
    latestEventEnd). We compare against our stored tail and:
      - append a new event when latestEventStart is newer than our last,
      - close an ongoing event when status flips to 0 (not discharging),
      - leave the log unchanged when the API row matches our tail.

    Sub-hour events between polls will be missed — this is an inherent
    limitation of polling at hourly granularity, not a fixable bug.
    """
    events = [dict(e) for e in existing]  # don't mutate caller's list
    api_start_iso = _epoch_ms_to_iso(site.get("latestEventStart"))
    api_end_iso = _epoch_ms_to_iso(site.get("latestEventEnd"))
    api_status = site.get("status")

    if not api_start_iso:
        # Site has never spilled (or EDM commissioned with no events yet)
        return events

    tail = events[-1] if events else None

    if tail and tail["start_time"] == api_start_iso:
        # Same event we already have — possibly newly ended
        if tail.get("is_ongoing") == "true" and api_status == CSO_STATUS_QUIET:
            tail["end_time"] = api_end_iso
            tail["duration_min"] = _duration_minutes(api_start_iso, api_end_iso)
            tail["is_ongoing"] = "false"
        return events

    # New event since our last poll.
    if tail and tail.get("is_ongoing") == "true":
        # Previous event finished without us seeing the transition. Best-effort:
        # mark it ended at this new event's start time (the actual end could be
        # any moment between our last poll and now).
        tail["end_time"] = api_start_iso
        tail["duration_min"] = _duration_minutes(tail["start_time"], api_start_iso)
        tail["is_ongoing"] = "false"

    new_event = {
        "start_time": api_start_iso,
        "end_time": api_end_iso if api_status == CSO_STATUS_QUIET else "",
        "duration_min": _duration_minutes(api_start_iso, api_end_iso) if api_status == CSO_STATUS_QUIET else "",
        "is_ongoing": "true" if api_status == CSO_STATUS_ACTIVE else "false",
    }
    events.append(new_event)
    return events


def _duration_minutes(start_iso: str, end_iso: str) -> str:
    """Compute integer minutes between two ISO timestamps, as string. '' on bad input."""
    if not start_iso or not end_iso:
        return ""
    try:
        s = datetime.fromisoformat(start_iso.replace("Z", "+00:00"))
        e = datetime.fromisoformat(end_iso.replace("Z", "+00:00"))
        return str(max(0, int((e - s).total_seconds() / 60)))
    except (ValueError, TypeError):
        return ""


def save_cso_events_csv(site_id: str, events: list[dict[str, str]]) -> None:
    """Atomically write the per-site event log."""
    path = _cso_events_path(site_id)

    def write_fn(f):
        writer = csv.DictWriter(f, fieldnames=CSO_EVENT_COLUMNS)
        writer.writeheader()
        writer.writerows(events)

    _atomic_write_csv(path, write_fn)


def save_cso_sites_csv(sites: list[dict[str, Any]]) -> None:
    """Write the site metadata CSV (stable across runs, edited only when sites change)."""
    filepath = os.path.join(DATA_DIR, "cso_sites.csv")

    def write_fn(f):
        writer = csv.writer(f)
        writer.writerow(["id", "river", "lat", "lon"])
        for s in sites:
            writer.writerow([s.get("Id"), s.get("_river_title"), s.get("latitude"), s.get("longitude")])

    _atomic_write_csv(filepath, write_fn)
    print(f"  Saved {len(sites)} CSO sites to {filepath}")


def save_cso_status_json(sites: list[dict[str, Any]]) -> None:
    """Atomically write a current-snapshot JSON of all sites' status.

    Frontend reads this once at startup to colour markers — saves loading
    50+ per-site CSVs just to determine the initial marker colour.
    """
    filepath = os.path.join(DATA_DIR, "cso_status.json")
    snapshot: dict[str, Any] = {
        "generated_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        "sites": {
            s.get("Id"): {
                "status": s.get("status"),
                "statusStart": _epoch_ms_to_iso(s.get("statusStart")),
                "latestEventStart": _epoch_ms_to_iso(s.get("latestEventStart")),
                "latestEventEnd": _epoch_ms_to_iso(s.get("latestEventEnd")),
                "lastUpdated": _epoch_ms_to_iso(s.get("lastUpdated")),
            }
            for s in sites
        },
    }

    dir_path = os.path.dirname(filepath) or "."
    fd, tmp_path = tempfile.mkstemp(dir=dir_path, suffix=".tmp")
    try:
        with os.fdopen(fd, "w") as f:
            json.dump(snapshot, f, indent=2)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_path, filepath)
    except BaseException:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise
    print(f"  Saved status snapshot ({len(sites)} sites) to {filepath}")


def process_cso() -> None:
    """Top-level CSO fetcher orchestration. Non-fatal on failure — EA station
    fetches must not depend on the CSO feed being up."""
    print("\n=== CSO (Combined Sewer Overflow) feed ===")
    try:
        sites = fetch_cso_catchment_sites()
    except Exception as e:
        print(f"  ERROR fetching CSO live feed (skipping CSO update): {e}")
        return

    print(f"  Fetched {len(sites)} sites from SWW FeatureServer")
    active = sum(1 for s in sites if s.get("status") == CSO_STATUS_ACTIVE)
    offline = sum(1 for s in sites if s.get("status") == CSO_STATUS_OFFLINE)
    print(f"  Currently discharging: {active}    Monitor offline: {offline}")

    save_cso_sites_csv(sites)
    save_cso_status_json(sites)

    appended = 0
    closed = 0
    for site in sites:
        site_id = site.get("Id")
        if not site_id:
            continue
        existing = read_cso_events(site_id)
        updated = update_cso_events(site, existing)
        if len(updated) > len(existing):
            appended += 1
        elif existing and updated and existing[-1] != updated[-1]:
            closed += 1
        save_cso_events_csv(site_id, updated)
    print(f"  Event logs: appended {appended} new events, closed {closed} ongoing events")


def main() -> None:
    parser = argparse.ArgumentParser(description="Fetch EA flood monitoring data")
    parser.add_argument(
        "--recent",
        type=int,
        metavar="DAYS",
        nargs="?",
        const=2,
        help="Only fetch recent data (default: 2 days) and merge with existing CSVs",
    )
    args = parser.parse_args()

    os.makedirs(DATA_DIR, exist_ok=True)

    # Save station metadata
    save_stations_csv()

    all_stations = LEVEL_STATIONS + RAINFALL_STATIONS
    going_back = args.recent if args.recent else 365 * 2

    if args.recent:
        print(f"\n=== Recent mode: fetching last {going_back} days and merging ===")
    else:
        print(f"\n=== Full mode: fetching up to {going_back} days of history ===")

    for station in all_stations:
        print(f"\nStation: {station['label']} ({station['id']})")
        filename = get_station_filename(station)

        new_readings = fetch_all_readings(station, going_back_days=going_back)

        if args.recent:
            existing = load_existing_csv(filename)
            readings = merge_readings(existing, new_readings)
            print(f"  Merged: {len(existing)} existing + {len(new_readings)} new = {len(readings)} total")
        else:
            readings = new_readings

        save_readings_csv(station, readings, filename)

    # CSO live feed — runs every invocation. Failure is non-fatal so EA
    # station fetches above don't get rolled back.
    process_cso()

    print("\n=== Done ===")
    print(f"All data saved to {DATA_DIR}/")


if __name__ == "__main__":
    main()
