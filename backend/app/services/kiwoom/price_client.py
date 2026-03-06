"""Price data retrieval for Kiwoom API."""

import asyncio
from datetime import datetime
from typing import Optional, List, Dict, Any
import logging

from app.services.kiwoom.base import StockPrice

logger = logging.getLogger(__name__)


class PriceClient:
    """Stock price data client."""

    def __init__(self, http: "TokenManager"):
        self._http = http

    # ── Parsing helpers ──

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

    # ── Public API ──

    async def get_stock_price(self, symbol: str) -> Optional[StockPrice]:
        """현재가 조회 (ka10001 - 주식기본정보요청)"""
        try:
            result = await self._http._request(
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
        """복수 종목 현재가 조회 (0.2초 간격 순차 요청으로 429 방지)"""
        results = []
        for i, symbol in enumerate(symbols):
            try:
                price = await self.get_stock_price(symbol)
                if price:
                    results.append(price)
            except Exception as e:
                logger.warning(f"시세 조회 실패 [{symbol}]: {e}")
            # 마지막 종목 제외, 요청 간 0.2초 딜레이 (초당 5회 이내)
            if i < len(symbols) - 1:
                await asyncio.sleep(0.2)
        return results

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
            result = await self._http._request(
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
            result = await self._http._request(
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
