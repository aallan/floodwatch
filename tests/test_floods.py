"""Flood warnings: times without a timezone, and which warnings are kept."""

import unittest
from unittest import mock

from monitor import floods
from tests.support import DBTestCase


class UKTime(unittest.TestCase):
    def test_summer_time(self):
        self.assertEqual(floods.uk_ts("2026-07-01T12:00:00"), floods.uk_ts("2026-07-01T11:00:00Z"))

    def test_winter_time(self):
        self.assertEqual(floods.uk_ts("2026-12-01T12:00:00"), floods.uk_ts("2026-12-01T12:00:00Z"))

    def test_an_explicit_offset_is_kept(self):
        self.assertEqual(floods.uk_ts("2026-07-01T12:00:00+00:00"), floods.uk_ts("2026-07-01T12:00:00Z"))

    def test_missing(self):
        self.assertIsNone(floods.uk_ts(None))


class RefreshAreas(DBTestCase):
    def test_areas_are_kept_by_where_they_are_or_their_river(self):
        items = [
            # Centre inside the catchment.
            {"notation": "113FWFTAWUMB", "label": "River Taw at Umberleigh", "riverOrSea": "River Taw",
             "county": "Devon", "lat": 50.99, "long": -3.98},
            # Centre over the watershed, but on the Taw by name.
            {"notation": "113WAFTAW", "label": "River Taw", "riverOrSea": "River Taw", "county": "Devon",
             "lat": 50.70, "long": -3.60},
            # The Torridge's: neither.
            {"notation": "113FWFTORBID", "label": "River Torridge at Bideford", "riverOrSea": "River Torridge",
             "county": "Devon", "lat": 51.02, "long": -4.21},
            # No position and no river.
            {"notation": "113FWFNONE", "label": "Nowhere", "county": "Devon"},
        ]
        inside = lambda lon, lat: lon > -4.1 and 50.8 < lat < 51.2
        with mock.patch.object(floods, "get", return_value={"items": items}), \
                mock.patch.object(floods, "membership", return_value=inside):
            self.assertEqual(floods.refresh_areas(self.con), 2)
        kept = {r["id"]: r["kind"] for r in self.con.execute("SELECT id, kind FROM flood_areas WHERE active = 1")}
        self.assertEqual(kept, {"113FWFTAWUMB": "warning", "113WAFTAW": "alert"})


class PollWarnings(DBTestCase):
    def setUp(self):
        super().setUp()
        for aid, kind in (("113WAFTW12", "alert"), ("113FWF2E1B", "warning")):
            self.con.execute("INSERT INTO flood_areas (id, kind, label, active, updated) VALUES (?, ?, ?, 1, 0)",
                             (aid, kind, aid.lower()))
        self.con.commit()

    def test_keeps_the_catchments_warnings_in_force_most_severe_first(self):
        items = [
            {"floodAreaID": "113WAFTW12", "severityLevel": 3, "description": "North Dartmoor Rivers", "message": " Alert "},
            {"floodAreaID": "113FWF2E1B", "severityLevel": 2, "description": "River Taw (Lower)",
             "timeSeverityChanged": "2026-10-30T09:00:00"},
            {"floodAreaID": "113WAFTW12", "severityLevel": 4},     # no longer in force
            {"floodAreaID": "113FWFTORR01", "severityLevel": 1},   # not one of the catchment's areas
        ]
        with mock.patch.object(floods, "get", return_value={"items": items}), \
                mock.patch.object(floods, "fetch_outline", return_value=None):
            out = floods.poll_warnings(self.con)
        self.assertEqual([(w["id"], w["label"]) for w in out],
                         [("113FWF2E1B", "Flood warning"), ("113WAFTW12", "Flood alert")])
        self.assertEqual(out[1]["message"], "Alert")
        self.assertEqual(out[0]["since"], floods.uk_ts("2026-10-30T09:00:00"))

    def test_a_failed_outline_still_shows_the_warning(self):
        items = [{"floodAreaID": "113FWF2E1B", "severityLevel": 2}]
        with mock.patch.object(floods, "get", return_value={"items": items}), \
                mock.patch.object(floods, "fetch_outline", side_effect=OSError("timed out")):
            out = floods.poll_warnings(self.con)
        self.assertEqual(len(out), 1)
        self.assertIsNone(out[0]["geometry"])

    def test_an_outline_is_fetched_once_and_kept(self):
        square = {"type": "MultiPolygon", "coordinates": [[[[-4.8, 50.5], [-4.7, 50.5], [-4.7, 50.6], [-4.8, 50.5]]]]}
        items = [{"floodAreaID": "113FWF2E1B", "severityLevel": 2}]
        with mock.patch.object(floods, "get", return_value={"items": items}), \
                mock.patch.object(floods, "fetch_outline", return_value=square) as fetch:
            floods.poll_warnings(self.con)
            out = floods.poll_warnings(self.con)
        self.assertEqual(fetch.call_count, 1)
        self.assertEqual(out[0]["geometry"], square)


if __name__ == "__main__":
    unittest.main()
