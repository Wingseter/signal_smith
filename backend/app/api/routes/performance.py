"""
Performance Analytics API Endpoints
신호별 수익률, Sharpe Ratio, MDD 추적
"""

from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import func, and_, case
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.api.routes.auth import get_current_user
from app.models.user import User
from app.models.transaction import Transaction as Order, TradingSignal
from app.models.stock import StockPrice

import numpy as np
import pandas as pd
import logging

logger = logging.getLogger(__name__)

router = APIRouter()


# Response Models
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


@router.get("/dashboard", response_model=PerformanceDashboard)
async def get_performance_dashboard(
    period: str = Query("3m", description="Period: 1m, 3m, 6m, 1y, all"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> PerformanceDashboard:
    """
    Get comprehensive performance dashboard with all metrics.
    """
    # Calculate date range
    end_date = datetime.now()
    if period == "1m":
        start_date = end_date - timedelta(days=30)
    elif period == "3m":
        start_date = end_date - timedelta(days=90)
    elif period == "6m":
        start_date = end_date - timedelta(days=180)
    elif period == "1y":
        start_date = end_date - timedelta(days=365)
    else:
        start_date = datetime(2020, 1, 1)

    # Fetch signals
    signals = (
        db.query(TradingSignal)
        .filter(
            TradingSignal.user_id == current_user.id,
            TradingSignal.created_at >= start_date,
        )
        .order_by(TradingSignal.created_at.desc())
        .all()
    )

    # Fetch executed orders
    orders = (
        db.query(Order)
        .filter(
            Order.user_id == current_user.id,
            Order.created_at >= start_date,
            Order.status == "filled",
        )
        .order_by(Order.created_at)
        .all()
    )

    # Calculate signal performance
    signal_performance = await _calculate_signal_performance(signals, db)

    # Calculate summary
    summary = _calculate_summary(signals, signal_performance)

    # Calculate equity curve and returns from orders
    equity_data = _calculate_equity_curve(orders, start_date)

    # Calculate risk metrics
    risk_metrics = _calculate_risk_metrics(equity_data["returns"])

    # Calculate drawdown series
    drawdown_series = _calculate_drawdown_series(equity_data["equity"])

    # Performance by symbol
    perf_by_symbol = _calculate_performance_by_symbol(signal_performance)

    # Performance by signal type
    perf_by_type = _calculate_performance_by_type(signal_performance)

    # Monthly returns
    monthly_returns = _calculate_monthly_returns(equity_data["equity"])

    return PerformanceDashboard(
        summary=summary,
        risk_metrics=risk_metrics,
        equity_curve=[
            TimeSeriesPoint(date=d.isoformat(), value=v)
            for d, v in equity_data["equity"]
        ],
        daily_returns=[
            TimeSeriesPoint(date=d.isoformat(), value=v)
            for d, v in equity_data["returns"]
        ],
        drawdown_series=drawdown_series,
        signal_performance=signal_performance[:50],  # Latest 50
        performance_by_symbol=perf_by_symbol,
        performance_by_type=perf_by_type,
        monthly_returns=monthly_returns,
    )


@router.get("/signals")
async def get_signal_performance(
    symbol: Optional[str] = None,
    signal_type: Optional[str] = None,
    executed_only: bool = False,
    limit: int = Query(50, le=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> List[SignalPerformance]:
    """
    Get performance of individual signals with filters.
    """
    query = db.query(TradingSignal).filter(TradingSignal.user_id == current_user.id)

    if symbol:
        query = query.filter(TradingSignal.symbol == symbol)
    if signal_type:
        query = query.filter(TradingSignal.signal_type == signal_type)
    if executed_only:
        query = query.filter(TradingSignal.executed == True)

    signals = query.order_by(TradingSignal.created_at.desc()).limit(limit).all()

    return await _calculate_signal_performance(signals, db)


@router.get("/risk-metrics")
async def get_risk_metrics(
    period: str = Query("3m", description="Period: 1m, 3m, 6m, 1y, all"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> RiskMetrics:
    """
    Get risk metrics for the portfolio.
    """
    end_date = datetime.now()
    period_map = {"1m": 30, "3m": 90, "6m": 180, "1y": 365, "all": 3650}
    start_date = end_date - timedelta(days=period_map.get(period, 90))

    orders = (
        db.query(Order)
        .filter(
            Order.user_id == current_user.id,
            Order.created_at >= start_date,
            Order.status == "filled",
        )
        .order_by(Order.created_at)
        .all()
    )

    equity_data = _calculate_equity_curve(orders, start_date)
    return _calculate_risk_metrics(equity_data["returns"])


@router.get("/by-symbol")
async def get_performance_by_symbol(
    period: str = Query("3m"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Dict[str, Dict[str, float]]:
    """
    Get performance breakdown by symbol.
    """
    end_date = datetime.now()
    period_map = {"1m": 30, "3m": 90, "6m": 180, "1y": 365, "all": 3650}
    start_date = end_date - timedelta(days=period_map.get(period, 90))

    signals = (
        db.query(TradingSignal)
        .filter(
            TradingSignal.user_id == current_user.id,
            TradingSignal.created_at >= start_date,
        )
        .all()
    )

    signal_performance = await _calculate_signal_performance(signals, db)
    return _calculate_performance_by_symbol(signal_performance)


@router.get("/drawdown")
async def get_drawdown_analysis(
    period: str = Query("3m"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    """
    Get detailed drawdown analysis.
    """
    end_date = datetime.now()
    period_map = {"1m": 30, "3m": 90, "6m": 180, "1y": 365, "all": 3650}
    start_date = end_date - timedelta(days=period_map.get(period, 90))

    orders = (
        db.query(Order)
        .filter(
            Order.user_id == current_user.id,
            Order.created_at >= start_date,
            Order.status == "filled",
        )
        .order_by(Order.created_at)
        .all()
    )

    equity_data = _calculate_equity_curve(orders, start_date)
    drawdown_series = _calculate_drawdown_series(equity_data["equity"])

    # Find worst drawdowns
    if drawdown_series:
        sorted_dd = sorted(drawdown_series, key=lambda x: x.value)
        worst_drawdowns = sorted_dd[:5]
    else:
        worst_drawdowns = []

    return {
        "current_drawdown": drawdown_series[-1].value if drawdown_series else 0,
        "max_drawdown": min(d.value for d in drawdown_series) if drawdown_series else 0,
        "drawdown_series": drawdown_series,
        "worst_drawdowns": worst_drawdowns,
    }


@router.get("/monthly-returns")
async def get_monthly_returns(
    year: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> List[Dict[str, Any]]:
    """
    Get monthly returns breakdown.
    """
    current_year = year or datetime.now().year
    start_date = datetime(current_year, 1, 1)
    end_date = datetime(current_year, 12, 31)

    orders = (
        db.query(Order)
        .filter(
            Order.user_id == current_user.id,
            Order.created_at >= start_date,
            Order.created_at <= end_date,
            Order.status == "filled",
        )
        .order_by(Order.created_at)
        .all()
    )

    equity_data = _calculate_equity_curve(orders, start_date)
    return _calculate_monthly_returns(equity_data["equity"])


# Helper Functions
async def _calculate_signal_performance(
    signals: List[TradingSignal], db: Session
) -> List[SignalPerformance]:
    """Calculate performance for each signal."""
    results = []

    for signal in signals:
        # Get current price
        current_price_record = (
            db.query(StockPrice)
            .filter(StockPrice.symbol == signal.symbol)
            .order_by(StockPrice.date.desc())
            .first()
        )

        current_price = float(current_price_record.close) if current_price_record else signal.price
        signal_price = float(signal.price)

        # Calculate P&L based on signal type
        if signal.signal_type == "buy":
            pnl = current_price - signal_price
            pnl_pct = ((current_price - signal_price) / signal_price) * 100
        else:  # sell
            pnl = signal_price - current_price
            pnl_pct = ((signal_price - current_price) / signal_price) * 100

        results.append(
            SignalPerformance(
                signal_id=signal.id,
                symbol=signal.symbol,
                signal_type=signal.signal_type,
                signal_date=signal.created_at.isoformat(),
                signal_price=signal_price,
                current_price=current_price,
                pnl=pnl,
                pnl_pct=pnl_pct,
                executed=signal.executed,
                strength=float(signal.strength) if signal.strength else 0.0,
            )
        )

    return results


def _calculate_summary(
    signals: List[TradingSignal], performance: List[SignalPerformance]
) -> PerformanceSummary:
    """Calculate performance summary."""
    if not signals:
        return PerformanceSummary(
            total_signals=0,
            executed_signals=0,
            buy_signals=0,
            sell_signals=0,
            win_rate=0,
            avg_return=0,
            total_pnl=0,
            best_signal=None,
            worst_signal=None,
        )

    total = len(signals)
    executed = sum(1 for s in signals if s.executed)
    buy_count = sum(1 for s in signals if s.signal_type == "buy")
    sell_count = sum(1 for s in signals if s.signal_type == "sell")

    wins = sum(1 for p in performance if p.pnl > 0)
    win_rate = (wins / len(performance)) * 100 if performance else 0

    avg_return = np.mean([p.pnl_pct for p in performance]) if performance else 0
    total_pnl = sum(p.pnl for p in performance)

    best = max(performance, key=lambda x: x.pnl_pct) if performance else None
    worst = min(performance, key=lambda x: x.pnl_pct) if performance else None

    return PerformanceSummary(
        total_signals=total,
        executed_signals=executed,
        buy_signals=buy_count,
        sell_signals=sell_count,
        win_rate=win_rate,
        avg_return=avg_return,
        total_pnl=total_pnl,
        best_signal=best.dict() if best else None,
        worst_signal=worst.dict() if worst else None,
    )


def _calculate_equity_curve(
    orders: List[Order], start_date: datetime
) -> Dict[str, List]:
    """Calculate equity curve from orders."""
    if not orders:
        return {"equity": [], "returns": []}

    # Build daily equity from orders
    initial_capital = 10_000_000  # Default
    equity = initial_capital
    equity_points = [(start_date, equity)]
    returns_points = []

    positions = {}  # symbol -> (quantity, avg_price)

    for order in orders:
        symbol = order.symbol
        quantity = order.quantity
        price = float(order.price)

        if order.side == "buy":
            if symbol in positions:
                old_qty, old_price = positions[symbol]
                new_qty = old_qty + quantity
                avg_price = ((old_qty * old_price) + (quantity * price)) / new_qty
                positions[symbol] = (new_qty, avg_price)
            else:
                positions[symbol] = (quantity, price)
            equity -= quantity * price
        else:  # sell
            if symbol in positions:
                old_qty, avg_price = positions[symbol]
                sell_qty = min(quantity, old_qty)
                pnl = (price - avg_price) * sell_qty
                equity += sell_qty * price

                if old_qty - sell_qty > 0:
                    positions[symbol] = (old_qty - sell_qty, avg_price)
                else:
                    del positions[symbol]

        # Calculate total portfolio value
        portfolio_value = equity
        for sym, (qty, avg_p) in positions.items():
            portfolio_value += qty * avg_p  # Simplified: use avg price

        equity_points.append((order.created_at, portfolio_value))

        # Calculate daily return
        if len(equity_points) > 1:
            prev_value = equity_points[-2][1]
            if prev_value > 0:
                daily_return = ((portfolio_value - prev_value) / prev_value) * 100
                returns_points.append((order.created_at, daily_return))

    return {"equity": equity_points, "returns": returns_points}


def _calculate_risk_metrics(returns: List[tuple]) -> RiskMetrics:
    """Calculate risk metrics from returns."""
    if not returns or len(returns) < 2:
        return RiskMetrics(
            sharpe_ratio=0,
            sortino_ratio=0,
            max_drawdown=0,
            max_drawdown_duration=0,
            volatility=0,
            var_95=0,
            calmar_ratio=0,
        )

    returns_values = [r[1] for r in returns]
    returns_array = np.array(returns_values)

    # Volatility (annualized)
    volatility = np.std(returns_array) * np.sqrt(252)

    # Risk-free rate (annualized, in %)
    risk_free = 3.5 / 252  # Daily risk-free rate

    # Sharpe Ratio
    excess_returns = returns_array - risk_free
    sharpe = (np.mean(excess_returns) / np.std(returns_array)) * np.sqrt(252) if np.std(returns_array) > 0 else 0

    # Sortino Ratio
    negative_returns = returns_array[returns_array < 0]
    downside_std = np.std(negative_returns) if len(negative_returns) > 0 else 0
    sortino = (np.mean(excess_returns) / downside_std) * np.sqrt(252) if downside_std > 0 else 0

    # VaR 95%
    var_95 = np.percentile(returns_array, 5)

    # Max Drawdown (simplified)
    cumulative = np.cumprod(1 + returns_array / 100)
    running_max = np.maximum.accumulate(cumulative)
    drawdowns = (cumulative - running_max) / running_max * 100
    max_dd = np.min(drawdowns) if len(drawdowns) > 0 else 0

    # Calmar Ratio
    annualized_return = np.mean(returns_array) * 252
    calmar = annualized_return / abs(max_dd) if max_dd != 0 else 0

    return RiskMetrics(
        sharpe_ratio=round(sharpe, 4),
        sortino_ratio=round(sortino, 4),
        max_drawdown=round(max_dd, 2),
        max_drawdown_duration=0,  # Would need more complex calculation
        volatility=round(volatility, 2),
        var_95=round(var_95, 2),
        calmar_ratio=round(calmar, 4),
    )


def _calculate_drawdown_series(equity: List[tuple]) -> List[TimeSeriesPoint]:
    """Calculate drawdown time series."""
    if not equity:
        return []

    series = []
    peak = equity[0][1]

    for date, value in equity:
        if value > peak:
            peak = value
        dd = ((value - peak) / peak) * 100 if peak > 0 else 0
        series.append(TimeSeriesPoint(date=date.isoformat(), value=round(dd, 2)))

    return series


def _calculate_performance_by_symbol(
    performance: List[SignalPerformance],
) -> Dict[str, Dict[str, float]]:
    """Calculate performance grouped by symbol."""
    by_symbol = {}

    for p in performance:
        if p.symbol not in by_symbol:
            by_symbol[p.symbol] = {"signals": 0, "wins": 0, "total_pnl": 0, "avg_return": []}

        by_symbol[p.symbol]["signals"] += 1
        if p.pnl > 0:
            by_symbol[p.symbol]["wins"] += 1
        by_symbol[p.symbol]["total_pnl"] += p.pnl
        by_symbol[p.symbol]["avg_return"].append(p.pnl_pct)

    result = {}
    for symbol, data in by_symbol.items():
        result[symbol] = {
            "signals": data["signals"],
            "win_rate": (data["wins"] / data["signals"]) * 100 if data["signals"] > 0 else 0,
            "total_pnl": round(data["total_pnl"], 0),
            "avg_return": round(np.mean(data["avg_return"]), 2) if data["avg_return"] else 0,
        }

    return result


def _calculate_performance_by_type(
    performance: List[SignalPerformance],
) -> Dict[str, Dict[str, float]]:
    """Calculate performance grouped by signal type."""
    by_type = {"buy": [], "sell": []}

    for p in performance:
        if p.signal_type in by_type:
            by_type[p.signal_type].append(p)

    result = {}
    for signal_type, signals in by_type.items():
        if signals:
            wins = sum(1 for s in signals if s.pnl > 0)
            result[signal_type] = {
                "count": len(signals),
                "win_rate": (wins / len(signals)) * 100,
                "avg_return": round(np.mean([s.pnl_pct for s in signals]), 2),
                "total_pnl": round(sum(s.pnl for s in signals), 0),
            }
        else:
            result[signal_type] = {
                "count": 0,
                "win_rate": 0,
                "avg_return": 0,
                "total_pnl": 0,
            }

    return result


def _calculate_monthly_returns(equity: List[tuple]) -> List[Dict[str, Any]]:
    """Calculate monthly returns."""
    if not equity:
        return []

    # Group by month
    monthly = {}
    for date, value in equity:
        key = f"{date.year}-{date.month:02d}"
        if key not in monthly:
            monthly[key] = {"start": value, "end": value}
        monthly[key]["end"] = value

    results = []
    for month, data in sorted(monthly.items()):
        ret = ((data["end"] - data["start"]) / data["start"]) * 100 if data["start"] > 0 else 0
        results.append({
            "month": month,
            "return": round(ret, 2),
            "start_value": round(data["start"], 0),
            "end_value": round(data["end"], 0),
        })

    return results
