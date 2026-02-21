"""Tests for fetch_data.py — data pipeline functions."""
import csv
import io
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, call, patch
from urllib.error import URLError

import pytest

# Ensure project root is importable
sys.path.insert(0, str(Path(__file__).parent.parent))

import fetch_data
from tests.conftest import make_mock_urlopen


# ============================================================
# get_measure_id — pure function, no mocking needed
# ============================================================

class TestGetMeasureId:
    def test_level_station(self, sample_station_level):
        """Level stations use the standard stage format."""
        result = fetch_data.get_measure_id(sample_station_level)
        assert result == "50140-level-stage-i-15_min-m"

    def test_rainfall_station(self, sample_station_rainfall):
        """Rainfall stations use the tipping bucket format."""
        result = fetch_data.get_measure_id(sample_station_rainfall)
        assert result == "50199-rainfall-tipping_bucket_raingauge-t-15_min-mm"

    def test_tidal_station_with_custom_measure_id(self, sample_station_tidal):
        """Tidal station with explicit measure_id key uses the custom value."""
        result = fetch_data.get_measure_id(sample_station_tidal)
        assert result == "50198-level-tidal_level-i-15_min-mAOD"

    def test_level_station_without_custom_key(self):
        """Level station without measure_id key derives it from type."""
        station = {"id": "50149", "label": "Sticklepath", "type": "level"}
        result = fetch_data.get_measure_id(station)
        assert result == "50149-level-stage-i-15_min-m"

    def test_tidal_without_custom_key_falls_through_to_level(self):
        """Tidal without measure_id uses level format (type in ('level', 'tidal'))."""
        station = {"id": "50198", "label": "Barnstaple", "type": "tidal"}
        result = fetch_data.get_measure_id(station)
        assert result == "50198-level-stage-i-15_min-m"


# ============================================================
# get_station_filename — pure function with regex sanitisation
# ============================================================

class TestGetStationFilename:
    def test_level_station(self):
        station = {"id": "50140", "label": "Umberleigh", "type": "level"}
        assert fetch_data.get_station_filename(station) == "level_50140_umberleigh.csv"

    def test_rainfall_station(self):
        """Rainfall stations use a simpler format — just id."""
        station = {"id": "E85220", "label": "Molland Sindercombe", "type": "rainfall"}
        assert fetch_data.get_station_filename(station) == "rainfall_E85220.csv"

    def test_tidal_station_with_parens(self):
        """Parentheses in label are preserved by the regex."""
        station = {"id": "50198", "label": "Barnstaple (Tidal)", "type": "tidal"}
        result = fetch_data.get_station_filename(station)
        assert result == "level_50198_barnstaple_(tidal).csv"

    def test_special_characters_sanitised(self):
        """Characters outside [a-z0-9_()-] become underscores."""
        station = {"id": "99999", "label": "Some/Bad Name!", "type": "level"}
        result = fetch_data.get_station_filename(station)
        assert "/" not in result
        assert "!" not in result
        assert result.startswith("level_99999_")
        assert result.endswith(".csv")

    def test_label_lowercased_and_spaces_become_underscores(self):
        station = {"id": "12345", "label": "Taw Bridge", "type": "level"}
        assert fetch_data.get_station_filename(station) == "level_12345_taw_bridge.csv"

    def test_id_sanitised(self):
        """Non-alphanumeric characters in ID are stripped."""
        station = {"id": "AB/CD", "label": "Test", "type": "level"}
        result = fetch_data.get_station_filename(station)
        assert result == "level_ABCD_test.csv"


# ============================================================
# merge_readings — pure function, critical dedup/sort logic
# ============================================================

