"""
Core Backtesting Engine
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple
import logging

import pandas as pd
import numpy as np

from app.services.backtesting.strategy import (
    Strategy,
    StrategyContext,
    Signal,
    SignalType,
    Position,
    Trade,
)
from app.services.backtesting.performance import PerformanceAnalyzer, PerformanceMetrics

logger = logging.getLogger(__name__)


@dataclass
class BacktestConfig:
    """Configuration for backtesting."""
    initial_capital: float = 10_000_000  # 1000만원
    commission_rate: float = 0.00015  # 0.015% (한국 증권사 평균)
    slippage_rate: float = 0.001  # 0.1% slippage
    max_position_size: float = 0.2  # Maximum 20% per position
    max_positions: int = 10  # Maximum concurrent positions
    stop_loss_pct: Optional[float] = None  # Optional stop loss %
    take_profit_pct: Optional[float] = None  # Optional take profit %
    allow_short: bool = False  # Allow short selling
    trade_on_close: bool = True  # Trade on close vs next open


@dataclass
class BacktestState:
    """Current state of the backtest."""
    date: datetime
    cash: float
    positions: Dict[str, Position] = field(default_factory=dict)
    trades: List[Trade] = field(default_factory=list)
    equity_curve: List[Tuple[datetime, float]] = field(default_factory=list)
    signals_history: List[Signal] = field(default_factory=list)

    @property
    def portfolio_value(self) -> float:
        """Calculate total portfolio value."""
        positions_value = sum(
            pos.current_price * pos.quantity for pos in self.positions.values()
        )
        return self.cash + positions_value

    @property
    def num_positions(self) -> int:
        """Number of open positions."""
        return len(self.positions)


@dataclass
class BacktestResult:
    """Complete backtest results."""
    strategy_name: str
    config: BacktestConfig
    start_date: datetime
    end_date: datetime
    initial_capital: float
    final_value: float
    trades: List[Trade]
    equity_curve: pd.DataFrame
    metrics: PerformanceMetrics
    signals: List[Signal]
    errors: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Convert results to dictionary."""
        return {
            "strategy_name": self.strategy_name,
            "start_date": self.start_date.isoformat(),
            "end_date": self.end_date.isoformat(),
            "initial_capital": self.initial_capital,
            "final_value": self.final_value,
            "total_return_pct": ((self.final_value - self.initial_capital) / self.initial_capital) * 100,
            "num_trades": len(self.trades),
            "metrics": self.metrics.to_dict() if self.metrics else {},
            "equity_curve": self.equity_curve.to_dict(orient="records") if self.equity_curve is not None else [],
            "trades": [
                {
                    "symbol": t.symbol,
                    "entry_date": t.entry_date.isoformat(),
                    "entry_price": t.entry_price,
                    "exit_date": t.exit_date.isoformat(),
                    "exit_price": t.exit_price,
                    "quantity": t.quantity,
                    "pnl": t.pnl,
                    "pnl_pct": t.pnl_pct,
                    "holding_days": t.holding_days,
                    "exit_reason": t.exit_reason,
                }
                for t in self.trades
            ],
            "errors": self.errors,
        }


class BacktestEngine:
    """
    Main backtesting engine for evaluating trading strategies.

    Example usage:
        engine = BacktestEngine(config)
        strategy = MACrossoverStrategy(short_period=5, long_period=20)
        result = engine.run(strategy, data, start_date, end_date)
    """

    def __init__(self, config: Optional[BacktestConfig] = None):
        self.config = config or BacktestConfig()
        self.state: Optional[BacktestState] = None
        self.analyzer = PerformanceAnalyzer()

    def run(
        self,
        strategy: Strategy,
        data: Dict[str, pd.DataFrame],
        start_date: datetime,
        end_date: datetime,
        symbols: Optional[List[str]] = None,
    ) -> BacktestResult:
        """
        Run a backtest for the given strategy.

        Args:
            strategy: Trading strategy to test
            data: Dictionary of symbol -> OHLCV DataFrame
            start_date: Backtest start date
            end_date: Backtest end date
            symbols: Optional list of symbols to trade (defaults to all in data)

        Returns:
            BacktestResult with performance metrics and trade history
        """
        errors = []
        symbols = symbols or list(data.keys())

        # Validate strategy
        if not strategy.validate_parameters():
            raise ValueError(f"Invalid strategy parameters for {strategy.name}")

        # Initialize state
        self.state = BacktestState(
            date=start_date,
            cash=self.config.initial_capital,
        )

        # Get trading dates from data
        trading_dates = self._get_trading_dates(data, start_date, end_date, symbols)
        if not trading_dates:
            raise ValueError("No trading dates found in the specified range")

        logger.info(
            f"Starting backtest: {strategy.name} from {start_date} to {end_date} "
            f"with {len(trading_dates)} trading days"
        )

        # Main backtest loop
        for current_date in trading_dates:
            self.state.date = current_date

            # Update position prices
            self._update_positions(data, current_date)

            # Check stop loss / take profit
            self._check_exit_conditions(data, current_date)

            # Generate signals for each symbol
            for symbol in symbols:
                if symbol not in data:
                    continue

                try:
                    signal = self._generate_signal(
                        strategy, symbol, data[symbol], current_date
                    )
                    if signal:
                        self._process_signal(signal, data, current_date)
                except Exception as e:
                    error_msg = f"Error processing {symbol} on {current_date}: {str(e)}"
                    logger.warning(error_msg)
                    errors.append(error_msg)

            # Record equity
            self.state.equity_curve.append((current_date, self.state.portfolio_value))

        # Close all remaining positions at end
        self._close_all_positions(data, end_date, "backtest_end")

        # Build equity curve DataFrame
        equity_df = pd.DataFrame(
            self.state.equity_curve,
            columns=["date", "equity"]
        )
        equity_df.set_index("date", inplace=True)

        # Calculate performance metrics
        metrics = self.analyzer.calculate_metrics(
            trades=self.state.trades,
            equity_curve=equity_df,
            initial_capital=self.config.initial_capital,
        )

        return BacktestResult(
            strategy_name=strategy.name,
            config=self.config,
            start_date=start_date,
            end_date=end_date,
            initial_capital=self.config.initial_capital,
            final_value=self.state.portfolio_value,
            trades=self.state.trades,
            equity_curve=equity_df,
            metrics=metrics,
            signals=self.state.signals_history,
            errors=errors,
        )

    def _get_trading_dates(
        self,
        data: Dict[str, pd.DataFrame],
        start_date: datetime,
        end_date: datetime,
        symbols: List[str],
    ) -> List[datetime]:
        """Get sorted list of trading dates from the data."""
        all_dates = set()
        for symbol in symbols:
            if symbol in data:
                df = data[symbol]
                mask = (df.index >= start_date) & (df.index <= end_date)
                all_dates.update(df[mask].index.tolist())
        return sorted(all_dates)

    def _update_positions(
        self,
        data: Dict[str, pd.DataFrame],
        current_date: datetime,
    ) -> None:
        """Update all position prices."""
        for symbol, position in list(self.state.positions.items()):
            if symbol in data:
                df = data[symbol]
                if current_date in df.index:
                    price = df.loc[current_date, "close"]
                    position.update_price(price)

    def _generate_signal(
        self,
        strategy: Strategy,
        symbol: str,
        df: pd.DataFrame,
        current_date: datetime,
    ) -> Optional[Signal]:
        """Generate signal for a symbol."""
        # Get historical data up to current date
        historical = df[df.index <= current_date].copy()

        # Check minimum history requirement
        if len(historical) < strategy.get_required_history():
            return None

        current_price = historical.iloc[-1]["close"]

        context = StrategyContext(
            symbol=symbol,
            current_date=current_date,
            current_price=current_price,
            ohlcv=historical,
            position=self.state.positions.get(symbol),
            cash=self.state.cash,
            portfolio_value=self.state.portfolio_value,
            parameters=strategy.parameters,
        )

        signal = strategy.generate_signal(context)

        if signal and signal.signal_type != SignalType.HOLD:
            self.state.signals_history.append(signal)

        return signal

    def _process_signal(
        self,
        signal: Signal,
        data: Dict[str, pd.DataFrame],
        current_date: datetime,
    ) -> None:
        """Process a trading signal."""
        symbol = signal.symbol

        if signal.signal_type == SignalType.BUY:
            self._open_position(signal, data, current_date)
        elif signal.signal_type == SignalType.SELL:
            self._close_position(signal, data, current_date, signal.reason or "signal")

    def _open_position(
        self,
        signal: Signal,
        data: Dict[str, pd.DataFrame],
        current_date: datetime,
    ) -> None:
        """Open a new position."""
        symbol = signal.symbol

        # Check if already have position
        if symbol in self.state.positions:
            return

        # Check max positions
        if self.state.num_positions >= self.config.max_positions:
            return

        # Calculate position size
        max_position_value = self.state.portfolio_value * self.config.max_position_size
        available_cash = min(self.state.cash, max_position_value)

        # Apply commission and slippage
        price = signal.price * (1 + self.config.slippage_rate)
        commission = available_cash * self.config.commission_rate

        shares = int((available_cash - commission) / price)
        if shares <= 0:
            return

        cost = shares * price + commission

        if cost > self.state.cash:
            return

        # Create position
        position = Position(
            symbol=symbol,
            quantity=shares,
            entry_price=price,
            entry_date=current_date,
            current_price=price,
        )

        self.state.positions[symbol] = position
        self.state.cash -= cost

        logger.debug(
            f"Opened position: {symbol} x{shares} @ {price:.0f} on {current_date}"
        )

    def _close_position(
        self,
        signal: Signal,
        data: Dict[str, pd.DataFrame],
        current_date: datetime,
        exit_reason: str = "signal",
    ) -> None:
        """Close an existing position."""
        symbol = signal.symbol

        if symbol not in self.state.positions:
            return

        position = self.state.positions[symbol]

        # Apply slippage
        exit_price = signal.price * (1 - self.config.slippage_rate)
        proceeds = position.quantity * exit_price
        commission = proceeds * self.config.commission_rate

        # Create trade record
        trade = Trade(
            symbol=symbol,
            entry_date=position.entry_date,
            entry_price=position.entry_price,
            exit_date=current_date,
            exit_price=exit_price,
            quantity=position.quantity,
            side="long",
            commission=commission,
            slippage=abs(signal.price - exit_price) * position.quantity,
            exit_reason=exit_reason,
        )

        self.state.trades.append(trade)
        self.state.cash += proceeds - commission
        del self.state.positions[symbol]

        logger.debug(
            f"Closed position: {symbol} x{position.quantity} @ {exit_price:.0f} "
            f"P&L: {trade.pnl:+.0f} ({trade.pnl_pct:+.2f}%)"
        )

    def _check_exit_conditions(
        self,
        data: Dict[str, pd.DataFrame],
        current_date: datetime,
    ) -> None:
        """Check stop loss and take profit conditions."""
        for symbol, position in list(self.state.positions.items()):
            if symbol not in data:
                continue

            current_price = position.current_price
            pnl_pct = position.unrealized_pnl_pct

            exit_reason = None

            # Check stop loss
            if self.config.stop_loss_pct and pnl_pct <= -self.config.stop_loss_pct:
                exit_reason = "stop_loss"

            # Check take profit
            if self.config.take_profit_pct and pnl_pct >= self.config.take_profit_pct:
                exit_reason = "take_profit"

            if exit_reason:
                signal = Signal(
                    signal_type=SignalType.SELL,
                    symbol=symbol,
                    price=current_price,
                    timestamp=current_date,
                    reason=exit_reason,
                )
                self._close_position(signal, data, current_date, exit_reason)

    def _close_all_positions(
        self,
        data: Dict[str, pd.DataFrame],
        end_date: datetime,
        reason: str = "backtest_end",
    ) -> None:
        """Close all remaining positions at end of backtest."""
        for symbol in list(self.state.positions.keys()):
            position = self.state.positions[symbol]
            signal = Signal(
                signal_type=SignalType.SELL,
                symbol=symbol,
                price=position.current_price,
                timestamp=end_date,
                reason=reason,
            )
            self._close_position(signal, data, end_date, reason)


