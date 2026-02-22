#!/usr/bin/env python3
"""
Floodwatch local development server.

Usage:
    python serve.py              # Start on port 8080 (localhost only)
    python serve.py 3000         # Start on custom port
    python serve.py --bind ::    # Listen on all interfaces
    python serve.py --stop       # Stop running server

Serves the static site and handles refresh.php requests
by proxying directly to the EA Flood Monitoring API.
"""

import csv
import json
import os
import random
import signal
import socket
import sys
import tempfile
import time as _time
import urllib.error
import urllib.request
from datetime import UTC, datetime, timedelta
from http.server import HTTPServer, SimpleHTTPRequestHandler
from typing import Any, TypedDict

PORT: int = 8080
PID_FILE: str = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.server.pid')
_last_refresh: float = 0
_REFRESH_MIN_INTERVAL: int = 300  # 5 minutes
DATA_DIR: str = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data')
API_BASE: str = 'https://environment.data.gov.uk/flood-monitoring'


class StationDict(TypedDict):
    id: str
    label: str
    type: str
    measureId: str
    file: str


STATIONS: list[StationDict] = [
    # Level stations
    {
        'id': '50149',
        'label': 'Sticklepath',
        'type': 'level',
        'measureId': '50149-level-stage-i-15_min-m',
        'file': 'level_50149_sticklepath.csv',
    },
    {
        'id': '50119',
        'label': 'Taw Bridge',
        'type': 'level',
        'measureId': '50119-level-stage-i-15_min-m',
        'file': 'level_50119_taw_bridge.csv',
    },
    {
        'id': '50132',
        'label': 'Newnham Bridge',
        'type': 'level',
        'measureId': '50132-level-stage-i-15_min-m',
        'file': 'level_50132_newnham_bridge.csv',
    },
    {
        'id': '50140',
        'label': 'Umberleigh',
        'type': 'level',
        'measureId': '50140-level-stage-i-15_min-m',
        'file': 'level_50140_umberleigh.csv',
    },
    {
        'id': '50198',
        'label': 'Barnstaple (Tidal)',
        'type': 'tidal',
        'measureId': '50198-level-tidal_level-i-15_min-mAOD',
        'file': 'level_50198_barnstaple_(tidal).csv',
    },
    # River Mole
    {
        'id': '50135',
        'label': 'North Molton',
        'type': 'level',
        'measureId': '50135-level-stage-i-15_min-m',
        'file': 'level_50135_north_molton.csv',
    },
    {
        'id': '50153',
        'label': 'Mole Mills',
        'type': 'level',
        'measureId': '50153-level-stage-i-15_min-m',
        'file': 'level_50153_mole_mills.csv',
    },
    {
        'id': '50115',
        'label': 'Woodleigh',
        'type': 'level',
        'measureId': '50115-level-stage-i-15_min-m',
        'file': 'level_50115_woodleigh.csv',
    },
    # Little Dart
    {
        'id': '50125',
        'label': 'Chulmleigh',
        'type': 'level',
        'measureId': '50125-level-stage-i-15_min-m',
        'file': 'level_50125_chulmleigh.csv',
    },
    # River Yeo
    {'id': '50151', 'label': 'Lapford', 'type': 'level', 'measureId': '50151-level-stage-i-15_min-m', 'file': 'level_50151_lapford.csv'},
    {
        'id': '50114',
        'label': 'Collard Bridge',
        'type': 'level',
        'measureId': '50114-level-stage-i-15_min-m',
        'file': 'level_50114_collard_bridge.csv',
    },
    # Rainfall - East
    {
        'id': '50199',
        'label': 'Lapford Bowerthy',
        'type': 'rainfall',
        'measureId': '50199-rainfall-tipping_bucket_raingauge-t-15_min-mm',
        'file': 'rainfall_50199.csv',
    },
    {
        'id': 'E85220',
        'label': 'Molland Sindercombe',
        'type': 'rainfall',
        'measureId': 'E85220-rainfall-tipping_bucket_raingauge-t-15_min-mm',
        'file': 'rainfall_E85220.csv',
    },
    {
        'id': 'E84360',
        'label': 'Crediton Knowle',
        'type': 'rainfall',
        'measureId': 'E84360-rainfall-tipping_bucket_raingauge-t-15_min-mm',
        'file': 'rainfall_E84360.csv',
    },
    {
        'id': '45183',
        'label': 'Kinsford Gate',
        'type': 'rainfall',
        'measureId': '45183-rainfall-tipping_bucket_raingauge-t-15_min-mm',
        'file': 'rainfall_45183.csv',
    },
    # Rainfall - West
    {
        'id': '50103',
        'label': 'Allisland',
        'type': 'rainfall',
        'measureId': '50103-rainfall-tipping_bucket_raingauge-t-15_min-mm',
        'file': 'rainfall_50103.csv',
    },
    {
        'id': '50194',
        'label': 'Kenwith Castle',
        'type': 'rainfall',
        'measureId': '50194-rainfall-tipping_bucket_raingauge-t-15_min-mm',
        'file': 'rainfall_50194.csv',
    },
    {
        'id': 'E82120',
        'label': 'Bratton Fleming Haxton',
        'type': 'rainfall',
        'measureId': 'E82120-rainfall-tipping_bucket_raingauge-t-15_min-mm',
        'file': 'rainfall_E82120.csv',
    },
    {
        'id': '47158',
        'label': 'Halwill',
        'type': 'rainfall',
        'measureId': '47158-rainfall-tipping_bucket_raingauge-t-15_min-mm',
        'file': 'rainfall_47158.csv',
    },
]


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


