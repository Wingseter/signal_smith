"""Tests for Redis-based rate limiter."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi import HTTPException

from app.core.rate_limit import RateLimiter


@pytest.fixture
def limiter():
    return RateLimiter(max_requests=3, window_seconds=60)


@pytest.fixture
def mock_request():
    req = MagicMock()
    req.client = MagicMock()
    req.client.host = "127.0.0.1"
    req.url = MagicMock()
    req.url.path = "/auth/login"
    return req


class TestRateLimiter:
    @pytest.mark.asyncio
    async def test_allows_under_limit(self, limiter, mock_request):
        mock_redis = AsyncMock()
        mock_redis.incr = AsyncMock(return_value=1)
        mock_redis.expire = AsyncMock()

        with patch("app.core.redis.get_redis", new_callable=AsyncMock, return_value=mock_redis):
            await limiter(mock_request)  # should not raise

    @pytest.mark.asyncio
    async def test_blocks_over_limit(self, limiter, mock_request):
        mock_redis = AsyncMock()
        mock_redis.incr = AsyncMock(return_value=4)  # exceeds max_requests=3
        mock_redis.ttl = AsyncMock(return_value=30)

        with patch("app.core.redis.get_redis", new_callable=AsyncMock, return_value=mock_redis):
            with pytest.raises(HTTPException) as exc_info:
                await limiter(mock_request)
            assert exc_info.value.status_code == 429

    @pytest.mark.asyncio
    async def test_sets_expire_on_first_request(self, limiter, mock_request):
        mock_redis = AsyncMock()
        mock_redis.incr = AsyncMock(return_value=1)
        mock_redis.expire = AsyncMock()

        with patch("app.core.redis.get_redis", new_callable=AsyncMock, return_value=mock_redis):
            await limiter(mock_request)
            mock_redis.expire.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_allows_when_redis_unavailable(self, limiter, mock_request):
        """If Redis is down, requests should be allowed through."""

        async def failing_get_redis():
            raise ConnectionError("Redis down")

        with patch("app.core.redis.get_redis", side_effect=failing_get_redis):
            await limiter(mock_request)  # should not raise

    def test_key_includes_ip_and_path(self, limiter, mock_request):
        key = limiter._key(mock_request)
        assert "127.0.0.1" in key
        assert "/auth/login" in key
