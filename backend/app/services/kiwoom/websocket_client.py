"""
Kiwoom WebSocket Client for Real-time Data

키움증권 OpenAPI+ 실시간 시세 데이터를 WebSocket으로 수신합니다.
https://openapi.kiwoom.com 문서 기반
"""

import asyncio
import json
from typing import Optional, Callable, Dict, Set, Any
from datetime import datetime
from dataclasses import dataclass
import logging

import httpx
import websockets
from websockets.exceptions import ConnectionClosed

from app.config import settings
from app.core.redis import get_redis

logger = logging.getLogger(__name__)


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


@dataclass
class RealtimeOrderbook:
    """실시간 호가 데이터"""
    symbol: str
    ask_prices: list  # 매도호가 리스트
    ask_volumes: list  # 매도잔량 리스트
    bid_prices: list  # 매수호가 리스트
    bid_volumes: list  # 매수잔량 리스트
    timestamp: datetime


class KiwoomWebSocketClient:
    """
    키움증권 OpenAPI+ 실시간 시세 WebSocket 클라이언트

    TR 코드 (실시간):
    - S3_: 실시간 체결가
    - S4_: 실시간 호가
    - H1_: 실시간 체결
    - H2_: 실시간 잔고
    """

    def __init__(self, is_mock: bool = True):
        """
        Args:
            is_mock: True면 모의투자, False면 실거래
        """
        self.is_mock = is_mock

        # 키움 WebSocket URL (설정에서 가져오거나 기본값 사용)
        if is_mock:
            self.ws_url = settings.kiwoom_ws_url or "wss://mockapi.kiwoom.com:10000"
        else:
            self.ws_url = "wss://api.kiwoom.com:10000"

        self.app_key = settings.kiwoom_app_key
        self.secret_key = settings.kiwoom_secret_key

        self._websocket = None
        self._access_token: Optional[str] = None
        self._subscribed_symbols: Set[str] = set()
        self._orderbook_subscribed: Set[str] = set()
        self._callbacks: Dict[str, Callable] = {}
        self._orderbook_callbacks: Dict[str, Callable] = {}
        self._running = False
        self._reconnect_delay = 5
        self._ping_interval = 30
        self._last_ping = None

    async def _get_access_token(self) -> str:
        """
        WebSocket 접속용 Access Token 발급

        키움 REST API를 통해 토큰을 먼저 발급받아야 합니다.
        """
        if self._access_token:
            return self._access_token

        base_url = settings.kiwoom_base_url or (
            "https://mockapi.kiwoom.com" if self.is_mock else "https://api.kiwoom.com"
        )

        async with httpx.AsyncClient(verify=False, timeout=30.0) as client:
            try:
                response = await client.post(
                    f"{base_url}/oauth2/token",
                    json={
                        "grant_type": "client_credentials",
                        "appkey": self.app_key,
                        "secretkey": self.secret_key,
                    },
                    headers={
                        "Content-Type": "application/json",
                    }
                )
                response.raise_for_status()
                data = response.json()

                # 키움 API는 'token' 필드 사용
                self._access_token = data.get("token") or data.get("access_token")
                if not self._access_token:
                    raise ValueError(f"토큰 발급 실패: {data}")

                logger.info("WebSocket용 Access Token 발급 성공")
                return self._access_token

            except httpx.HTTPStatusError as e:
                logger.error(f"토큰 발급 HTTP 에러: {e.response.status_code} - {e.response.text}")
                raise
            except Exception as e:
                logger.error(f"토큰 발급 실패: {str(e)}")
                raise

    async def connect(self) -> bool:
        """WebSocket 연결"""
        if not self.app_key or not self.secret_key:
            raise ValueError("API 키가 설정되지 않았습니다. KIWOOM_APP_KEY, KIWOOM_SECRET_KEY 확인 필요")

        try:
            # 토큰 발급
            access_token = await self._get_access_token()

            # WebSocket 연결 (키움 프로토콜에 맞게)
            self._websocket = await websockets.connect(
                self.ws_url,
                ping_interval=self._ping_interval,
                ping_timeout=10,
                extra_headers={
                    "Authorization": f"Bearer {access_token}",
                    "appkey": self.app_key,
                }
            )
            self._running = True
            self._last_ping = datetime.now()

            logger.info(f"WebSocket 연결 성공: {self.ws_url}")
            return True

        except Exception as e:
            logger.error(f"WebSocket 연결 실패: {str(e)}")
            return False

    async def disconnect(self) -> None:
        """WebSocket 연결 해제"""
        self._running = False
        if self._websocket:
            try:
                await self._websocket.close()
            except Exception:
                pass
            self._websocket = None
        self._subscribed_symbols.clear()
        self._orderbook_subscribed.clear()
        self._access_token = None
        logger.info("WebSocket 연결 해제")

    async def subscribe_price(
        self,
        symbol: str,
        callback: Optional[Callable[[RealtimePrice], Any]] = None,
    ) -> bool:
        """
        종목 실시간 체결가 구독

        Args:
            symbol: 종목 코드 (예: "005930")
            callback: 시세 수신 시 호출할 콜백 함수
        """
        if not self._websocket:
            await self.connect()

        if symbol in self._subscribed_symbols:
            logger.debug(f"이미 구독 중: {symbol}")
            return True

        try:
            access_token = await self._get_access_token()

            # 키움 실시간 구독 요청 메시지
            subscribe_msg = json.dumps({
                "header": {
                    "token": access_token,
                    "tr_type": "1",  # 1: 등록, 2: 해제
                },
                "body": {
                    "tr_cd": "S3_",  # 실시간 체결가
                    "tr_key": symbol,
                }
            })

            await self._websocket.send(subscribe_msg)
            self._subscribed_symbols.add(symbol)

            if callback:
                self._callbacks[symbol] = callback

            logger.info(f"실시간 체결가 구독: {symbol}")
            return True

        except Exception as e:
            logger.error(f"체결가 구독 실패 [{symbol}]: {str(e)}")
            return False

    async def subscribe_orderbook(
        self,
        symbol: str,
        callback: Optional[Callable[[RealtimeOrderbook], Any]] = None,
    ) -> bool:
        """
        종목 실시간 호가 구독

        Args:
            symbol: 종목 코드
            callback: 호가 수신 시 호출할 콜백 함수
        """
        if not self._websocket:
            await self.connect()

        if symbol in self._orderbook_subscribed:
            return True

        try:
            access_token = await self._get_access_token()

            subscribe_msg = json.dumps({
                "header": {
                    "token": access_token,
                    "tr_type": "1",
                },
                "body": {
                    "tr_cd": "S4_",  # 실시간 호가
                    "tr_key": symbol,
                }
            })

            await self._websocket.send(subscribe_msg)
            self._orderbook_subscribed.add(symbol)

            if callback:
                self._orderbook_callbacks[symbol] = callback

            logger.info(f"실시간 호가 구독: {symbol}")
            return True

        except Exception as e:
            logger.error(f"호가 구독 실패 [{symbol}]: {str(e)}")
            return False

    async def unsubscribe_price(self, symbol: str) -> bool:
        """종목 실시간 체결가 구독 해제"""
        if symbol not in self._subscribed_symbols:
            return True

        try:
            access_token = await self._get_access_token()

            unsubscribe_msg = json.dumps({
                "header": {
                    "token": access_token,
                    "tr_type": "2",  # 해제
                },
                "body": {
                    "tr_cd": "S3_",
                    "tr_key": symbol,
                }
            })

            await self._websocket.send(unsubscribe_msg)
            self._subscribed_symbols.discard(symbol)
            self._callbacks.pop(symbol, None)

            logger.info(f"실시간 체결가 구독 해제: {symbol}")
            return True

        except Exception as e:
            logger.error(f"구독 해제 실패 [{symbol}]: {str(e)}")
            return False

    async def unsubscribe_orderbook(self, symbol: str) -> bool:
        """종목 실시간 호가 구독 해제"""
        if symbol not in self._orderbook_subscribed:
            return True

        try:
            access_token = await self._get_access_token()

            unsubscribe_msg = json.dumps({
                "header": {
                    "token": access_token,
                    "tr_type": "2",
                },
                "body": {
                    "tr_cd": "S4_",
                    "tr_key": symbol,
                }
            })

            await self._websocket.send(unsubscribe_msg)
            self._orderbook_subscribed.discard(symbol)
            self._orderbook_callbacks.pop(symbol, None)

            logger.info(f"실시간 호가 구독 해제: {symbol}")
            return True

        except Exception as e:
            logger.error(f"호가 구독 해제 실패 [{symbol}]: {str(e)}")
            return False

    # 기존 메서드 호환성 유지
    async def subscribe(
        self,
        symbol: str,
        callback: Optional[Callable[[RealtimePrice], Any]] = None,
    ) -> bool:
        """기존 코드 호환을 위한 별칭"""
        return await self.subscribe_price(symbol, callback)

    async def unsubscribe(self, symbol: str) -> bool:
        """기존 코드 호환을 위한 별칭"""
        return await self.unsubscribe_price(symbol)

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
                        await self.subscribe_price(symbol)
                    for symbol in list(self._orderbook_subscribed):
                        await self.subscribe_orderbook(symbol)

                message = await self._websocket.recv()
                await self._handle_message(message, default_callback)

            except ConnectionClosed:
                logger.warning("WebSocket 연결 끊김, 재연결 시도...")
                self._websocket = None
                self._access_token = None  # 토큰 재발급 필요
                await asyncio.sleep(self._reconnect_delay)

            except Exception as e:
                logger.error(f"WebSocket 오류: {str(e)}")
                await asyncio.sleep(1)

    async def _handle_message(
        self,
        message: str,
        default_callback: Optional[Callable] = None
    ) -> None:
        """수신된 메시지 처리"""
        try:
            # JSON 메시지 처리
            if message.startswith("{"):
                data = json.loads(message)
                await self._handle_json_message(data, default_callback)
            else:
                # 파이프 구분 메시지 처리 (기존 키움 형식)
                await self._handle_pipe_message(message, default_callback)

        except Exception as e:
            logger.error(f"메시지 처리 오류: {str(e)}")

    async def _handle_json_message(
        self,
        data: dict,
        default_callback: Optional[Callable] = None
    ) -> None:
        """JSON 형식 메시지 처리"""
        try:
            header = data.get("header", {})
            body = data.get("body", {})
            tr_cd = header.get("tr_cd") or body.get("tr_cd")

            if tr_cd == "S3_":
                # 실시간 체결가
                price_data = self._parse_price_json(body)
                if price_data:
                    await self._process_price(price_data, default_callback)

            elif tr_cd == "S4_":
                # 실시간 호가
                orderbook_data = self._parse_orderbook_json(body)
                if orderbook_data:
                    await self._process_orderbook(orderbook_data)

            elif tr_cd == "H1_":
                # 체결 통보
                logger.debug(f"체결 통보: {body}")

            elif tr_cd == "H2_":
                # 잔고 통보
                logger.debug(f"잔고 통보: {body}")

        except Exception as e:
            logger.error(f"JSON 메시지 처리 오류: {str(e)}")

    async def _handle_pipe_message(
        self,
        message: str,
        default_callback: Optional[Callable] = None
    ) -> None:
        """파이프(|) 구분 형식 메시지 처리"""
        try:
            parts = message.split("|")
            if len(parts) < 4:
                return

            header = parts[0]
            tr_cd = parts[1]
            data_count = parts[2]
            data = parts[3]

            if tr_cd == "S3_":
                price_data = self._parse_price_pipe(data)
                if price_data:
                    await self._process_price(price_data, default_callback)

            elif tr_cd == "S4_":
                orderbook_data = self._parse_orderbook_pipe(data)
                if orderbook_data:
                    await self._process_orderbook(orderbook_data)

        except Exception as e:
            logger.error(f"파이프 메시지 처리 오류: {str(e)}")

    def _parse_price_json(self, body: dict) -> Optional[RealtimePrice]:
        """JSON 형식 체결가 데이터 파싱"""
        try:
            output = body.get("output", body)

            return RealtimePrice(
                symbol=output.get("shcode", output.get("stk_cd", "")),
                current_price=int(output.get("price", output.get("stck_prpr", 0))),
                change=int(output.get("change", output.get("prdy_vrss", 0))),
                change_rate=float(output.get("chgrate", output.get("prdy_ctrt", 0))),
                volume=int(output.get("volume", output.get("acml_vol", 0))),
                ask_price=int(output.get("offerho", output.get("askp1", 0))),
                bid_price=int(output.get("bidho", output.get("bidp1", 0))),
                timestamp=datetime.now(),
            )
        except (ValueError, KeyError) as e:
            logger.error(f"체결가 JSON 파싱 오류: {str(e)}")
            return None

    def _parse_price_pipe(self, data: str) -> Optional[RealtimePrice]:
        """파이프 구분 체결가 데이터 파싱"""
        try:
            fields = data.split("^")
            if len(fields) < 15:
                return None

            return RealtimePrice(
                symbol=fields[0],           # 종목코드
                current_price=int(fields[2]),  # 현재가
                change=int(fields[4]),      # 전일대비
                change_rate=float(fields[5]),  # 등락률
                volume=int(fields[12]),     # 누적거래량
                ask_price=int(fields[6]) if fields[6] else 0,  # 매도호가
                bid_price=int(fields[7]) if fields[7] else 0,  # 매수호가
                timestamp=datetime.now(),
            )
        except (ValueError, IndexError) as e:
            logger.error(f"체결가 파이프 파싱 오류: {str(e)}")
            return None

    def _parse_orderbook_json(self, body: dict) -> Optional[RealtimeOrderbook]:
        """JSON 형식 호가 데이터 파싱"""
        try:
            output = body.get("output", body)

            ask_prices = []
            ask_volumes = []
            bid_prices = []
            bid_volumes = []

            # 10단계 호가 파싱
            for i in range(1, 11):
                ask_prices.append(int(output.get(f"askp{i}", 0)))
                ask_volumes.append(int(output.get(f"askv{i}", 0)))
                bid_prices.append(int(output.get(f"bidp{i}", 0)))
                bid_volumes.append(int(output.get(f"bidv{i}", 0)))

            return RealtimeOrderbook(
                symbol=output.get("shcode", output.get("stk_cd", "")),
                ask_prices=ask_prices,
                ask_volumes=ask_volumes,
                bid_prices=bid_prices,
                bid_volumes=bid_volumes,
                timestamp=datetime.now(),
            )
        except (ValueError, KeyError) as e:
            logger.error(f"호가 JSON 파싱 오류: {str(e)}")
            return None

    def _parse_orderbook_pipe(self, data: str) -> Optional[RealtimeOrderbook]:
        """파이프 구분 호가 데이터 파싱"""
        try:
            fields = data.split("^")
            if len(fields) < 41:  # 최소 10단계 호가 필요
                return None

            ask_prices = []
            ask_volumes = []
            bid_prices = []
            bid_volumes = []

            # 10단계 호가 파싱 (필드 위치는 키움 API 문서 참조)
            for i in range(10):
                ask_idx = 2 + i * 2
                bid_idx = 22 + i * 2
                ask_prices.append(int(fields[ask_idx]) if fields[ask_idx] else 0)
                ask_volumes.append(int(fields[ask_idx + 1]) if fields[ask_idx + 1] else 0)
                bid_prices.append(int(fields[bid_idx]) if fields[bid_idx] else 0)
                bid_volumes.append(int(fields[bid_idx + 1]) if fields[bid_idx + 1] else 0)

            return RealtimeOrderbook(
                symbol=fields[0],
                ask_prices=ask_prices,
                ask_volumes=ask_volumes,
                bid_prices=bid_prices,
                bid_volumes=bid_volumes,
                timestamp=datetime.now(),
            )
        except (ValueError, IndexError) as e:
            logger.error(f"호가 파이프 파싱 오류: {str(e)}")
            return None

    async def _process_price(
        self,
        price: RealtimePrice,
        default_callback: Optional[Callable] = None
    ) -> None:
        """체결가 데이터 처리"""
        # Redis에 캐시
        await self._cache_price(price)

        # 콜백 호출
        callback = self._callbacks.get(price.symbol, default_callback)
        if callback:
            if asyncio.iscoroutinefunction(callback):
                await callback(price)
            else:
                callback(price)

    async def _process_orderbook(
        self,
        orderbook: RealtimeOrderbook
    ) -> None:
        """호가 데이터 처리"""
        # Redis에 캐시
        await self._cache_orderbook(orderbook)

        # 콜백 호출
        callback = self._orderbook_callbacks.get(orderbook.symbol)
        if callback:
            if asyncio.iscoroutinefunction(callback):
                await callback(orderbook)
            else:
                callback(orderbook)

    async def _cache_price(self, price: RealtimePrice) -> None:
        """Redis에 실시간 체결가 캐시"""
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
                f"realtime:price:{price.symbol}",
                json.dumps(cache_data)
            )

        except Exception as e:
            logger.error(f"체결가 캐시 저장 실패: {str(e)}")

    async def _cache_orderbook(self, orderbook: RealtimeOrderbook) -> None:
        """Redis에 실시간 호가 캐시"""
        try:
            redis = await get_redis()
            cache_key = f"realtime:orderbook:{orderbook.symbol}"
            cache_data = {
                "symbol": orderbook.symbol,
                "ask_prices": orderbook.ask_prices,
                "ask_volumes": orderbook.ask_volumes,
                "bid_prices": orderbook.bid_prices,
                "bid_volumes": orderbook.bid_volumes,
                "timestamp": orderbook.timestamp.isoformat(),
            }
            await redis.set(cache_key, json.dumps(cache_data), ex=60)

            # 실시간 채널에 발행
            await redis.publish(
                f"realtime:orderbook:{orderbook.symbol}",
                json.dumps(cache_data)
            )

        except Exception as e:
            logger.error(f"호가 캐시 저장 실패: {str(e)}")

    # 기존 메서드 호환성 유지
    def _parse_message(self, message: str) -> Optional[RealtimePrice]:
        """기존 코드 호환을 위한 메서드"""
        if message.startswith("{"):
            data = json.loads(message)
            body = data.get("body", data)
            return self._parse_price_json(body)
        else:
            parts = message.split("|")
            if len(parts) >= 4:
                return self._parse_price_pipe(parts[3])
        return None


# 싱글톤 인스턴스 (설정에서 is_mock 값 가져옴)
kiwoom_ws_client = KiwoomWebSocketClient(is_mock=settings.kiwoom_is_mock)
