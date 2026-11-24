import asyncio

from backend.app.services.rate_limit import LeadRateLimiter


def test_lead_limit_applies_to_authenticated_user_across_ip_addresses():
    async def check() -> None:
        limiter = LeadRateLimiter(limit=3, window_seconds=3600)
        assert await limiter.allow("192.0.2.1", 42)
        assert await limiter.allow("192.0.2.2", 42)
        assert await limiter.allow("192.0.2.3", 42)
        assert not await limiter.allow("192.0.2.4", 42)

    asyncio.run(check())


def test_lead_limit_applies_to_ip_across_users():
    async def check() -> None:
        limiter = LeadRateLimiter(limit=2, window_seconds=3600)
        assert await limiter.allow("192.0.2.1", 1)
        assert await limiter.allow("192.0.2.1", 2)
        assert not await limiter.allow("192.0.2.1", 3)

    asyncio.run(check())
