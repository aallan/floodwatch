"""Token bucket rate limiting: one bucket per client plus one for everybody."""

import threading
import time
from collections import OrderedDict


class TokenBucket:
    """A bucket holding up to ``burst`` tokens, refilled at ``rate_per_minute``.

    Not thread-safe on its own; ``Limiter`` serialises access with a lock.
    """

    def __init__(self, rate_per_minute, burst, clock=time.monotonic):
        self._rate = rate_per_minute / 60.0
        self._burst = burst
        self._clock = clock
        self._tokens = float(burst)
        self._stamp = clock()

    def wait(self):
        """Seconds until a token is available (0 if one is now). Takes nothing."""
        now = self._clock()
        elapsed = max(0.0, now - self._stamp)
        self._stamp = now
        self._tokens = min(self._burst, self._tokens + elapsed * self._rate)
        if self._tokens >= 1:
            return 0.0
        return (1 - self._tokens) / self._rate

    def spend(self):
        self._tokens -= 1

    def take(self):
        """Take a token. Returns 0 if allowed, else the seconds until one is."""
        delay = self.wait()
        if delay == 0:
            self.spend()
        return delay


class Limiter:
    """Allows a request only if both the client's bucket and the overall bucket have a token."""

    def __init__(self, per_client, overall, max_clients=10_000, clock=time.monotonic):
        self._per_client = per_client
        self._clock = clock
        self._max_clients = max_clients
        self._overall = TokenBucket(*overall, clock=clock)
        self._clients = OrderedDict()
        self._lock = threading.Lock()

    def check(self, client):
        """Count one request. Returns 0 if allowed, else the seconds the client should wait."""
        with self._lock:
            bucket = self._clients.get(client)
            if bucket is None:
                bucket = TokenBucket(*self._per_client, clock=self._clock)
            delay = max(bucket.wait(), self._overall.wait())
            if delay == 0:
                bucket.spend()
                self._overall.spend()
            self._remember(client, bucket)
            return delay

    def _remember(self, client, bucket):
        self._clients[client] = bucket
        self._clients.move_to_end(client)
        while len(self._clients) > self._max_clients:
            self._clients.popitem(last=False)
