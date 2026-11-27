"""live.json: each station's latest reading, state and trend."""

import unittest

from monitor import live
from tests.support import NOW, DBTestCase


class Trend(DBTestCase):
    def series(self, per_hour, n=5):
        m = self.add_station("T")
        self.add_readings(m, [(NOW - 900 * i, 1.0 - per_hour * i / 4) for i in range(n)])
        return m

    def test_rising(self):
        self.assertEqual(live._trend(self.con, self.series(0.05), NOW), "rising")

    def test_falling(self):
        self.assertEqual(live._trend(self.con, self.series(-0.05), NOW), "falling")

    def test_a_slope_under_a_centimetre_an_hour_is_steady(self):
        self.assertEqual(live._trend(self.con, self.series(0.005), NOW), "steady")

    def test_needs_three_readings_in_the_hour(self):
        self.assertIsNone(live._trend(self.con, self.series(0.05, n=2), NOW))

    def test_only_the_last_hour_counts(self):
        m = self.add_station("T")
        # A steep rise two hours ago, then flat for the last hour.
        self.add_readings(m, [(NOW - 7200, 0.0), (NOW - 6300, 0.5)]
                          + [(NOW - 900 * i, 1.0) for i in range(4)])
        self.assertEqual(live._trend(self.con, m, NOW), "steady")


class Build(DBTestCase):
    def state_of(self, sid):
        return next(s for s in live.build(self.con, NOW)["stations"] if s["id"] == sid)

    def test_level_states(self):
        for sid, value in (("high", 1.5), ("normal", 0.5), ("low", 0.1)):
            self.add_readings(self.add_station(sid), [(NOW - 600, value)])
        self.add_readings(self.add_station("unknown", typical=None), [(NOW - 600, 0.5)])
        self.add_readings(self.add_station("stale"), [(NOW - live.STALE_AFTER - 60, 0.5)])
        for sid in ("high", "normal", "low", "unknown", "stale"):
            self.assertEqual(self.state_of(sid)["state"], sid)

    def state_after(self, value, **station):
        sid = f"S{len(self.con.execute('SELECT id FROM stations').fetchall())}"
        self.add_readings(self.add_station(sid, **station), [(NOW - 600, value)])
        return self.state_of(sid)["state"]

    def entry_for(self, newest_age, per_hour=0.2):
        # Five readings a quarter of an hour apart, rising, the newest `newest_age` old.
        m = self.add_station("T")
        self.add_readings(m, [(NOW - newest_age - 900 * i, 1.0 - per_hour * i / 4) for i in range(5)])
        return self.state_of("T")

    def test_near_the_top_of_the_range_is_approach(self):
        # typical [0.5, 2.0]: 70% of 2.0 is 1.4
        self.assertEqual(self.state_after(1.39, typical=(0.5, 2.0)), "normal")
        self.assertEqual(self.state_after(1.4, typical=(0.5, 2.0)), "approach")
        self.assertEqual(self.state_after(2.3, typical=(0.5, 2.0)), "high")

    def test_no_typical_range_is_unknown_not_approach(self):
        self.assertEqual(self.state_after(5, typical=None), "unknown")

    def test_a_stale_gauge_has_no_trend(self):
        entry = self.entry_for(4 * 3600)
        self.assertEqual(entry["state"], "stale")
        self.assertNotIn("trend", entry)

    def test_a_fresh_gauge_keeps_its_trend(self):
        self.assertEqual(self.entry_for(60)["trend"], "rising")

    def test_a_station_with_no_readings_is_left_out(self):
        self.add_station("silent")
        self.assertEqual(live.build(self.con, NOW)["stations"], [])

    def test_rain_totals(self):
        m = self.add_station("R", kind="rain", measure="R-rainfall", unit="mm", typical=None)
        self.add_readings(m, [(NOW - 600, 0.4), (NOW - 1800, 0.2), (NOW - 7200, 1.0), (NOW - 90000, 5.0)])
        s = self.state_of("R")
        self.assertEqual((s["h1"], s["h24"], s["state"]), (0.6, 1.6, "raining"))

    def test_dry_rain_gauge(self):
        m = self.add_station("R", kind="rain", measure="R-rainfall", unit="mm", typical=None)
        self.add_readings(m, [(NOW - 600, 0.0), (NOW - 7200, 1.0)])
        self.assertEqual(self.state_of("R")["state"], "dry")

    def test_tidal(self):
        m = self.add_station("W", kind="tidal", typical=None)
        self.add_readings(m, [(NOW - 600, 1.7)])
        self.assertEqual(self.state_of("W")["state"], "tidal")

    def test_flow_forecast_flag(self):
        self.add_readings(self.add_station("50140"), [(NOW - 600, 0.8)])
        self.add_readings(self.add_station("99999"), [(NOW - 600, 0.8)])
        self.assertTrue(self.state_of("50140").get("flow"))
        self.assertNotIn("flow", self.state_of("99999"))


if __name__ == "__main__":
    unittest.main()


class Write(DBTestCase):
    def test_tests_write_live_json_somewhere_temporary(self):
        # Writing live.json from a test database must never replace the
        # map's real file in site/data, which the local server serves.
        real = live.ROOT / "site" / "data" / "live.json"
        before = real.read_bytes() if real.exists() else None
        live.write(self.con, now=NOW)
        self.assertNotEqual(live.LIVE, real)
        self.assertTrue(live.LIVE.exists())
        self.assertEqual(real.read_bytes() if real.exists() else None, before)
