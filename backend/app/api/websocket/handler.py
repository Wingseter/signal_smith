"""
WebSocket Handler

실시간 데이터 스트리밍을 위한 WebSocket 엔드포인트.
- 실시간 시세
- AI 분석 업데이트
- 거래 알림
"""

import asyncio
import json
import logging
from typing import Dict, Set, Optional

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.core.redis import get_redis
from app.services.stock_service import stock_service

logger = logging.getLogger(__name__)

router = APIRouter()


class ConnectionManager:
    """WebSocket connection manager."""

    def __init__(self):
        self.active_connections: Dict[str, Set[WebSocket]] = {}
        self.symbol_subscriptions: Dict[WebSocket, Set[str]] = {}

    async def connect(self, websocket: WebSocket, channel: str = "default"):
        await websocket.accept()
        if channel not in self.active_connections:
            self.active_connections[channel] = set()
        self.active_connections[channel].add(websocket)
        self.symbol_subscriptions[websocket] = set()

    def disconnect(self, websocket: WebSocket, channel: str = "default"):
        if channel in self.active_connections:
            self.active_connections[channel].discard(websocket)
        if websocket in self.symbol_subscriptions:
            del self.symbol_subscriptions[websocket]

    async def send_personal_message(self, message: dict, websocket: WebSocket):
        try:
            await websocket.send_json(message)
        except Exception:
            logger.debug("Failed to send personal message, client may have disconnected")

    async def broadcast(self, message: dict, channel: str = "default"):
        if channel in self.active_connections:
            disconnected = []
            for connection in self.active_connections[channel]:
                try:
                    await connection.send_json(message)
                except Exception:
                    logger.debug("Broadcast send failed, marking connection for cleanup")
                    disconnected.append(connection)
            for conn in disconnected:
                self.disconnect(conn, channel)

    async def broadcast_to_symbol_subscribers(self, symbol: str, message: dict):
        """특정 종목 구독자에게만 브로드캐스트"""
        disconnected = []
        for websocket, symbols in self.symbol_subscriptions.items():
            if symbol in symbols:
                try:
                    await websocket.send_json(message)
                except Exception:
                    logger.debug("Symbol broadcast failed for %s", symbol)
                    disconnected.append(websocket)
        for conn in disconnected:
            self.disconnect(conn)

    def subscribe_symbol(self, websocket: WebSocket, symbol: str):
        if websocket in self.symbol_subscriptions:
            self.symbol_subscriptions[websocket].add(symbol)

    def unsubscribe_symbol(self, websocket: WebSocket, symbol: str):
        if websocket in self.symbol_subscriptions:
            self.symbol_subscriptions[websocket].discard(symbol)

    def get_subscribed_symbols(self, websocket: WebSocket) -> Set[str]:
        return self.symbol_subscriptions.get(websocket, set())


manager = ConnectionManager()


@router.websocket("/market")
async def websocket_market(websocket: WebSocket):
    """
    실시간 시세 WebSocket

    클라이언트 메시지 형식:
    - 구독: {"action": "subscribe", "symbols": ["005930", "000660"]}
    - 해제: {"action": "unsubscribe", "symbols": ["005930"]}
    - 핑: {"action": "ping"}

    서버 응답 형식:
    - 구독 확인: {"type": "subscribed", "symbols": [...]}
    - 시세 업데이트: {"type": "price", "symbol": "005930", "data": {...}}
    """
    await manager.connect(websocket, "market")

    # 시세 업데이트 태스크
    price_task = None

    async def send_price_updates():
        """구독 중인 종목의 시세를 주기적으로 전송"""
        while True:
            try:
                symbols = list(manager.get_subscribed_symbols(websocket))
                if symbols:
                    # 실시간 시세 조회
                    for symbol in symbols:
                        price = await stock_service.get_current_price(symbol)
                        if price:
                            await manager.send_personal_message(
                                {
                                    "type": "price",
                                    "symbol": symbol,
                                    "data": price,
                                },
                                websocket,
                            )
                await asyncio.sleep(3)  # 3초 간격으로 업데이트
            except asyncio.CancelledError:
                break
            except Exception as e:
                await asyncio.sleep(5)

    try:
        while True:
            data = await websocket.receive_text()
            message = json.loads(data)
            action = message.get("action")

            if action == "subscribe":
                symbols = message.get("symbols", [])
                for symbol in symbols:
                    manager.subscribe_symbol(websocket, symbol)

                await manager.send_personal_message(
                    {"type": "subscribed", "symbols": symbols},
                    websocket,
                )

                # 시세 업데이트 태스크 시작
                if price_task is None or price_task.done():
                    price_task = asyncio.create_task(send_price_updates())

            elif action == "unsubscribe":
                symbols = message.get("symbols", [])
                for symbol in symbols:
                    manager.unsubscribe_symbol(websocket, symbol)

                await manager.send_personal_message(
                    {"type": "unsubscribed", "symbols": symbols},
                    websocket,
                )

            elif action == "ping":
                await manager.send_personal_message(
                    {"type": "pong"},
                    websocket,
                )

            elif action == "get_price":
                # 단일 종목 즉시 조회
                symbol = message.get("symbol")
                if symbol:
                    price = await stock_service.get_current_price(symbol)
                    await manager.send_personal_message(
                        {
                            "type": "price",
                            "symbol": symbol,
                            "data": price,
                        },
                        websocket,
                    )

    except WebSocketDisconnect:
        if price_task:
            price_task.cancel()
        manager.disconnect(websocket, "market")


