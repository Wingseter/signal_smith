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
from app.models.stock import StockPrice
from app.models.transaction import TradingSignal, Transaction as Order
from app.models.user import User

import logging
import numpy as np

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


def _normalize_strength(raw_strength: Optional[float]) -> float:
    if raw_strength is None:
        return 0.0
    strength = float(raw_strength)
    # 과거 코드가 0~1 스케일을 저장한 케이스를 보정
    return round(strength * 100, 2) if 0 <= strength <= 1 else round(strength, 2)


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
async def get_performance_dashboard(
    period: str = Query("3m", description="Period: 1m, 3m, 6m, 1y, all"),
    db: Session = Depends(get_sync_db_dep),
    current_user: User = Depends(get_current_user),
) -> PerformanceDashboard:
    start_date = _period_start(period)
    orders = _load_user_orders(db, current_user.id, start_date)

    user_symbols = sorted({o.symbol for o in orders})
    signals = _load_relevant_signals(db, user_symbols, start_date=start_date)

    signal_performance = _calculate_signal_performance(signals, db)
    summary = _calculate_summary(signals, signal_performance)
    equity_data = _calculate_equity_curve(orders, start_date)
    risk_metrics = _calculate_risk_metrics(equity_data["returns"])
    drawdown_series = _calculate_drawdown_series(equity_data["equity"])
    perf_by_symbol = _calculate_performance_by_symbol(signal_performance)
    perf_by_type = _calculate_performance_by_type(signal_performance)
    monthly_returns = _calculate_monthly_returns(equity_data["equity"])

    return PerformanceDashboard(
        summary=summary,
        risk_metrics=risk_metrics,
        equity_curve=[TimeSeriesPoint(date=d.isoformat(), value=v) for d, v in equity_data["equity"]],
        daily_returns=[TimeSeriesPoint(date=d.isoformat(), value=v) for d, v in equity_data["returns"]],
        drawdown_series=drawdown_series,
        signal_performance=signal_performance[:50],
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
    db: Session = Depends(get_sync_db_dep),
    current_user: User = Depends(get_current_user),
) -> List[SignalPerformance]:
    # 사용자 주문 이력이 있는 종목으로 범위를 제한
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
    return _calculate_signal_performance(signals, db)


@router.get("/risk-metrics")
async def get_risk_metrics(
    period: str = Query("3m", description="Period: 1m, 3m, 6m, 1y, all"),
    db: Session = Depends(get_sync_db_dep),
    current_user: User = Depends(get_current_user),
) -> RiskMetrics:
    start_date = _period_start(period)
    orders = _load_user_orders(db, current_user.id, start_date)
    equity_data = _calculate_equity_curve(orders, start_date)
    return _calculate_risk_metrics(equity_data["returns"])


@router.get("/by-symbol")
async def get_performance_by_symbol(
    period: str = Query("3m"),
    db: Session = Depends(get_sync_db_dep),
    current_user: User = Depends(get_current_user),
) -> Dict[str, Dict[str, float]]:
    start_date = _period_start(period)
    orders = _load_user_orders(db, current_user.id, start_date)
    symbols = sorted({o.symbol for o in orders})
    signals = _load_relevant_signals(db, symbols=symbols, start_date=start_date)
    signal_performance = _calculate_signal_performance(signals, db)
    return _calculate_performance_by_symbol(signal_performance)


@router.get("/drawdown")
async def get_drawdown_analysis(
    period: str = Query("3m"),
    db: Session = Depends(get_sync_db_dep),
    current_user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    start_date = _period_start(period)
    orders = _load_user_orders(db, current_user.id, start_date)
    equity_data = _calculate_equity_curve(orders, start_date)
    drawdown_series = _calculate_drawdown_series(equity_data["equity"])

    worst_drawdowns = sorted(drawdown_series, key=lambda p: p.value)[:5] if drawdown_series else []
    return {
        "current_drawdown": drawdown_series[-1].value if drawdown_series else 0,
        "max_drawdown": min(d.value for d in drawdown_series) if drawdown_series else 0,
        "drawdown_series": drawdown_series,
        "worst_drawdowns": worst_drawdowns,
    }


@router.get("/monthly-returns")
async def get_monthly_returns(
    year: Optional[int] = None,
    db: Session = Depends(get_sync_db_dep),
    current_user: User = Depends(get_current_user),
) -> List[Dict[str, Any]]:
    current_year = year or datetime.now().year
    start_date = datetime(current_year, 1, 1)
    end_date = datetime(current_year, 12, 31)
    orders = _load_user_orders(db, current_user.id, start_date, end_date=end_date)
    equity_data = _calculate_equity_curve(orders, start_date)
    return _calculate_monthly_returns(equity_data["equity"])


def _calculate_signal_performance(signals: List[TradingSignal], db: Session) -> List[SignalPerformance]:
    """Calculate performance for each signal."""
    results: List[SignalPerformance] = []
    for signal in signals:
        current_price_record = (
            db.query(StockPrice)
            .filter(StockPrice.symbol == signal.symbol)
            .order_by(StockPrice.date.desc())
            .first()
        )
        current_price = float(current_price_record.close) if current_price_record else 0.0

        reference_record = (
            db.query(StockPrice)
            .filter(
                StockPrice.symbol == signal.symbol,
                StockPrice.date <= signal.created_at,
            )
            .order_by(StockPrice.date.desc())
            .first()
        )
        if reference_record:
            signal_price = float(reference_record.close)
        elif signal.target_price is not None:
            signal_price = float(signal.target_price)
        else:
            signal_price = current_price

        if signal.signal_type == "buy":
            pnl = current_price - signal_price
            pnl_pct = ((current_price - signal_price) / signal_price) * 100 if signal_price > 0 else 0.0
        else:
            pnl = signal_price - current_price
            pnl_pct = ((signal_price - current_price) / signal_price) * 100 if signal_price > 0 else 0.0

        results.append(
            SignalPerformance(
                signal_id=signal.id,
                symbol=signal.symbol,
                signal_type=signal.signal_type,
                signal_date=signal.created_at.isoformat(),
                signal_price=round(signal_price, 2),
                current_price=round(current_price, 2),
                pnl=round(pnl, 2),
                pnl_pct=round(pnl_pct, 2),
                executed=bool(signal.is_executed),
                strength=_normalize_strength(float(signal.strength) if signal.strength is not None else None),
            )
        )
    return results


def _calculate_summary(signals: List[TradingSignal], performance: List[SignalPerformance]) -> PerformanceSummary:
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
    executed = sum(1 for s in signals if s.is_executed)
    buy_count = sum(1 for s in signals if s.signal_type == "buy")
    sell_count = sum(1 for s in signals if s.signal_type == "sell")

    wins = sum(1 for p in performance if p.pnl > 0)
    win_rate = (wins / len(performance)) * 100 if performance else 0
    avg_return = float(np.mean([p.pnl_pct for p in performance])) if performance else 0
    total_pnl = sum(p.pnl for p in performance)

    best = max(performance, key=lambda x: x.pnl_pct) if performance else None
    worst = min(performance, key=lambda x: x.pnl_pct) if performance else None

    return PerformanceSummary(
        total_signals=total,
        executed_signals=executed,
        buy_signals=buy_count,
        sell_signals=sell_count,
        win_rate=round(win_rate, 2),
        avg_return=round(avg_return, 2),
        total_pnl=round(total_pnl, 2),
        best_signal=best.model_dump() if best else None,
        worst_signal=worst.model_dump() if worst else None,
    )


def _calculate_equity_curve(orders: List[Order], start_date: datetime) -> Dict[str, List]:
    if not orders:
        return {"equity": [], "returns": []}

    initial_capital = 10_000_000
    cash = float(initial_capital)
    equity_points: List[tuple] = [(start_date, float(initial_capital))]
    returns_points: List[tuple] = []
    positions: Dict[str, tuple] = {}  # symbol -> (quantity, avg_price)

    for order in orders:
        symbol = order.symbol
        quantity = int(order.filled_quantity or order.quantity or 0)
        price = float(order.filled_price or order.price or 0)
        side = order.transaction_type

        if quantity <= 0:
            continue

        if side == "buy":
            if symbol in positions:
                old_qty, old_price = positions[symbol]
                new_qty = old_qty + quantity
                avg_price = ((old_qty * old_price) + (quantity * price)) / new_qty
                positions[symbol] = (new_qty, avg_price)
            else:
                positions[symbol] = (quantity, price)
            cash -= quantity * price
        else:
            if symbol in positions:
                old_qty, avg_price = positions[symbol]
                sell_qty = min(quantity, old_qty)
                cash += sell_qty * price
                remain_qty = old_qty - sell_qty
                if remain_qty > 0:
                    positions[symbol] = (remain_qty, avg_price)
                else:
                    del positions[symbol]

        portfolio_value = cash + sum(qty * avg_price for qty, avg_price in positions.values())
        equity_points.append((order.created_at, portfolio_value))

        if len(equity_points) > 1:
            prev_value = equity_points[-2][1]
            daily_return = ((portfolio_value - prev_value) / prev_value) * 100 if prev_value > 0 else 0
            returns_points.append((order.created_at, daily_return))

    return {"equity": equity_points, "returns": returns_points}


def _calculate_risk_metrics(returns: List[tuple]) -> RiskMetrics:
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

    returns_array = np.array([r[1] for r in returns], dtype=float)
    volatility = float(np.std(returns_array) * np.sqrt(252))
    risk_free = 3.5 / 252
    excess = returns_array - risk_free

    std = float(np.std(returns_array))
    sharpe = (float(np.mean(excess)) / std) * np.sqrt(252) if std > 0 else 0

    downside = returns_array[returns_array < 0]
    downside_std = float(np.std(downside)) if len(downside) else 0
    sortino = (float(np.mean(excess)) / downside_std) * np.sqrt(252) if downside_std > 0 else 0

    var_95 = float(np.percentile(returns_array, 5))
    cumulative = np.cumprod(1 + returns_array / 100)
    running_max = np.maximum.accumulate(cumulative)
    drawdowns = (cumulative - running_max) / running_max * 100
    max_dd = float(np.min(drawdowns)) if len(drawdowns) else 0
    annualized_return = float(np.mean(returns_array) * 252)
    calmar = annualized_return / abs(max_dd) if max_dd != 0 else 0

    return RiskMetrics(
        sharpe_ratio=round(sharpe, 4),
        sortino_ratio=round(sortino, 4),
        max_drawdown=round(max_dd, 2),
        max_drawdown_duration=0,
        volatility=round(volatility, 2),
        var_95=round(var_95, 2),
        calmar_ratio=round(calmar, 4),
    )


def _calculate_drawdown_series(equity: List[tuple]) -> List[TimeSeriesPoint]:
    if not equity:
        return []

    series: List[TimeSeriesPoint] = []
    peak = equity[0][1]
    for date, value in equity:
        if value > peak:
            peak = value
        dd = ((value - peak) / peak) * 100 if peak > 0 else 0
        series.append(TimeSeriesPoint(date=date.isoformat(), value=round(dd, 2)))
    return series


def _calculate_performance_by_symbol(performance: List[SignalPerformance]) -> Dict[str, Dict[str, float]]:
    by_symbol: Dict[str, Dict[str, Any]] = {}
    for p in performance:
        if p.symbol not in by_symbol:
            by_symbol[p.symbol] = {"signals": 0, "wins": 0, "total_pnl": 0.0, "returns": []}
        by_symbol[p.symbol]["signals"] += 1
        if p.pnl > 0:
            by_symbol[p.symbol]["wins"] += 1
        by_symbol[p.symbol]["total_pnl"] += p.pnl
        by_symbol[p.symbol]["returns"].append(p.pnl_pct)

    result: Dict[str, Dict[str, float]] = {}
    for symbol, data in by_symbol.items():
        signals = int(data["signals"])
        win_rate = (data["wins"] / signals) * 100 if signals else 0
        avg_return = float(np.mean(data["returns"])) if data["returns"] else 0
        result[symbol] = {
            "signals": float(signals),
            "win_rate": round(win_rate, 2),
            "total_pnl": round(float(data["total_pnl"]), 2),
            "avg_return": round(avg_return, 2),
        }
    return result


def _calculate_performance_by_type(performance: List[SignalPerformance]) -> Dict[str, Dict[str, float]]:
    grouped: Dict[str, List[SignalPerformance]] = {"buy": [], "sell": []}
    for p in performance:
        if p.signal_type in grouped:
            grouped[p.signal_type].append(p)

    result: Dict[str, Dict[str, float]] = {}
    for signal_type, signals in grouped.items():
        if not signals:
            result[signal_type] = {"count": 0, "win_rate": 0, "avg_return": 0, "total_pnl": 0}
            continue

        wins = sum(1 for s in signals if s.pnl > 0)
        avg_return = float(np.mean([s.pnl_pct for s in signals]))
        total_pnl = sum(s.pnl for s in signals)
        result[signal_type] = {
            "count": float(len(signals)),
            "win_rate": round((wins / len(signals)) * 100, 2),
            "avg_return": round(avg_return, 2),
            "total_pnl": round(total_pnl, 2),
        }
    return result


def _calculate_monthly_returns(equity: List[tuple]) -> List[Dict[str, Any]]:
    if not equity:
        return []

    monthly: Dict[str, Dict[str, float]] = {}
    for date, value in equity:
        key = f"{date.year}-{date.month:02d}"
        if key not in monthly:
            monthly[key] = {"start": float(value), "end": float(value)}
        monthly[key]["end"] = float(value)

    results: List[Dict[str, Any]] = []
    for month, data in sorted(monthly.items()):
        start_value = data["start"]
        end_value = data["end"]
        ret = ((end_value - start_value) / start_value) * 100 if start_value > 0 else 0
        results.append(
            {
                "month": month,
                "return": round(ret, 2),
                "start_value": round(start_value, 2),
                "end_value": round(end_value, 2),
            }
        )
    return results
