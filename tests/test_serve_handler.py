"""Tests for serve.py — FloodwatchHandler HTTP behaviour."""
import csv
import json
import os
import sys
import threading
import time
import urllib.request
import urllib.error
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

import serve


@pytest.fixture
def server(tmp_path, monkeypatch):
    """Start FloodwatchHandler on a random port, yield base URL, then shut down."""
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    monkeypatch.setattr(serve, "DATA_DIR", str(data_dir))
    monkeypatch.setattr(serve, "_last_refresh", 0)

    # Write a sample CSV so we can test cache headers
    sample_csv = data_dir / "test.csv"
    with open(sample_csv, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["dateTime", "value"])
        writer.writerow(["2026-01-01T00:00:00Z", "0.5"])

    # Mock refresh_station to avoid real API calls
    monkeypatch.setattr(
        serve, "refresh_station",
        lambda s: {"id": s["id"], "label": s["label"], "new_readings": 0, "total": 100}
    )

    httpd = serve.ReusableHTTPServer(("::1", 0), serve.FloodwatchHandler)
    port = httpd.server_address[1]
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()

    yield f"http://[::1]:{port}"

    httpd.shutdown()
    httpd.server_close()


class TestFloodwatchHandler:
    def test_post_refresh_returns_200(self, server):
        """POST /refresh.php returns 200 with valid JSON."""
        req = urllib.request.Request(f"{server}/refresh.php", method="POST", data=b"")
        with urllib.request.urlopen(req, timeout=10) as resp:
            assert resp.status == 200
            body = json.loads(resp.read())
            assert body["success"] is True

    def test_rate_limiting_returns_429(self, server, monkeypatch):
        """Second POST within 5 minutes returns 429."""
        # First request succeeds
        req1 = urllib.request.Request(f"{server}/refresh.php", method="POST", data=b"")
        with urllib.request.urlopen(req1, timeout=10) as resp:
            assert resp.status == 200

        # Second request should be rate-limited
        req2 = urllib.request.Request(f"{server}/refresh.php", method="POST", data=b"")
        with pytest.raises(urllib.error.HTTPError) as exc_info:
            urllib.request.urlopen(req2, timeout=10)
        assert exc_info.value.code == 429
        body = json.loads(exc_info.value.read())
        assert body["success"] is False
        assert "retry_after" in body

    def test_options_returns_cors_headers(self, server):
        """OPTIONS /refresh returns CORS headers."""
        req = urllib.request.Request(f"{server}/refresh", method="OPTIONS")
        with urllib.request.urlopen(req, timeout=10) as resp:
            assert resp.status == 200
            assert "POST" in resp.headers.get("Access-Control-Allow-Methods", "")

    def test_csv_has_no_cache_headers(self, server):
        """GET for a .csv file includes Cache-Control: no-cache.

        Uses an actual CSV from the project's data/ directory since
        FloodwatchHandler serves from the script's own directory.
        """
        with urllib.request.urlopen(f"{server}/data/stations.csv", timeout=10) as resp:
            assert resp.status == 200
            cache_control = resp.headers.get("Cache-Control", "")
            assert "no-cache" in cache_control

    def test_post_to_unknown_path_returns_404(self, server):
        """POST to a non-refresh path returns 404."""
        req = urllib.request.Request(f"{server}/unknown", method="POST", data=b"")
        with pytest.raises(urllib.error.HTTPError) as exc_info:
            urllib.request.urlopen(req, timeout=10)
        assert exc_info.value.code == 404
