"""The poll cycle: every feed is polled, and filling gauge history comes last."""

import unittest
from unittest import mock

from monitor import poll
from tests.support import QuietTestCase


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
                mock.patch.object(poll, "poll_floods", side_effect=step("floods")), \
                mock.patch.object(poll, "poll_weather", side_effect=step("weather")), \
                mock.patch.object(poll, "poll_powercuts", side_effect=step("power")), \
                mock.patch.object(poll, "poll_drought", side_effect=step("drought")), \
                mock.patch.object(poll, "fill_gauge_gaps", side_effect=step("fill")):
            poll.cycle()
        return order

    def test_filling_gauge_history_comes_last(self):
        self.assertEqual(self.run_cycle(), ["gauges", "overflows", "floods", "weather", "power", "drought", "fill"])

    def test_a_failing_feed_doesnt_stop_the_others(self):
        order = self.run_cycle(overflows=TimeoutError("no complete answer within 120 s"))
        self.assertEqual(order, ["gauges", "overflows", "floods", "weather", "power", "drought", "fill"])

    def test_the_first_cycle_reads_every_feed_afresh(self):
        first, second = [], []
        self.run_cycle(fresh=first)
        self.run_cycle(fresh=second)
        self.assertEqual(first, [True] * 6)
        self.assertEqual(second, [False] * 6)

    def test_no_history_fill_when_the_gauges_failed(self):
        order = self.run_cycle(gauges=TimeoutError("timed out"))
        self.assertEqual(order, ["gauges", "overflows", "floods", "weather", "power", "drought"])


if __name__ == "__main__":
    unittest.main()
