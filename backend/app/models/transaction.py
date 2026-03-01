from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import Optional

from sqlalchemy import Date, DateTime, ForeignKey, Integer, JSON, Numeric, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class TransactionType(str, Enum):
    BUY = "buy"
    SELL = "sell"


class TransactionStatus(str, Enum):
    PENDING = "pending"
    SUBMITTED = "submitted"
    FILLED = "filled"
    PARTIALLY_FILLED = "partially_filled"
    CANCELLED = "cancelled"
    REJECTED = "rejected"


class Transaction(Base):
    """Trading transaction records."""

    __tablename__ = "transactions"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    symbol: Mapped[str] = mapped_column(String(20), index=True)
    transaction_type: Mapped[str] = mapped_column(String(10))  # buy, sell
    quantity: Mapped[int] = mapped_column(Integer)
    price: Mapped[Decimal] = mapped_column(Numeric(15, 2))
    total_amount: Mapped[Decimal] = mapped_column(Numeric(15, 2))
    status: Mapped[str] = mapped_column(String(20), default=TransactionStatus.PENDING.value)
    order_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)  # External order ID
    filled_quantity: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    filled_price: Mapped[Optional[Decimal]] = mapped_column(Numeric(15, 2), nullable=True)
    commission: Mapped[Optional[Decimal]] = mapped_column(Numeric(15, 2), nullable=True)
    note: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    ai_recommendation: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    executed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # Relationships
    user = relationship("User", back_populates="transactions")


class TradingSignal(Base):
    """AI-generated trading signals."""

    __tablename__ = "trading_signals"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    symbol: Mapped[str] = mapped_column(String(20), index=True)
    company_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)  # 종목명
    signal_type: Mapped[str] = mapped_column(String(10))  # buy, sell, hold
    strength: Mapped[Decimal] = mapped_column(Numeric(5, 2))  # 0 to 100
    source_agent: Mapped[str] = mapped_column(String(50))
    reason: Mapped[str] = mapped_column(String(1000))
    target_price: Mapped[Optional[Decimal]] = mapped_column(Numeric(15, 2), nullable=True)
    stop_loss: Mapped[Optional[Decimal]] = mapped_column(Numeric(15, 2), nullable=True)
    quantity: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)  # 주문 수량
    signal_status: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)  # pending/queued/auto_executed
    trigger_details: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)  # 퀀트 트리거 상세
    holding_deadline: Mapped[Optional[date]] = mapped_column(Date, nullable=True)  # 보유 기한 (초과 시 매도)
    quant_score: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)  # GPT 퀀트 점수 (1-10)
    fundamental_score: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)  # Claude 펀더멘털 점수 (1-10)
    allocation_percent: Mapped[Optional[float]] = mapped_column(Numeric(5, 2), nullable=True)  # 투자 비율 (%)
    suggested_amount: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)  # 제안 금액 (원)
    is_executed: Mapped[bool] = mapped_column(default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class SignalEvent(Base):
    """Audit trail for signal lifecycle events (gate blocks, orders, state transitions)."""

    __tablename__ = "signal_events"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    signal_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("trading_signals.id"), nullable=True, index=True
    )
    event_type: Mapped[str] = mapped_column(String(50), index=True)
    symbol: Mapped[str] = mapped_column(String(20), index=True)
    action: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    details: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )
