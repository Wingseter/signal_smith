import json
from typing import Dict, Set

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

router = APIRouter()


class ConnectionManager:
    """WebSocket connection manager."""

    def __init__(self):
        self.active_connections: Dict[str, Set[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, channel: str = "default"):
        await websocket.accept()
        if channel not in self.active_connections:
            self.active_connections[channel] = set()
        self.active_connections[channel].add(websocket)

    def disconnect(self, websocket: WebSocket, channel: str = "default"):
        if channel in self.active_connections:
            self.active_connections[channel].discard(websocket)

    async def send_personal_message(self, message: dict, websocket: WebSocket):
        await websocket.send_json(message)

    async def broadcast(self, message: dict, channel: str = "default"):
        if channel in self.active_connections:
            for connection in self.active_connections[channel]:
                try:
                    await connection.send_json(message)
                except Exception:
                    pass

    async def broadcast_to_all(self, message: dict):
        for channel in self.active_connections:
            await self.broadcast(message, channel)


manager = ConnectionManager()


@router.websocket("/market")
async def websocket_market(websocket: WebSocket):
    """WebSocket endpoint for real-time market data."""
    await manager.connect(websocket, "market")
    try:
        while True:
            data = await websocket.receive_text()
            message = json.loads(data)

            # Handle subscription requests
            if message.get("action") == "subscribe":
                symbols = message.get("symbols", [])
                await manager.send_personal_message(
                    {"type": "subscribed", "symbols": symbols},
                    websocket,
                )
            elif message.get("action") == "unsubscribe":
                symbols = message.get("symbols", [])
                await manager.send_personal_message(
                    {"type": "unsubscribed", "symbols": symbols},
                    websocket,
                )

    except WebSocketDisconnect:
        manager.disconnect(websocket, "market")


@router.websocket("/analysis")
async def websocket_analysis(websocket: WebSocket):
    """WebSocket endpoint for real-time AI analysis updates."""
    await manager.connect(websocket, "analysis")
    try:
        while True:
            data = await websocket.receive_text()
            message = json.loads(data)

            # Handle requests
            if message.get("action") == "subscribe_symbol":
                symbol = message.get("symbol")
                await manager.send_personal_message(
                    {"type": "subscribed", "symbol": symbol},
                    websocket,
                )

    except WebSocketDisconnect:
        manager.disconnect(websocket, "analysis")


@router.websocket("/trading")
async def websocket_trading(websocket: WebSocket):
    """WebSocket endpoint for real-time trading updates."""
    await manager.connect(websocket, "trading")
    try:
        while True:
            data = await websocket.receive_text()
            message = json.loads(data)

            # Handle ping/pong
            if message.get("type") == "ping":
                await manager.send_personal_message(
                    {"type": "pong"},
                    websocket,
                )

    except WebSocketDisconnect:
        manager.disconnect(websocket, "trading")


# Helper function to broadcast market updates
async def broadcast_price_update(symbol: str, price_data: dict):
    await manager.broadcast(
        {
            "type": "price_update",
            "symbol": symbol,
            "data": price_data,
        },
        "market",
    )


# Helper function to broadcast analysis updates
async def broadcast_analysis_update(symbol: str, analysis_data: dict):
    await manager.broadcast(
        {
            "type": "analysis_update",
            "symbol": symbol,
            "data": analysis_data,
        },
        "analysis",
    )


# Helper function to broadcast trading updates
async def broadcast_trading_update(user_id: int, order_data: dict):
    await manager.broadcast(
        {
            "type": "order_update",
            "user_id": user_id,
            "data": order_data,
        },
        "trading",
    )
