"""Small in-memory sliding-window rate limiter for the website login box."""

import time
from collections import defaultdict, deque


class RateLimiter:
    def __init__(self, rules: list[tuple[int, float]], global_rule: tuple[int, float]):
        """rules: (max requests, window seconds) per key; global_rule applies to everyone."""
        self.rules = rules
        self.global_rule = global_rule
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        self._all: deque[float] = deque()

    @staticmethod
    def _count(q: deque[float], window: float, now: float) -> int:
        return sum(1 for t in q if now - t < window)

    def check(self, key: str, now: float | None = None) -> float:
        """Return 0 if allowed (and count it), else seconds until the next try is allowed."""
        now = time.time() if now is None else now
        longest = max([w for _, w in self.rules] + [self.global_rule[1]])
        q = self._hits[key]
        while q and now - q[0] >= longest:
            q.popleft()
        while self._all and now - self._all[0] >= self.global_rule[1]:
            self._all.popleft()

        waits = []
        for limit, window in self.rules:
            recent = [t for t in q if now - t < window]
            if len(recent) >= limit:
                waits.append(window - (now - recent[0]))
        limit, window = self.global_rule
        if len(self._all) >= limit:
            waits.append(window - (now - self._all[0]))
        if waits:
            return max(1.0, max(waits))

        q.append(now)
        self._all.append(now)
        if len(self._hits) > 10000:  # forget idle visitors
            for k in [k for k, v in self._hits.items() if not v]:
                del self._hits[k]
        return 0.0
