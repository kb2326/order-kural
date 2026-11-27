"""A small in-memory cost guard for the public live link: per-IP per hour, and a cap per day for everyone."""
from __future__ import annotations

import threading
import time
from collections import deque

HOUR = 3600
DAY = 86400


class RateLimiter:
    def __init__(self, per_ip_hour: int, per_day: int, clock=time.monotonic):
        self.per_ip_hour = per_ip_hour
        self.per_day = per_day
        self.clock = clock
        self._ip: dict[str, deque] = {}
        self._all: deque = deque()
        self._lock = threading.Lock()

    def allow(self, ip: str) -> bool:
        with self._lock:
            now = self.clock()
            while self._all and now - self._all[0] >= DAY:
                self._all.popleft()
            mine = self._ip.setdefault(ip, deque())
            while mine and now - mine[0] >= HOUR:
                mine.popleft()
            if len(mine) >= self.per_ip_hour or len(self._all) >= self.per_day:
                return False
            mine.append(now)
            self._all.append(now)
            return True