@router.websocket("/analysis")
async def websocket_analysis(websocket: WebSocket):
    """
    AI 분석 업데이트 WebSocket

    실시간으로 AI 분석 결과를 수신합니다.
    """
    await manager.connect(websocket, "analysis")

    # Redis pubsub 구독
    redis = await get_redis()
    pubsub = redis.pubsub()

    async def listen_redis():
        """Redis에서 분석 업데이트 수신"""
        await pubsub.subscribe("analysis_updates")
        async for message in pubsub.listen():
            if message["type"] == "message":
                try:
                    data = json.loads(message["data"])
                    await manager.send_personal_message(
                        {"type": "analysis", "data": data},
                        websocket,
                    )
                except Exception:
                    logger.debug("Analysis pubsub message parse error")

    listen_task = asyncio.create_task(listen_redis())

    try:
        while True:
            data = await websocket.receive_text()
            message = json.loads(data)

            if message.get("action") == "subscribe_symbol":
                symbol = message.get("symbol")
                manager.subscribe_symbol(websocket, symbol)
                await manager.send_personal_message(
                    {"type": "subscribed", "symbol": symbol},
                    websocket,
                )

            elif message.get("action") == "ping":
                await manager.send_personal_message(
                    {"type": "pong"},
                    websocket,
                )

    except WebSocketDisconnect:
        listen_task.cancel()
        await pubsub.unsubscribe("analysis_updates")
        manager.disconnect(websocket, "analysis")


@router.websocket("/trading")
async def websocket_trading(websocket: WebSocket):
    """
    거래 알림 WebSocket

    주문 체결, 잔고 변경 등의 알림을 실시간으로 수신합니다.
    """
    await manager.connect(websocket, "trading")

    # Redis pubsub 구독
    redis = await get_redis()
    pubsub = redis.pubsub()

    async def listen_redis():
        """Redis에서 거래 알림 수신"""
        await pubsub.subscribe("trading_updates")
        async for message in pubsub.listen():
            if message["type"] == "message":
                try:
                    data = json.loads(message["data"])
                    await manager.send_personal_message(
                        {"type": "trading", "data": data},
                        websocket,
                    )
                except Exception:
                    logger.debug("Trading pubsub message parse error")

    listen_task = asyncio.create_task(listen_redis())

    try:
        while True:
            data = await websocket.receive_text()
            message = json.loads(data)

            if message.get("type") == "ping":
                await manager.send_personal_message(
                    {"type": "pong"},
                    websocket,
                )

    except WebSocketDisconnect:
        listen_task.cancel()
        await pubsub.unsubscribe("trading_updates")
        manager.disconnect(websocket, "trading")


# ========== Helper Functions ==========

async def broadcast_price_update(symbol: str, price_data: dict):
    """시세 업데이트 브로드캐스트"""
    await manager.broadcast_to_symbol_subscribers(
        symbol,
        {
            "type": "price",
            "symbol": symbol,
            "data": price_data,
        },
    )


async def broadcast_analysis_update(symbol: str, analysis_data: dict):
    """분석 업데이트 브로드캐스트"""
    redis = await get_redis()
    await redis.publish(
        "analysis_updates",
        json.dumps({
            "symbol": symbol,
            "analysis": analysis_data,
        }),
    )


async def broadcast_trading_update(user_id: int, order_data: dict):
    """거래 알림 브로드캐스트"""
    redis = await get_redis()
    await redis.publish(
        "trading_updates",
        json.dumps({
            "user_id": user_id,
            "order": order_data,
        }),
    )
