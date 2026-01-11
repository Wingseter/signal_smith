"""
Backtest Models
백테스트 결과 저장을 위한 데이터 모델
"""

from datetime import datetime
from decimal import Decimal
from typing import Optional, Dict, Any, List

from sqlalchemy import DateTime, Integer, Numeric, String, Text, ForeignKey, func, JSON, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class BacktestResult(Base):
    """Backtest execution result."""

    __tablename__ = "backtest_results"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), index=True)

    # Strategy info
    strategy_name: Mapped[str] = mapped_column(String(50))
    strategy_display_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    parameters: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)

    # Backtest configuration
    symbols: Mapped[List[str]] = mapped_column(JSON)  # List of symbols tested
    start_date: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    end_date: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    initial_capital: Mapped[Decimal] = mapped_column(Numeric(18, 2))

    # Results
    final_value: Mapped[Decimal] = mapped_column(Numeric(18, 2))
    total_return_pct: Mapped[Decimal] = mapped_column(Numeric(10, 4))
    total_trades: Mapped[int] = mapped_column(Integer)
    winning_trades: Mapped[int] = mapped_column(Integer, default=0)
    losing_trades: Mapped[int] = mapped_column(Integer, default=0)

    # Performance metrics (stored as JSON for flexibility)
    metrics: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)

    # Detailed data
    trades: Mapped[Optional[List[Dict[str, Any]]]] = mapped_column(JSON, nullable=True)
    equity_curve: Mapped[Optional[List[Dict[str, Any]]]] = mapped_column(JSON, nullable=True)

    # Status
    is_favorite: Mapped[bool] = mapped_column(Boolean, default=False)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    tags: Mapped[Optional[List[str]]] = mapped_column(JSON, nullable=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    def __repr__(self) -> str:
        return f"<BacktestResult {self.id}: {self.strategy_name} ({self.total_return_pct}%)>"


class BacktestComparison(Base):
    """Saved backtest comparison sets."""

    __tablename__ = "backtest_comparisons"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), index=True)

    name: Mapped[str] = mapped_column(String(100))
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Comparison configuration
    symbols: Mapped[List[str]] = mapped_column(JSON)
    start_date: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    end_date: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    initial_capital: Mapped[Decimal] = mapped_column(Numeric(18, 2))

    # Strategies compared
    strategies: Mapped[List[str]] = mapped_column(JSON)

    # Results summary
    results: Mapped[Dict[str, Any]] = mapped_column(JSON)
    best_strategy: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    ranking: Mapped[Optional[List[Dict[str, Any]]]] = mapped_column(JSON, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    def __repr__(self) -> str:
        return f"<BacktestComparison {self.id}: {self.name}>"
