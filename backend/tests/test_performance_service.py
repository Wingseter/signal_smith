"""Tests for performance analytics service."""

from datetime import datetime, timedelta
from types import SimpleNamespace

import numpy as np

from app.services.performance_service import PerformanceService, _normalize_strength


def _make_signal(symbol="005930", signal_type="buy", is_executed=True, strength=None):
    return SimpleNamespace(
        id=1, symbol=symbol, signal_type=signal_type,
        is_executed=is_executed, strength=strength,
        created_at=datetime(2026, 1, 15),
        target_price=50000,
    )


def _make_perf(symbol="005930", signal_type="buy", pnl=1000, pnl_pct=2.0):
    return {"symbol": symbol, "signal_type": signal_type, "pnl": pnl, "pnl_pct": pnl_pct}


def _make_order(symbol="005930", tx_type="buy", qty=10, price=50000, dt=None):
    return SimpleNamespace(
        symbol=symbol, transaction_type=tx_type,
        filled_quantity=qty, quantity=qty,
        filled_price=price, price=price,
        created_at=dt or datetime(2026, 1, 15),
    )


svc = PerformanceService()


class TestNormalizeStrength:
    def test_decimal_to_percent(self):
        assert _normalize_strength(0.85) == 85.0

    def test_already_percent(self):
        assert _normalize_strength(85.0) == 85.0

    def test_none(self):
        assert _normalize_strength(None) == 0.0

    def test_zero(self):
        assert _normalize_strength(0.0) == 0.0

    def test_boundary_one(self):
        assert _normalize_strength(1.0) == 100.0


class TestCalculateSummary:
    def test_empty(self):
        result = svc.calculate_summary([], [])
        assert result["total_signals"] == 0
        assert result["win_rate"] == 0

    def test_mixed_signals(self):
        signals = [
            _make_signal(signal_type="buy", is_executed=True),
            _make_signal(signal_type="sell", is_executed=False),
            _make_signal(signal_type="buy", is_executed=True),
        ]
        perf = [
            _make_perf(pnl=1000, pnl_pct=2.0),
            _make_perf(pnl=-500, pnl_pct=-1.0),
            _make_perf(pnl=200, pnl_pct=0.4),
        ]
        result = svc.calculate_summary(signals, perf)
        assert result["total_signals"] == 3
        assert result["executed_signals"] == 2
        assert result["buy_signals"] == 2
        assert result["sell_signals"] == 1
        # 2 out of 3 positive pnl
        assert result["win_rate"] == round(2 / 3 * 100, 2)
        assert result["total_pnl"] == 700

    def test_all_winners(self):
        signals = [_make_signal(), _make_signal()]
        perf = [_make_perf(pnl=100, pnl_pct=1.0), _make_perf(pnl=200, pnl_pct=2.0)]
        result = svc.calculate_summary(signals, perf)
        assert result["win_rate"] == 100.0
        assert result["total_pnl"] == 300


class TestCalculateEquityCurve:
    def test_empty(self):
        result = svc.calculate_equity_curve([], datetime.now())
        assert result == {"equity": [], "returns": []}

    def test_buy_then_sell(self):
        t1 = datetime(2026, 1, 10)
        t2 = datetime(2026, 1, 15)
        orders = [
            _make_order(tx_type="buy", qty=10, price=50000, dt=t1),
            _make_order(tx_type="sell", qty=10, price=55000, dt=t2),
        ]
        result = svc.calculate_equity_curve(orders, datetime(2026, 1, 1))
        equity = result["equity"]
        # Initial point + 2 order points
        assert len(equity) == 3
        # After buy: cash = 10M - 500K = 9.5M, position value = 10*50000 = 500K, total = 10M
        assert equity[1][1] == 10_000_000
        # After sell: cash = 9.5M + 550K = 10.05M, no positions, total = 10.05M
        assert equity[2][1] == 10_050_000

    def test_multiple_buys(self):
        t1 = datetime(2026, 1, 10)
        t2 = datetime(2026, 1, 12)
        orders = [
            _make_order(tx_type="buy", qty=10, price=50000, dt=t1),
            _make_order(symbol="035720", tx_type="buy", qty=5, price=100000, dt=t2),
        ]
        result = svc.calculate_equity_curve(orders, datetime(2026, 1, 1))
        assert len(result["equity"]) == 3


