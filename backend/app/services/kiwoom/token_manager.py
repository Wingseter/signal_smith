"""Token management and HTTP request infrastructure for Kiwoom API."""

import asyncio
import random
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
import logging

import httpx

from app.config import settings
from app.core.redis import get_redis
from app.services.kiwoom.base import KiwoomBaseClient

logger = logging.getLogger(__name__)


class TokenManager(KiwoomBaseClient):
    """Token management + HTTP request base client."""

    BASE_URL = "https://api.kiwoom.com"
    MOCK_URL = "https://mockapi.kiwoom.com"

    def __init__(self, is_mock: bool = True):
        self.is_mock = is_mock
        self.base_url = settings.kiwoom_base_url or (self.MOCK_URL if is_mock else self.BASE_URL)
        self.app_key = settings.kiwoom_app_key
        self.secret_key = settings.kiwoom_secret_key
        self.account_number = settings.kiwoom_account_number
        self.account_password = settings.kiwoom_account_password
        self._access_token: Optional[str] = None
        self._token_expires_at: Optional[datetime] = None
        self._connected = False

    async def connect(self) -> bool:
        """API 연결 및 토큰 발급"""
        if not self.app_key or not self.secret_key:
            raise ValueError("API 키가 설정되지 않았습니다. .env 파일의 KIWOOM_APP_KEY, KIWOOM_SECRET_KEY를 확인하세요.")

        try:
            await self._get_access_token()
            self._connected = True
            logger.info("키움증권 API 연결 성공")
            return True
        except Exception as e:
            self._connected = False
            logger.error(f"키움증권 API 연결 실패: {str(e)}")
            raise ConnectionError(f"API 연결 실패: {str(e)}")

    async def disconnect(self) -> None:
        """API 연결 해제"""
        self._access_token = None
        self._token_expires_at = None
        self._connected = False
        logger.info("키움증권 API 연결 해제")

    async def is_connected(self) -> bool:
        """연결 상태 확인"""
        if not self._connected:
            return False
        if self._token_expires_at and datetime.now() >= self._token_expires_at:
            return False
        return True

    async def _get_access_token(self) -> str:
        """액세스 토큰 발급/갱신 (au10001)"""
        # Redis 캐시 확인
        redis = await get_redis()
        cache_key = f"kiwoom:token:{'mock' if self.is_mock else 'real'}"
        cached_token = await redis.get(cache_key)
        if cached_token:
            self._access_token = cached_token
            return cached_token

        # 토큰 유효성 확인
        if self._access_token and self._token_expires_at:
            if datetime.now() < self._token_expires_at - timedelta(minutes=5):
                return self._access_token

        # 새 토큰 발급
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{self.base_url}/oauth2/token",
                json={
                    "grant_type": "client_credentials",
                    "appkey": self.app_key,
                    "secretkey": self.secret_key,
                },
                headers={"Content-Type": "application/json;charset=UTF-8"},
            )
            response.raise_for_status()
            data = response.json()

            # 키움증권 응답 형식 확인
            if data.get("return_code") != 0:
                raise Exception(f"토큰 발급 실패: {data.get('return_msg', 'Unknown error')}")

            self._access_token = data["token"]

            # expires_dt 형식 처리 (다양한 형식 지원)
            expires_dt = data.get("expires_dt") or data.get("token_expired")
            if expires_dt:
                expires_dt = str(expires_dt).strip()
                try:
                    if len(expires_dt) == 14:  # YYYYMMDDHHMMSS
                        self._token_expires_at = datetime.strptime(expires_dt, "%Y%m%d%H%M%S")
                    elif "T" in expires_dt:  # ISO 형식
                        self._token_expires_at = datetime.fromisoformat(expires_dt.replace("Z", "+00:00"))
                    elif " " in expires_dt:  # YYYY-MM-DD HH:MM:SS
                        self._token_expires_at = datetime.strptime(expires_dt, "%Y-%m-%d %H:%M:%S")
                    else:
                        self._token_expires_at = datetime.now() + timedelta(hours=24)
                except ValueError:
                    self._token_expires_at = datetime.now() + timedelta(hours=24)
            else:
                # 기본 24시간
                self._token_expires_at = datetime.now() + timedelta(hours=24)

            # Redis에 캐시 (만료 5분 전까지)
            ttl = int((self._token_expires_at - datetime.now()).total_seconds()) - 300
            if ttl > 0:
                await redis.set(cache_key, self._access_token, ex=ttl)

            logger.info(f"키움증권 토큰 발급 완료 (만료: {self._token_expires_at})")
            return self._access_token

    def _get_headers(self, api_id: str = None, cont_yn: str = "N", next_key: str = "") -> Dict[str, str]:
        """
        API 요청 헤더 생성

        Args:
            api_id: TR명 (예: ka10001, ka10081, kt10000 등)
            cont_yn: 연속조회여부 ('N' 또는 'Y')
            next_key: 연속조회키
        """
        headers = {
            "Content-Type": "application/json;charset=UTF-8",
            "authorization": f"Bearer {self._access_token}",
            "cont-yn": cont_yn,
            "next-key": next_key,
        }
        if api_id:
            headers["api-id"] = api_id
        return headers

    async def _request(
        self,
        method: str,
        endpoint: str,
        data: Dict[str, Any] = None,
        api_id: str = None,
        _retry: bool = False,
        _retry_429: int = 0,
    ) -> Dict[str, Any]:
        """API 요청 공통 메서드 (429 exponential backoff + jitter 포함)"""
        if not await self.is_connected():
            await self.connect()

        url = f"{self.base_url}{endpoint}"
        headers = self._get_headers(api_id=api_id)

        # 디버그 로깅
        logger.debug(f"API 요청: {method} {url}")
        logger.debug(f"Headers: {headers}")
        logger.debug(f"Data: {data}")

        async with httpx.AsyncClient(timeout=30.0, verify=settings.kiwoom_verify_ssl) as client:
            if method.upper() == "GET":
                response = await client.get(url, headers=headers, params=data)
            else:
                response = await client.post(url, headers=headers, json=data)

            logger.debug(f"Response Status: {response.status_code}")
            logger.debug(f"Response Body: {response.text[:500] if response.text else 'Empty'}")

            # 429 Rate Limit: exponential backoff + jitter (최대 3회)
            if response.status_code == 429:
                max_429_retries = 3
                if _retry_429 >= max_429_retries:
                    logger.error(
                        f"429 Rate Limit 최대 재시도 초과 ({max_429_retries}회): "
                        f"{api_id or endpoint}"
                    )
                    response.raise_for_status()

                # Retry-After 헤더 우선 사용
                retry_after = response.headers.get("Retry-After")
                if retry_after:
                    delay = float(retry_after)
                else:
                    # Exponential backoff: 1s, 2s, 4s + jitter (최대 50%)
                    base_delay = 2 ** _retry_429
                    jitter = random.uniform(0, base_delay * 0.5)
                    delay = base_delay + jitter

                logger.warning(
                    f"429 Rate Limit — {delay:.1f}초 대기 후 재시도 "
                    f"({_retry_429 + 1}/{max_429_retries}): {api_id or endpoint}"
                )
                await asyncio.sleep(delay)
                return await self._request(
                    method, endpoint, data, api_id, _retry, _retry_429 + 1
                )

            response.raise_for_status()
            result = response.json()

            # 토큰 만료 에러 시 재발급 후 재시도
            return_msg = result.get("return_msg", "")
            if result.get("return_code") != 0 and ("8005" in str(return_msg) or "유효하지" in str(return_msg)):
                if not _retry:
                    logger.info("토큰 만료 감지, 재발급 시도...")
                    await self._invalidate_token()
                    await self.connect()
                    return await self._request(method, endpoint, data, api_id, _retry=True)

            # 에러 체크
            if result.get("return_code") != 0:
                logger.warning(f"API 요청 실패: {result.get('return_msg')}")

            return result

    async def _invalidate_token(self):
        """캐시된 토큰 무효화"""
        self._access_token = None
        self._token_expires_at = None
        self._connected = False
        try:
            redis = await get_redis()
            cache_key = f"kiwoom:token:{'mock' if self.is_mock else 'real'}"
            await redis.delete(cache_key)
            logger.info("캐시된 토큰 삭제 완료")
        except Exception as e:
            logger.warning(f"토큰 캐시 삭제 실패: {e}")

    # ── Abstract method stubs (satisfied by facade) ──

    async def get_stock_price(self, symbol, **kw):
        raise NotImplementedError("Use facade")

    async def get_stock_prices(self, symbols, **kw):
        raise NotImplementedError("Use facade")

    async def get_daily_prices(self, symbol, **kw):
        raise NotImplementedError("Use facade")

    async def get_minute_prices(self, symbol, **kw):
        raise NotImplementedError("Use facade")

    async def place_order(self, symbol, side, quantity, price=0, order_type=None):
        raise NotImplementedError("Use facade")

    async def cancel_order(self, order_no, symbol, quantity):
        raise NotImplementedError("Use facade")

    async def modify_order(self, order_no, symbol, quantity, price):
        raise NotImplementedError("Use facade")

    async def get_balance(self):
        raise NotImplementedError("Use facade")

    async def get_holdings(self):
        raise NotImplementedError("Use facade")

    async def get_realized_pnl(self, **kw):
        raise NotImplementedError("Use facade")

    async def get_order_history(self, **kw):
        raise NotImplementedError("Use facade")

    async def get_stock_info(self, symbol, **kw):
        raise NotImplementedError("Use facade")

    async def search_stocks(self, keyword, **kw):
        raise NotImplementedError("Use facade")

    async def get_market_stocks(self, **kw):
        raise NotImplementedError("Use facade")
