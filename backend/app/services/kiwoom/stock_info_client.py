"""Stock information retrieval for Kiwoom API."""

from typing import Optional, List, Dict, Any
import logging

logger = logging.getLogger(__name__)


class StockInfoClient:
    """Stock information client."""

    def __init__(self, http: "TokenManager"):
        self._http = http

    async def get_stock_info(self, symbol: str) -> Optional[Dict[str, Any]]:
        """종목 기본 정보 조회 (ka10100 - 종목정보 조회)"""
        try:
            result = await self._http._request(
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
            result = await self._http._request(
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
            mrkt_tp = "0" if market.upper() == "KOSPI" else "10"

            result = await self._http._request(
                "POST",
                "/api/dostk/stkinfo",
                data={
                    "trnm": "ka10101",
                    # ka10101 필수 파라미터는 mrkt_tp
                    "mrkt_tp": mrkt_tp,
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
