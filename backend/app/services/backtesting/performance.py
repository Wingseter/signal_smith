"""
Performance Analysis Module for Backtesting
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd

from app.services.backtesting.strategy import Trade


@dataclass
class PerformanceMetrics:
    """Complete set of performance metrics."""
    # Returns
    total_return: float = 0.0
    total_return_pct: float = 0.0
    annualized_return: float = 0.0
    benchmark_return: float = 0.0
    alpha: float = 0.0
    beta: float = 0.0

    # Risk
    volatility: float = 0.0
    annualized_volatility: float = 0.0
    max_drawdown: float = 0.0
    max_drawdown_duration: int = 0  # days
    var_95: float = 0.0  # Value at Risk 95%
    cvar_95: float = 0.0  # Conditional VaR 95%

    # Risk-adjusted
    sharpe_ratio: float = 0.0
    sortino_ratio: float = 0.0
    calmar_ratio: float = 0.0
    information_ratio: float = 0.0

    # Trading
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    win_rate: float = 0.0
    avg_win: float = 0.0
    avg_loss: float = 0.0
    profit_factor: float = 0.0
    avg_trade_pnl: float = 0.0
    avg_holding_days: float = 0.0
    max_consecutive_wins: int = 0
    max_consecutive_losses: int = 0

    # Exposure
    avg_exposure: float = 0.0
    time_in_market: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        """Convert metrics to dictionary."""
        return {
            "returns": {
                "total_return": round(self.total_return, 0),
                "total_return_pct": round(self.total_return_pct, 2),
                "annualized_return": round(self.annualized_return, 2),
                "benchmark_return": round(self.benchmark_return, 2),
                "alpha": round(self.alpha, 4),
                "beta": round(self.beta, 4),
            },
            "risk": {
                "volatility": round(self.volatility, 4),
                "annualized_volatility": round(self.annualized_volatility, 2),
                "max_drawdown": round(self.max_drawdown, 2),
                "max_drawdown_duration": self.max_drawdown_duration,
                "var_95": round(self.var_95, 2),
                "cvar_95": round(self.cvar_95, 2),
            },
            "risk_adjusted": {
                "sharpe_ratio": round(self.sharpe_ratio, 4),
                "sortino_ratio": round(self.sortino_ratio, 4),
                "calmar_ratio": round(self.calmar_ratio, 4),
                "information_ratio": round(self.information_ratio, 4),
            },
            "trading": {
                "total_trades": self.total_trades,
                "winning_trades": self.winning_trades,
                "losing_trades": self.losing_trades,
                "win_rate": round(self.win_rate, 2),
                "avg_win": round(self.avg_win, 0),
                "avg_loss": round(self.avg_loss, 0),
                "profit_factor": round(self.profit_factor, 4),
                "avg_trade_pnl": round(self.avg_trade_pnl, 0),
                "avg_holding_days": round(self.avg_holding_days, 1),
                "max_consecutive_wins": self.max_consecutive_wins,
                "max_consecutive_losses": self.max_consecutive_losses,
            },
            "exposure": {
                "avg_exposure": round(self.avg_exposure, 2),
                "time_in_market": round(self.time_in_market, 2),
            },
        }


class PerformanceAnalyzer:
    """Analyze trading performance and calculate metrics."""

    TRADING_DAYS_PER_YEAR = 252
    RISK_FREE_RATE = 0.035  # 3.5% (한국 기준금리 기준)

    def calculate_metrics(
        self,
        trades: List[Trade],
        equity_curve: pd.DataFrame,
        initial_capital: float,
        benchmark_returns: Optional[pd.Series] = None,
    ) -> PerformanceMetrics:
        """
        Calculate comprehensive performance metrics.

        Args:
            trades: List of completed trades
            equity_curve: DataFrame with 'equity' column indexed by date
            initial_capital: Starting capital
            benchmark_returns: Optional benchmark daily returns for comparison

        Returns:
            PerformanceMetrics with all calculated values
        """
        metrics = PerformanceMetrics()

        if equity_curve.empty:
            return metrics

        # Calculate returns
        returns = equity_curve["equity"].pct_change().dropna()

        # Basic return metrics
        final_value = equity_curve["equity"].iloc[-1]
        metrics.total_return = final_value - initial_capital
        metrics.total_return_pct = (metrics.total_return / initial_capital) * 100

        # Annualized return
        days = (equity_curve.index[-1] - equity_curve.index[0]).days
        if days > 0:
            years = days / 365
            metrics.annualized_return = (
                ((final_value / initial_capital) ** (1 / years)) - 1
            ) * 100 if years > 0 else 0

        # Volatility
        if len(returns) > 1:
            metrics.volatility = returns.std()
            metrics.annualized_volatility = (
                metrics.volatility * np.sqrt(self.TRADING_DAYS_PER_YEAR) * 100
            )

        # Sharpe Ratio
        if metrics.volatility > 0:
            excess_return = returns.mean() - (self.RISK_FREE_RATE / self.TRADING_DAYS_PER_YEAR)
            metrics.sharpe_ratio = (
                excess_return / metrics.volatility * np.sqrt(self.TRADING_DAYS_PER_YEAR)
            )

        # Sortino Ratio (only downside volatility)
        negative_returns = returns[returns < 0]
        if len(negative_returns) > 0:
            downside_std = negative_returns.std()
            if downside_std > 0:
                excess_return = returns.mean() - (self.RISK_FREE_RATE / self.TRADING_DAYS_PER_YEAR)
                metrics.sortino_ratio = (
                    excess_return / downside_std * np.sqrt(self.TRADING_DAYS_PER_YEAR)
                )

        # Maximum Drawdown
        metrics.max_drawdown, metrics.max_drawdown_duration = self._calculate_max_drawdown(
            equity_curve["equity"]
        )

        # Calmar Ratio
        if metrics.max_drawdown != 0:
            metrics.calmar_ratio = metrics.annualized_return / abs(metrics.max_drawdown)

        # VaR and CVaR
        if len(returns) > 0:
            metrics.var_95 = np.percentile(returns, 5) * 100
            tail_returns = returns[returns <= np.percentile(returns, 5)]
            if len(tail_returns) > 0:
                metrics.cvar_95 = tail_returns.mean() * 100

        # Benchmark comparison
        if benchmark_returns is not None and len(benchmark_returns) > 0:
            aligned = returns.align(benchmark_returns, join="inner")
            if len(aligned[0]) > 0:
                strategy_returns, bench_returns = aligned
                metrics.benchmark_return = (
                    (1 + bench_returns).prod() - 1
                ) * 100

                # Alpha and Beta
                covariance = np.cov(strategy_returns, bench_returns)
                if covariance.shape == (2, 2) and covariance[1, 1] != 0:
                    metrics.beta = covariance[0, 1] / covariance[1, 1]
                    metrics.alpha = (
                        strategy_returns.mean() - metrics.beta * bench_returns.mean()
                    ) * self.TRADING_DAYS_PER_YEAR * 100

                # Information Ratio
                tracking_error = (strategy_returns - bench_returns).std()
                if tracking_error > 0:
                    excess = (strategy_returns - bench_returns).mean()
                    metrics.information_ratio = (
                        excess / tracking_error * np.sqrt(self.TRADING_DAYS_PER_YEAR)
                    )

        # Trade statistics
        self._calculate_trade_metrics(trades, metrics)

        return metrics

    def _calculate_max_drawdown(
        self, equity: pd.Series
    ) -> tuple[float, int]:
        """Calculate maximum drawdown and its duration."""
        if len(equity) == 0:
            return 0.0, 0

        # Calculate running maximum
        running_max = equity.expanding().max()

        # Calculate drawdown
        drawdown = (equity - running_max) / running_max * 100

        # Find maximum drawdown
        max_dd = drawdown.min()

        # Calculate duration
        max_dd_duration = 0
        current_duration = 0
        peak_idx = 0

        for i, (eq, peak) in enumerate(zip(equity, running_max)):
            if eq >= peak:
                peak_idx = i
                max_dd_duration = max(max_dd_duration, current_duration)
                current_duration = 0
            else:
                current_duration = i - peak_idx

        max_dd_duration = max(max_dd_duration, current_duration)

        return max_dd, max_dd_duration

    def _calculate_trade_metrics(
        self, trades: List[Trade], metrics: PerformanceMetrics
    ) -> None:
        """Calculate trade-related metrics."""
        if not trades:
            return

        metrics.total_trades = len(trades)

        # Win/Loss analysis
        wins = [t for t in trades if t.pnl > 0]
        losses = [t for t in trades if t.pnl < 0]

        metrics.winning_trades = len(wins)
        metrics.losing_trades = len(losses)

        if metrics.total_trades > 0:
            metrics.win_rate = (metrics.winning_trades / metrics.total_trades) * 100

        if wins:
            metrics.avg_win = np.mean([t.pnl for t in wins])

        if losses:
            metrics.avg_loss = np.mean([t.pnl for t in losses])

        # Profit Factor
        gross_profit = sum(t.pnl for t in wins) if wins else 0
        gross_loss = abs(sum(t.pnl for t in losses)) if losses else 0

        if gross_loss > 0:
            metrics.profit_factor = gross_profit / gross_loss

        # Average trade metrics
        metrics.avg_trade_pnl = np.mean([t.pnl for t in trades])
        metrics.avg_holding_days = np.mean([t.holding_days for t in trades])

        # Consecutive wins/losses
        metrics.max_consecutive_wins, metrics.max_consecutive_losses = (
            self._calculate_consecutive_streaks(trades)
        )

    def _calculate_consecutive_streaks(
        self, trades: List[Trade]
    ) -> tuple[int, int]:
        """Calculate maximum consecutive wins and losses."""
        if not trades:
            return 0, 0

        max_wins = 0
        max_losses = 0
        current_wins = 0
        current_losses = 0

        for trade in trades:
            if trade.pnl > 0:
                current_wins += 1
                current_losses = 0
                max_wins = max(max_wins, current_wins)
            elif trade.pnl < 0:
                current_losses += 1
                current_wins = 0
                max_losses = max(max_losses, current_losses)
            else:
                current_wins = 0
                current_losses = 0

        return max_wins, max_losses

    def generate_report(
        self, metrics: PerformanceMetrics, strategy_name: str
    ) -> str:
        """Generate a text-based performance report."""
        report = f"""
