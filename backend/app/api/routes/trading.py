"""
Trading API Routes

주문 실행 및 계좌 관리 API.
키움증권 API를 통해 실제 거래를 수행합니다.
"""

from datetime import datetime
from decimal import Decimal
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.routes.auth import get_current_user
from app.config import settings
from app.core.database import get_db
from app.models import Transaction, TradingSignal, TransactionStatus, TransactionType, User
from app.services.trading_service import trading_service

router = APIRouter()


# ========== Request/Response Models ==========

class OrderCreate(BaseModel):
    symbol: str
    side: str  # 'buy' or 'sell'
    quantity: int
    price: int = 0  # 0 for market order
    order_type: str = "limit"  # 'limit' or 'market'
    note: Optional[str] = None


class OrderResponse(BaseModel):
    id: int
    symbol: str
    transaction_type: str
    quantity: int
    price: float
    total_amount: float
    status: str
    order_id: Optional[str] = None
    created_at: str
    executed_at: Optional[str] = None

    class Config:
        from_attributes = True


class BalanceResponse(BaseModel):
    total_deposit: int
    available_amount: int
    total_purchase: int
    total_evaluation: int
    total_profit_loss: int
    profit_rate: float


class HoldingResponse(BaseModel):
    symbol: str
    name: str
    quantity: int
    avg_price: int
    current_price: int
    evaluation: int
    profit_loss: int
    profit_rate: float


class TradingSignalResponse(BaseModel):
    id: int
    symbol: str
    signal_type: str
    strength: float
    source_agent: str
    reason: str
    target_price: Optional[float] = None
    stop_loss: Optional[float] = None
    created_at: str

    class Config:
        from_attributes = True


class ExecuteSignalRequest(BaseModel):
    quantity: int


# ========== 주문 API ==========

@router.post("/orders")
async def create_order(
    order_data: OrderCreate,
    current_user: User = Depends(get_current_user),
):
    """
    주문 실행

    키움증권 API를 통해 실제 주문을 실행합니다.

    - side: 'buy' 또는 'sell'
    - order_type: 'limit' (지정가) 또는 'market' (시장가)
    - price: 지정가 주문시 가격, 시장가 주문시 0
    """
    result = await trading_service.place_order(
        user_id=current_user.id,
        symbol=order_data.symbol,
        side=order_data.side,
        quantity=order_data.quantity,
        price=order_data.price,
        order_type=order_data.order_type,
    )

    if not result["success"]:
        raise HTTPException(
            status_code=400,
            detail=result.get("message", result.get("error", "주문 실패")),
        )

    return result


@router.get("/orders", response_model=List[OrderResponse])
async def list_orders(
    status: Optional[str] = Query(None, description="pending, submitted, filled, cancelled"),
    symbol: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    current_user: User = Depends(get_current_user),
):
    """주문 내역 조회"""
    orders = await trading_service.get_order_history(current_user.id, limit)

    # 필터링
    if status:
        orders = [o for o in orders if o["status"] == status]
    if symbol:
        orders = [o for o in orders if o["symbol"] == symbol]

    return orders


@router.get("/orders/{order_id}", response_model=OrderResponse)
async def get_order(
    order_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """주문 상세 조회"""
    result = await db.execute(
        select(Transaction).where(
            Transaction.id == order_id,
            Transaction.user_id == current_user.id,
        )
    )
    order = result.scalar_one_or_none()

    if not order:
        raise HTTPException(status_code=404, detail="주문을 찾을 수 없습니다.")

    return {
        "id": order.id,
        "symbol": order.symbol,
        "transaction_type": order.transaction_type,
        "quantity": order.quantity,
        "price": float(order.price),
        "total_amount": float(order.total_amount),
        "status": order.status,
        "order_id": order.order_id,
        "created_at": order.created_at.isoformat(),
        "executed_at": order.executed_at.isoformat() if order.executed_at else None,
    }


@router.post("/orders/{order_id}/cancel")
async def cancel_order(
    order_id: int,
    current_user: User = Depends(get_current_user),
):
    """주문 취소"""
    result = await trading_service.cancel_order(current_user.id, order_id)

    if not result["success"]:
        raise HTTPException(
            status_code=400,
            detail=result.get("error", "취소 실패"),
        )

    return {"message": "주문이 취소되었습니다."}


# ========== 계좌 API ==========

@router.get("/account/balance", response_model=BalanceResponse)
async def get_account_balance(
    current_user: User = Depends(get_current_user),
):
    """
    계좌 잔고 조회

    키움증권 계좌의 예수금, 주문가능금액, 총평가금액 등을 조회합니다.
    """
    balance = await trading_service.get_account_balance()
    return balance


@router.get("/account/holdings", response_model=List[HoldingResponse])
async def get_holdings(
    current_user: User = Depends(get_current_user),
):
    """
    보유 종목 조회

    현재 보유 중인 종목의 수량, 평균단가, 평가손익 등을 조회합니다.
    """
    holdings = await trading_service.get_holdings()
    return holdings


# ========== 트레이딩 시그널 API ==========

@router.get("/signals", response_model=List[TradingSignalResponse])
async def list_signals(
    symbol: Optional[str] = Query(None),
    signal_type: Optional[str] = Query(None, description="buy, sell, hold"),
    executed: Optional[bool] = Query(None, description="실행 여부 필터"),
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """AI 트레이딩 시그널 조회"""
    query = select(TradingSignal)

    if symbol:
        query = query.where(TradingSignal.symbol == symbol)
    if signal_type:
        query = query.where(TradingSignal.signal_type == signal_type)
    if executed is not None:
        query = query.where(TradingSignal.is_executed == executed)

    query = query.order_by(TradingSignal.created_at.desc()).limit(limit)
    result = await db.execute(query)
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
            "created_at": s.created_at.isoformat(),
        }
        for s in signals
    ]


@router.get("/signals/pending", response_model=List[TradingSignalResponse])
async def get_pending_signals(
    limit: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
):
    """미실행 트레이딩 시그널 조회"""
    signals = await trading_service.get_pending_signals(limit)
    return signals


@router.post("/signals/{signal_id}/execute")
async def execute_signal(
    signal_id: int,
    request: ExecuteSignalRequest,
    current_user: User = Depends(get_current_user),
):
    """
    트레이딩 시그널 실행

    AI가 생성한 트레이딩 시그널을 기반으로 주문을 실행합니다.
    """
    result = await trading_service.execute_signal(
        signal_id=signal_id,
        user_id=current_user.id,
        quantity=request.quantity,
    )

    if not result["success"]:
        raise HTTPException(
            status_code=400,
            detail=result.get("error", "시그널 실행 실패"),
        )

    return result


# ========== 설정 API ==========

@router.get("/settings")
async def get_trading_settings(
    current_user: User = Depends(get_current_user),
):
    """거래 설정 조회"""
    return {
        "trading_enabled": settings.trading_enabled,
        "max_position_size": settings.max_position_size,
        "stop_loss_percent": settings.stop_loss_percent,
        "take_profit_percent": settings.take_profit_percent,
    }
