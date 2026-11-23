"""Station history: raw readings for short ranges, buckets for long ones, and the CSV download."""

import unittest

from monitor import history
from tests.support import NOW, DBTestCase


class Buckets(unittest.TestCase):
    def test_the_smallest_bucket_that_fits(self):
        self.assertEqual(history.bucket_for(30 * 86400), 3600)          # 720 hours
        self.assertEqual(history.bucket_for(200 * 86400), 3 * 3600)     # 4,800 hours is too many
        self.assertEqual(history.bucket_for(3 * 365 * 86400), 12 * 3600)
        self.assertEqual(history.bucket_for(100 * 365 * 86400), 7 * 86400)


class Readings(DBTestCase):
    def setUp(self):
        super().setUp()
        self.level = self.station("L")
        self.rain = self.station("R", kind="rain")
        # Four readings in each of two hours, 40 days ago, and one today.
        old = (NOW - 40 * 86400) // 3600 * 3600
        for m in (self.level["measure"], self.rain["measure"]):
            self.add_readings(m, [(old + i * 900, v) for i, v in enumerate((0.1, 0.9, 0.3, 0.2, 0.5, 0.4, 0.6, 0.1))]
                              + [(NOW - 600, 0.7)])
        self.old = old

    def station(self, sid, kind="level"):
        self.add_station(sid, kind=kind, measure=f"{sid}-m", unit="mm" if kind == "rain" else "m")
        return self.con.execute("SELECT * FROM stations WHERE id = ?", (sid,)).fetchone()

    def test_short_ranges_are_every_reading(self):
        d = history.readings(self.con, self.level, 7, now=NOW)
        self.assertEqual(d["readings"], [[NOW - 600, 0.7]])
        self.assertIsNone(d["bucket"])
        self.assertEqual(d["first"], self.old)

    def test_all_time_keeps_each_hours_highest_level(self):
        d = history.readings(self.con, self.level, None, now=NOW)
        self.assertEqual(d["bucket"], 3600)
        self.assertEqual(d["readings"][:2], [[self.old, 0.9], [self.old + 3600, 0.6]])

    def test_all_time_totals_the_rain(self):
        d = history.readings(self.con, self.rain, None, now=NOW)
        self.assertEqual(d["readings"][:2], [[self.old, 1.5], [self.old + 3600, 1.6]])

    def test_csv(self):
        text = "".join(history.csv_rows(self.con, self.level, chunk=3))
        lines = text.splitlines()
        self.assertEqual(lines[0], "dateTime,value,unit,station_id,station_label")
        self.assertEqual(len(lines), 10)
        self.assertEqual(history.csv_filename(self.rain), "rainfall_r_somewhere.csv")


if __name__ == "__main__":
    unittest.main()
