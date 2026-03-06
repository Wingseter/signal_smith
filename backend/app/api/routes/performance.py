"""
Performance Analytics API Endpoints
신호 성과, 리스크 지표, 월간 수익률 집계
"""

from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.routes.auth import get_current_user
from app.core.database import get_sync_db_dep
from app.models.transaction import TradingSignal, Transaction as Order
from app.models.user import User
from app.services.performance_service import performance_service

import logging

logger = logging.getLogger(__name__)

router = APIRouter()


class SignalPerformance(BaseModel):
    """Individual signal performance."""

    signal_id: int
    symbol: str
    signal_type: str
    signal_date: str
    signal_price: float
    current_price: float
    pnl: float
    pnl_pct: float
    executed: bool
    strength: float


class PerformanceSummary(BaseModel):
    """Overall performance summary."""

    total_signals: int
    executed_signals: int
    buy_signals: int
    sell_signals: int
    win_rate: float
    avg_return: float
    total_pnl: float
    best_signal: Optional[Dict[str, Any]]
    worst_signal: Optional[Dict[str, Any]]


class RiskMetrics(BaseModel):
    """Risk-related metrics."""

    sharpe_ratio: float
    sortino_ratio: float
    max_drawdown: float
    max_drawdown_duration: int
    volatility: float
    var_95: float
    calmar_ratio: float


class TimeSeriesPoint(BaseModel):
    """Time series data point."""

    date: str
    value: float


class PerformanceDashboard(BaseModel):
    """Complete performance dashboard data."""

    summary: PerformanceSummary
    risk_metrics: RiskMetrics
    equity_curve: List[TimeSeriesPoint]
    daily_returns: List[TimeSeriesPoint]
    drawdown_series: List[TimeSeriesPoint]
    signal_performance: List[SignalPerformance]
    performance_by_symbol: Dict[str, Dict[str, float]]
    performance_by_type: Dict[str, Dict[str, float]]
    monthly_returns: List[Dict[str, Any]]


def _period_start(period: str) -> datetime:
    end_date = datetime.now()
    period_days = {"1m": 30, "3m": 90, "6m": 180, "1y": 365, "all": 3650}
    return end_date - timedelta(days=period_days.get(period, 90))


def _load_user_orders(db: Session, user_id: int, start_date: datetime, end_date: Optional[datetime] = None) -> List[Order]:
    query = (
        db.query(Order)
        .filter(
            Order.user_id == user_id,
            Order.created_at >= start_date,
            Order.status == "filled",
        )
        .order_by(Order.created_at)
    )
    if end_date:
        query = query.filter(Order.created_at <= end_date)
    return query.all()


def _load_relevant_signals(
    db: Session,
    symbols: List[str],
    start_date: Optional[datetime] = None,
    limit: Optional[int] = None,
    signal_type: Optional[str] = None,
    executed_only: bool = False,
) -> List[TradingSignal]:
    if not symbols:
        return []

    query = db.query(TradingSignal).filter(TradingSignal.symbol.in_(symbols))
    if start_date:
        query = query.filter(TradingSignal.created_at >= start_date)
    if signal_type:
        query = query.filter(TradingSignal.signal_type == signal_type)
    if executed_only:
        query = query.filter(TradingSignal.is_executed == True)
    query = query.order_by(TradingSignal.created_at.desc())
    if limit:
        query = query.limit(limit)
    return query.all()


@router.get("/dashboard", response_model=PerformanceDashboard)
def get_performance_dashboard(
    period: str = Query("3m", description="Period: 1m, 3m, 6m, 1y, all"),
    db: Session = Depends(get_sync_db_dep),
    current_user: User = Depends(get_current_user),
) -> PerformanceDashboard:
    start_date = _period_start(period)
    orders = _load_user_orders(db, current_user.id, start_date)

    user_symbols = sorted({o.symbol for o in orders})
    signals = _load_relevant_signals(db, user_symbols, start_date=start_date)

    signal_perf = performance_service.calculate_signal_performance(signals, db)
    summary = performance_service.calculate_summary(signals, signal_perf)
    equity_data = performance_service.calculate_equity_curve(orders, start_date)
    risk_metrics = performance_service.calculate_risk_metrics(equity_data["returns"])
    drawdown_series = performance_service.calculate_drawdown_series(equity_data["equity"])
    perf_by_symbol = performance_service.calculate_performance_by_symbol(signal_perf)
    perf_by_type = performance_service.calculate_performance_by_type(signal_perf)
    monthly_returns = performance_service.calculate_monthly_returns(equity_data["equity"])

    return PerformanceDashboard(
        summary=PerformanceSummary(**summary),
        risk_metrics=RiskMetrics(**risk_metrics),
        equity_curve=[TimeSeriesPoint(date=d.isoformat(), value=v) for d, v in equity_data["equity"]],
        daily_returns=[TimeSeriesPoint(date=d.isoformat(), value=v) for d, v in equity_data["returns"]],
        drawdown_series=[TimeSeriesPoint(**d) for d in drawdown_series],
        signal_performance=[SignalPerformance(**p) for p in signal_perf[:50]],
        performance_by_symbol=perf_by_symbol,
        performance_by_type=perf_by_type,
        monthly_returns=monthly_returns,
    )


