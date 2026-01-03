from datetime import datetime
from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.routes.auth import get_current_user
from app.config import settings
from app.core.database import get_db
from app.models import Transaction, TradingSignal, TransactionStatus, TransactionType, User

router = APIRouter()


class OrderCreate(BaseModel):
    symbol: str
    transaction_type: TransactionType
    quantity: int
    price: Decimal
    note: Optional[str] = None


class OrderResponse(BaseModel):
    id: int
    symbol: str
    transaction_type: str
    quantity: int
    price: Decimal
    total_amount: Decimal
    status: str
    order_id: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True


class TradingSignalResponse(BaseModel):
    id: int
    symbol: str
    signal_type: str
    strength: Decimal
    source_agent: str
    reason: str
    target_price: Optional[Decimal]
    stop_loss: Optional[Decimal]
    created_at: datetime

    class Config:
        from_attributes = True


@router.post("/orders", response_model=OrderResponse)
async def create_order(
    order_data: OrderCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a new trading order."""
    if not settings.trading_enabled:
        raise HTTPException(
            status_code=400,
            detail="Trading is currently disabled",
        )

    total_amount = order_data.price * order_data.quantity

    if order_data.transaction_type == TransactionType.BUY:
        if total_amount > settings.max_position_size:
            raise HTTPException(
                status_code=400,
                detail=f"Order exceeds maximum position size of {settings.max_position_size}",
            )

    transaction = Transaction(
        user_id=current_user.id,
        symbol=order_data.symbol,
        transaction_type=order_data.transaction_type.value,
        quantity=order_data.quantity,
        price=order_data.price,
        total_amount=total_amount,
        status=TransactionStatus.PENDING.value,
        note=order_data.note,
    )
    db.add(transaction)
    await db.commit()
    await db.refresh(transaction)

    # TODO: Submit order to Kiwoom API
    # This would be handled by a background task

    return transaction


@router.get("/orders", response_model=list[OrderResponse])
async def list_orders(
    status: Optional[str] = Query(None),
    symbol: Optional[str] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List user's trading orders."""
    query = select(Transaction).where(Transaction.user_id == current_user.id)

    if status:
        query = query.where(Transaction.status == status)
    if symbol:
        query = query.where(Transaction.symbol == symbol)

    query = query.order_by(Transaction.created_at.desc()).offset(skip).limit(limit)
    result = await db.execute(query)
    return result.scalars().all()


@router.get("/orders/{order_id}", response_model=OrderResponse)
async def get_order(
    order_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get order details."""
    result = await db.execute(
        select(Transaction).where(
            Transaction.id == order_id, Transaction.user_id == current_user.id
        )
    )
    order = result.scalar_one_or_none()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    return order


@router.post("/orders/{order_id}/cancel", response_model=OrderResponse)
async def cancel_order(
    order_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Cancel a pending order."""
    result = await db.execute(
        select(Transaction).where(
            Transaction.id == order_id, Transaction.user_id == current_user.id
        )
    )
    order = result.scalar_one_or_none()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    if order.status not in [TransactionStatus.PENDING.value, TransactionStatus.SUBMITTED.value]:
        raise HTTPException(
            status_code=400,
            detail="Only pending or submitted orders can be cancelled",
        )

    order.status = TransactionStatus.CANCELLED.value
    await db.commit()
    await db.refresh(order)

    # TODO: Cancel order via Kiwoom API if submitted

    return order


@router.get("/signals", response_model=list[TradingSignalResponse])
async def list_signals(
    symbol: Optional[str] = Query(None),
    signal_type: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List AI-generated trading signals."""
    query = select(TradingSignal)

    if symbol:
        query = query.where(TradingSignal.symbol == symbol)
    if signal_type:
        query = query.where(TradingSignal.signal_type == signal_type)

    query = query.order_by(TradingSignal.created_at.desc()).limit(limit)
    result = await db.execute(query)
    return result.scalars().all()