class TestMergeReadings:
    def test_merge_empty_existing_with_new(self):
        new = [{"dateTime": "2026-01-13T00:00:00Z", "value": 0.5}]
        result = fetch_data.merge_readings([], new)
        assert len(result) == 1
        assert result[0]["value"] == 0.5

    def test_merge_deduplicates_by_datetime(self):
        existing = [{"dateTime": "2026-01-13T00:00:00Z", "value": 0.5}]
        new = [{"dateTime": "2026-01-13T00:00:00Z", "value": 0.5}]
        result = fetch_data.merge_readings(existing, new)
        assert len(result) == 1

    def test_merge_sorts_chronologically(self):
        existing = [{"dateTime": "2026-01-13T02:00:00Z", "value": 0.7}]
        new = [{"dateTime": "2026-01-13T01:00:00Z", "value": 0.6}]
        result = fetch_data.merge_readings(existing, new)
        assert result[0]["dateTime"] == "2026-01-13T01:00:00Z"
        assert result[1]["dateTime"] == "2026-01-13T02:00:00Z"

    def test_merge_skips_empty_datetime(self):
        readings = [
            {"dateTime": "", "value": 0.5},
            {"dateTime": "2026-01-13T00:00:00Z", "value": 0.6},
        ]
        result = fetch_data.merge_readings([], readings)
        assert len(result) == 1
        assert result[0]["value"] == 0.6

    def test_merge_both_empty(self):
        assert fetch_data.merge_readings([], []) == []

    def test_merge_preserves_all_fields(self):
        """Merged readings retain all original keys, not just dateTime/value."""
        existing = [{"dateTime": "2026-01-13T00:00:00Z", "value": 0.5, "extra": "kept"}]
        result = fetch_data.merge_readings(existing, [])
        assert result[0]["extra"] == "kept"

    def test_merge_large_set(self):
        """Handles merging hundreds of readings."""
        existing = [{"dateTime": f"2026-01-{i:02d}T00:00:00Z", "value": i} for i in range(1, 29)]
        new = [{"dateTime": f"2026-01-{i:02d}T00:00:00Z", "value": i} for i in range(15, 32)]
        result = fetch_data.merge_readings(existing, new)
        assert len(result) == 31  # 1-31 Jan, deduplicated


# ============================================================
# load_existing_csv — filesystem, uses data_dir fixture
# ============================================================

class TestLoadExistingCsv:
    def test_load_valid_csv(self, data_dir):
        csv_content = "dateTime,value,unit,station_id,station_label\n"
        csv_content += "2026-02-10T08:00:00Z,0.530,m,50140,Umberleigh\n"
        csv_content += "2026-02-10T08:15:00Z,0.528,m,50140,Umberleigh\n"
        (data_dir / "test.csv").write_text(csv_content)

        result = fetch_data.load_existing_csv("test.csv")
        assert len(result) == 2
        assert result[0]["dateTime"] == "2026-02-10T08:00:00Z"
        assert result[0]["value"] == "0.530"

    def test_load_nonexistent_csv(self, data_dir):
        result = fetch_data.load_existing_csv("nonexistent.csv")
        assert result == []

    def test_load_header_only_csv(self, data_dir):
        csv_content = "dateTime,value,unit,station_id,station_label\n"
        (data_dir / "empty.csv").write_text(csv_content)
        result = fetch_data.load_existing_csv("empty.csv")
        assert result == []


# ============================================================
# save_readings_csv — filesystem, uses data_dir fixture
# ============================================================

