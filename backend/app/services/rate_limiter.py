"""
Minimal in-memory, per-user sliding-window rate limiter.

Deliberately not using a library (e.g. slowapi) here: the need is narrow
(limit one specific route by authenticated user_id), and an in-memory dict
is sufficient for a single-process deployment. If this backend ever runs as
multiple instances, this state would need to move to something shared
(Redis) - it's process-local by design right now.
"""

import time
from collections import defaultdict
from typing import Dict, List

from fastapi import Depends, HTTPException

from app.services.auth import verify_token


class RateLimiter:
    def __init__(self, max_requests: int, window_seconds: int):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._requests: Dict[int, List[float]] = defaultdict(list)

    def check(self, key: int) -> None:
        now = time.monotonic()
        window_start = now - self.window_seconds
        timestamps = self._requests[key]

        while timestamps and timestamps[0] < window_start:
            timestamps.pop(0)

        if len(timestamps) >= self.max_requests:
            # timestamps can legitimately be empty here if max_requests is 0
            # (nothing to age out yet) - fall back to the full window in that case.
            retry_after = int(self.window_seconds - (now - timestamps[0])) + 1 if timestamps else self.window_seconds
            raise HTTPException(
                status_code=429,
                detail=f"Rate limit exceeded: max {self.max_requests} analysis requests per "
                       f"{self.window_seconds} seconds. Try again in about {retry_after}s.",
                headers={"Retry-After": str(retry_after)},
            )

        timestamps.append(now)

    def reset(self) -> None:
        """Test-only: clear all tracked state."""
        self._requests.clear()


# 10 analyses per 5-minute window per user. Generous enough for normal
# interactive use (reviewing several PRs in a session) while bounding a
# single user hammering the endpoint - each call already fans out into
# several GitHub API calls and several LLM calls.
analyze_rate_limiter = RateLimiter(max_requests=10, window_seconds=300)


def rate_limited_user(user_id: int = Depends(verify_token)) -> int:
    """Drop-in replacement for `Depends(verify_token)` that also enforces
    the per-user rate limit before the route body runs."""
    analyze_rate_limiter.check(user_id)
    return user_id
