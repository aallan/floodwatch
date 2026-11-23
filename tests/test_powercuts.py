"""Power cuts: reading NGED's live file and keeping the catchment's.

The fixture is five rows of NGED's Live Power Cuts file as published on
2 November 2026, under the NGED Open Data Licence. Three were in Cornwall,
and have been moved, with their postcodes, into the Taw catchment: near
South Molton, near Chulmleigh, and one at Barnstaple with nobody yet
confirmed off. The other two are as published: one at Lynton on the Exmoor
coast, just outside the catchment, and one near Bristol.
"""

import json
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest import mock
from zoneinfo import ZoneInfo

from monitor import powercuts

CSV = (Path(__file__).parent / "fixtures" / "nged_power_cuts.csv").read_text()
UK = ZoneInfo("Europe/London")
PLACES = [{"name": "South Molton", "place": "town", "lat": 51.017, "lon": -3.834},
          {"name": "Chulmleigh", "place": "village", "lat": 50.913, "lon": -3.868},
          {"name": "Barnstaple", "place": "town", "lat": 51.080, "lon": -4.058}]


def uk(*args):
    return int(datetime(*args, tzinfo=UK).timestamp())


def in_catchment(lon, lat):
    """The Taw catchment, near enough, for these five: Lynton and Bristol are outside it."""
    return -4.2 < lon < -3.6 and 50.65 < lat < 51.15


class Parse(unittest.TestCase):
    def setUp(self):
        self.cuts = {c["id"]: c for c in powercuts.parse(CSV)}

    def test_every_row_is_read(self):
        self.assertEqual(len(self.cuts), 5)

    def test_a_power_cut(self):
        c = self.cuts["INCD-19742-u"]
        self.assertEqual((c["lat"], c["lon"]), (51.01644, -3.83214))
        self.assertEqual((c["off"], c["predicted"], c["restored"]), (109, 0, 108))
        self.assertEqual((c["category"], c["status"], c["planned"]), ("HV OVERHEAD", "In Progress", False))
        self.assertEqual((c["start"], c["etr"]), (uk(2026, 11, 2, 12, 54), uk(2026, 11, 2, 17, 30)))
        self.assertEqual(len(c["postcodes"]), 13)   # 21 in the file, some of them twice
        self.assertTrue(all(p.startswith("EX36 ") for p in c["postcodes"]))

    def test_no_estimate_is_none(self):
        self.assertIsNone(self.cuts["INCD-19746-u"]["etr"])
        self.assertEqual(self.cuts["INCD-19746-u"]["postcodes"], ["EX18 7JF"])

    def test_upload_time(self):
        self.assertEqual(self.cuts["INCD-19742-u"]["uploaded"], uk(2026, 11, 2, 14, 55))

    def test_bad_rows_are_skipped(self):
        bad = CSV.replace("INCD-19674-u", "../x").replace("51.01644", "north")
        self.assertEqual(len(powercuts.parse(bad)), 3)

    def test_bad_values_are_tidied(self):
        text = CSV.replace("2026-11-02T17:30:00", "soon").replace("EX36 3DN", "<b>")
        c = {c["id"]: c for c in powercuts.parse(text)}["INCD-19742-u"]
        self.assertIsNone(c["etr"])
        self.assertNotIn("<b>", c["postcodes"])
        self.assertEqual(len(c["postcodes"]), 12)

    def test_a_byte_order_mark(self):
        self.assertEqual(len(powercuts.parse("﻿" + CSV)), 5)


class Ours(unittest.TestCase):
    def setUp(self):
        self.kept = powercuts.ours(powercuts.parse(CSV), in_catchment, PLACES)

    def test_only_the_catchments_with_someone_off(self):
        self.assertEqual([c["id"] for c in self.kept], ["INCD-19742-u", "INCD-19746-u"])

    def test_named_after_the_nearest_place(self):
        self.assertEqual([c["place"] for c in self.kept], ["South Molton", "Chulmleigh"])

    def test_largest_first(self):
        self.assertEqual([c["off"] for c in self.kept], [109, 11])


class Poll(unittest.TestCase):
    def test_writes_the_summary(self):
        with tempfile.TemporaryDirectory() as d, \
                mock.patch.object(powercuts, "SUMMARY", Path(d) / "powercuts.json"), \
                mock.patch.object(powercuts.net, "fetch", return_value=CSV.encode()), \
                mock.patch.object(powercuts.region, "membership", return_value=in_catchment), \
                mock.patch.object(powercuts.ea, "load_places", return_value=PLACES):
            kept = powercuts.poll(now=uk(2026, 11, 2, 15, 0))
            summary = json.loads((Path(d) / "powercuts.json").read_text())
        self.assertEqual(len(kept), 2)
        self.assertEqual(summary["updated"], uk(2026, 11, 2, 14, 55))
        self.assertEqual(summary["source"], powercuts.DATASET)
        self.assertEqual([c["id"] for c in summary["power_cuts"]], ["INCD-19742-u", "INCD-19746-u"])
        self.assertNotIn("uploaded", summary["power_cuts"][0])

    def test_a_failed_fetch_leaves_the_last_summary(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "powercuts.json"
            path.write_text('{"power_cuts":[]}')
            with mock.patch.object(powercuts, "SUMMARY", path), \
                    mock.patch.object(powercuts.net, "fetch", side_effect=TimeoutError("timed out")):
                with self.assertRaises(TimeoutError):
                    powercuts.poll()
            self.assertEqual(path.read_text(), '{"power_cuts":[]}')


if __name__ == "__main__":
    unittest.main()
