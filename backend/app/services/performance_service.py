"""
Performance analytics service.

Extracted from routes/performance.py — pure calculation logic
that doesn't depend on FastAPI request context.
"""

from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

import logging
import numpy as np

from sqlalchemy.orm import Session

from app.models.stock import StockPrice
from app.models.transaction import TradingSignal, Transaction as Order

logger = logging.getLogger(__name__)


def _normalize_strength(raw_strength: Optional[float]) -> float:
    if raw_strength is None:
        return 0.0
    strength = float(raw_strength)
    return round(strength * 100, 2) if 0 <= strength <= 1 else round(strength, 2)


class PerformanceService:
    """Portfolio performance calculation service."""

    def calculate_signal_performance(
        self, signals: List[TradingSignal], db: Session
    ) -> List[dict]:
        """Calculate performance for each signal.

        Returns list of dicts matching SignalPerformance schema.
        """
        results: List[dict] = []
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

            results.append({
                "signal_id": signal.id,
                "symbol": signal.symbol,
                "signal_type": signal.signal_type,
                "signal_date": signal.created_at.isoformat(),
                "signal_price": round(signal_price, 2),
                "current_price": round(current_price, 2),
                "pnl": round(pnl, 2),
                "pnl_pct": round(pnl_pct, 2),
                "executed": bool(signal.is_executed),
                "strength": _normalize_strength(float(signal.strength) if signal.strength is not None else None),
            })
        return results

    def calculate_summary(
        self, signals: List[TradingSignal], performance: List[dict]
    ) -> dict:
        """Calculate overall performance summary."""
        if not signals:
            return {
                "total_signals": 0,
                "executed_signals": 0,
                "buy_signals": 0,
                "sell_signals": 0,
                "win_rate": 0,
                "avg_return": 0,
                "total_pnl": 0,
                "best_signal": None,
                "worst_signal": None,
            }

        total = len(signals)
        executed = sum(1 for s in signals if s.is_executed)
        buy_count = sum(1 for s in signals if s.signal_type == "buy")
        sell_count = sum(1 for s in signals if s.signal_type == "sell")

        wins = sum(1 for p in performance if p["pnl"] > 0)
        win_rate = (wins / len(performance)) * 100 if performance else 0
        avg_return = float(np.mean([p["pnl_pct"] for p in performance])) if performance else 0
        total_pnl = sum(p["pnl"] for p in performance)

        best = max(performance, key=lambda x: x["pnl_pct"]) if performance else None
        worst = min(performance, key=lambda x: x["pnl_pct"]) if performance else None

        return {
            "total_signals": total,
            "executed_signals": executed,
            "buy_signals": buy_count,
            "sell_signals": sell_count,
            "win_rate": round(win_rate, 2),
            "avg_return": round(avg_return, 2),
            "total_pnl": round(total_pnl, 2),
            "best_signal": best,
            "worst_signal": worst,
        }

    def calculate_equity_curve(
        self, orders: List[Order], start_date: datetime
    ) -> Dict[str, List]:
        """Calculate equity curve from order history."""
        if not orders:
            return {"equity": [], "returns": []}

        initial_capital = 10_000_000
        cash = float(initial_capital)
        equity_points: List[Tuple[datetime, float]] = [(start_date, float(initial_capital))]
        returns_points: List[Tuple[datetime, float]] = []
        positions: Dict[str, Tuple[int, float]] = {}

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

    def calculate_risk_metrics(self, returns: List[tuple]) -> dict:
        """Calculate risk metrics from returns series."""
        if not returns or len(returns) < 2:
            return {
                "sharpe_ratio": 0,
                "sortino_ratio": 0,
                "max_drawdown": 0,
                "max_drawdown_duration": 0,
                "volatility": 0,
                "var_95": 0,
                "calmar_ratio": 0,
            }

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

        return {
            "sharpe_ratio": round(sharpe, 4),
            "sortino_ratio": round(sortino, 4),
            "max_drawdown": round(max_dd, 2),
            "max_drawdown_duration": 0,
            "volatility": round(volatility, 2),
            "var_95": round(var_95, 2),
            "calmar_ratio": round(calmar, 4),
        }

    def calculate_drawdown_series(self, equity: List[tuple]) -> List[dict]:
        """Calculate drawdown series from equity curve."""
        if not equity:
            return []

        series: List[dict] = []
        peak = equity[0][1]
        for date, value in equity:
            if value > peak:
                peak = value
            dd = ((value - peak) / peak) * 100 if peak > 0 else 0
            series.append({"date": date.isoformat(), "value": round(dd, 2)})
        return series

    def calculate_performance_by_symbol(
        self, performance: List[dict]
    ) -> Dict[str, Dict[str, float]]:
        """Group performance metrics by symbol."""
        by_symbol: Dict[str, Dict[str, Any]] = {}
        for p in performance:
            if p["symbol"] not in by_symbol:
                by_symbol[p["symbol"]] = {"signals": 0, "wins": 0, "total_pnl": 0.0, "returns": []}
            by_symbol[p["symbol"]]["signals"] += 1
            if p["pnl"] > 0:
                by_symbol[p["symbol"]]["wins"] += 1
            by_symbol[p["symbol"]]["total_pnl"] += p["pnl"]
            by_symbol[p["symbol"]]["returns"].append(p["pnl_pct"])

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

    def calculate_performance_by_type(
        self, performance: List[dict]
    ) -> Dict[str, Dict[str, float]]:
        """Group performance metrics by signal type."""
        grouped: Dict[str, List[dict]] = {"buy": [], "sell": []}
        for p in performance:
            if p["signal_type"] in grouped:
                grouped[p["signal_type"]].append(p)

        result: Dict[str, Dict[str, float]] = {}
        for signal_type, signals in grouped.items():
            if not signals:
                result[signal_type] = {"count": 0, "win_rate": 0, "avg_return": 0, "total_pnl": 0}
                continue

            wins = sum(1 for s in signals if s["pnl"] > 0)
            avg_return = float(np.mean([s["pnl_pct"] for s in signals]))
            total_pnl = sum(s["pnl"] for s in signals)
            result[signal_type] = {
                "count": float(len(signals)),
                "win_rate": round((wins / len(signals)) * 100, 2),
                "avg_return": round(avg_return, 2),
                "total_pnl": round(total_pnl, 2),
            }
        return result

    def calculate_monthly_returns(self, equity: List[tuple]) -> List[Dict[str, Any]]:
        """Calculate monthly returns from equity curve."""
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
            results.append({
                "month": month,
                "return": round(ret, 2),
                "start_value": round(start_value, 2),
                "end_value": round(end_value, 2),
            })
        return results


performance_service = PerformanceService()
