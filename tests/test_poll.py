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
                mock.patch.object(poll, "restore_archive", side_effect=step("archive")), \
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
    def test_restores_once_after_the_stations_are_listed(self):
        with mock.patch.object(poll.archive, "restore", return_value=(10, 2, {})) as restore, \
                mock.patch.object(poll.live, "write"), mock.patch.object(poll.overflows, "write_summary"):
            poll.restore_archive(self.con)          # no stations listed yet: wait
            restore.assert_not_called()
            self.add_station("50140")
            poll.restore_archive(self.con)
            poll.restore_archive(self.con)          # done already
        restore.assert_called_once()
        self.assertTrue(poll.db.get_meta(self.con, "archive_restored"))


if __name__ == "__main__":
    unittest.main()
