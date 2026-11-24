"""Small in-process sliding-window limiter for public lead submissions."""

from __future__ import annotations

import asyncio
import time
from collections import defaultdict, deque

from backend.app.core.config import LEAD_RATE_LIMIT, LEAD_RATE_WINDOW_SECONDS


class LeadRateLimiter:
    """Limit successful lead submissions per IP address and authenticated user."""

    def __init__(
        self,
        limit: int = LEAD_RATE_LIMIT,
        window_seconds: int = LEAD_RATE_WINDOW_SECONDS,
    ) -> None:
        self.limit = limit
        self.window_seconds = window_seconds
        self._events: dict[str, deque[float]] = defaultdict(deque)
        self._lock = asyncio.Lock()

    async def allow(self, ip_address: str, user_id: int) -> bool:
        """Return false if either the caller IP or user exceeded the limit."""
        now = time.monotonic()
        cutoff = now - self.window_seconds
        keys = (f"ip:{ip_address}", f"user:{user_id}")

        async with self._lock:
            for key, events in list(self._events.items()):
                while events and events[0] <= cutoff:
                    events.popleft()
                if not events:
                    self._events.pop(key, None)

            if any(len(self._events[key]) >= self.limit for key in keys):
                return False

            for key in keys:
                self._events[key].append(now)
            return True


lead_rate_limiter = LeadRateLimiter()
