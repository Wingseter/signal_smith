"""
Kiwoom REST API Client (KOA Studio)

Cross-platform REST API client for Kiwoom Securities.
Works on macOS, Linux, and Windows.

API Documentation: https://www.kiwoom.com/h/customer/download/VOpenApiInfoView
"""

import asyncio
import hashlib
import hmac
import time
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
import json

import httpx

from app.config import settings
from app.core.redis import get_redis
from app.services.kiwoom.base import (
    KiwoomBaseClient,
    StockPrice,
    OrderResult,
    Balance,
    Holding,
    OrderType,
    OrderSide,
)


class KiwoomRestClient(KiwoomBaseClient):
    """
    키움증권 REST API 클라이언트

    KOA Studio REST API를 사용하여 시세 조회, 주문, 계좌 관리를 수행합니다.
    """

    # API Endpoints
    BASE_URL = "https://openapi.koreainvestment.com:9443"  # 실전투자
    PAPER_URL = "https://openapivts.koreainvestment.com:29443"  # 모의투자

    def __init__(self, is_paper_trading: bool = True):
        """
        Args:
            is_paper_trading: True면 모의투자, False면 실전투자
        """
        self.is_paper_trading = is_paper_trading
        self.base_url = self.PAPER_URL if is_paper_trading else self.BASE_URL

        self.app_key = settings.kis_app_key
        self.app_secret = settings.kis_app_secret
        self.account_number = settings.kis_account_number
        self.account_product_code = settings.kis_account_product_code

        self._access_token: Optional[str] = None
        self._token_expires_at: Optional[datetime] = None
        self._connected = False

    async def connect(self) -> bool:
        """API 연결 및 토큰 발급"""
        if not self.app_key or not self.app_secret:
            raise ValueError("API 키가 설정되지 않았습니다. .env 파일을 확인하세요.")

        try:
            await self._get_access_token()
            self._connected = True
            return True
        except Exception as e:
            self._connected = False
            raise ConnectionError(f"API 연결 실패: {str(e)}")

    async def disconnect(self) -> None:
        """API 연결 해제"""
        self._access_token = None
        self._token_expires_at = None
        self._connected = False

    async def is_connected(self) -> bool:
        """연결 상태 확인"""
        if not self._connected:
            return False
        if self._token_expires_at and datetime.now() >= self._token_expires_at:
            return False
        return True

    async def _get_access_token(self) -> str:
        """액세스 토큰 발급/갱신"""
        # Redis 캐시 확인
        redis = await get_redis()
        cache_key = f"kiwoom:token:{'paper' if self.is_paper_trading else 'real'}"
        cached_token = await redis.get(cache_key)
        if cached_token:
            self._access_token = cached_token
            return cached_token

        # 토큰 유효성 확인
        if self._access_token and self._token_expires_at:
            if datetime.now() < self._token_expires_at - timedelta(minutes=5):
                return self._access_token

        # 새 토큰 발급
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/oauth2/tokenP",
                json={
                    "grant_type": "client_credentials",
                    "appkey": self.app_key,
                    "appsecret": self.app_secret,
                },
                headers={"Content-Type": "application/json"},
            )
            response.raise_for_status()
            data = response.json()

            self._access_token = data["access_token"]
            expires_in = data.get("expires_in", 86400)
            self._token_expires_at = datetime.now() + timedelta(seconds=expires_in)

            # Redis에 캐시
            await redis.set(cache_key, self._access_token, ex=expires_in - 300)

            return self._access_token

    def _get_headers(self, tr_id: str) -> Dict[str, str]:
        """API 요청 헤더 생성"""
        return {
            "Content-Type": "application/json; charset=utf-8",
            "authorization": f"Bearer {self._access_token}",
            "appkey": self.app_key,
            "appsecret": self.app_secret,
            "tr_id": tr_id,
            "custtype": "P",  # 개인
        }

    # ========== 시세 조회 ==========

    async def get_stock_price(self, symbol: str) -> Optional[StockPrice]:
        """현재가 조회"""
        if not await self.is_connected():
            await self.connect()

        try:
            async with httpx.AsyncClient() as client:
                # TR: FHKST01010100 - 주식현재가 시세
                response = await client.get(
                    f"{self.base_url}/uapi/domestic-stock/v1/quotations/inquire-price",
                    headers=self._get_headers("FHKST01010100"),
                    params={
                        "FID_COND_MRKT_DIV_CODE": "J",  # 주식
                        "FID_INPUT_ISCD": symbol,
                    },
                )
                response.raise_for_status()
                data = response.json()

                if data.get("rt_cd") != "0":
                    return None

                output = data.get("output", {})
                return StockPrice(
                    symbol=symbol,
                    name=output.get("hts_kor_isnm", ""),
                    current_price=int(output.get("stck_prpr", 0)),
                    change=int(output.get("prdy_vrss", 0)),
                    change_rate=float(output.get("prdy_ctrt", 0)),
                    open_price=int(output.get("stck_oprc", 0)),
                    high_price=int(output.get("stck_hgpr", 0)),
                    low_price=int(output.get("stck_lwpr", 0)),
                    volume=int(output.get("acml_vol", 0)),
                    trade_amount=int(output.get("acml_tr_pbmn", 0)),
                    timestamp=datetime.now(),
                )

        except Exception as e:
            print(f"시세 조회 실패 [{symbol}]: {str(e)}")
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
        """일봉 데이터 조회"""
        if not await self.is_connected():
            await self.connect()

        if not end_date:
            end_date = datetime.now().strftime("%Y%m%d")

        try:
            async with httpx.AsyncClient() as client:
                # TR: FHKST01010400 - 주식일봉조회
                response = await client.get(
                    f"{self.base_url}/uapi/domestic-stock/v1/quotations/inquire-daily-price",
                    headers=self._get_headers("FHKST01010400"),
                    params={
                        "FID_COND_MRKT_DIV_CODE": "J",
                        "FID_INPUT_ISCD": symbol,
                        "FID_PERIOD_DIV_CODE": "D",  # 일봉
                        "FID_ORG_ADJ_PRC": "0",  # 수정주가
                    },
                )
                response.raise_for_status()
                data = response.json()

                if data.get("rt_cd") != "0":
                    return []

                prices = []
                for item in data.get("output", []):
                    prices.append({
                        "date": item.get("stck_bsop_date"),
                        "open": int(item.get("stck_oprc", 0)),
                        "high": int(item.get("stck_hgpr", 0)),
                        "low": int(item.get("stck_lwpr", 0)),
                        "close": int(item.get("stck_clpr", 0)),
                        "volume": int(item.get("acml_vol", 0)),
                        "change": int(item.get("prdy_vrss", 0)),
                        "change_rate": float(item.get("prdy_ctrt", 0)),
                    })
                return prices

        except Exception as e:
            print(f"일봉 조회 실패 [{symbol}]: {str(e)}")
            return []

    async def get_minute_prices(
        self,
        symbol: str,
        interval: int = 1,
    ) -> List[Dict[str, Any]]:
        """분봉 데이터 조회"""
        if not await self.is_connected():
            await self.connect()

        try:
            async with httpx.AsyncClient() as client:
                # TR: FHKST01010500 - 주식분봉조회
                response = await client.get(
                    f"{self.base_url}/uapi/domestic-stock/v1/quotations/inquire-time-itemchartprice",
                    headers=self._get_headers("FHKST01010500"),
                    params={
                        "FID_ETC_CLS_CODE": "",
                        "FID_COND_MRKT_DIV_CODE": "J",
                        "FID_INPUT_ISCD": symbol,
                        "FID_INPUT_HOUR_1": "160000",  # 조회시간
                        "FID_PW_DATA_INCU_YN": "N",
                    },
                )
                response.raise_for_status()
                data = response.json()

                if data.get("rt_cd") != "0":
                    return []

                prices = []
                for item in data.get("output2", []):
                    prices.append({
                        "time": item.get("stck_cntg_hour"),
                        "open": int(item.get("stck_oprc", 0)),
                        "high": int(item.get("stck_hgpr", 0)),
                        "low": int(item.get("stck_lwpr", 0)),
                        "close": int(item.get("stck_prpr", 0)),
                        "volume": int(item.get("cntg_vol", 0)),
                    })
                return prices

        except Exception as e:
            print(f"분봉 조회 실패 [{symbol}]: {str(e)}")
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
        """주문 실행"""
        if not await self.is_connected():
            await self.connect()

        # TR ID 결정
        if self.is_paper_trading:
            tr_id = "VTTC0802U" if side == OrderSide.BUY else "VTTC0801U"
        else:
            tr_id = "TTTC0802U" if side == OrderSide.BUY else "TTTC0801U"

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.base_url}/uapi/domestic-stock/v1/trading/order-cash",
                    headers=self._get_headers(tr_id),
                    json={
                        "CANO": self.account_number,
                        "ACNT_PRDT_CD": self.account_product_code,
                        "PDNO": symbol,
                        "ORD_DVSN": order_type.value,
                        "ORD_QTY": str(quantity),
                        "ORD_UNPR": str(price) if price > 0 else "0",
                    },
                )
                response.raise_for_status()
                data = response.json()

                success = data.get("rt_cd") == "0"
                output = data.get("output", {})

                return OrderResult(
                    order_no=output.get("ODNO", "") if success else "",
                    symbol=symbol,
                    order_type=order_type.value,
                    side=side.value,
                    quantity=quantity,
                    price=price,
                    status="submitted" if success else "rejected",
                    message=data.get("msg1", ""),
                    timestamp=datetime.now(),
                )

        except Exception as e:
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
        """주문 취소"""
        if not await self.is_connected():
            await self.connect()

        tr_id = "VTTC0803U" if self.is_paper_trading else "TTTC0803U"

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.base_url}/uapi/domestic-stock/v1/trading/order-rvsecncl",
                    headers=self._get_headers(tr_id),
                    json={
                        "CANO": self.account_number,
                        "ACNT_PRDT_CD": self.account_product_code,
                        "KRX_FWDG_ORD_ORGNO": "",
                        "ORGN_ODNO": order_no,
                        "ORD_DVSN": "00",
                        "RVSE_CNCL_DVSN_CD": "02",  # 취소
                        "ORD_QTY": str(quantity),
                        "ORD_UNPR": "0",
                        "QTY_ALL_ORD_YN": "Y",  # 전량
                    },
                )
                response.raise_for_status()
                data = response.json()

                success = data.get("rt_cd") == "0"

                return OrderResult(
                    order_no=order_no,
                    symbol=symbol,
                    order_type="cancel",
                    side="",
                    quantity=quantity,
                    price=0,
                    status="cancelled" if success else "failed",
                    message=data.get("msg1", ""),
                    timestamp=datetime.now(),
                )

        except Exception as e:
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
        """주문 정정"""
        if not await self.is_connected():
            await self.connect()

        tr_id = "VTTC0803U" if self.is_paper_trading else "TTTC0803U"

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.base_url}/uapi/domestic-stock/v1/trading/order-rvsecncl",
                    headers=self._get_headers(tr_id),
                    json={
                        "CANO": self.account_number,
                        "ACNT_PRDT_CD": self.account_product_code,
                        "KRX_FWDG_ORD_ORGNO": "",
                        "ORGN_ODNO": order_no,
                        "ORD_DVSN": "00",
                        "RVSE_CNCL_DVSN_CD": "01",  # 정정
                        "ORD_QTY": str(quantity),
                        "ORD_UNPR": str(price),
                        "QTY_ALL_ORD_YN": "N",
                    },
                )
                response.raise_for_status()
                data = response.json()

                success = data.get("rt_cd") == "0"

                return OrderResult(
                    order_no=order_no,
                    symbol=symbol,
                    order_type="modify",
                    side="",
                    quantity=quantity,
                    price=price,
                    status="modified" if success else "failed",
                    message=data.get("msg1", ""),
                    timestamp=datetime.now(),
                )

        except Exception as e:
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
        """계좌 잔고 조회"""
        if not await self.is_connected():
            await self.connect()

        tr_id = "VTTC8434R" if self.is_paper_trading else "TTTC8434R"

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.base_url}/uapi/domestic-stock/v1/trading/inquire-balance",
                    headers=self._get_headers(tr_id),
                    params={
                        "CANO": self.account_number,
                        "ACNT_PRDT_CD": self.account_product_code,
                        "AFHR_FLPR_YN": "N",
                        "OFL_YN": "",
                        "INQR_DVSN": "02",
                        "UNPR_DVSN": "01",
                        "FUND_STTL_ICLD_YN": "N",
                        "FNCG_AMT_AUTO_RDPT_YN": "N",
                        "PRCS_DVSN": "00",
                        "CTX_AREA_FK100": "",
                        "CTX_AREA_NK100": "",
                    },
                )
                response.raise_for_status()
                data = response.json()

                if data.get("rt_cd") != "0":
                    raise Exception(data.get("msg1", "잔고 조회 실패"))

                output2 = data.get("output2", [{}])[0] if data.get("output2") else {}

                return Balance(
                    total_deposit=int(output2.get("dnca_tot_amt", 0)),
                    available_amount=int(output2.get("ord_psbl_cash", 0)),
                    total_purchase=int(output2.get("pchs_amt_smtl_amt", 0)),
                    total_evaluation=int(output2.get("evlu_amt_smtl_amt", 0)),
                    total_profit_loss=int(output2.get("evlu_pfls_smtl_amt", 0)),
                    profit_rate=float(output2.get("tot_evlu_pfls_rt", 0)),
                )

        except Exception as e:
            print(f"잔고 조회 실패: {str(e)}")
            return Balance(
                total_deposit=0,
                available_amount=0,
                total_purchase=0,
                total_evaluation=0,
                total_profit_loss=0,
                profit_rate=0.0,
            )

    async def get_holdings(self) -> List[Holding]:
        """보유 종목 조회"""
        if not await self.is_connected():
            await self.connect()

        tr_id = "VTTC8434R" if self.is_paper_trading else "TTTC8434R"

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.base_url}/uapi/domestic-stock/v1/trading/inquire-balance",
                    headers=self._get_headers(tr_id),
                    params={
                        "CANO": self.account_number,
                        "ACNT_PRDT_CD": self.account_product_code,
                        "AFHR_FLPR_YN": "N",
                        "OFL_YN": "",
                        "INQR_DVSN": "02",
                        "UNPR_DVSN": "01",
                        "FUND_STTL_ICLD_YN": "N",
                        "FNCG_AMT_AUTO_RDPT_YN": "N",
                        "PRCS_DVSN": "00",
                        "CTX_AREA_FK100": "",
                        "CTX_AREA_NK100": "",
                    },
                )
                response.raise_for_status()
                data = response.json()

                if data.get("rt_cd") != "0":
                    return []

                holdings = []
                for item in data.get("output1", []):
                    if int(item.get("hldg_qty", 0)) > 0:
                        holdings.append(Holding(
                            symbol=item.get("pdno", ""),
                            name=item.get("prdt_name", ""),
                            quantity=int(item.get("hldg_qty", 0)),
                            avg_price=int(item.get("pchs_avg_pric", 0)),
                            current_price=int(item.get("prpr", 0)),
                            evaluation=int(item.get("evlu_amt", 0)),
                            profit_loss=int(item.get("evlu_pfls_amt", 0)),
                            profit_rate=float(item.get("evlu_pfls_rt", 0)),
                        ))
                return holdings

        except Exception as e:
            print(f"보유종목 조회 실패: {str(e)}")
            return []

    async def get_order_history(
        self,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """주문 내역 조회"""
        if not await self.is_connected():
            await self.connect()

        tr_id = "VTTC8001R" if self.is_paper_trading else "TTTC8001R"

        if not start_date:
            start_date = (datetime.now() - timedelta(days=7)).strftime("%Y%m%d")
        if not end_date:
            end_date = datetime.now().strftime("%Y%m%d")

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.base_url}/uapi/domestic-stock/v1/trading/inquire-daily-ccld",
                    headers=self._get_headers(tr_id),
                    params={
                        "CANO": self.account_number,
                        "ACNT_PRDT_CD": self.account_product_code,
                        "INQR_STRT_DT": start_date,
                        "INQR_END_DT": end_date,
                        "SLL_BUY_DVSN_CD": "00",  # 전체
                        "INQR_DVSN": "00",
                        "PDNO": "",
                        "CCLD_DVSN": "00",
                        "ORD_GNO_BRNO": "",
                        "ODNO": "",
                        "INQR_DVSN_3": "00",
                        "INQR_DVSN_1": "",
                        "CTX_AREA_FK100": "",
                        "CTX_AREA_NK100": "",
                    },
                )
                response.raise_for_status()
                data = response.json()

                if data.get("rt_cd") != "0":
                    return []

                orders = []
                for item in data.get("output1", []):
                    orders.append({
                        "order_date": item.get("ord_dt"),
                        "order_no": item.get("odno"),
                        "symbol": item.get("pdno"),
                        "name": item.get("prdt_name"),
                        "side": "buy" if item.get("sll_buy_dvsn_cd") == "02" else "sell",
                        "order_type": item.get("ord_dvsn_name"),
                        "quantity": int(item.get("ord_qty", 0)),
                        "price": int(item.get("ord_unpr", 0)),
                        "filled_quantity": int(item.get("tot_ccld_qty", 0)),
                        "filled_price": int(item.get("avg_prvs", 0)),
                        "status": item.get("ord_tmd"),
                    })
                return orders

        except Exception as e:
            print(f"주문 내역 조회 실패: {str(e)}")
            return []

    # ========== 종목 정보 ==========

    async def get_stock_info(self, symbol: str) -> Optional[Dict[str, Any]]:
        """종목 기본 정보 조회"""
        if not await self.is_connected():
            await self.connect()

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.base_url}/uapi/domestic-stock/v1/quotations/search-stock-info",
                    headers=self._get_headers("CTPF1002R"),
                    params={
                        "PRDT_TYPE_CD": "300",
                        "PDNO": symbol,
                    },
                )
                response.raise_for_status()
                data = response.json()

                if data.get("rt_cd") != "0":
                    return None

                output = data.get("output", {})
                return {
                    "symbol": symbol,
                    "name": output.get("prdt_name", ""),
                    "market": output.get("std_idst_clsf_cd_name", ""),
                    "sector": output.get("idx_bztp_lcls_cd_name", ""),
                    "listed_shares": int(output.get("lstg_stqt", 0)),
                    "capital": int(output.get("cpfn", 0)),
                }

        except Exception as e:
            print(f"종목 정보 조회 실패 [{symbol}]: {str(e)}")
            return None

    async def search_stocks(self, keyword: str) -> List[Dict[str, Any]]:
        """종목 검색 - REST API에서는 직접 지원하지 않음"""
        # 로컬 종목 코드 목록에서 검색하거나
        # 미리 캐싱된 데이터에서 검색하는 방식으로 구현
        return []

    async def get_market_stocks(self, market: str = "KOSPI") -> List[Dict[str, Any]]:
        """시장별 종목 리스트 - REST API에서는 별도 API 필요"""
        # 한국거래소 API 또는 캐싱된 데이터 사용
        return []


# 싱글톤 인스턴스
kiwoom_client = KiwoomRestClient(is_paper_trading=True)
