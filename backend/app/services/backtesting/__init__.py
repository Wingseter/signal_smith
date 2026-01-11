"""
Backtesting Engine for Signal Smith

A comprehensive backtesting system for evaluating trading strategies
using historical Korean stock market data.
"""

from app.services.backtesting.engine import BacktestEngine
from app.services.backtesting.strategy import Strategy, StrategyContext, Signal, SignalType
from app.services.backtesting.performance import PerformanceAnalyzer, PerformanceMetrics
from app.services.backtesting.strategies import (
    MACrossoverStrategy,
    RSIStrategy,
    BollingerBandStrategy,
    MACDStrategy,
)

__all__ = [
    "BacktestEngine",
    "Strategy",
    "StrategyContext",
    "Signal",
    "SignalType",
    "PerformanceAnalyzer",
    "PerformanceMetrics",
    "MACrossoverStrategy",
    "RSIStrategy",
    "BollingerBandStrategy",
    "MACDStrategy",
]
