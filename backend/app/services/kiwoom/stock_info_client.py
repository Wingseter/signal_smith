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
        """시장별 종목 리스트 (ka10099 - 종목정보 리스트)"""
        try:
            import httpx
            from app.config import settings

            mrkt_tp = "0" if market.upper() == "KOSPI" else "10"
            stocks = []
            cont_yn = "N"
            next_key = ""

            while True:
                headers = self._http._get_headers(api_id="ka10099")
                headers["cont-yn"] = cont_yn
                headers["next-key"] = next_key

                url = f"{self._http.base_url}/api/dostk/stkinfo"
                async with httpx.AsyncClient(timeout=30.0, verify=settings.kiwoom_verify_ssl) as client:
                    response = await client.post(url, headers=headers, json={"mrkt_tp": mrkt_tp})
                    response.raise_for_status()
                    result = response.json()

                for item in result.get("list", []):
                    code = item.get("code", "")
                    if not code or len(code) != 6:
                        continue
                    stocks.append({
                        "symbol": code,
                        "name": item.get("name", ""),
                        "market": market,
                        "last_price": item.get("lastPrice", ""),
                    })

                # 연속조회 처리
                resp_cont = response.headers.get("cont-yn", "N")
                resp_next = response.headers.get("next-key", "")
                if resp_cont == "Y" and resp_next:
                    cont_yn = resp_cont
                    next_key = resp_next
                    logger.debug(f"[{market}] 연속조회: {len(stocks)}개 누적")
                else:
                    break

            logger.info(f"[{market}] 종목 {len(stocks)}개 조회 완료")
            return stocks

        except Exception as e:
            logger.error(f"시장 종목 조회 실패 [{market}]: {str(e)}")
            return []
