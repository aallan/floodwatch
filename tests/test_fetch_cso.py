"""Tests for CSO (Combined Sewer Overflow) fetching logic.

The most interesting code is in `update_cso_events` — the state machine that
turns successive snapshots of the SWW live feed into an append-only event
log. Those tests are exhaustive. Helpers (epoch conversion, WHERE-clause
construction, duration math) get lighter coverage.
"""

import csv
import json
from pathlib import Path

import pytest

import fetch_data

FIXTURES_DIR = Path(__file__).parent / "fixtures"


# ============================================================
# Helper-function tests
# ============================================================


class TestEpochMsToIso:
    def test_none_returns_empty_string(self):
        assert fetch_data._epoch_ms_to_iso(None) == ""

    def test_known_value(self):
        # 2026-06-02 10:13:20.300 UTC = 1780395200300 ms (from real Chulmleigh row)
        assert fetch_data._epoch_ms_to_iso(1780395200300) == "2026-06-02T10:13:20.300000Z"

    def test_epoch_zero(self):
        assert fetch_data._epoch_ms_to_iso(0) == "1970-01-01T00:00:00Z"


class TestDurationMinutes:
    def test_typical_event(self):
        # 80-minute Chulmleigh spill yesterday
        assert fetch_data._duration_minutes("2026-06-02T10:13:20.300000Z", "2026-06-02T11:34:00.300000Z") == "80"

    def test_empty_inputs(self):
        assert fetch_data._duration_minutes("", "2026-06-02T11:34:00Z") == ""
        assert fetch_data._duration_minutes("2026-06-02T10:13:20Z", "") == ""
        assert fetch_data._duration_minutes("", "") == ""

    def test_end_before_start_clamps_to_zero(self):
        # If a buggy upstream feed reports end < start, we record 0 not a negative.
        assert fetch_data._duration_minutes("2026-06-02T11:00:00Z", "2026-06-02T10:00:00Z") == "0"

    def test_malformed_returns_empty(self):
        assert fetch_data._duration_minutes("not-a-date", "2026-06-02T10:00:00Z") == ""


class TestBuildWhereClause:
    def test_includes_swr_filter(self):
        w = fetch_data._build_cso_where_clause()
        assert "South West Water" in w
        assert "company=" in w

    def test_includes_every_allowed_river(self):
        w = fetch_data._build_cso_where_clause().upper()
        for r in fetch_data.CSO_RIVER_ALLOWLIST:
            assert f"LIKE '%{r}%'" in w, f"missing allowlist entry: {r}"

    def test_excludes_torridge_etc(self):
        w = fetch_data._build_cso_where_clause().upper()
        for e in fetch_data.CSO_RIVER_EXCLUDE:
            assert f"NOT LIKE '%{e}%'" in w, f"missing exclude entry: {e}"


# ============================================================
# update_cso_events — the meat of the test budget
# ============================================================


@pytest.fixture
def quiet_site():
    """A site currently not discharging, whose most recent event ended cleanly."""
    return {
        "Id": "SBB00257",
        "status": 0,
        "statusStart": 1780400040300,  # 2026-06-02 11:34:00.300 UTC
        "latestEventStart": 1780395200300,  # 2026-06-02 10:13:20.300 UTC
        "latestEventEnd": 1780400040300,
    }


@pytest.fixture
def active_site():
    """A site currently discharging — latestEventEnd is unset."""
    return {
        "Id": "SBB01336",
        "status": 1,
        "statusStart": 1780483445260,
        "latestEventStart": 1780483445260,  # 2026-06-03 13:24:05.260 UTC
        "latestEventEnd": None,
    }


@pytest.fixture
def offline_site():
    """A site whose EDM monitor is offline. status=-1."""
    return {
        "Id": "SBB00249",
        "status": -1,
        "statusStart": None,
        "latestEventStart": None,
        "latestEventEnd": None,
    }