class TestSaveReadingsCsv:
    def test_save_level_station(self, data_dir, sample_station_level, sample_readings):
        fetch_data.save_readings_csv(sample_station_level, sample_readings, "test_level.csv")

        filepath = data_dir / "test_level.csv"
        assert filepath.exists()

        with open(filepath) as f:
            reader = csv.DictReader(f)
            rows = list(reader)

        assert len(rows) == 5
        assert rows[0]["unit"] == "m"
        assert rows[0]["station_id"] == "50140"
        assert rows[0]["station_label"] == "Umberleigh"

    def test_save_rainfall_station(self, data_dir, sample_station_rainfall, sample_readings):
        fetch_data.save_readings_csv(sample_station_rainfall, sample_readings, "test_rain.csv")

        with open(data_dir / "test_rain.csv") as f:
            rows = list(csv.DictReader(f))
        assert rows[0]["unit"] == "mm"

    def test_save_tidal_station(self, data_dir, sample_station_tidal, sample_readings):
        fetch_data.save_readings_csv(sample_station_tidal, sample_readings, "test_tidal.csv")

        with open(data_dir / "test_tidal.csv") as f:
            rows = list(csv.DictReader(f))
        assert rows[0]["unit"] == "mAOD"

    def test_save_skips_empty_datetime(self, data_dir, sample_station_level):
        readings = [
            {"dateTime": "2026-02-10T10:00:00Z", "value": 0.5},
            {"dateTime": "", "value": 0.3},
        ]
        fetch_data.save_readings_csv(sample_station_level, readings, "test_skip.csv")

        with open(data_dir / "test_skip.csv") as f:
            rows = list(csv.DictReader(f))
        assert len(rows) == 1

    def test_csv_headers(self, data_dir, sample_station_level, sample_readings):
        fetch_data.save_readings_csv(sample_station_level, sample_readings, "test_hdrs.csv")

        with open(data_dir / "test_hdrs.csv") as f:
            header = f.readline().strip()
        assert header == "dateTime,value,unit,station_id,station_label"


# ============================================================
# save_stations_csv — filesystem, uses data_dir fixture
# ============================================================

class TestSaveStationsCsv:
    def test_writes_all_stations(self, data_dir):
        fetch_data.save_stations_csv()
        filepath = data_dir / "stations.csv"
        assert filepath.exists()

        with open(filepath) as f:
            reader = csv.DictReader(f)
            rows = list(reader)

        expected_count = len(fetch_data.LEVEL_STATIONS) + len(fetch_data.RAINFALL_STATIONS)
        assert len(rows) == expected_count
        assert rows[0]["id"] == "50149"  # first level station (Sticklepath)

    def test_headers(self, data_dir):
        fetch_data.save_stations_csv()
        with open(data_dir / "stations.csv") as f:
            header = f.readline().strip()
        assert header == "id,label,lat,lon,river,type,rloi,measure_id"


# ============================================================
# api_get — HTTP mocking with monkeypatch
# ============================================================

