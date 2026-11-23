"""The poll cycle: every feed is polled, and filling gauge history comes last."""

import unittest
from unittest import mock

from monitor import poll
from tests.support import DBTestCase, QuietTestCase


class Cycle(QuietTestCase):
    def setUp(self):
        super().setUp()
        patcher = mock.patch.object(poll, "_started", False)
        patcher.start()
        self.addCleanup(patcher.stop)

    def run_cycle(self, fresh=None, **failures):
        order = []

        def step(name, result=None):
            def run(*args):
                order.append(name)
                if fresh is not None and name != "fill":
                    fresh.append(args[1])
                if name in failures:
                    raise failures[name]
                return result
            return run

        with mock.patch.object(poll.db, "connect", return_value=mock.MagicMock()), \
                mock.patch.object(poll, "poll_gauges", side_effect=step("gauges", ({"m": 1}, {}))), \
                mock.patch.object(poll, "poll_overflows", side_effect=step("overflows")), \
                mock.patch.object(poll, "restore_spills", side_effect=step("archive")), \
                mock.patch.object(poll, "poll_floods", side_effect=step("floods")), \
                mock.patch.object(poll, "poll_weather", side_effect=step("weather")), \
                mock.patch.object(poll, "poll_powercuts", side_effect=step("power")), \
                mock.patch.object(poll, "poll_drought", side_effect=step("drought")), \
                mock.patch.object(poll, "fill_gauge_gaps", side_effect=step("fill")):
            poll.cycle()
        return order

    def test_filling_gauge_history_comes_last(self):
        self.assertEqual(self.run_cycle(), ["gauges", "overflows", "archive", "floods", "weather", "power", "drought", "fill"])

    def test_a_failing_feed_doesnt_stop_the_others(self):
        order = self.run_cycle(overflows=TimeoutError("no complete answer within 120 s"))
        self.assertEqual(order, ["gauges", "overflows", "archive", "floods", "weather", "power", "drought", "fill"])

    def test_the_first_cycle_reads_every_feed_afresh(self):
        first, second = [], []
        self.run_cycle(fresh=first)
        self.run_cycle(fresh=second)
        self.assertEqual(first, [True] * 7)
        self.assertEqual(second, [False] * 7)

    def test_no_history_fill_when_the_gauges_failed(self):
        order = self.run_cycle(gauges=TimeoutError("timed out"))
        self.assertEqual(order, ["gauges", "overflows", "archive", "floods", "weather", "power", "drought"])



class RestoreArchive(DBTestCase):
    def setUp(self):
        super().setUp()
        for patcher in (mock.patch.object(poll.overflows, "write_summary"),
                        mock.patch.object(poll.archive, "has_readings", return_value=True)):
            patcher.start()
            self.addCleanup(patcher.stop)

    def test_readings_are_restored_once_after_the_stations_are_listed(self):
        with mock.patch.object(poll.archive, "restore_readings", return_value=({"50140": 10}, {})) as restore:
            poll.restore_readings(self.con)          # no stations listed yet: wait
            restore.assert_not_called()
            self.add_station("50140")
            poll.restore_readings(self.con)
            poll.restore_readings(self.con)          # done already
        restore.assert_called_once()
        self.assertTrue(poll.db.get_meta(self.con, "archive_readings_restored"))

    def test_a_failed_readings_restore_is_tried_again(self):
        self.add_station("50140")
        with mock.patch.object(poll.archive, "restore_readings", side_effect=[OSError("disk"), ({}, {})]) as restore:
            poll.restore_readings(self.con)
            self.assertFalse(poll.db.get_meta(self.con, "archive_readings_restored"))
            poll.restore_readings(self.con)
        self.assertEqual(restore.call_count, 2)
        self.assertTrue(poll.db.get_meta(self.con, "archive_readings_restored"))

    def test_spills_wait_for_the_overflows_however_long_that_takes(self):
        # The stations are listed but the first overflow polls failed: the
        # spill logs mustn't be marked restored with nothing to load them into.
        self.add_station("50140")
        with mock.patch.object(poll.archive, "restore_spills", return_value={"SBB00257": 3}) as restore:
            poll.restore_spills(self.con)
            poll.restore_spills(self.con)
            restore.assert_not_called()
            self.assertFalse(poll.db.get_meta(self.con, "archive_spills_restored"))
            self.add_overflow("SBB00257")
            poll.restore_spills(self.con)
            poll.restore_spills(self.con)            # done already
        restore.assert_called_once()

    def test_readings_are_restored_before_the_latest_are_stored(self):
        # So `held` includes the archive, and the gap fill fetches only what
        # the archive doesn't hold.
        order = []
        with mock.patch.object(poll, "restore_readings", side_effect=lambda con: order.append("restore")), \
                mock.patch.object(poll.ea, "store_latest", side_effect=lambda con: order.append("latest") or ({}, {})), \
                mock.patch.object(poll.ea, "refresh_stations", return_value=0):
            poll.poll_gauges(self.con)
        self.assertEqual(order, ["restore", "latest"])

    def test_a_server_restored_before_the_split_isnt_restored_again(self):
        poll.db.set_meta(self.con, "archive_restored", 1)
        self.add_station("50140")
        self.add_overflow("SBB00257")
        with mock.patch.object(poll.archive, "restore_readings") as readings, \
                mock.patch.object(poll.archive, "restore_spills") as spills:
            poll.restore_readings(self.con)
            poll.restore_spills(self.con)
        readings.assert_not_called()
        spills.assert_not_called()


class DailyRefreshes(DBTestCase):
    def test_a_failed_overflow_list_refresh_doesnt_stop_the_spill_log(self):
        with mock.patch.object(poll.overflows, "refresh_overflows", side_effect=TimeoutError("annual returns down")), \
                mock.patch.object(poll.overflows, "poll_overflows", return_value=3) as live, \
                mock.patch.object(poll.overflows, "write_summary"):
            poll.poll_overflows(self.con, fresh=True)
        live.assert_called_once()
        self.assertFalse(poll.db.get_meta(self.con, "overflows_refreshed"))   # tried again next cycle

    def test_a_failed_flood_area_refresh_doesnt_stop_the_warnings(self):
        with mock.patch.object(poll.floods, "refresh_areas", side_effect=TimeoutError("down")), \
                mock.patch.object(poll.floods, "poll_warnings", return_value=[]) as warnings, \
                mock.patch.object(poll.floods, "write_summary"):
            poll.poll_floods(self.con, fresh=True)
        warnings.assert_called_once()
        self.assertFalse(poll.db.get_meta(self.con, "flood_areas_refreshed"))


class Drought(DBTestCase):
    def test_a_report_that_fails_is_tried_again_in_an_hour_not_every_cycle(self):
        with mock.patch.object(poll.drought, "poll", side_effect=ValueError("no stage sections")) as report, \
                mock.patch.object(poll.time, "time", return_value=1_000_000):
            with self.assertRaises(ValueError):
                poll.poll_drought(self.con)
            poll.poll_drought(self.con)               # five minutes later: not yet
            self.assertEqual(report.call_count, 1)
        with mock.patch.object(poll.drought, "poll", side_effect=ValueError("still")) as report, \
                mock.patch.object(poll.time, "time", return_value=1_000_000 + poll.DROUGHT_RETRY + 1):
            with self.assertRaises(ValueError):
                poll.poll_drought(self.con)
        report.assert_called_once()


if __name__ == "__main__":
    unittest.main()