class TestUpdateCsoEvents:
    def test_empty_log_quiet_site_records_completed_event(self, quiet_site):
        out = fetch_data.update_cso_events(quiet_site, existing=[])
        assert len(out) == 1
        assert out[0]["start_time"] == "2026-06-02T10:13:20.300000Z"
        assert out[0]["end_time"] == "2026-06-02T11:34:00.300000Z"
        assert out[0]["duration_min"] == "80"
        assert out[0]["is_ongoing"] == "false"

    def test_empty_log_active_site_records_ongoing_event(self, active_site):
        out = fetch_data.update_cso_events(active_site, existing=[])
        assert len(out) == 1
        # 1780483445260 ms epoch == 2026-06-03 10:44:05.260 UTC
        assert out[0]["start_time"] == "2026-06-03T10:44:05.260000Z"
        assert out[0]["end_time"] == ""
        assert out[0]["duration_min"] == ""
        assert out[0]["is_ongoing"] == "true"

    def test_empty_log_site_with_no_event_yields_empty(self, offline_site):
        out = fetch_data.update_cso_events(offline_site, existing=[])
        assert out == []

    def test_offline_site_does_not_append_if_no_event(self):
        # An offline site with a stale historical event should still leave the log alone
        # (we only know about events when latestEventStart is populated).
        site = {"Id": "X", "status": -1, "latestEventStart": None, "latestEventEnd": None}
        out = fetch_data.update_cso_events(site, existing=[])
        assert out == []

    def test_idempotent_when_state_unchanged(self, quiet_site):
        """Second poll with the same API state must not duplicate the event."""
        first = fetch_data.update_cso_events(quiet_site, existing=[])
        second = fetch_data.update_cso_events(quiet_site, existing=first)
        assert first == second
        assert len(second) == 1

    def test_ongoing_event_closes_when_status_flips_to_quiet(self, active_site):
        """When we previously logged an ongoing event and the next poll shows
        the SAME start time but status=0, we update our row in place — no new row."""
        log = fetch_data.update_cso_events(active_site, existing=[])
        assert log[0]["is_ongoing"] == "true"

        # Same event, now ended
        ended = dict(active_site)
        ended["status"] = 0
        ended["latestEventEnd"] = active_site["latestEventStart"] + 30 * 60 * 1000  # +30 min
        out = fetch_data.update_cso_events(ended, existing=log)
        assert len(out) == 1, "should not append — same event, now closed"
        assert out[0]["is_ongoing"] == "false"
        assert out[0]["end_time"] != ""
        assert out[0]["duration_min"] == "30"

    def test_new_event_after_quiet_period(self, quiet_site):
        """Existing log ends with a closed event. New API state shows a fresh event."""
        log = fetch_data.update_cso_events(quiet_site, existing=[])

        # New event starts later
        new = {
            "Id": quiet_site["Id"],
            "status": 1,
            "latestEventStart": quiet_site["latestEventStart"] + 2 * 86400 * 1000,  # +2 days
            "latestEventEnd": None,
        }
        out = fetch_data.update_cso_events(new, existing=log)
        assert len(out) == 2
        assert out[0]["start_time"] == log[0]["start_time"]  # original preserved
        assert out[1]["is_ongoing"] == "true"
        assert out[1]["start_time"] != log[0]["start_time"]

    def test_missed_transition_best_effort_closes_previous(self, active_site):
        """Poll N: event A ongoing. Poll N+1: event B started, A's end was
        between polls. We best-effort close A at B's start time."""
        log = fetch_data.update_cso_events(active_site, existing=[])
        assert log[0]["is_ongoing"] == "true"

        # A new event appears in the next poll — A's end was never observed
        new_event_start_ms = active_site["latestEventStart"] + 10 * 60 * 1000  # +10 min
        new = {
            "Id": active_site["Id"],
            "status": 1,
            "latestEventStart": new_event_start_ms,
            "latestEventEnd": None,
        }
        out = fetch_data.update_cso_events(new, existing=log)
        assert len(out) == 2
        # Previous row closed best-effort at new event's start time
        assert out[0]["is_ongoing"] == "false"
        assert out[0]["end_time"] == fetch_data._epoch_ms_to_iso(new_event_start_ms)
        # New event ongoing
        assert out[1]["is_ongoing"] == "true"
        assert out[1]["start_time"] == fetch_data._epoch_ms_to_iso(new_event_start_ms)

    def test_does_not_mutate_caller_list(self, quiet_site):
        """update_cso_events should be functionally pure on its `existing` arg."""
        original = [{"start_time": "2025-01-01T00:00:00Z", "end_time": "2025-01-01T01:00:00Z", "duration_min": "60", "is_ongoing": "false"}]
        snapshot = [dict(e) for e in original]
        fetch_data.update_cso_events(quiet_site, existing=original)
        assert original == snapshot, "input list must not be mutated"


# ============================================================
# fetch_cso_catchment_sites — uses saved fixture, no live API
# ============================================================


