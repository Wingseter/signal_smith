"""Unified WebSocket connection managers.

Replaces per-route ``ConnectionManager`` classes with shared, tested
implementations. All existing WebSocket API contracts are preserved.
"""

import logging
from typing import Dict, List, Set

from fastapi import WebSocket

logger = logging.getLogger(__name__)


class BaseConnectionManager:
    """Simple broadcast-capable WebSocket manager.

    Usage (in route modules)::

        manager = BaseConnectionManager("council")

        @router.websocket("/ws")
        async def ws(websocket: WebSocket):
            await manager.connect(websocket)
            ...
    """

    def __init__(self, name: str = "default"):
        self.name = name
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        self.active_connections.append(websocket)
        logger.info("[%s] WebSocket connected (%d active)", self.name, len(self.active_connections))

    def disconnect(self, websocket: WebSocket) -> None:
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
        logger.info("[%s] WebSocket disconnected (%d active)", self.name, len(self.active_connections))

    async def broadcast(self, message: dict) -> None:
        """Send *message* to all connections, cleaning up broken ones."""
        disconnected: List[WebSocket] = []
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception as exc:
                logger.debug("[%s] broadcast send error: %s", self.name, exc)
                disconnected.append(connection)
        for conn in disconnected:
            self.disconnect(conn)

    async def send_personal(self, message: dict, websocket: WebSocket) -> None:
        try:
            await websocket.send_json(message)
        except Exception:
            logger.debug("[%s] personal send failed", self.name)


class ChannelConnectionManager:
    """Channel- and symbol-subscription-aware WebSocket manager.

    Used for the ``/ws/market`` endpoint that needs per-symbol subscriptions.
    """

    def __init__(self, name: str = "channel"):
        self.name = name
        self.active_connections: Dict[str, Set[WebSocket]] = {}
        self.symbol_subscriptions: Dict[WebSocket, Set[str]] = {}

    async def connect(self, websocket: WebSocket, channel: str = "default") -> None:
        await websocket.accept()
        if channel not in self.active_connections:
            self.active_connections[channel] = set()
        self.active_connections[channel].add(websocket)
        self.symbol_subscriptions[websocket] = set()
        logger.info("[%s/%s] WebSocket connected", self.name, channel)

    def disconnect(self, websocket: WebSocket, channel: str = "default") -> None:
        if channel in self.active_connections:
            self.active_connections[channel].discard(websocket)
        self.symbol_subscriptions.pop(websocket, None)
        logger.info("[%s/%s] WebSocket disconnected", self.name, channel)

    async def send_personal(self, message: dict, websocket: WebSocket) -> None:
        try:
            await websocket.send_json(message)
        except Exception:
            logger.debug("[%s] personal send failed", self.name)

    async def broadcast(self, message: dict, channel: str = "default") -> None:
        if channel not in self.active_connections:
            return
        disconnected: List[WebSocket] = []
        for connection in self.active_connections[channel]:
            try:
                await connection.send_json(message)
            except Exception:
                logger.debug("[%s/%s] broadcast send failed", self.name, channel)
                disconnected.append(connection)
        for conn in disconnected:
            self.disconnect(conn, channel)

    async def broadcast_to_symbol_subscribers(self, symbol: str, message: dict) -> None:
        disconnected: List[WebSocket] = []
        for websocket, symbols in self.symbol_subscriptions.items():
            if symbol in symbols:
                try:
                    await websocket.send_json(message)
                except Exception:
                    logger.debug("[%s] symbol broadcast failed for %s", self.name, symbol)
                    disconnected.append(websocket)
        for conn in disconnected:
            self.disconnect(conn)

    def subscribe_symbol(self, websocket: WebSocket, symbol: str) -> None:
        if websocket in self.symbol_subscriptions:
            self.symbol_subscriptions[websocket].add(symbol)

    def unsubscribe_symbol(self, websocket: WebSocket, symbol: str) -> None:
        if websocket in self.symbol_subscriptions:
            self.symbol_subscriptions[websocket].discard(symbol)

    def get_subscribed_symbols(self, websocket: WebSocket) -> Set[str]:
        return self.symbol_subscriptions.get(websocket, set())
