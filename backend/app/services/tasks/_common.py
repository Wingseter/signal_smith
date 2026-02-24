"""Shared helpers for Celery tasks."""

import asyncio
import logging

logger = logging.getLogger(__name__)


def run_async(coro):
    """Helper to run async functions in sync Celery context."""
    try:
        loop = asyncio.get_event_loop()
        if loop.is_closed():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    return loop.run_until_complete(coro)


def is_market_hours() -> bool:
    """Check if Korean stock market is open (KST)."""
    from app.services.council.trading_hours import trading_hours, MarketSession

    session = trading_hours.get_market_session()
    return session in (MarketSession.REGULAR,)
