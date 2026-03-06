"""
Account service — unified account summary with Redis caching.

Consolidates duplicate logic from routes/council.py (_get_account_summary)
and services/tasks/scanning_tasks.py (_refresh_account_summary_async).
"""

import json
import logging
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

CACHE_KEY = "account:summary"
STALE_THRESHOLD = timedelta(minutes=3)
CACHE_TTL_SECONDS = 90


class AccountService:
    """Kiwoom account balance + holdings with Redis caching."""

    async def get_account_summary(self, force_refresh: bool = False) -> dict:
        """Get cached account summary. Falls back to Kiwoom API on cache miss.

        Background task (refresh_account_summary) refreshes the cache every 30s.
        """
        if not force_refresh:
            cached = await self._get_cached_summary()
            if cached is not None:
                return cached

        return await self._refresh_and_cache()

    async def refresh_summary(self) -> dict:
        """Force-refresh from Kiwoom API and update cache. Called by Celery task."""
        return await self._refresh_and_cache()

    async def _get_cached_summary(self) -> dict | None:
        """Return cached summary if fresh enough, else None."""
        from app.core.redis import get_redis

        try:
            redis = await get_redis()
            cached = await redis.get(CACHE_KEY)
            if not cached:
                return None

            cached_data = json.loads(cached)
            updated_at = cached_data.get("updated_at")
            if updated_at:
                try:
                    cached_at = datetime.fromisoformat(updated_at)
                    if datetime.now() - cached_at <= STALE_THRESHOLD:
                        return cached_data
                except ValueError:
                    pass
            else:
                return cached_data
        except Exception:
            pass

        return None

    async def _refresh_and_cache(self) -> dict:
        """Call Kiwoom API and store result in Redis."""
        from app.core.redis import get_redis
        from app.services.trading_service import trading_service

        balance = await trading_service.get_account_balance()
        holdings = await trading_service.get_holdings()

        result = {
            "balance": balance,
            "holdings": holdings,
            "count": len(holdings),
            "updated_at": datetime.now().isoformat(),
        }

        try:
            redis = await get_redis()
            await redis.set(CACHE_KEY, json.dumps(result), ex=CACHE_TTL_SECONDS)
        except Exception:
            pass

        return result


account_service = AccountService()
