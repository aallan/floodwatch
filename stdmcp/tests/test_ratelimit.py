import threading
import unittest

from stdmcp.ratelimit import Limiter, TokenBucket


class FakeClock:
    def __init__(self):
        self.now = 1000.0

    def __call__(self):
        return self.now

    def advance(self, seconds):
        self.now += seconds


class TokenBucketTests(unittest.TestCase):
    def test_burst_then_refill(self):
        clock = FakeClock()
        bucket = TokenBucket(300, 60, clock=clock)
        for _ in range(60):
            self.assertEqual(bucket.take(), 0)
        self.assertAlmostEqual(bucket.take(), 0.2)
        clock.advance(0.2)
        self.assertEqual(bucket.take(), 0)
        self.assertGreater(bucket.take(), 0)

    def test_refill_is_capped_at_burst(self):
        clock = FakeClock()
        bucket = TokenBucket(300, 5, clock=clock)
        clock.advance(3600)
        for _ in range(5):
            self.assertEqual(bucket.take(), 0)
        self.assertGreater(bucket.take(), 0)


class LimiterTests(unittest.TestCase):
    def test_overall_limit_applies_across_clients(self):
        clock = FakeClock()
        limiter = Limiter(per_client=(60, 10), overall=(60, 3), clock=clock)
        self.assertEqual(limiter.check("a"), 0)
        self.assertEqual(limiter.check("b"), 0)
        self.assertEqual(limiter.check("c"), 0)
        self.assertAlmostEqual(limiter.check("d"), 1.0)

    def test_refusal_by_one_bucket_spends_nothing_from_the_other(self):
        clock = FakeClock()
        limiter = Limiter(per_client=(60, 1), overall=(60, 2), clock=clock)
        self.assertEqual(limiter.check("a"), 0)
        # "a" is refused by its own bucket, so the overall bucket keeps its second token.
        self.assertGreater(limiter.check("a"), 0)
        self.assertEqual(limiter.check("b"), 0)
        # And a refusal by the overall bucket leaves the client's own token intact.
        self.assertGreater(limiter.check("c"), 0)
        clock.advance(1)
        self.assertEqual(limiter.check("c"), 0)

    def test_retry_after_is_positive_and_small(self):
        clock = FakeClock()
        limiter = Limiter(per_client=(300, 60), overall=(600, 120), clock=clock)
        for _ in range(60):
            self.assertEqual(limiter.check("a"), 0)
        wait = limiter.check("a")
        self.assertGreater(wait, 0)
        self.assertLessEqual(wait, 1.0)

    def test_idle_clients_are_forgotten(self):
        clock = FakeClock()
        limiter = Limiter(per_client=(60, 1), overall=(6000, 1000), max_clients=3, clock=clock)
        self.assertEqual(limiter.check("a"), 0)
        self.assertGreater(limiter.check("a"), 0)
        for name in ("b", "c", "d"):
            self.assertEqual(limiter.check(name), 0)
        self.assertLessEqual(len(limiter._clients), 3)
        # "a" was the least recently used, so it was dropped and starts afresh.
        self.assertEqual(limiter.check("a"), 0)

    def test_recently_used_clients_survive_eviction(self):
        clock = FakeClock()
        limiter = Limiter(per_client=(60, 1), overall=(6000, 1000), max_clients=2, clock=clock)
        limiter.check("a")
        limiter.check("b")
        limiter.check("a")  # touch "a", so "b" is now the oldest
        limiter.check("c")
        self.assertGreater(limiter.check("a"), 0)

    def test_threads_never_exceed_the_burst(self):
        clock = FakeClock()
        limiter = Limiter(per_client=(60, 50), overall=(60, 50), clock=clock)
        allowed = []

        def worker():
            for _ in range(20):
                if limiter.check("a") == 0:
                    allowed.append(1)

        threads = [threading.Thread(target=worker) for _ in range(8)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        self.assertEqual(len(allowed), 50)


if __name__ == "__main__":
    unittest.main()
