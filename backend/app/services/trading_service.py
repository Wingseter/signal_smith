"""
Trading Service

주문 실행 및 계좌 관리를 위한 서비스.
키움증권 API를 통해 실제 거래를 수행합니다.
"""

from typing import Optional, List, Dict, Any
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.database import async_session_maker
from app.models import Transaction, TransactionStatus, TransactionType, TradingSignal
from app.services.kiwoom.rest_client import kiwoom_client
from app.services.kiwoom.base import OrderType, OrderSide


class TradingService:
    """거래 서비스"""

    def __init__(self):
        self.kiwoom = kiwoom_client
        self.trading_enabled = settings.trading_enabled
        self.max_position_size = settings.max_position_size
        self.stop_loss_percent = settings.stop_loss_percent
        self.take_profit_percent = settings.take_profit_percent

    # ========== 주문 실행 ==========

    async def place_order(
        self,
        user_id: int,
        symbol: str,
        side: str,  # 'buy' or 'sell'
        quantity: int,
        price: int = 0,
        order_type: str = "limit",
    ) -> Dict[str, Any]:
        """
        주문 실행

        Args:
            user_id: 사용자 ID
            symbol: 종목 코드
            side: 'buy' 또는 'sell'
            quantity: 수량
            price: 가격 (0일 경우 현재가 조회 후 지정가 주문으로 자동 변환)
            order_type: 'limit', 'market' 등 (가격이 0이면 강제로 limit 최적화 실행)

        Returns:
            주문 결과
        """
        if not self.trading_enabled:
            return {
                "success": False,
                "error": "Trading is disabled",
                "message": "자동 매매가 비활성화되어 있습니다.",
            }

        # 가격이 0이거나 시장가 주문인 경우 현재가를 조회하여 지정가로 최적화
        if price == 0 or order_type == "market":
            stock_info = await self.kiwoom.get_stock_price(symbol)
            if not stock_info or stock_info.current_price == 0:
                return {
                    "success": False,
                    "error": "Price fetch failed",
                    "message": "현재가를 조회하지 못해 주문을 진행할 수 없습니다.",
                }
            # 슬리피지를 방지하기 위해 현재가로 지정가 매매 수행
            price = stock_info.current_price
            order_type = "limit"
            import logging
            logger = logging.getLogger(__name__)
            logger.info(f"[{symbol}] 시장가 대안으로 현재가({price:,}원) 지정가 주문 전환 ('{side}')")

        # 포지션 크기 검증
        if side == "buy":
            total_amount = price * quantity
            if total_amount > self.max_position_size:
                return {
                    "success": False,
                    "error": "Position size exceeded",
                    "message": f"최대 포지션 크기({self.max_position_size:,}원)를 초과합니다.",
                }

        # 주문 유형 변환
        kiwoom_order_type = {
            "limit": OrderType.LIMIT,
            "market": OrderType.MARKET,
        }.get(order_type, OrderType.LIMIT)

        kiwoom_side = OrderSide.BUY if side == "buy" else OrderSide.SELL

        # DB에 주문 기록 (대기 상태)
        async with async_session_maker() as session:
            transaction = Transaction(
                user_id=user_id,
                symbol=symbol,
                transaction_type=side,
                quantity=quantity,
                price=Decimal(str(price)),
                total_amount=Decimal(str(price * quantity)),
                status=TransactionStatus.PENDING.value,
            )
            session.add(transaction)
            await session.commit()
            await session.refresh(transaction)
            transaction_id = transaction.id

        # 키움 API로 주문 실행
        try:
            result = await self.kiwoom.place_order(
                symbol=symbol,
                side=kiwoom_side,
                quantity=quantity,
                price=price,
                order_type=kiwoom_order_type,
            )

            # DB 업데이트
            async with async_session_maker() as session:
                db_result = await session.execute(
                    select(Transaction).where(Transaction.id == transaction_id)
                )
                transaction = db_result.scalar_one()

                if result.status == "submitted":
                    transaction.status = TransactionStatus.SUBMITTED.value
                    transaction.order_id = result.order_no
                else:
                    transaction.status = TransactionStatus.REJECTED.value
                    transaction.note = result.message

                await session.commit()

            return {
                "success": result.status == "submitted",
                "transaction_id": transaction_id,
                "order_no": result.order_no,
                "status": result.status,
                "message": result.message,
            }

        except Exception as e:
            # 오류 시 상태 업데이트
            async with async_session_maker() as session:
                db_result = await session.execute(
                    select(Transaction).where(Transaction.id == transaction_id)
                )
                transaction = db_result.scalar_one()
                transaction.status = TransactionStatus.REJECTED.value
                transaction.note = str(e)
                await session.commit()

            return {
                "success": False,
                "transaction_id": transaction_id,
                "error": str(e),
            }

    async def cancel_order(
        self,
        user_id: int,
        transaction_id: int,
    ) -> Dict[str, Any]:
        """주문 취소"""
        async with async_session_maker() as session:
            result = await session.execute(
                select(Transaction).where(
                    Transaction.id == transaction_id,
                    Transaction.user_id == user_id,
                )
            )
            transaction = result.scalar_one_or_none()

            if not transaction:
                return {"success": False, "error": "Order not found"}

            if transaction.status not in [
                TransactionStatus.PENDING.value,
                TransactionStatus.SUBMITTED.value,
            ]:
                return {"success": False, "error": "Order cannot be cancelled"}

            if not transaction.order_id:
                # 아직 제출되지 않은 주문
                transaction.status = TransactionStatus.CANCELLED.value
                await session.commit()
                return {"success": True}

            # 키움 API로 취소 요청
            cancel_result = await self.kiwoom.cancel_order(
                order_no=transaction.order_id,
                symbol=transaction.symbol,
                quantity=transaction.quantity,
            )

            if cancel_result.status == "cancelled":
                transaction.status = TransactionStatus.CANCELLED.value
            else:
                return {
                    "success": False,
                    "error": cancel_result.message,
                }

            await session.commit()
            return {"success": True}

    # ========== 계좌 조회 ==========

    async def get_account_balance(self) -> Dict[str, Any]:
        """계좌 잔고 조회"""
        balance = await self.kiwoom.get_balance()
        return {
            "total_deposit": balance.total_deposit,
            "available_amount": balance.available_amount,
            "total_purchase": balance.total_purchase,
            "total_evaluation": balance.total_evaluation,
            "total_profit_loss": balance.total_profit_loss,
            "profit_rate": balance.profit_rate,
        }

    async def get_holdings(self) -> List[Dict[str, Any]]:
        """보유 종목 조회"""
        holdings = await self.kiwoom.get_holdings()
        return [
            {
                "symbol": h.symbol,
                "name": h.name,
                "quantity": h.quantity,
                "avg_price": h.avg_price,
                "current_price": h.current_price,
                "evaluation": h.evaluation,
                "profit_loss": h.profit_loss,
                "profit_rate": h.profit_rate,
            }
            for h in holdings
        ]

    async def get_order_history(
        self,
        user_id: int,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """주문 내역 조회"""
        async with async_session_maker() as session:
            result = await session.execute(
                select(Transaction)
                .where(Transaction.user_id == user_id)
                .order_by(Transaction.created_at.desc())
                .limit(limit)
            )
            transactions = result.scalars().all()

            return [
                {
                    "id": t.id,
                    "symbol": t.symbol,
                    "transaction_type": t.transaction_type,
                    "quantity": t.quantity,
                    "price": float(t.price),
                    "total_amount": float(t.total_amount),
                    "status": t.status,
                    "order_id": t.order_id,
                    "created_at": t.created_at.isoformat(),
                    "executed_at": t.executed_at.isoformat() if t.executed_at else None,
                }
                for t in transactions
            ]

    # ========== AI 트레이딩 시그널 ==========

    async def create_trading_signal(
        self,
        symbol: str,
        signal_type: str,
        strength: float,
        source_agent: str,
        reason: str,
        target_price: Optional[float] = None,
        stop_loss: Optional[float] = None,
        quantity: Optional[int] = None,
        signal_status: Optional[str] = None,
        trigger_details: Optional[Dict[str, Any]] = None,
        holding_deadline: Optional[date] = None,
        company_name: Optional[str] = None,
        quant_score: Optional[int] = None,
        fundamental_score: Optional[int] = None,
        is_executed: bool = False,
    ) -> int:
        """AI 트레이딩 시그널 생성"""
        async with async_session_maker() as session:
            signal = TradingSignal(
                symbol=symbol,
                company_name=company_name,
                signal_type=signal_type,
                strength=Decimal(str(strength)),
                source_agent=source_agent,
                reason=reason,
                target_price=Decimal(str(target_price)) if target_price else None,
                stop_loss=Decimal(str(stop_loss)) if stop_loss else None,
                quantity=quantity,
                signal_status=signal_status,
                trigger_details=trigger_details,
                holding_deadline=holding_deadline,
                quant_score=quant_score,
                fundamental_score=fundamental_score,
                is_executed=is_executed,
            )
            session.add(signal)
            await session.commit()
            await session.refresh(signal)
            return signal.id

    async def execute_signal(
        self,
        signal_id: int,
        user_id: int,
        quantity: int,
    ) -> Dict[str, Any]:
        """트레이딩 시그널 기반 주문 실행"""
        async with async_session_maker() as session:
            result = await session.execute(
                select(TradingSignal).where(TradingSignal.id == signal_id)
            )
            signal = result.scalar_one_or_none()

            if not signal:
                return {"success": False, "error": "Signal not found"}

            if signal.is_executed:
                return {"success": False, "error": "Signal already executed"}

            # 시그널 기반 주문
            side = "buy" if signal.signal_type == "buy" else "sell"
            price = int(signal.target_price) if signal.target_price else 0

            order_result = await self.place_order(
                user_id=user_id,
                symbol=signal.symbol,
                side=side,
                quantity=quantity,
                price=price,
                order_type="limit" if price > 0 else "market",
            )

            if order_result["success"]:
                signal.is_executed = True
                await session.commit()

            return order_result

    async def get_pending_signals(
        self,
        limit: int = 20,
    ) -> List[Dict[str, Any]]:
        """미실행 트레이딩 시그널 조회"""
        async with async_session_maker() as session:
            result = await session.execute(
                select(TradingSignal)
                .where(TradingSignal.is_executed == False)
                .order_by(TradingSignal.created_at.desc())
                .limit(limit)
            )
            signals = result.scalars().all()

            return [
                {
                    "id": s.id,
                    "symbol": s.symbol,
                    "signal_type": s.signal_type,
                    "strength": float(s.strength),
                    "source_agent": s.source_agent,
                    "reason": s.reason,
                    "target_price": float(s.target_price) if s.target_price else None,
                    "stop_loss": float(s.stop_loss) if s.stop_loss else None,
                    "quantity": s.quantity,
                    "signal_status": s.signal_status,
                    "created_at": s.created_at.isoformat(),
                }
                for s in signals
            ]


# 싱글톤 인스턴스
trading_service = TradingService()