@router.get("/signals")
def get_signal_performance(
    symbol: Optional[str] = None,
    signal_type: Optional[str] = None,
    executed_only: bool = False,
    limit: int = Query(50, le=200),
    db: Session = Depends(get_sync_db_dep),
    current_user: User = Depends(get_current_user),
) -> List[SignalPerformance]:
    all_orders = (
        db.query(Order)
        .filter(Order.user_id == current_user.id)
        .order_by(Order.created_at.desc())
        .all()
    )
    user_symbols = sorted({o.symbol for o in all_orders})

    if symbol:
        symbols = [symbol]
    else:
        symbols = user_symbols

    signals = _load_relevant_signals(
        db,
        symbols=symbols,
        signal_type=signal_type,
        executed_only=executed_only,
        limit=limit,
    )
    perf = performance_service.calculate_signal_performance(signals, db)
    return [SignalPerformance(**p) for p in perf]


@router.get("/risk-metrics")
def get_risk_metrics(
    period: str = Query("3m", description="Period: 1m, 3m, 6m, 1y, all"),
    db: Session = Depends(get_sync_db_dep),
    current_user: User = Depends(get_current_user),
) -> RiskMetrics:
    start_date = _period_start(period)
    orders = _load_user_orders(db, current_user.id, start_date)
    equity_data = performance_service.calculate_equity_curve(orders, start_date)
    return RiskMetrics(**performance_service.calculate_risk_metrics(equity_data["returns"]))


@router.get("/by-symbol")
def get_performance_by_symbol(
    period: str = Query("3m"),
    db: Session = Depends(get_sync_db_dep),
    current_user: User = Depends(get_current_user),
) -> Dict[str, Dict[str, float]]:
    start_date = _period_start(period)
    orders = _load_user_orders(db, current_user.id, start_date)
    symbols = sorted({o.symbol for o in orders})
    signals = _load_relevant_signals(db, symbols=symbols, start_date=start_date)
    signal_perf = performance_service.calculate_signal_performance(signals, db)
    return performance_service.calculate_performance_by_symbol(signal_perf)


@router.get("/drawdown")
def get_drawdown_analysis(
    period: str = Query("3m"),
    db: Session = Depends(get_sync_db_dep),
    current_user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    start_date = _period_start(period)
    orders = _load_user_orders(db, current_user.id, start_date)
    equity_data = performance_service.calculate_equity_curve(orders, start_date)
    drawdown_series = performance_service.calculate_drawdown_series(equity_data["equity"])

    worst_drawdowns = sorted(drawdown_series, key=lambda p: p["value"])[:5] if drawdown_series else []
    return {
        "current_drawdown": drawdown_series[-1]["value"] if drawdown_series else 0,
        "max_drawdown": min(d["value"] for d in drawdown_series) if drawdown_series else 0,
        "drawdown_series": [TimeSeriesPoint(**d) for d in drawdown_series],
        "worst_drawdowns": [TimeSeriesPoint(**d) for d in worst_drawdowns],
    }


@router.get("/monthly-returns")
def get_monthly_returns(
    year: Optional[int] = None,
    db: Session = Depends(get_sync_db_dep),
    current_user: User = Depends(get_current_user),
) -> List[Dict[str, Any]]:
    current_year = year or datetime.now().year
    start_date = datetime(current_year, 1, 1)
    end_date = datetime(current_year, 12, 31)
    orders = _load_user_orders(db, current_user.id, start_date, end_date=end_date)
    equity_data = performance_service.calculate_equity_curve(orders, start_date)
    return performance_service.calculate_monthly_returns(equity_data["equity"])