═══════════════════════════════════════════════════════════════
                    백테스팅 성과 리포트
                    전략: {strategy_name}
═══════════════════════════════════════════════════════════════

📈 수익률 지표
───────────────────────────────────────────────────────────────
  총 수익금:          {metrics.total_return:>15,.0f}원
  총 수익률:          {metrics.total_return_pct:>15.2f}%
  연환산 수익률:      {metrics.annualized_return:>15.2f}%
  벤치마크 수익률:    {metrics.benchmark_return:>15.2f}%

📊 리스크 지표
───────────────────────────────────────────────────────────────
  연환산 변동성:      {metrics.annualized_volatility:>15.2f}%
  최대 낙폭(MDD):     {metrics.max_drawdown:>15.2f}%
  MDD 기간:           {metrics.max_drawdown_duration:>15}일
  VaR (95%):          {metrics.var_95:>15.2f}%
  CVaR (95%):         {metrics.cvar_95:>15.2f}%

⚖️ 위험조정 수익률
───────────────────────────────────────────────────────────────
  샤프 비율:          {metrics.sharpe_ratio:>15.4f}
  소르티노 비율:      {metrics.sortino_ratio:>15.4f}
  칼마 비율:          {metrics.calmar_ratio:>15.4f}
  정보 비율:          {metrics.information_ratio:>15.4f}

💹 매매 통계
───────────────────────────────────────────────────────────────
  총 거래 수:         {metrics.total_trades:>15}회
  승률:               {metrics.win_rate:>15.2f}%
  승리 거래:          {metrics.winning_trades:>15}회
  손실 거래:          {metrics.losing_trades:>15}회
  평균 이익:          {metrics.avg_win:>15,.0f}원
  평균 손실:          {metrics.avg_loss:>15,.0f}원
  손익비:             {metrics.profit_factor:>15.4f}
  평균 보유일:        {metrics.avg_holding_days:>15.1f}일
  최대 연속 승리:     {metrics.max_consecutive_wins:>15}회
  최대 연속 손실:     {metrics.max_consecutive_losses:>15}회

═══════════════════════════════════════════════════════════════
"""
        return report
