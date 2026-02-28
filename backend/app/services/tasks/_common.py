"""Shared helpers for Celery tasks."""

import asyncio
import logging

logger = logging.getLogger(__name__)


def run_async(coro):
    """Run an async coroutine from a synchronous Celery task context.

    Uses asyncio.run() which creates a fresh event loop per call,
    avoiding loop reuse/pollution across Celery worker threads.
    """
    return asyncio.run(coro)


def is_market_hours() -> bool:
    """Return True when the market accepts orders (KST).

    Delegates to trading_hours.can_execute_order() for single source of truth,
    covering regular (09:00-15:30), pre-market (08:30-09:00),
    and post-market (15:40-18:30) sessions.
    """
    from app.services.council.trading_hours import trading_hours

    can_trade, _ = trading_hours.can_execute_order()
    return can_trade