class TestApiGet:
    def test_success_first_attempt(self, monkeypatch):
        mock_resp = make_mock_urlopen({"items": [{"value": 1}]})
        monkeypatch.setattr("fetch_data.urlopen", lambda *a, **kw: mock_resp)

        result = fetch_data.api_get("http://example.com/test")
        assert result == {"items": [{"value": 1}]}

    def test_retry_on_failure_then_success(self, monkeypatch):
        call_count = 0
        mock_resp = make_mock_urlopen({"items": []})

        def fake_urlopen(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise URLError("connection failed")
            return mock_resp

        monkeypatch.setattr("fetch_data.urlopen", fake_urlopen)
        monkeypatch.setattr("fetch_data.time.sleep", lambda _: None)

        result = fetch_data.api_get("http://example.com/test", retries=3)
        assert result == {"items": []}
        assert call_count == 3

    def test_raises_after_max_retries(self, monkeypatch):
        def always_fail(*args, **kwargs):
            raise URLError("connection failed")

        monkeypatch.setattr("fetch_data.urlopen", always_fail)
        monkeypatch.setattr("fetch_data.time.sleep", lambda _: None)

        with pytest.raises(URLError):
            fetch_data.api_get("http://example.com/test", retries=3)

    def test_exponential_backoff(self, monkeypatch):
        sleep_calls = []

        def always_fail(*args, **kwargs):
            raise URLError("connection failed")

        monkeypatch.setattr("fetch_data.urlopen", always_fail)
        monkeypatch.setattr("fetch_data.time.sleep", lambda s: sleep_calls.append(s))

        with pytest.raises(URLError):
            fetch_data.api_get("http://example.com/test", retries=3)

        # Backoff: 2^0=1, 2^1=2 (only sleeps between retries, not after the last)
        assert sleep_calls == [1, 2]


# ============================================================
# fetch_readings_batch — mocked HTTP
# ============================================================

class TestFetchReadingsBatch:
    def test_returns_items_on_success(self, monkeypatch):
        items = [{"dateTime": "2026-01-13T00:00:00Z", "value": 0.5}]
        mock_resp = make_mock_urlopen({"items": items})
        monkeypatch.setattr("fetch_data.urlopen", lambda *a, **kw: mock_resp)

        result = fetch_data.fetch_readings_batch("50140-level-stage-i-15_min-m", "2026-01-01", "2026-01-13")
        assert len(result) == 1
        assert result[0]["value"] == 0.5

    def test_returns_empty_on_error(self, monkeypatch):
        def always_fail(*args, **kwargs):
            raise URLError("connection failed")

        monkeypatch.setattr("fetch_data.urlopen", always_fail)
        monkeypatch.setattr("fetch_data.time.sleep", lambda _: None)

        result = fetch_data.fetch_readings_batch("50140-level-stage-i-15_min-m", "2026-01-01", "2026-01-13")
        assert result == []


# ============================================================
# fetch_all_readings — mocked HTTP, tests chunking and dedup
# ============================================================

class TestFetchAllReadings:
    def test_deduplicates_overlapping_chunks(self, monkeypatch):
        """If the same reading appears in multiple chunks, it's only in the result once."""
        chunk_data = [
            {"dateTime": "2026-02-01T00:00:00Z", "value": 0.5},
            {"dateTime": "2026-02-01T00:00:00Z", "value": 0.5},  # duplicate
            {"dateTime": "2026-02-01T01:00:00Z", "value": 0.6},
        ]
        monkeypatch.setattr(
            fetch_data, "fetch_readings_batch",
            lambda *a, **kw: chunk_data
        )
        monkeypatch.setattr("fetch_data.time.sleep", lambda _: None)

        station = {"id": "50140", "label": "Umberleigh", "type": "level"}
        result = fetch_data.fetch_all_readings(station, going_back_days=1)
        # Should have deduplicated: only 2 unique dateTimes
        assert len(result) == 2

    def test_stops_after_empty_streak(self, monkeypatch):
        """Stops fetching after 3 consecutive empty chunks."""
        call_count = 0

        def mock_batch(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            return []  # always empty

        monkeypatch.setattr(fetch_data, "fetch_readings_batch", mock_batch)
        monkeypatch.setattr("fetch_data.time.sleep", lambda _: None)

        station = {"id": "50140", "label": "Umberleigh", "type": "level"}
        result = fetch_data.fetch_all_readings(station, going_back_days=365)
        assert result == []
        # Should stop after 3 empty chunks, not iterate all 13+ chunks for 365 days
        assert call_count == 3

    def test_returns_sorted(self, monkeypatch):
        """Results are sorted chronologically regardless of chunk order."""
        batch_num = 0

        def mock_batch(*args, **kwargs):
            nonlocal batch_num
            batch_num += 1
            if batch_num == 1:
                return [{"dateTime": "2026-02-15T00:00:00Z", "value": 0.7}]
            elif batch_num == 2:
                return [{"dateTime": "2026-01-15T00:00:00Z", "value": 0.5}]
            return []

        monkeypatch.setattr(fetch_data, "fetch_readings_batch", mock_batch)
        monkeypatch.setattr("fetch_data.time.sleep", lambda _: None)

        station = {"id": "50140", "label": "Umberleigh", "type": "level"}
        result = fetch_data.fetch_all_readings(station, going_back_days=60)
        assert len(result) >= 2
        assert result[0]["dateTime"] < result[-1]["dateTime"]