class MultiStrategyBacktest:
    """Run multiple strategies and compare results."""

    def __init__(self, config: Optional[BacktestConfig] = None):
        self.config = config or BacktestConfig()
        self.engine = BacktestEngine(config)

    def run_comparison(
        self,
        strategies: List[Strategy],
        data: Dict[str, pd.DataFrame],
        start_date: datetime,
        end_date: datetime,
    ) -> Dict[str, BacktestResult]:
        """
        Run multiple strategies on the same data and compare.

        Returns:
            Dictionary of strategy name -> BacktestResult
        """
        results = {}

        for strategy in strategies:
            try:
                result = self.engine.run(strategy, data, start_date, end_date)
                results[strategy.name] = result
            except Exception as e:
                logger.error(f"Error running strategy {strategy.name}: {e}")
                results[strategy.name] = None

        return results

    def get_ranking(
        self,
        results: Dict[str, BacktestResult],
        metric: str = "sharpe_ratio",
    ) -> List[Tuple[str, float]]:
        """
        Rank strategies by a specific metric.

        Args:
            results: Dictionary of backtest results
            metric: Metric to rank by

        Returns:
            List of (strategy_name, metric_value) sorted descending
        """
        rankings = []

        for name, result in results.items():
            if result and result.metrics:
                value = getattr(result.metrics, metric, 0)
                rankings.append((name, value))

        return sorted(rankings, key=lambda x: x[1], reverse=True)
