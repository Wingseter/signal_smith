from datetime import datetime
from decimal import Decimal
from typing import Optional, Dict, Any

from sqlalchemy import DateTime, Integer, Numeric, String, Text, func, JSON
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class Stock(Base):
    """Stock master information."""

    __tablename__ = "stocks"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    symbol: Mapped[str] = mapped_column(String(20), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(100))
    market: Mapped[str] = mapped_column(String(20))  # KOSPI, KOSDAQ
    sector: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    industry: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    market_cap: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    is_active: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class StockPrice(Base):
    """Stock price history (OHLCV)."""

    __tablename__ = "stock_prices"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    symbol: Mapped[str] = mapped_column(String(20), index=True)
    date: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    open: Mapped[Decimal] = mapped_column(Numeric(15, 2))
    high: Mapped[Decimal] = mapped_column(Numeric(15, 2))
    low: Mapped[Decimal] = mapped_column(Numeric(15, 2))
    close: Mapped[Decimal] = mapped_column(Numeric(15, 2))
    volume: Mapped[int] = mapped_column(Integer)
    change_percent: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 4), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class StockAnalysis(Base):
    """AI analysis results for stocks."""

    __tablename__ = "stock_analyses"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    symbol: Mapped[str] = mapped_column(String(20), index=True)
    analysis_type: Mapped[str] = mapped_column(String(50))  # quant, fundamental, news, technical
    agent_name: Mapped[str] = mapped_column(String(50))  # gemini, chatgpt, claude, ml
    summary: Mapped[str] = mapped_column(Text)
    score: Mapped[Optional[Decimal]] = mapped_column(Numeric(5, 2), nullable=True)  # -100 to 100
    recommendation: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)  # buy, hold, sell
    details: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON string (legacy)
    raw_data: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)  # Full analysis data
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
