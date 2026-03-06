"""Account data retrieval for Kiwoom API."""

from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
import logging

import httpx

from app.config import settings
from app.services.kiwoom.base import Balance, Holding, RealizedPnlItem
from .parsers import parse_int, parse_float

logger = logging.getLogger(__name__)


class AccountClient:
    """Account and holdings client."""

    def __init__(self, http: "TokenManager"):
        self._http = http

    async def get_balance(self) -> Balance:
        """
        계좌 잔고 조회

        kt00001 (예수금상세현황요청): 예수금, 주문가능금액 등
        ka01690 (일별잔고수익률): 매입금액, 평가금액, 평가손익, 수익률 (실전투자만 지원)
        """
        total_deposit = 0
        d1_estimated_deposit = 0
        d2_estimated_deposit = 0
        available_amount = 0
        total_purchase = 0
        total_evaluation = 0
        total_profit_loss = 0
        profit_rate = 0.0

        # 1. kt00001 - 예수금상세현황요청 (예수금, 주문가능금액)
        try:
            result = await self._http._request(
                "POST",
                "/api/dostk/acnt",
                data={
                    "trnm": "kt00001",
                    "qry_tp": "3",  # 조회구분: 2-일반조회, 3-추정조회
                },
                api_id="kt00001"
            )

            logger.debug(f"kt00001 응답: {result}")

            if result.get("return_code") == 0:
                # kt00001 응답 필드명
                # entr: 예수금
                # d1_entra: D+1 추정예수금
                # d2_entra: D+2 추정예수금
                # ord_alow_amt: 주문가능금액
                entr_amount = parse_int(result.get("entr"))
                d1_estimated_deposit = parse_int(result.get("d1_entra"))
                d2_estimated_deposit = parse_int(result.get("d2_entra"))
                available_amount = parse_int(result.get("ord_alow_amt"))
                # 일반 예수금(entr)과 D+1/D+2 추정예수금 중 가장 큰 값을 예수금 기준으로 사용
                total_deposit = max(entr_amount, d1_estimated_deposit, d2_estimated_deposit)
                logger.info(
                    "kt00001 - 예수금(entr): %s, D+1추정(d1_entra): %s, D+2추정(d2_entra): %s, 주문가능: %s, 적용예수금: %s",
                    entr_amount,
                    d1_estimated_deposit,
                    d2_estimated_deposit,
                    available_amount,
                    total_deposit,
                )
            else:
                logger.warning(f"kt00001 조회 실패: {result.get('return_msg')}")

        except Exception as e:
            logger.error(f"kt00001 조회 오류: {str(e)}")

        # 2. kt00018 - 계좌평가잔고내역요청 (매입금액, 평가금액, 수익률)
        # 모의투자도 지원함
        try:
            result = await self._http._request(
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
        try:
            result = await self._http._request(
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
        if not end_date:
            end_date = datetime.now().strftime("%Y%m%d")
        if not start_date:
            start_date = (datetime.now() - timedelta(days=30)).strftime("%Y%m%d")

        try:
            all_items: List[RealizedPnlItem] = []
            cont_yn = "N"
            next_key = ""

            while True:
                headers = self._http._get_headers(api_id="ka10073", cont_yn=cont_yn, next_key=next_key)

                async with httpx.AsyncClient(timeout=30.0, verify=settings.kiwoom_verify_ssl) as client:
                    response = await client.post(
                        f"{self._http.base_url}/api/dostk/acnt",
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
            result = await self._http._request(
                "POST",
                "/api/dostk/acnt",
                data={
                    "trnm": "kt00005",
                    "acnt": self._http.account_number,
                    "acnt_pwd": self._http.account_password,
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
