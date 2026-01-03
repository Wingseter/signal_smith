"""
Kiwoom WebSocket Client for Real-time Data

실시간 시세 데이터를 WebSocket으로 수신합니다.
"""

import asyncio
import json
from typing import Optional, Callable, Dict, Set, Any
from datetime import datetime
from dataclasses import dataclass

import httpx
import websockets
from websockets.exceptions import ConnectionClosed

from app.config import settings
from app.core.redis import get_redis


@dataclass
class RealtimePrice:
    """실시간 시세 데이터"""
    symbol: str
    current_price: int
    change: int
    change_rate: float
    volume: int
    ask_price: int  # 매도호가
    bid_price: int  # 매수호가
    timestamp: datetime


class KiwoomWebSocketClient:
    """키움증권 실시간 시세 WebSocket 클라이언트"""

    WS_URL = "ws://ops.koreainvestment.com:21000"  # 실전
    WS_PAPER_URL = "ws://ops.koreainvestment.com:31000"  # 모의

    def __init__(self, is_paper_trading: bool = True):
        self.is_paper_trading = is_paper_trading
        self.ws_url = self.WS_PAPER_URL if is_paper_trading else self.WS_URL

        self.app_key = settings.kis_app_key
        self.app_secret = settings.kis_app_secret

        self._websocket = None
        self._approval_key: Optional[str] = None
        self._subscribed_symbols: Set[str] = set()
        self._callbacks: Dict[str, Callable] = {}
        self._running = False
        self._reconnect_delay = 5

    async def _get_approval_key(self) -> str:
        """WebSocket 접속 승인 키 발급"""
        if self._approval_key:
            return self._approval_key

        base_url = (
            "https://openapivts.koreainvestment.com:29443"
            if self.is_paper_trading
            else "https://openapi.koreainvestment.com:9443"
        )

        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{base_url}/oauth2/Approval",
                json={
                    "grant_type": "client_credentials",
                    "appkey": self.app_key,
                    "secretkey": self.app_secret,
                },
            )
            response.raise_for_status()
            data = response.json()
            self._approval_key = data["approval_key"]
            return self._approval_key

    async def connect(self) -> bool:
        """WebSocket 연결"""
        if not self.app_key or not self.app_secret:
            raise ValueError("API 키가 설정되지 않았습니다.")

        try:
            approval_key = await self._get_approval_key()
            self._websocket = await websockets.connect(
                self.ws_url,
                ping_interval=30,
                ping_timeout=10,
            )
            self._running = True
            print(f"WebSocket 연결 성공: {self.ws_url}")
            return True

        except Exception as e:
            print(f"WebSocket 연결 실패: {str(e)}")
            return False

    async def disconnect(self) -> None:
        """WebSocket 연결 해제"""
        self._running = False
        if self._websocket:
            await self._websocket.close()
            self._websocket = None
        self._subscribed_symbols.clear()
        print("WebSocket 연결 해제")

    async def subscribe(
        self,
        symbol: str,
        callback: Optional[Callable[[RealtimePrice], Any]] = None,
    ) -> bool:
        """
        종목 실시간 시세 구독

        Args:
            symbol: 종목 코드
            callback: 시세 수신 시 호출할 콜백 함수
        """
        if not self._websocket:
            await self.connect()

        if symbol in self._subscribed_symbols:
            return True

        try:
            approval_key = await self._get_approval_key()

            # 구독 요청 메시지
            subscribe_msg = json.dumps({
                "header": {
                    "approval_key": approval_key,
                    "custtype": "P",
                    "tr_type": "1",  # 등록
                    "content-type": "utf-8",
                },
                "body": {
                    "input": {
                        "tr_id": "H0STCNT0",  # 실시간 체결가
                        "tr_key": symbol,
                    }
                }
            })

            await self._websocket.send(subscribe_msg)
            self._subscribed_symbols.add(symbol)

            if callback:
                self._callbacks[symbol] = callback

            print(f"실시간 시세 구독: {symbol}")
            return True

        except Exception as e:
            print(f"구독 실패 [{symbol}]: {str(e)}")
            return False

    async def unsubscribe(self, symbol: str) -> bool:
        """종목 실시간 시세 구독 해제"""
        if symbol not in self._subscribed_symbols:
            return True

        try:
            approval_key = await self._get_approval_key()

            # 구독 해제 메시지
            unsubscribe_msg = json.dumps({
                "header": {
                    "approval_key": approval_key,
                    "custtype": "P",
                    "tr_type": "2",  # 해제
                    "content-type": "utf-8",
                },
                "body": {
                    "input": {
                        "tr_id": "H0STCNT0",
                        "tr_key": symbol,
                    }
                }
            })

            await self._websocket.send(unsubscribe_msg)
            self._subscribed_symbols.discard(symbol)
            self._callbacks.pop(symbol, None)

            print(f"실시간 시세 구독 해제: {symbol}")
            return True

        except Exception as e:
            print(f"구독 해제 실패 [{symbol}]: {str(e)}")
            return False

    async def run(self, default_callback: Optional[Callable] = None) -> None:
        """
        실시간 데이터 수신 루프

        Args:
            default_callback: 개별 콜백이 없을 때 사용할 기본 콜백
        """
        while self._running:
            try:
                if not self._websocket:
                    await self.connect()
                    # 기존 구독 복원
                    for symbol in list(self._subscribed_symbols):
                        await self.subscribe(symbol)

                message = await self._websocket.recv()
                price_data = self._parse_message(message)

                if price_data:
                    # Redis에 캐시
                    await self._cache_price(price_data)

                    # 콜백 호출
                    callback = self._callbacks.get(price_data.symbol, default_callback)
                    if callback:
                        if asyncio.iscoroutinefunction(callback):
                            await callback(price_data)
                        else:
                            callback(price_data)

            except ConnectionClosed:
                print("WebSocket 연결 끊김, 재연결 시도...")
                self._websocket = None
                await asyncio.sleep(self._reconnect_delay)

            except Exception as e:
                print(f"WebSocket 오류: {str(e)}")
                await asyncio.sleep(1)

    def _parse_message(self, message: str) -> Optional[RealtimePrice]:
        """WebSocket 메시지 파싱"""
        try:
            # 키움 실시간 데이터는 '|'로 구분
            parts = message.split("|")
            if len(parts) < 4:
                return None

            # 헤더 확인
            header = parts[0]
            tr_id = parts[1]
            data_count = parts[2]
            data = parts[3]

            if tr_id != "H0STCNT0":  # 체결가 데이터만 처리
                return None

            # 데이터 파싱 (^로 구분)
            fields = data.split("^")
            if len(fields) < 20:
                return None

            return RealtimePrice(
                symbol=fields[0],  # 종목코드
                current_price=int(fields[2]),  # 현재가
                change=int(fields[4]),  # 전일대비
                change_rate=float(fields[5]),  # 등락률
                volume=int(fields[12]),  # 누적거래량
                ask_price=int(fields[6]) if fields[6] else 0,  # 매도호가
                bid_price=int(fields[7]) if fields[7] else 0,  # 매수호가
                timestamp=datetime.now(),
            )

        except (ValueError, IndexError) as e:
            return None

    async def _cache_price(self, price: RealtimePrice) -> None:
        """Redis에 실시간 시세 캐시"""
        try:
            redis = await get_redis()
            cache_key = f"realtime:price:{price.symbol}"
            cache_data = {
                "symbol": price.symbol,
                "current_price": price.current_price,
                "change": price.change,
                "change_rate": price.change_rate,
                "volume": price.volume,
                "ask_price": price.ask_price,
                "bid_price": price.bid_price,
                "timestamp": price.timestamp.isoformat(),
            }
            await redis.set(cache_key, json.dumps(cache_data), ex=60)

            # 실시간 채널에 발행
            await redis.publish(
                f"realtime:{price.symbol}",
                json.dumps(cache_data)
            )

        except Exception as e:
            print(f"캐시 저장 실패: {str(e)}")


# 싱글톤 인스턴스
kiwoom_ws_client = KiwoomWebSocketClient(is_paper_trading=True)
