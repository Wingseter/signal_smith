"""Structured audit logging for signal lifecycle events.

Provides both sync (Celery) and async (FastAPI) functions that:
1. Emit a structured log line (picked up by JSONFormatter)
2. Persist a SignalEvent row to the database

DB write failures are logged but never propagated — audit is non-fatal.
"""

import logging
from typing import Optional

from app.models.transaction import SignalEvent

logger = logging.getLogger(__name__)


def log_signal_event(
    event_type: str,
    symbol: str,
    action: Optional[str] = None,
    signal_id: Optional[int] = None,
    details: Optional[dict] = None,
) -> None:
    """Sync audit event (for Celery tasks). Uses get_sync_db."""
    extra = {
        "event_type": event_type,
        "symbol": symbol,
        "action": action,
        "signal_id": signal_id,
    }
    if details:
        extra["details"] = details
    logger.info(
        "signal_event: %s %s %s", event_type, symbol, action or "",
        extra={"extra_data": extra},
    )

    try:
        from app.core.database import get_sync_db

        with get_sync_db() as db:
            event = SignalEvent(
                signal_id=signal_id,
                event_type=event_type,
                symbol=symbol,
                action=action,
                details=details,
            )
            db.add(event)
            # commit handled by context manager
    except Exception:
        logger.warning("Failed to persist signal_event to DB", exc_info=True)


async def log_signal_event_async(
    event_type: str,
    symbol: str,
    action: Optional[str] = None,
    signal_id: Optional[int] = None,
    details: Optional[dict] = None,
) -> None:
    """Async audit event (for FastAPI / orchestrator). Uses async_session_maker."""
    extra = {
        "event_type": event_type,
        "symbol": symbol,
        "action": action,
        "signal_id": signal_id,
    }
    if details:
        extra["details"] = details
    logger.info(
        "signal_event: %s %s %s", event_type, symbol, action or "",
        extra={"extra_data": extra},
    )

    try:
        from app.core.database import async_session_maker

        async with async_session_maker() as session:
            event = SignalEvent(
                signal_id=signal_id,
                event_type=event_type,
                symbol=symbol,
                action=action,
                details=details,
            )
            session.add(event)
            await session.commit()
    except Exception:
        logger.warning("Failed to persist signal_event to DB", exc_info=True)
