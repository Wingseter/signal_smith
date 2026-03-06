"""Tests for account service caching logic."""

import asyncio
import json
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, patch

from app.services.account_service import AccountService, CACHE_KEY, STALE_THRESHOLD


def _fresh_timestamp():
    return (datetime.now() - timedelta(seconds=30)).isoformat()


def _stale_timestamp():
    return (datetime.now() - timedelta(minutes=5)).isoformat()


class TestGetCachedSummary:
    def _make_svc_and_redis(self, cached_value=None):
        svc = AccountService()
        mock_redis = AsyncMock()
        mock_redis.get = AsyncMock(return_value=cached_value)
        return svc, mock_redis

    def test_cache_miss(self):
        svc, mock_redis = self._make_svc_and_redis(None)

        async def _get_redis():
            return mock_redis

        with patch("app.core.redis.get_redis", _get_redis):
            result = asyncio.run(svc._get_cached_summary())
        assert result is None

    def test_cache_fresh(self):
        data = {"balance": 1000, "updated_at": _fresh_timestamp()}
        svc, mock_redis = self._make_svc_and_redis(json.dumps(data))

        async def _get_redis():
            return mock_redis

        with patch("app.core.redis.get_redis", _get_redis):
            result = asyncio.run(svc._get_cached_summary())
        assert result is not None
        assert result["balance"] == 1000

    def test_cache_stale(self):
        data = {"balance": 1000, "updated_at": _stale_timestamp()}
        svc, mock_redis = self._make_svc_and_redis(json.dumps(data))

        async def _get_redis():
            return mock_redis

        with patch("app.core.redis.get_redis", _get_redis):
            result = asyncio.run(svc._get_cached_summary())
        assert result is None

    def test_cache_no_timestamp(self):
        data = {"balance": 1000}
        svc, mock_redis = self._make_svc_and_redis(json.dumps(data))

        async def _get_redis():
            return mock_redis

        with patch("app.core.redis.get_redis", _get_redis):
            result = asyncio.run(svc._get_cached_summary())
        assert result is not None
        assert result["balance"] == 1000

    def test_redis_error(self):
        svc = AccountService()

        async def _broken_redis():
            raise ConnectionError("redis down")

        with patch("app.core.redis.get_redis", _broken_redis):
            result = asyncio.run(svc._get_cached_summary())
        assert result is None


class TestGetAccountSummary:
    def test_returns_cache_when_fresh(self):
        svc = AccountService()
        cached_data = {"balance": 2000, "updated_at": _fresh_timestamp()}
        svc._get_cached_summary = AsyncMock(return_value=cached_data)
        svc._refresh_and_cache = AsyncMock()

        result = asyncio.run(svc.get_account_summary())
        assert result["balance"] == 2000
        svc._refresh_and_cache.assert_not_called()

    def test_refreshes_on_cache_miss(self):
        svc = AccountService()
        fresh = {"balance": 3000, "updated_at": _fresh_timestamp()}
        svc._get_cached_summary = AsyncMock(return_value=None)
        svc._refresh_and_cache = AsyncMock(return_value=fresh)

        result = asyncio.run(svc.get_account_summary())
        assert result["balance"] == 3000
        svc._refresh_and_cache.assert_called_once()

    def test_force_refresh_bypasses_cache(self):
        svc = AccountService()
        fresh = {"balance": 4000, "updated_at": _fresh_timestamp()}
        svc._get_cached_summary = AsyncMock(return_value={"balance": 1})
        svc._refresh_and_cache = AsyncMock(return_value=fresh)

        result = asyncio.run(svc.get_account_summary(force_refresh=True))
        assert result["balance"] == 4000
        svc._get_cached_summary.assert_not_called()


class TestRefreshAndCache:
    def test_calls_trading_service_and_caches(self):
        svc = AccountService()
        mock_redis = AsyncMock()
        mock_trading = AsyncMock()
        mock_trading.get_account_balance = AsyncMock(return_value={"total": 5000})
        mock_trading.get_holdings = AsyncMock(return_value=[{"symbol": "005930"}])

        async def _get_redis():
            return mock_redis

        with patch("app.core.redis.get_redis", _get_redis), \
             patch("app.services.trading_service.trading_service", mock_trading):
            result = asyncio.run(svc._refresh_and_cache())

        assert result["balance"] == {"total": 5000}
        assert result["count"] == 1
        assert "updated_at" in result
        mock_redis.set.assert_called_once()

    def test_redis_failure_still_returns_data(self):
        svc = AccountService()
        mock_redis = AsyncMock()
        mock_redis.set = AsyncMock(side_effect=ConnectionError("redis down"))
        mock_trading = AsyncMock()
        mock_trading.get_account_balance = AsyncMock(return_value={"total": 5000})
        mock_trading.get_holdings = AsyncMock(return_value=[])

        async def _get_redis():
            return mock_redis

        with patch("app.core.redis.get_redis", _get_redis), \
             patch("app.services.trading_service.trading_service", mock_trading):
            result = asyncio.run(svc._refresh_and_cache())

        assert result["balance"] == {"total": 5000}
