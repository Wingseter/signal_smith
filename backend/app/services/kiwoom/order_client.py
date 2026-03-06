"""Order execution for Kiwoom API."""

from datetime import datetime
import logging

from app.services.kiwoom.base import OrderResult, OrderType, OrderSide

logger = logging.getLogger(__name__)


class OrderClient:
    """Stock order client."""

    def __init__(self, http: "TokenManager"):
        self._http = http

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
            result = await self._http._request(
                "POST",
                "/api/dostk/ordr",
                data={
                    "dmst_stex_tp": "KRX",  # 국내거래소구분 (필수)
                    "stk_cd": symbol,
                    "ord_qty": str(quantity),
                    "ord_uv": str(price) if price > 0 else "",
                    "trde_tp": trde_tp,
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
            result = await self._http._request(
                "POST",
                "/api/dostk/ordr",
                data={
                    "dmst_stex_tp": "KRX",  # 국내거래소구분 (필수)
                    "orig_ord_no": order_no,
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
            result = await self._http._request(
                "POST",
                "/api/dostk/ordr",
                data={
                    "dmst_stex_tp": "KRX",  # 국내거래소구분 (필수)
                    "orig_ord_no": order_no,
                    "stk_cd": symbol,
                    "mdfy_qty": str(quantity),
                    "mdfy_uv": str(price),
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
