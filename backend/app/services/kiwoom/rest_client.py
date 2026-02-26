"""
Kiwoom Securities REST API Client

Cross-platform REST API client for Kiwoom Securities.
Works on macOS, Linux, and Windows.

API Documentation: https://openapi.kiwoom.com
"""

import asyncio
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
import logging

import httpx

from app.config import settings
from app.core.redis import get_redis
from app.services.kiwoom.base import (
    KiwoomBaseClient,
    StockPrice,
    OrderResult,
    Balance,
    Holding,
    RealizedPnlItem,
    OrderType,
    OrderSide,
)

logger = logging.getLogger(__name__)


class KiwoomRestClient(KiwoomBaseClient):
    """
    키움증권 REST API 클라이언트

    키움증권 REST API를 사용하여 시세 조회, 주문, 계좌 관리를 수행합니다.
    https://openapi.kiwoom.com
    """

    # API Endpoints
    BASE_URL = "https://api.kiwoom.com"  # 실전투자
    MOCK_URL = "https://mockapi.kiwoom.com"  # 모의투자

    def __init__(self, is_mock: bool = True):
        """
        Args:
            is_mock: True면 모의투자, False면 실전투자
        """
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
        _retry: bool = False
    ) -> Dict[str, Any]:
        """API 요청 공통 메서드"""
        if not await self.is_connected():
            await self.connect()

        url = f"{self.base_url}{endpoint}"
        headers = self._get_headers(api_id=api_id)

        # 디버그 로깅
        logger.debug(f"API 요청: {method} {url}")
        logger.debug(f"Headers: {headers}")
        logger.debug(f"Data: {data}")

        async with httpx.AsyncClient(timeout=30.0, verify=False) as client:
            if method.upper() == "GET":
                response = await client.get(url, headers=headers, params=data)
            else:
                response = await client.post(url, headers=headers, json=data)

            logger.debug(f"Response Status: {response.status_code}")
            logger.debug(f"Response Body: {response.text[:500] if response.text else 'Empty'}")

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

    # ========== 시세 조회 ==========

    def _parse_signed_int(self, value: str) -> int:
        """부호가 포함된 문자열을 정수로 변환 (예: '+139000' -> 139000)

        키움 API는 가격 앞에 +/-를 붙여 등락 방향을 표시.
        가격 자체는 절대값이므로 부호를 제거하여 절대값 반환.
        """
        if not value:
            return 0
        value = str(value).strip()
        # 부호 제거 후 절대값 반환
        return abs(int(value.replace('+', '').replace(',', '')))

    def _parse_signed_change(self, value: str) -> int:
        """등락폭 문자열을 정수로 변환 (부호 유지)"""
        if not value:
            return 0
        value = str(value).strip().replace(',', '')
        if value.startswith('+'):
            return int(value[1:])
        elif value.startswith('-'):
            return -int(value[1:])
        return int(value)

    def _parse_signed_float(self, value: str) -> float:
        """부호가 포함된 문자열을 실수로 변환 (부호 유지)"""
        if not value:
            return 0.0
        value = str(value).strip().replace(',', '')
        if value.startswith('+'):
            return float(value[1:])
        elif value.startswith('-'):
            return -float(value[1:])
        return float(value)

    async def get_stock_price(self, symbol: str) -> Optional[StockPrice]:
        """현재가 조회 (ka10001 - 주식기본정보요청)"""
        try:
            result = await self._request(
                "POST",
                "/api/dostk/stkinfo",
                data={
                    "trnm": "ka10001",
                    "stk_cd": symbol,
                },
                api_id="ka10001"
            )

            if result.get("return_code") != 0:
                return None

            # 키움 API는 데이터를 직접 result에 반환 (data 키 없음)
            return StockPrice(
                symbol=symbol,
                name=result.get("stk_nm", ""),
                current_price=self._parse_signed_int(result.get("cur_prc", "0")),
                change=self._parse_signed_change(result.get("pred_pre", "0")),
                change_rate=self._parse_signed_float(result.get("flu_rt", "0")),
                open_price=self._parse_signed_int(result.get("open_pric", "0")),
                high_price=self._parse_signed_int(result.get("high_pric", "0")),
                low_price=self._parse_signed_int(result.get("low_pric", "0")),
                volume=int(result.get("trde_qty", 0)),
                trade_amount=int(result.get("trde_amt", 0)) if result.get("trde_amt") else 0,
                timestamp=datetime.now(),
            )

        except Exception as e:
            logger.error(f"시세 조회 실패 [{symbol}]: {str(e)}")
            return None

    async def get_stock_prices(self, symbols: List[str]) -> List[StockPrice]:
        """복수 종목 현재가 조회"""
        tasks = [self.get_stock_price(symbol) for symbol in symbols]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        return [r for r in results if isinstance(r, StockPrice)]

    async def get_daily_prices(
        self,
        symbol: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """일봉 데이터 조회 (ka10081 - 주식일봉차트조회요청)

        Args:
            symbol: 종목코드 (예: 005930)
            start_date: 시작일 (미사용, 연속조회로 대체)
            end_date: 기준일자 (YYYYMMDD, 기본값: 오늘)

        Returns:
            일봉 데이터 리스트 (최신순)
        """
        if not end_date:
            end_date = datetime.now().strftime("%Y%m%d")

        try:
            result = await self._request(
                "POST",
                "/api/dostk/chart",
                data={
                    "stk_cd": symbol,
                    "base_dt": end_date,
                    "upd_stkpc_tp": "1",  # 수정주가 적용 (필수 파라미터)
                },
                api_id="ka10081"
            )

            if result.get("return_code") != 0:
                logger.warning(f"일봉 조회 API 오류 [{symbol}]: {result.get('return_msg')}")
                return []

            prices = []
            # 응답 필드명: stk_dt_pole_chart_qry (주식일봉차트조회)
            for item in result.get("stk_dt_pole_chart_qry", []):
                prices.append({
                    "date": item.get("dt"),
                    "open": self._parse_signed_int(item.get("open_pric", "0")),
                    "high": self._parse_signed_int(item.get("high_pric", "0")),
                    "low": self._parse_signed_int(item.get("low_pric", "0")),
                    "close": self._parse_signed_int(item.get("cur_prc", "0")),  # 현재가 = 종가
                    "volume": int(item.get("trde_qty", 0)),
                })
            return prices

        except Exception as e:
            logger.error(f"일봉 조회 실패 [{symbol}]: {str(e)}")
            return []

    async def get_minute_prices(
        self,
        symbol: str,
        interval: int = 1,
    ) -> List[Dict[str, Any]]:
        """분봉 데이터 조회 (ka10080 - 주식분봉차트조회요청)"""
        try:
            result = await self._request(
                "POST",
                "/api/dostk/chart",
                data={
                    "trnm": "ka10080",
                    "stk_cd": symbol,
                    "tick_scope": str(interval),  # 분봉 간격
                    "req_cnt": "100",
                },
                api_id="ka10080"
            )

            if result.get("return_code") != 0:
                return []

            prices = []
            for item in result.get("data", {}).get("chart", []):
                prices.append({
                    "time": item.get("dt"),
                    "open": int(item.get("open_prc", 0)),
                    "high": int(item.get("high_prc", 0)),
                    "low": int(item.get("low_prc", 0)),
                    "close": int(item.get("clos_prc", 0)),
                    "volume": int(item.get("trde_qty", 0)),
                })
            return prices

        except Exception as e:
            logger.error(f"분봉 조회 실패 [{symbol}]: {str(e)}")
            return []

    # ========== 주문 ==========

    async def place_order(
        self,
        symbol: str,
        side: OrderSide,
        quantity: int,
        price: int = 0,
        order_type: OrderType = OrderType.LIMIT,
    ) -> OrderResult:
        """주문 실행 (kt10000/kt10001 - 주식 매수/매도 주문)"""
        # 매수: kt10000, 매도: kt10001
        tr_name = "kt10000" if side == OrderSide.BUY else "kt10001"

        # 주문유형: 0-보통(지정가), 3-시장가
        trde_tp = "0" if order_type == OrderType.LIMIT else "3"

        try:
            result = await self._request(
                "POST",
                "/api/dostk/ordr",  # 수정: order → ordr
                data={
                    "dmst_stex_tp": "KRX",  # 국내거래소구분 (필수)
                    "stk_cd": symbol,
                    "ord_qty": str(quantity),
                    "ord_uv": str(price) if price > 0 else "",  # 수정: ord_prc → ord_uv
                    "trde_tp": trde_tp,  # 수정: ord_tp → trde_tp
                    "cond_uv": "",  # 조건단가
                },
                api_id=tr_name
            )

            success = result.get("return_code") == 0
            data = result.get("data", {})

            return OrderResult(
                order_no=data.get("ord_no", "") if success else "",
                symbol=symbol,
                order_type=order_type.value,
                side=side.value,
                quantity=quantity,
                price=price,
                status="submitted" if success else "rejected",
                message=result.get("return_msg", ""),
                timestamp=datetime.now(),
            )

        except Exception as e:
            logger.error(f"주문 실패 [{symbol}]: {str(e)}")
            return OrderResult(
                order_no="",
                symbol=symbol,
                order_type=order_type.value,
                side=side.value,
                quantity=quantity,
                price=price,
                status="error",
                message=str(e),
                timestamp=datetime.now(),
            )

    async def cancel_order(
        self,
        order_no: str,
        symbol: str,
        quantity: int,
    ) -> OrderResult:
        """주문 취소 (kt10003 - 주식 취소주문)"""
        try:
            result = await self._request(
                "POST",
                "/api/dostk/ordr",  # 수정: order → ordr
                data={
                    "dmst_stex_tp": "KRX",  # 국내거래소구분 (필수)
                    "orig_ord_no": order_no,  # 수정: org_ord_no → orig_ord_no
                    "stk_cd": symbol,
                    "cncl_qty": str(quantity) if quantity > 0 else "0",  # 0이면 전량 취소
                },
                api_id="kt10003"
            )

            success = result.get("return_code") == 0

            return OrderResult(
                order_no=order_no,
                symbol=symbol,
                order_type="cancel",
                side="",
                quantity=quantity,
                price=0,
                status="cancelled" if success else "failed",
                message=result.get("return_msg", ""),
                timestamp=datetime.now(),
            )

        except Exception as e:
            logger.error(f"주문 취소 실패 [{order_no}]: {str(e)}")
            return OrderResult(
                order_no=order_no,
                symbol=symbol,
                order_type="cancel",
                side="",
                quantity=quantity,
                price=0,
                status="error",
                message=str(e),
                timestamp=datetime.now(),
            )

    async def modify_order(
        self,
        order_no: str,
        symbol: str,
        quantity: int,
        price: int,
    ) -> OrderResult:
        """주문 정정 (kt10002 - 주식 정정주문)"""
        try:
            result = await self._request(
                "POST",
                "/api/dostk/ordr",  # 수정: order → ordr
                data={
                    "dmst_stex_tp": "KRX",  # 국내거래소구분 (필수)
                    "orig_ord_no": order_no,  # 수정: org_ord_no → orig_ord_no
                    "stk_cd": symbol,
                    "mdfy_qty": str(quantity),
                    "mdfy_uv": str(price),  # 수정: mdfy_prc → mdfy_uv
                    "mdfy_cond_uv": "",  # 정정조건단가
                },
                api_id="kt10002"
            )

            success = result.get("return_code") == 0

            return OrderResult(
                order_no=order_no,
                symbol=symbol,
                order_type="modify",
                side="",
                quantity=quantity,
                price=price,
                status="modified" if success else "failed",
                message=result.get("return_msg", ""),
                timestamp=datetime.now(),
            )

        except Exception as e:
            logger.error(f"주문 정정 실패 [{order_no}]: {str(e)}")
            return OrderResult(
                order_no=order_no,
                symbol=symbol,
                order_type="modify",
                side="",
                quantity=quantity,
                price=price,
                status="error",
                message=str(e),
                timestamp=datetime.now(),
            )

    # ========== 계좌 ==========

    async def get_balance(self) -> Balance:
        """
        계좌 잔고 조회

        kt00001 (예수금상세현황요청): 예수금, 주문가능금액 등
        ka01690 (일별잔고수익률): 매입금액, 평가금액, 평가손익, 수익률 (실전투자만 지원)
        """
        # 문자열을 정수로 변환하는 헬퍼 함수
        def parse_int(val) -> int:
            if val is None:
                return 0
            try:
                cleaned = str(val).strip().replace(",", "")
                # 부호 처리
                if cleaned.startswith("-"):
                    return -int(cleaned[1:])
                elif cleaned.startswith("+"):
                    return int(cleaned[1:])
                return int(cleaned) if cleaned else 0
            except (ValueError, TypeError):
                return 0

        def parse_float(val) -> float:
            if val is None:
                return 0.0
            try:
                cleaned = str(val).strip().replace(",", "")
                return float(cleaned) if cleaned else 0.0
            except (ValueError, TypeError):
                return 0.0

        total_deposit = 0
        available_amount = 0
        total_purchase = 0
        total_evaluation = 0
        total_profit_loss = 0
        profit_rate = 0.0

        # 1. kt00001 - 예수금상세현황요청 (예수금, 주문가능금액)
        try:
            result = await self._request(
                "POST",
                "/api/dostk/acnt",
                data={
                    "trnm": "kt00001",
                    "qry_tp": "2",  # 조회구분: 2-일반조회, 3-추정조회
                },
                api_id="kt00001"
            )

            logger.debug(f"kt00001 응답: {result}")

            if result.get("return_code") == 0:
                # kt00001 응답 필드명
                # entr: 예수금
                # ord_alow_amt: 주문가능금액
                total_deposit = parse_int(result.get("entr"))
                available_amount = parse_int(result.get("ord_alow_amt"))
                logger.info(f"kt00001 - 예수금: {total_deposit}, 주문가능: {available_amount}")
            else:
                logger.warning(f"kt00001 조회 실패: {result.get('return_msg')}")

        except Exception as e:
            logger.error(f"kt00001 조회 오류: {str(e)}")

        # 2. kt00018 - 계좌평가잔고내역요청 (매입금액, 평가금액, 수익률)
        # 모의투자도 지원함
        try:
            result = await self._request(
                "POST",
                "/api/dostk/acnt",
                data={
                    "trnm": "kt00018",
                    "qry_tp": "1",  # 1:합산, 2:개별
                    "dmst_stex_tp": "KRX",  # KRX:한국거래소
                },
                api_id="kt00018"
            )

            logger.debug(f"kt00018 응답 (잔고조회): {result}")

            if result.get("return_code") == 0:
                # kt00018 응답 필드명
                # tot_pur_amt: 총매입금액
                # tot_evlt_amt: 총평가금액
                # tot_evlt_pl: 총평가손익금액
                # tot_prft_rt: 총수익률(%)
                total_purchase = parse_int(result.get("tot_pur_amt"))
                total_evaluation = parse_int(result.get("tot_evlt_amt"))
                total_profit_loss = parse_int(result.get("tot_evlt_pl"))
                profit_rate = parse_float(result.get("tot_prft_rt"))

                logger.info(f"kt00018 - 매입: {total_purchase}, 평가: {total_evaluation}, 손익: {total_profit_loss}, 수익률: {profit_rate}%")
            else:
                logger.warning(f"kt00018 조회 실패: {result.get('return_msg')}")

        except Exception as e:
            logger.error(f"kt00018 조회 오류: {str(e)}")

        return Balance(
            total_deposit=total_deposit,
            available_amount=available_amount,
            total_purchase=total_purchase,
            total_evaluation=total_evaluation,
            total_profit_loss=total_profit_loss,
            profit_rate=profit_rate,
        )

    async def get_holdings(self) -> List[Holding]:
        """
        보유 종목 조회 (kt00018 - 계좌평가잔고내역요청)

        응답 필드:
        - acnt_evlt_remn_indv_tot: 계좌평가잔고개별합산 (LIST)
          - stk_cd: 종목번호
          - stk_nm: 종목명
          - rmnd_qty: 보유수량
          - pur_pric: 매입가
          - cur_prc: 현재가
          - evlt_amt: 평가금액
          - evltv_prft: 평가손익
          - prft_rt: 수익률(%)
        """
        def parse_int(val) -> int:
            if val is None:
                return 0
            try:
                cleaned = str(val).strip().replace(",", "")
                if cleaned.startswith("-"):
                    return -int(cleaned[1:])
                elif cleaned.startswith("+"):
                    return int(cleaned[1:])
                return int(cleaned) if cleaned else 0
            except (ValueError, TypeError):
                return 0

        def parse_float(val) -> float:
            if val is None:
                return 0.0
            try:
                cleaned = str(val).strip().replace(",", "")
                return float(cleaned) if cleaned else 0.0
            except (ValueError, TypeError):
                return 0.0

        try:
            result = await self._request(
                "POST",
                "/api/dostk/acnt",
                data={
                    "trnm": "kt00018",
                    "qry_tp": "1",  # 1:합산, 2:개별
                    "dmst_stex_tp": "KRX",  # KRX:한국거래소, NXT:넥스트트레이드
                },
                api_id="kt00018"
            )

            logger.debug(f"kt00018 응답: {result}")

            if result.get("return_code") != 0:
                logger.warning(f"kt00018 조회 실패: {result.get('return_msg')}")
                return []

            holdings = []
            # acnt_evlt_remn_indv_tot: 계좌평가잔고개별합산 리스트
            items = result.get("acnt_evlt_remn_indv_tot", [])

            for item in items:
                qty = parse_int(item.get("rmnd_qty"))
                if qty > 0:
                    # 종목코드에서 'A' 접두어 제거 (예: A005930 -> 005930)
                    stk_cd = str(item.get("stk_cd", "")).replace("A", "")

                    holdings.append(Holding(
                        symbol=stk_cd,
                        name=item.get("stk_nm", ""),
                        quantity=qty,
                        avg_price=parse_int(item.get("pur_pric")),
                        current_price=parse_int(item.get("cur_prc")),
                        evaluation=parse_int(item.get("evlt_amt")),
                        profit_loss=parse_int(item.get("evltv_prft")),
                        profit_rate=parse_float(item.get("prft_rt")),
                    ))

            logger.info(f"kt00018 - 보유종목 {len(holdings)}개 조회")
            return holdings

        except Exception as e:
            logger.error(f"보유종목 조회 실패: {str(e)}")
            return []

    async def get_realized_pnl(
        self,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> List[RealizedPnlItem]:
        """
        일자별 종목별 실현손익 조회 (ka10073 - 일자별종목별실현손익요청_기간)

        Args:
            start_date: 시작일 (YYYYMMDD)
            end_date: 종료일 (YYYYMMDD)

        Returns:
            실현손익 항목 리스트
        """
        def parse_int(val) -> int:
            if val is None:
                return 0
            try:
                cleaned = str(val).strip().replace(",", "")
                if cleaned.startswith("-"):
                    return -int(cleaned[1:])
                elif cleaned.startswith("+"):
                    return int(cleaned[1:])
                return int(cleaned) if cleaned else 0
            except (ValueError, TypeError):
                return 0

        def parse_float(val) -> float:
            if val is None:
                return 0.0
            try:
                cleaned = str(val).strip().replace(",", "")
                if cleaned.startswith("-"):
                    return -float(cleaned[1:])
                elif cleaned.startswith("+"):
                    return float(cleaned[1:])
                return float(cleaned) if cleaned else 0.0
            except (ValueError, TypeError):
                return 0.0

        if not end_date:
            end_date = datetime.now().strftime("%Y%m%d")
        if not start_date:
            start_date = (datetime.now() - timedelta(days=30)).strftime("%Y%m%d")

        try:
            all_items: List[RealizedPnlItem] = []
            cont_yn = "N"
            next_key = ""

            while True:
                headers = self._get_headers(api_id="ka10073", cont_yn=cont_yn, next_key=next_key)

                async with httpx.AsyncClient(timeout=30.0, verify=False) as client:
                    response = await client.post(
                        f"{self.base_url}/api/dostk/acnt",
                        headers=headers,
                        json={
                            "stk_cd": "",
                            "strt_dt": start_date,
                            "end_dt": end_date,
                        },
                    )
                    response.raise_for_status()
                    result = response.json()

                if result.get("return_code") != 0:
                    if not all_items:
                        logger.warning(f"ka10073 조회 실패: {result.get('return_msg')}")
                    break

                items = result.get("dt_stk_rlzt_pl", [])
                for item in items:
                    stk_cd = str(item.get("stk_cd", "")).replace("A", "").strip()
                    if not stk_cd:
                        continue

                    qty = parse_int(item.get("cntr_qty"))
                    buy_uv = parse_int(item.get("buy_uv"))
                    sell_price = parse_int(item.get("cntr_pric"))
                    profit_loss = parse_int(item.get("tdy_sel_pl"))
                    profit_rate = parse_float(item.get("pl_rt"))

                    # buy_uv=0이지만 체결가·손익률이 있는 경우 역산
                    # buy_price = sell_price / (1 + profit_rate / 100)
                    if buy_uv == 0 and sell_price > 0 and profit_rate != 0:
                        buy_uv = round(sell_price / (1 + profit_rate / 100))
                        if profit_loss == 0 and qty > 0:
                            profit_loss = round((sell_price - buy_uv) * qty)

                    all_items.append(RealizedPnlItem(
                        date=item.get("dt", ""),
                        symbol=stk_cd,
                        name=item.get("stk_nm", "").strip(),
                        quantity=qty,
                        buy_price=buy_uv,
                        sell_price=sell_price,
                        profit_loss=profit_loss,
                        profit_rate=profit_rate,
                        commission=parse_int(item.get("tdy_trde_cmsn")),
                        tax=parse_int(item.get("tdy_trde_tax")),
                    ))

                # 연속조회 처리
                resp_cont_yn = result.get("cont_yn", "N")
                resp_next_key = result.get("next_key", "")
                if resp_cont_yn == "Y" and resp_next_key:
                    cont_yn = "Y"
                    next_key = resp_next_key
                else:
                    break

            logger.info(f"ka10073 - 실현손익 {len(all_items)}건 조회 ({start_date}~{end_date})")
            return all_items

        except Exception as e:
            logger.error(f"실현손익 조회 실패: {str(e)}")
            return []

    async def get_order_history(
        self,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """주문 내역 조회 (kt00005 - 계좌별주문체결내역상세요청)"""
        if not start_date:
            start_date = (datetime.now() - timedelta(days=7)).strftime("%Y%m%d")
        if not end_date:
            end_date = datetime.now().strftime("%Y%m%d")

        try:
            result = await self._request(
                "POST",
                "/api/dostk/acnt",
                data={
                    "trnm": "kt00005",
                    "acnt": self.account_number,
                    "acnt_pwd": self.account_password,
                    "strt_dt": start_date,
                    "end_dt": end_date,
                },
                api_id="kt00005"
            )

            if result.get("return_code") != 0:
                return []

            orders = []
            for item in result.get("data", {}).get("orders", []):
                orders.append({
                    "order_date": item.get("ord_dt"),
                    "order_no": item.get("ord_no"),
                    "symbol": item.get("stk_cd"),
                    "name": item.get("stk_nm"),
                    "side": "buy" if item.get("buy_sell_tp") == "1" else "sell",
                    "order_type": item.get("ord_tp_nm"),
                    "quantity": int(item.get("ord_qty", 0)),
                    "price": int(item.get("ord_prc", 0)),
                    "filled_quantity": int(item.get("ccld_qty", 0)),
                    "filled_price": int(item.get("ccld_prc", 0)),
                    "status": item.get("ord_st_nm"),
                })
            return orders

        except Exception as e:
            logger.error(f"주문 내역 조회 실패: {str(e)}")
            return []

    # ========== 종목 정보 ==========

    async def get_stock_info(self, symbol: str) -> Optional[Dict[str, Any]]:
        """종목 기본 정보 조회 (ka10100 - 종목정보 조회)"""
        try:
            result = await self._request(
                "POST",
                "/api/dostk/stkinfo",
                data={
                    "trnm": "ka10100",
                    "stk_cd": symbol,
                },
                api_id="ka10100"
            )

            if result.get("return_code") != 0:
                return None

            data = result.get("data", {})
            return {
                "symbol": symbol,
                "name": data.get("stk_nm", ""),
                "market": data.get("mrkt_nm", ""),
                "sector": data.get("sect_nm", ""),
                "listed_shares": int(data.get("lstd_stk_cnt", 0)),
                "capital": int(data.get("cptl", 0)),
            }

        except Exception as e:
            logger.error(f"종목 정보 조회 실패 [{symbol}]: {str(e)}")
            return None

    async def search_stocks(self, keyword: str) -> List[Dict[str, Any]]:
        """종목 검색 (ka10099 - 종목정보 리스트)"""
        try:
            result = await self._request(
                "POST",
                "/api/dostk/stkinfo",
                data={
                    "trnm": "ka10099",
                    "srch_txt": keyword,
                },
                api_id="ka10099"
            )

            if result.get("return_code") != 0:
                return []

            stocks = []
            for item in result.get("data", {}).get("stocks", []):
                stocks.append({
                    "symbol": item.get("stk_cd", ""),
                    "name": item.get("stk_nm", ""),
                    "market": item.get("mrkt_nm", ""),
                })
            return stocks

        except Exception as e:
            logger.error(f"종목 검색 실패 [{keyword}]: {str(e)}")
            return []

    async def get_market_stocks(self, market: str = "KOSPI") -> List[Dict[str, Any]]:
        """시장별 종목 리스트 (ka10101 - 업종코드 리스트)"""
        try:
            # 시장코드: 0-코스피, 10-코스닥
            mrkt_cd = "0" if market.upper() == "KOSPI" else "10"

            result = await self._request(
                "POST",
                "/api/dostk/stkinfo",
                data={
                    "trnm": "ka10101",
                    "mrkt_cd": mrkt_cd,
                },
                api_id="ka10101"
            )

            if result.get("return_code") != 0:
                return []

            stocks = []
            for item in result.get("data", {}).get("stocks", []):
                stocks.append({
                    "symbol": item.get("stk_cd", ""),
                    "name": item.get("stk_nm", ""),
                    "market": market,
                })
            return stocks

        except Exception as e:
            logger.error(f"시장 종목 조회 실패 [{market}]: {str(e)}")
            return []


# 싱글톤 인스턴스
kiwoom_client = KiwoomRestClient(is_mock=settings.kiwoom_is_mock)
