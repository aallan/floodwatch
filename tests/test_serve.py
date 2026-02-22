"""Tests for serve.py — dev server logic (non-HTTP functions)."""

import csv
import json
import os
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock
from urllib.error import URLError

sys.path.insert(0, str(Path(__file__).parent.parent))

import serve
from tests.conftest import make_mock_urlopen

# ============================================================
# api_get — retries with exponential backoff and jitter
# ============================================================


class TestServeApiGet:
    def test_success(self, monkeypatch):
        mock_resp = make_mock_urlopen({"items": [{"value": 1}]})
        monkeypatch.setattr("serve.urllib.request.urlopen", lambda *a, **kw: mock_resp)

        result = serve.api_get("http://example.com/test")
        assert result == {"items": [{"value": 1}]}

    def test_returns_none_after_retries_on_url_error(self, monkeypatch):
        call_count = 0

        def fail(*a, **kw):
            nonlocal call_count
            call_count += 1
            raise URLError("connection failed")

        monkeypatch.setattr("serve.urllib.request.urlopen", fail)
        monkeypatch.setattr("serve._time.sleep", lambda _: None)
        result = serve.api_get("http://example.com/test")
        assert result is None
        assert call_count == 3

    def test_returns_none_after_retries_on_bad_json(self, monkeypatch):
        mock_resp = MagicMock()
        mock_resp.read.return_value = b"not json"
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)

        monkeypatch.setattr("serve.urllib.request.urlopen", lambda *a, **kw: mock_resp)
        monkeypatch.setattr("serve._time.sleep", lambda _: None)
        result = serve.api_get("http://example.com/test")
        assert result is None

    def test_retry_then_success(self, monkeypatch):
        call_count = 0
        mock_resp = make_mock_urlopen({"items": []})

        def fake_urlopen(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise URLError("connection failed")
            return mock_resp

        monkeypatch.setattr("serve.urllib.request.urlopen", fake_urlopen)
        monkeypatch.setattr("serve._time.sleep", lambda _: None)

        result = serve.api_get("http://example.com/test", retries=3)
        assert result == {"items": []}
        assert call_count == 3

    def test_exponential_backoff_with_jitter(self, monkeypatch):
        sleep_calls = []

        def always_fail(*args, **kwargs):
            raise URLError("connection failed")

        monkeypatch.setattr("serve.urllib.request.urlopen", always_fail)
        monkeypatch.setattr("serve._time.sleep", lambda s: sleep_calls.append(s))

        serve.api_get("http://example.com/test", retries=3)

        assert len(sleep_calls) == 2
        assert 1.0 <= sleep_calls[0] < 2.0  # 2^0 + jitter
        assert 2.0 <= sleep_calls[1] < 3.0  # 2^1 + jitter


# ============================================================
# refresh_station — filesystem + HTTP mocking
# ============================================================


class TestRefreshStation:
    def _write_csv(self, data_dir, filename, rows):
        """Write a CSV with standard headers."""
        filepath = data_dir / filename
        with open(filepath, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["dateTime", "value", "unit", "station_id", "station_label"])
            for row in rows:
                writer.writerow(row)

    def test_no_existing_data_fetches_28_days(self, data_dir, monkeypatch):
        """When no CSV exists, fetches 28 days of data."""
        api_items = [
            {"dateTime": "2026-02-10T10:00:00Z", "value": 0.5},
            {"dateTime": "2026-02-10T10:15:00Z", "value": 0.6},
        ]
        monkeypatch.setattr(serve, "api_get", lambda url: {"items": api_items})

        station = serve.STATIONS[0]  # Sticklepath
        result = serve.refresh_station(station)
        assert result["new_readings"] == 2

        # Verify CSV was written
        assert (data_dir / station["file"]).exists()

    def test_small_gap_uses_since_param(self, data_dir, monkeypatch):
        """When gap <= 5 days, uses ?since= parameter."""
        station = serve.STATIONS[0]
        # Write existing CSV with data from 2 days ago
        two_days_ago = (datetime.now(UTC) - timedelta(days=2)).strftime("%Y-%m-%dT%H:%M:%SZ")
        self._write_csv(
            data_dir,
            station["file"],
            [
                [two_days_ago, "0.500", "m", station["id"], station["label"]],
            ],
        )

        captured_urls = []

        def mock_api_get(url):
            captured_urls.append(url)
            return {"items": [{"dateTime": "2026-02-20T10:00:00Z", "value": 0.55}]}

        monkeypatch.setattr(serve, "api_get", mock_api_get)

        serve.refresh_station(station)
        # Should have used ?since= (not startdate/enddate)
        assert any("since=" in url for url in captured_urls)

    def test_large_gap_uses_chunked_fetch(self, data_dir, monkeypatch):
        """When gap > 5 days, uses chunked date-range fetch."""
        station = serve.STATIONS[0]
        # Write existing CSV with data from 10 days ago
        ten_days_ago = (datetime.now(UTC) - timedelta(days=10)).strftime("%Y-%m-%dT%H:%M:%SZ")
        self._write_csv(
            data_dir,
            station["file"],
            [
                [ten_days_ago, "0.500", "m", station["id"], station["label"]],
            ],
        )

        def mock_api_get(url):
            return {"items": [{"dateTime": "2026-02-20T10:00:00Z", "value": 0.55}]}

        monkeypatch.setattr(serve, "api_get", mock_api_get)

        result = serve.refresh_station(station)
        assert result["new_readings"] >= 1

    def test_deduplicates_readings(self, data_dir, monkeypatch):
        """New readings with same dateTime as existing are not duplicated."""
        station = serve.STATIONS[0]
        existing_dt = (datetime.now(UTC) - timedelta(hours=2)).strftime("%Y-%m-%dT%H:%M:%SZ")
        self._write_csv(
            data_dir,
            station["file"],
            [
                [existing_dt, "0.500", "m", station["id"], station["label"]],
            ],
        )

        # API returns the same dateTime
        monkeypatch.setattr(serve, "api_get", lambda url: {"items": [{"dateTime": existing_dt, "value": 0.500}]})

        result = serve.refresh_station(station)
        assert result["new_readings"] == 0
        assert result["total"] == 1

    def test_tidal_station_unit(self, data_dir, monkeypatch):
        """Tidal station CSV rows use mAOD unit."""
        # Find the tidal station
        tidal = next(s for s in serve.STATIONS if s["type"] == "tidal")

        monkeypatch.setattr(serve, "api_get", lambda url: {"items": [{"dateTime": "2026-02-20T10:00:00Z", "value": 2.5}]})

        serve.refresh_station(tidal)

        # Read the CSV back and check the unit
        filepath = data_dir / tidal["file"]
        with open(filepath) as f:
            rows = list(csv.DictReader(f))
        assert rows[0]["unit"] == "mAOD"


# ============================================================
# write_pid / read_pid — PID file management
# ============================================================


class TestPidFile:
    def test_write_and_read(self, tmp_path, monkeypatch):
        pid_file = str(tmp_path / ".server.pid")
        monkeypatch.setattr(serve, "PID_FILE", pid_file)

        serve.write_pid()
        pid = serve.read_pid()
        assert pid == os.getpid()

    def test_read_no_file(self, tmp_path, monkeypatch):
        pid_file = str(tmp_path / "nonexistent.pid")
        monkeypatch.setattr(serve, "PID_FILE", pid_file)

        assert serve.read_pid() is None

    def test_read_corrupt_file(self, tmp_path, monkeypatch):
        pid_file = tmp_path / ".server.pid"
        pid_file.write_text("not_a_number")
        monkeypatch.setattr(serve, "PID_FILE", str(pid_file))

        assert serve.read_pid() is None


# ============================================================
# handle_refresh — integration test (mocked refresh_station)
# ============================================================


class TestHandleRefresh:
    def test_returns_valid_json(self, monkeypatch):
        monkeypatch.setattr(serve, "refresh_station", lambda s: {"id": s["id"], "label": s["label"], "new_readings": 0, "total": 100})

        result_json = serve.handle_refresh()
        result = json.loads(result_json)

        assert result["success"] is True
        assert "timestamp" in result
        assert len(result["details"]) == len(serve.STATIONS)

    def test_counts_updated_stations(self, monkeypatch):
        call_idx = 0

        def mock_refresh(s):
            nonlocal call_idx
            call_idx += 1
            nr = 5 if call_idx <= 3 else 0  # first 3 stations get new readings
            return {"id": s["id"], "label": s["label"], "new_readings": nr, "total": 100}

        monkeypatch.setattr(serve, "refresh_station", mock_refresh)
        result = json.loads(serve.handle_refresh())
        assert result["stations_updated"] == 3


# ============================================================
# _atomic_write_csv — atomic file write in serve.py
# ============================================================


class TestAtomicWriteServe:
    def test_no_temp_files_after_refresh(self, data_dir, monkeypatch):
        """After refresh_station, no .tmp files remain in the data dir."""
        station = serve.STATIONS[0]
        monkeypatch.setattr(serve, "api_get", lambda url: {"items": [{"dateTime": "2026-02-20T10:00:00Z", "value": 0.55}]})

        serve.refresh_station(station)

        tmp_files = list(Path(str(data_dir)).glob("*.tmp"))
        assert tmp_files == []


# ============================================================
# start_server — bind warning
# ============================================================


class TestBindWarning:
    def _run_start_server(self, monkeypatch, tmp_path, capsys, bind_addr):
        mock_server = MagicMock()
        mock_server.server_address = (bind_addr, 8080)
        mock_server.serve_forever.side_effect = KeyboardInterrupt

        monkeypatch.setattr(serve, "ReusableHTTPServer", lambda addr, handler: mock_server)
        monkeypatch.setattr(serve, "PID_FILE", str(tmp_path / ".server.pid"))
        monkeypatch.setattr(serve, "read_pid", lambda: None)

        serve.start_server(8080, bind_addr)
        return capsys.readouterr()

    def test_warns_on_all_interfaces(self, monkeypatch, tmp_path, capsys):
        captured = self._run_start_server(monkeypatch, tmp_path, capsys, '::')
        assert "publicly accessible" in captured.out

    def test_no_warning_on_localhost(self, monkeypatch, tmp_path, capsys):
        captured = self._run_start_server(monkeypatch, tmp_path, capsys, '::1')
        assert "publicly accessible" not in captured.out
