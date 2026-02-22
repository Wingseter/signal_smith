"""Central event bus for decoupled service-to-service communication.

Replaces ad-hoc ``add_*_callback`` lists on service singletons with a
single, typed publish/subscribe mechanism.
"""

import logging
from typing import Any, Awaitable, Callable, Dict, List

logger = logging.getLogger(__name__)

# ── Event name constants ──

SIGNAL_CREATED = "signal.created"
MEETING_COMPLETED = "meeting.completed"
MEETING_UPDATED = "meeting.updated"
SCAN_RESULT = "scan.result"
SCAN_UPDATE = "scan.update"
NEWS_CRAWLED = "news.crawled"
NEWS_ANALYZED = "news.analyzed"

Listener = Callable[..., Awaitable[Any]]


class EventBus:
    """Simple async pub/sub event bus."""

    def __init__(self) -> None:
        self._listeners: Dict[str, List[Listener]] = {}

    def on(self, event: str, listener: Listener) -> None:
        """Register *listener* for *event*."""
        self._listeners.setdefault(event, []).append(listener)

    def off(self, event: str, listener: Listener) -> None:
        """Unregister *listener* from *event*."""
        listeners = self._listeners.get(event, [])
        if listener in listeners:
            listeners.remove(listener)

    async def emit(self, event: str, *args: Any, **kwargs: Any) -> None:
        """Emit *event*, calling all registered listeners.

        Errors in individual listeners are logged but do not propagate.
        """
        for listener in self._listeners.get(event, []):
            try:
                await listener(*args, **kwargs)
            except Exception:
                logger.error("Event listener error for '%s'", event, exc_info=True)


# Module-level singleton
event_bus = EventBus()