class TestCalculateRiskMetrics:
    def test_empty(self):
        result = svc.calculate_risk_metrics([])
        assert result["sharpe_ratio"] == 0
        assert result["var_95"] == 0

    def test_single_return(self):
        result = svc.calculate_risk_metrics([(datetime.now(), 1.0)])
        assert result["sharpe_ratio"] == 0

    def test_known_returns(self):
        dates = [datetime(2026, 1, i) for i in range(1, 11)]
        returns = list(zip(dates, [1.0, -0.5, 0.8, -0.3, 1.2, -0.1, 0.5, -0.4, 0.9, 0.3]))
        result = svc.calculate_risk_metrics(returns)
        # Sharpe should be finite
        assert isinstance(result["sharpe_ratio"], float)
        # VaR95 should be negative (worst 5th percentile)
        assert result["var_95"] < 0
        # Max drawdown should be <= 0
        assert result["max_drawdown"] <= 0


class TestCalculateDrawdownSeries:
    def test_empty(self):
        assert svc.calculate_drawdown_series([]) == []

    def test_monotonic_increase(self):
        equity = [
            (datetime(2026, 1, i), 100 + i * 10)
            for i in range(1, 5)
        ]
        series = svc.calculate_drawdown_series(equity)
        assert all(s["value"] == 0 for s in series)

    def test_peak_then_drop(self):
        equity = [
            (datetime(2026, 1, 1), 100),
            (datetime(2026, 1, 2), 120),  # peak
            (datetime(2026, 1, 3), 108),  # drop
            (datetime(2026, 1, 4), 90),   # deeper drop
        ]
        series = svc.calculate_drawdown_series(equity)
        assert series[0]["value"] == 0  # start
        assert series[1]["value"] == 0  # new peak
        assert series[2]["value"] == -10.0  # (108-120)/120 * 100
        assert series[3]["value"] == -25.0  # (90-120)/120 * 100


class TestCalculateMonthlyReturns:
    def test_empty(self):
        assert svc.calculate_monthly_returns([]) == []

    def test_single_month(self):
        equity = [
            (datetime(2026, 1, 1), 1000),
            (datetime(2026, 1, 15), 1100),
            (datetime(2026, 1, 31), 1050),
        ]
        result = svc.calculate_monthly_returns(equity)
        assert len(result) == 1
        assert result[0]["month"] == "2026-01"
        # (1050 - 1000) / 1000 * 100 = 5.0
        assert result[0]["return"] == 5.0

    def test_cross_month(self):
        equity = [
            (datetime(2026, 1, 1), 1000),
            (datetime(2026, 1, 31), 1100),
            (datetime(2026, 2, 1), 1100),
            (datetime(2026, 2, 28), 1210),
        ]
        result = svc.calculate_monthly_returns(equity)
        assert len(result) == 2
        assert result[0]["month"] == "2026-01"
        assert result[1]["month"] == "2026-02"


class TestCalculatePerformanceBySymbol:
    def test_empty(self):
        assert svc.calculate_performance_by_symbol([]) == {}

    def test_mixed(self):
        perf = [
            _make_perf(symbol="005930", pnl=1000, pnl_pct=2.0),
            _make_perf(symbol="005930", pnl=-500, pnl_pct=-1.0),
            _make_perf(symbol="035720", pnl=300, pnl_pct=0.5),
        ]
        result = svc.calculate_performance_by_symbol(perf)
        assert "005930" in result
        assert "035720" in result
        assert result["005930"]["signals"] == 2
        assert result["005930"]["win_rate"] == 50.0
        assert result["005930"]["total_pnl"] == 500
        assert result["035720"]["signals"] == 1
        assert result["035720"]["win_rate"] == 100.0


class TestCalculatePerformanceByType:
    def test_empty(self):
        result = svc.calculate_performance_by_type([])
        assert result["buy"]["count"] == 0
        assert result["sell"]["count"] == 0

    def test_mixed(self):
        perf = [
            _make_perf(signal_type="buy", pnl=1000, pnl_pct=2.0),
            _make_perf(signal_type="buy", pnl=-500, pnl_pct=-1.0),
            _make_perf(signal_type="sell", pnl=300, pnl_pct=0.5),
        ]
        result = svc.calculate_performance_by_type(perf)
        assert result["buy"]["count"] == 2
        assert result["buy"]["win_rate"] == 50.0
        assert result["sell"]["count"] == 1
        assert result["sell"]["win_rate"] == 100.0