def api_get(url: str, timeout: int = 60, retries: int = 3) -> dict[str, Any] | None:
    """Fetch JSON from the EA API with retries and exponential backoff."""
    for attempt in range(retries):
        req = urllib.request.Request(url, headers={'Accept': 'application/json'})
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return json.loads(resp.read().decode())
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as e:
            print(f'  API error (attempt {attempt + 1}/{retries}): {e}')
            if attempt < retries - 1:
                _time.sleep(2**attempt + random.uniform(0, 1))
    return None


def refresh_station(station: StationDict) -> dict[str, Any]:
    """Fetch new readings for a station since the last known timestamp."""
    csv_path = os.path.join(DATA_DIR, station['file'])
    existing_times = set()
    existing_rows = []
    latest_time = None

    # Read existing CSV
    if os.path.exists(csv_path):
        with open(csv_path, newline='') as f:
            reader = csv.reader(f)
            next(reader, None)  # skip header
            for row in reader:
                if len(row) >= 2:
                    existing_times.add(row[0])
                    existing_rows.append(row)
                    if latest_time is None or row[0] > latest_time:
                        latest_time = row[0]

    now = datetime.now(UTC)
    items = []

    if latest_time:
        last_dt = datetime.fromisoformat(latest_time.replace('Z', '+00:00'))
        gap_days = (now - last_dt).days

        if gap_days <= 5:
            url = f"{API_BASE}/id/measures/{station['measureId']}/readings?since={urllib.request.quote(latest_time)}&_sorted&_limit=10000"
            data = api_get(url)
            if data:
                items = data.get('items', [])
        else:
            # Fetch in 28-day chunks
            chunk_end = now
            start_limit = last_dt
            while chunk_end > start_limit:
                chunk_start = chunk_end - timedelta(days=28)
                if chunk_start < start_limit:
                    chunk_start = start_limit
                url = (
                    f"{API_BASE}/id/measures/{station['measureId']}/readings"
                    f"?startdate={chunk_start.strftime('%Y-%m-%d')}"
                    f"&enddate={chunk_end.strftime('%Y-%m-%d')}"
                    f"&_sorted&_limit=100000"
                )
                data = api_get(url)
                if data:
                    items.extend(data.get('items', []))
                chunk_end = chunk_start - timedelta(days=1)
    else:
        # No existing data
        start_date = now - timedelta(days=28)
        url = (
            f"{API_BASE}/id/measures/{station['measureId']}/readings"
            f"?startdate={start_date.strftime('%Y-%m-%d')}"
            f"&enddate={now.strftime('%Y-%m-%d')}"
            f"&_sorted&_limit=100000"
        )
        data = api_get(url)
        if data:
            items = data.get('items', [])

    # Merge new readings
    unit = 'mm' if station['type'] == 'rainfall' else ('mAOD' if station['type'] == 'tidal' else 'm')
    new_count = 0
    for item in items:
        dt = item.get('dateTime', '')
        val = item.get('value', '')
        if dt and val != '' and dt not in existing_times:
            existing_rows.append([dt, str(val), unit, station['id'], station['label']])
            existing_times.add(dt)
            new_count += 1

    if new_count > 0:
        existing_rows.sort(key=lambda r: r[0])

        def write_fn(f):
            writer = csv.writer(f)
            writer.writerow(['dateTime', 'value', 'unit', 'station_id', 'station_label'])
            writer.writerows(existing_rows)

        _atomic_write_csv(csv_path, write_fn)

    return {'id': station['id'], 'label': station['label'], 'new_readings': new_count, 'total': len(existing_rows)}


def handle_refresh() -> str:
    """Run refresh for all stations, return JSON result."""
    results = []
    updated = 0
    for station in STATIONS:
        print(f'  Refreshing {station["label"]}...')
        try:
            result = refresh_station(station)
            results.append(result)
            if result['new_readings'] > 0:
                updated += 1
                print(f'    +{result["new_readings"]} readings ({result["total"]} total)')
            else:
                print('    No new data')
        except Exception as e:
            print(f'    Error: {e}')
            results.append({'id': station['id'], 'label': station['label'], 'error': str(e)})

    return json.dumps(
        {'success': True, 'timestamp': datetime.now(UTC).isoformat(), 'stations_updated': updated, 'details': results}, indent=2
    )


