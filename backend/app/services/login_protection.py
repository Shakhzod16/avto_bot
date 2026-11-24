"""Process-local login lockout after repeated failed admin logins."""

from __future__ import annotations

import asyncio
import time
from collections import defaultdict, deque


class LoginAttemptTracker:
    """Lock a username/IP pair for 15 minutes after five failed attempts."""

    def __init__(
        self,
        max_attempts: int = 5,
        window_seconds: int = 15 * 60,
    ) -> None:
        self.max_attempts = max_attempts
        self.window_seconds = window_seconds
        self._failures: dict[str, deque[float]] = defaultdict(deque)
        self._locked_until: dict[str, float] = {}
        self._lock = asyncio.Lock()

    async def remaining_lock_seconds(self, key: str) -> int:
        now = time.monotonic()
        async with self._lock:
            until = self._locked_until.get(key, 0)
            if until <= now:
                self._locked_until.pop(key, None)
                self._failures.pop(key, None)
                return 0
            return max(1, int(until - now))

    async def record_failure(self, key: str) -> int:
        now = time.monotonic()
        cutoff = now - self.window_seconds
        async with self._lock:
            failures = self._failures[key]
            while failures and failures[0] <= cutoff:
                failures.popleft()
            failures.append(now)
            if len(failures) >= self.max_attempts:
                self._locked_until[key] = now + self.window_seconds
                failures.clear()
                return self.window_seconds
            return 0

    async def reset(self, key: str) -> None:
        async with self._lock:
            self._failures.pop(key, None)
            self._locked_until.pop(key, None)


admin_login_tracker = LoginAttemptTracker()
