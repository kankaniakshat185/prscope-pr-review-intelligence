from unittest.mock import patch

import pytest
from fastapi import HTTPException

from app.services.rate_limiter import RateLimiter, analyze_rate_limiter


def test_allows_requests_up_to_the_limit():
    limiter = RateLimiter(max_requests=3, window_seconds=60)
    limiter.check(1)
    limiter.check(1)
    limiter.check(1)  # 3rd request, still within the limit - should not raise


def test_rejects_requests_over_the_limit():
    limiter = RateLimiter(max_requests=2, window_seconds=60)
    limiter.check(1)
    limiter.check(1)
    with pytest.raises(HTTPException) as exc_info:
        limiter.check(1)
    assert exc_info.value.status_code == 429
    assert "Retry-After" in exc_info.value.headers


def test_users_are_tracked_independently():
    limiter = RateLimiter(max_requests=1, window_seconds=60)
    limiter.check(1)  # user 1 uses their one slot
    limiter.check(2)  # user 2 is unaffected by user 1's usage
    with pytest.raises(HTTPException):
        limiter.check(1)  # user 1 is now over their own limit


def test_old_requests_age_out_of_the_window():
    with patch("app.services.rate_limiter.time.monotonic") as mock_time:
        limiter = RateLimiter(max_requests=1, window_seconds=60)

        mock_time.return_value = 1000.0
        limiter.check(1)  # uses the one slot at t=1000

        with pytest.raises(HTTPException):
            limiter.check(1)  # still within the 60s window

        mock_time.return_value = 1000.0 + 61  # 61s later - window has expired
        limiter.check(1)  # should succeed again, old request aged out


def test_analyze_endpoint_enforces_the_rate_limit(client, mock_token):
    # Temporarily zero out the limit so the very first authenticated request
    # is rejected before touching GitHub or any LLM provider - proves the
    # dependency is actually wired into the route, not just unit-correct.
    original_max = analyze_rate_limiter.max_requests
    analyze_rate_limiter.max_requests = 0
    try:
        r = client.post(
            "/api/analysis/analyze",
            headers={"Authorization": f"Bearer {mock_token}"},
            json={"repo_url": "https://github.com/x/y", "pr_number": 1},
        )
        assert r.status_code == 429
        assert "Retry-After" in r.headers
    finally:
        analyze_rate_limiter.max_requests = original_max