class FloodwatchHandler(SimpleHTTPRequestHandler):
    """Serve static files + handle refresh.php endpoint."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=os.path.dirname(os.path.abspath(__file__)), **kwargs)

    # Content-Security-Policy — restricts which resources the browser may load.
    # All JS is in external files so script-src needs no 'unsafe-inline'.
    # style-src keeps 'unsafe-inline' because Leaflet divIcon HTML strings
    # contain dynamic inline styles (rotation angles, colours) that cannot
    # be expressed as static CSS classes.
    CSP = (
        "default-src 'self'; "
        "script-src 'self' https://unpkg.com https://cdn.jsdelivr.net; "
        "style-src 'self' 'unsafe-inline' https://unpkg.com; "
        "img-src 'self' data: https://*.basemaps.cartocdn.com https://*.tile.openstreetmap.org; "
        "connect-src 'self' https://environment.data.gov.uk https://api.open-meteo.com "
        "https://flood-api.open-meteo.com https://unpkg.com https://cdn.jsdelivr.net; "
        "font-src 'self'; "
        "object-src 'none'; "
        "base-uri 'self'"
    )

    def end_headers(self):
        # CSP on all responses
        self.send_header('Content-Security-Policy', self.CSP)
        # Prevent browser caching of data files so refreshes are always fresh
        path = self.path.split('?')[0]  # strip query string
        if path.endswith('.csv') or path.endswith('.geojson'):
            self.send_header('Cache-Control', 'no-cache, no-store, must-revalidate')
            self.send_header('Pragma', 'no-cache')
            self.send_header('Expires', '0')
        super().end_headers()

    def do_POST(self):
        global _last_refresh
        if self.path == '/refresh.php' or self.path == '/refresh':
            now = _time.time()
            elapsed = now - _last_refresh
            if _last_refresh and elapsed < _REFRESH_MIN_INTERVAL:
                self.send_response(429)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                retry_after = int(_REFRESH_MIN_INTERVAL - elapsed)
                self.wfile.write(json.dumps({'success': False, 'error': 'Too many requests', 'retry_after': retry_after}).encode())
                return
            _last_refresh = now
            print('Refresh requested...')
            result = handle_refresh()
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(result.encode())
        else:
            self.send_error(404)

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()

    def log_message(self, format, *args):
        # Quieter logging — skip noisy asset requests
        msg = format % args
        if '.csv' not in msg and '.geojson' not in msg and '.js' not in msg and '.css' not in msg and '.png' not in msg:
            print(f'  {msg}')


def write_pid() -> None:
    with open(PID_FILE, 'w') as f:
        f.write(str(os.getpid()))


def read_pid() -> int | None:
    if os.path.exists(PID_FILE):
        with open(PID_FILE) as f:
            try:
                return int(f.read().strip())
            except ValueError:
                return None
    return None


def stop_server() -> None:
    pid = read_pid()
    if pid:
        try:
            os.kill(pid, signal.SIGTERM)
            print(f'Stopped server (PID {pid})')
        except ProcessLookupError:
            print(f'Server not running (stale PID {pid})')
        try:
            os.remove(PID_FILE)
        except OSError:
            pass
    else:
        print('No server running')


class ReusableHTTPServer(HTTPServer):
    """HTTPServer with SO_REUSEADDR and dual-stack (IPv4 + IPv6) support.

    macOS resolves 'localhost' to ::1 (IPv6) first, so we must listen on
    IPv6 to avoid connection timeouts in the browser.  Setting
    address_family to AF_INET6 and enabling IPV6_V6ONLY=0 (the default
    on macOS) lets the socket accept both IPv4 and IPv6 connections.
    """

    address_family = socket.AF_INET6
    allow_reuse_address = True
    allow_reuse_port = True


def start_server(port: int, bind_addr: str = '::1') -> None:
    # Check if already running via PID file
    pid = read_pid()
    if pid:
        try:
            os.kill(pid, 0)  # Check if process exists
            print(f'Server already running on PID {pid}. Stopping it first...')
            os.kill(pid, signal.SIGTERM)
            import time

            time.sleep(1)
        except ProcessLookupError:
            pass
        try:
            os.remove(PID_FILE)
        except OSError:
            pass

    server = ReusableHTTPServer((bind_addr, port), FloodwatchHandler)
    write_pid()

    def cleanup():
        try:
            os.remove(PID_FILE)
        except OSError:
            pass

    def handle_sigterm(sig, frame):
        """SIGTERM (from `serve.py stop`) — call shutdown from a thread to
        unblock serve_forever(), which runs in the main thread."""
        import threading

        threading.Thread(target=server.shutdown, daemon=True).start()

    signal.signal(signal.SIGTERM, handle_sigterm)

    print(f"""
╔══════════════════════════════════════════╗
║   Floodwatch Dev Server                  ║
║   http://localhost:{port:<5}                 ║
║                                          ║
║   Press Ctrl+C to stop                   ║
╚══════════════════════════════════════════╝
""")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    print('Shutting down...')
    server.server_close()
    cleanup()


if __name__ == '__main__':
    args = sys.argv[1:]

    if '--stop' in args or 'stop' in args:
        stop_server()
    else:
        port = PORT
        bind_addr = '::1'
        i = 0
        while i < len(args):
            if args[i] in ('--bind', '-b') and i + 1 < len(args):
                bind_addr = args[i + 1]
                i += 2
            elif args[i].isdigit():
                port = int(args[i])
                i += 1
            else:
                i += 1
        start_server(port, bind_addr)