class TestFetchCsoCatchmentSites:
    def test_parses_fixture_and_normalises_river_name(self, monkeypatch):
        with open(FIXTURES_DIR / "cso_live_sample.json") as f:
            fixture = json.load(f)

        monkeypatch.setattr(fetch_data, "api_post", lambda url, params: fixture)
        sites = fetch_data.fetch_cso_catchment_sites()

        assert len(sites) == len(fixture["features"])
        # Each site has the normalised river-name field
        for s in sites:
            assert "_river_title" in s
            # Title case: no all-caps words like "LITTLE DART RIVER"
            assert s["_river_title"] == s["receivingWaterCourse"].title() if s.get("receivingWaterCourse") else True

    def test_sites_sorted_by_id(self, monkeypatch):
        with open(FIXTURES_DIR / "cso_live_sample.json") as f:
            fixture = json.load(f)
        monkeypatch.setattr(fetch_data, "api_post", lambda url, params: fixture)
        sites = fetch_data.fetch_cso_catchment_sites()
        ids = [s["Id"] for s in sites]
        assert ids == sorted(ids)


# ============================================================
# CSV I/O round-trip
# ============================================================


class TestCsoEventsRoundTrip:
    def test_write_then_read_preserves_data(self, data_dir):
        events = [
            {
                "start_time": "2026-06-02T10:13:20.300000Z",
                "end_time": "2026-06-02T11:34:00.300000Z",
                "duration_min": "80",
                "is_ongoing": "false",
            },
            {"start_time": "2026-06-03T13:24:05.260000Z", "end_time": "", "duration_min": "", "is_ongoing": "true"},
        ]
        fetch_data.save_cso_events_csv("SBB00257", events)
        readback = fetch_data.read_cso_events("SBB00257")
        assert readback == events

    def test_read_missing_file_returns_empty(self, data_dir):
        assert fetch_data.read_cso_events("DOES_NOT_EXIST") == []


class TestCsoSitesCsv:
    def test_writes_expected_columns(self, data_dir):
        sites = [
            {"Id": "SBB00257", "_river_title": "Little Dart River", "latitude": 50.91, "longitude": -3.87},
            {"Id": "SBB00072", "_river_title": "River Taw Estuary", "latitude": 51.09, "longitude": -4.10},
        ]
        fetch_data.save_cso_sites_csv(sites)
        with open(data_dir / "cso_sites.csv") as f:
            rows = list(csv.DictReader(f))
        assert len(rows) == 2
        assert rows[0]["id"] == "SBB00257"
        assert rows[0]["river"] == "Little Dart River"
        assert float(rows[0]["lat"]) == pytest.approx(50.91)


class TestCsoStatusJson:
    def test_snapshot_contains_iso_timestamps(self, data_dir):
        sites = [
            {
                "Id": "SBB00257",
                "status": 0,
                "statusStart": 1780400040300,
                "latestEventStart": 1780395200300,
                "latestEventEnd": 1780400040300,
                "lastUpdated": 1780484400000,
            },
            {
                "Id": "SBB01336",
                "status": 1,
                "statusStart": 1780483445260,
                "latestEventStart": 1780483445260,
                "latestEventEnd": None,
                "lastUpdated": 1780484400000,
            },
        ]
        fetch_data.save_cso_status_json(sites)
        with open(data_dir / "cso_status.json") as f:
            snap = json.load(f)
        assert "generated_at" in snap
        assert snap["generated_at"].endswith("Z")
        assert set(snap["sites"].keys()) == {"SBB00257", "SBB01336"}
        assert snap["sites"]["SBB00257"]["status"] == 0
        assert snap["sites"]["SBB01336"]["latestEventEnd"] == ""  # None → ''


# ============================================================
# process_cso — top-level orchestration, with mocked HTTP
# ============================================================


class TestProcessCso:
    def test_writes_all_expected_files(self, data_dir, monkeypatch):
        with open(FIXTURES_DIR / "cso_live_sample.json") as f:
            fixture = json.load(f)
        monkeypatch.setattr(fetch_data, "api_post", lambda url, params: fixture)

        fetch_data.process_cso()

        assert (data_dir / "cso_sites.csv").exists()
        assert (data_dir / "cso_status.json").exists()
        # Each fixture site got an event CSV
        for feat in fixture["features"]:
            assert (data_dir / f"cso_{feat['attributes']['Id']}.csv").exists()

    def test_http_failure_is_non_fatal(self, data_dir, monkeypatch, capsys):
        def boom(*args, **kw):
            raise RuntimeError("upstream is down")

        monkeypatch.setattr(fetch_data, "api_post", boom)
        # Should not raise — CSO failure must not abort the wider fetch
        fetch_data.process_cso()
        out = capsys.readouterr().out
        assert "ERROR" in out
        # Sites file should NOT exist because we bailed before writing
        assert not (data_dir / "cso_sites.csv").exists()
