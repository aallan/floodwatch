#!/usr/bin/env python3
"""
Fetch flood monitoring and rainfall data from the Environment Agency API.
Saves data as CSV files for the static site.
"""
import argparse
import csv
import json
import os
import sys
import time
from datetime import datetime, timedelta, timezone
from urllib.request import urlopen, Request
from urllib.error import HTTPError, URLError
import re

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")

# River Taw level stations (upstream to downstream order by lat)
LEVEL_STATIONS = [
    {"id": "50149", "label": "Sticklepath", "rloi": "3100", "lat": 50.737824, "lon": -3.917597, "river": "River Taw", "type": "level"},
    {"id": "50119", "label": "Taw Bridge", "rloi": "3123", "lat": 50.845457, "lon": -3.886253, "river": "River Taw", "type": "level"},
    {"id": "50132", "label": "Newnham Bridge", "rloi": "3113", "lat": 50.939901, "lon": -3.907581, "river": "River Taw", "type": "level"},
    {"id": "50140", "label": "Umberleigh", "rloi": "3106", "lat": 50.99542, "lon": -3.985089, "river": "River Taw", "type": "level"},
    {"id": "50198", "label": "Barnstaple (Tidal)", "rloi": "9013", "lat": 51.080046, "lon": -4.064537, "river": "River Taw", "type": "tidal", "measure_id": "50198-level-tidal_level-i-15_min-mAOD"},
    # River Mole tributary stations (upstream to downstream)
    {"id": "50135", "label": "North Molton", "rloi": "3110", "lat": 51.055152, "lon": -3.795036, "river": "River Mole", "type": "level"},
    {"id": "50153", "label": "Mole Mills", "rloi": "3096", "lat": 51.016893, "lon": -3.822486, "river": "River Mole", "type": "level"},
    {"id": "50115", "label": "Woodleigh", "rloi": "3127", "lat": 50.973061, "lon": -3.909695, "river": "River Mole", "type": "level"},
    # Little Dart River tributary station
    {"id": "50125", "label": "Chulmleigh", "rloi": "3118", "lat": 50.907767, "lon": -3.863651, "river": "Little Dart River", "type": "level"},
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

API_BASE = "https://environment.data.gov.uk/flood-monitoring"


def api_get(url, retries=3):
    """Fetch JSON from the API with retries."""
    for attempt in range(retries):
        try:
            req = Request(url, headers={"Accept": "application/json"})
            with urlopen(req, timeout=60) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except (HTTPError, URLError, TimeoutError) as e:
            print(f"  Attempt {attempt+1}/{retries} failed for {url}: {e}")
            if attempt < retries - 1:
                time.sleep(2 ** attempt)
            else:
                raise


def get_measure_id(station):
    """Get the measure ID for a station."""
    if "measure_id" in station:
        return station["measure_id"]
    if station["type"] in ("level", "tidal"):
        return f"{station['id']}-level-stage-i-15_min-m"
    else:
        return f"{station['id']}-rainfall-tipping_bucket_raingauge-t-15_min-mm"


def fetch_readings_batch(measure_id, start_date, end_date):
    """Fetch readings for a date range (API handles up to ~1 month well)."""
    url = f"{API_BASE}/id/measures/{measure_id}/readings?startdate={start_date}&enddate={end_date}&_sorted&_limit=100000"
    try:
        data = api_get(url)
        return data.get("items", [])
    except Exception as e:
        print(f"  Warning: Could not fetch {start_date} to {end_date}: {e}")
        return []


def fetch_all_readings(station, going_back_days=365*2):
    """Fetch all available readings for a station, going back as far as possible."""
    measure_id = get_measure_id(station)

    all_readings = []
    end_date = datetime.now(timezone.utc).date()

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

        readings = fetch_readings_batch(
            measure_id,
            current_start.isoformat(),
            current_end.isoformat()
        )

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


def load_existing_csv(filename):
    """Load existing readings from a CSV file as a list of dicts."""
    filepath = os.path.join(DATA_DIR, filename)
    if not os.path.exists(filepath):
        return []
    readings = []
    with open(filepath, "r") as f:
        reader = csv.DictReader(f)
        for row in reader:
            readings.append({"dateTime": row["dateTime"], "value": row["value"]})
    return readings


def merge_readings(existing, new_readings):
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


def save_readings_csv(station, readings, filename):
    """Save readings to a CSV file."""
    filepath = os.path.join(DATA_DIR, filename)
    with open(filepath, "w", newline="") as f:
        writer = csv.writer(f)
        unit = "mm" if station["type"] == "rainfall" else ("mAOD" if station["type"] == "tidal" else "m")
        writer.writerow(["dateTime", "value", "unit", "station_id", "station_label"])
        for r in readings:
            val = r.get("value", "")
            dt = r.get("dateTime", "")
            if dt and val != "":
                writer.writerow([dt, val, unit, station["id"], station["label"]])
    print(f"  Saved {len(readings)} readings to {filepath}")


def save_stations_csv():
    """Save station metadata to CSV."""
    filepath = os.path.join(DATA_DIR, "stations.csv")
    with open(filepath, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["id", "label", "lat", "lon", "river", "type", "rloi", "measure_id"])
        for s in LEVEL_STATIONS:
            writer.writerow([
                s["id"], s["label"], s["lat"], s["lon"],
                s.get("river", ""), s["type"],
                s.get("rloi", ""), get_measure_id(s)
            ])
        for s in RAINFALL_STATIONS:
            writer.writerow([
                s["id"], s["label"], s["lat"], s["lon"],
                "", s["type"],
                "", get_measure_id(s)
            ])
    print(f"Saved station metadata to {filepath}")


def get_station_filename(station):
    """Get the CSV filename for a station."""
    if station["type"] == "rainfall":
        return f"rainfall_{station['id']}.csv"
    safe_label = re.sub(r'[^a-z0-9_()-]', '_', station['label'].lower().replace(' ', '_'))
    safe_id = re.sub(r'[^a-zA-Z0-9_-]', '', station['id'])
    return f"level_{safe_id}_{safe_label}.csv"


def main():
    parser = argparse.ArgumentParser(description="Fetch EA flood monitoring data")
    parser.add_argument("--recent", type=int, metavar="DAYS", nargs="?", const=2,
                        help="Only fetch recent data (default: 2 days) and merge with existing CSVs")
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

    print("\n=== Done ===")
    print(f"All data saved to {DATA_DIR}/")


if __name__ == "__main__":
    main()
