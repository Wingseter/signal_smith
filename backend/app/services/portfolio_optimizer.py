"""
Portfolio Optimization Engine
리스크 조정 포지션 크기 및 분산투자 제안

Implements:
- Mean-Variance Optimization (Markowitz)
- Risk Parity
- Maximum Sharpe Ratio
- Minimum Volatility
- Kelly Criterion Position Sizing
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
from scipy.optimize import minimize

import logging

logger = logging.getLogger(__name__)


class OptimizationMethod(Enum):
    """Portfolio optimization methods."""
    MEAN_VARIANCE = "mean_variance"
    MAX_SHARPE = "max_sharpe"
    MIN_VOLATILITY = "min_volatility"
    RISK_PARITY = "risk_parity"
    EQUAL_WEIGHT = "equal_weight"
    KELLY = "kelly"


class RiskLevel(Enum):
    """Risk tolerance levels."""
    CONSERVATIVE = "conservative"
    MODERATE = "moderate"
    AGGRESSIVE = "aggressive"


@dataclass
class AssetInfo:
    """Information about an asset."""
    symbol: str
    name: str
    sector: str
    current_price: float
    expected_return: float = 0.0
    volatility: float = 0.0
    beta: float = 1.0
    market_cap: float = 0.0


@dataclass
class PortfolioAllocation:
    """Optimized portfolio allocation."""
    symbol: str
    name: str
    weight: float  # 0 to 1
    shares: int
    value: float
    sector: str
    expected_return: float
    volatility: float
    contribution_to_risk: float


@dataclass
class OptimizationResult:
    """Result of portfolio optimization."""
    method: str
    allocations: List[PortfolioAllocation]
    total_value: float
    expected_return: float
    expected_volatility: float
    sharpe_ratio: float
    diversification_ratio: float
    max_drawdown_estimate: float
    sector_allocation: Dict[str, float]
    risk_metrics: Dict[str, float]
    rebalance_suggestions: List[Dict[str, Any]]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "method": self.method,
            "allocations": [
                {
                    "symbol": a.symbol,
                    "name": a.name,
                    "weight": round(a.weight * 100, 2),
                    "shares": a.shares,
                    "value": round(a.value, 0),
                    "sector": a.sector,
                    "expected_return": round(a.expected_return * 100, 2),
                    "volatility": round(a.volatility * 100, 2),
                    "contribution_to_risk": round(a.contribution_to_risk * 100, 2),
                }
                for a in self.allocations
            ],
            "total_value": round(self.total_value, 0),
            "expected_return": round(self.expected_return * 100, 2),
            "expected_volatility": round(self.expected_volatility * 100, 2),
            "sharpe_ratio": round(self.sharpe_ratio, 4),
            "diversification_ratio": round(self.diversification_ratio, 4),
            "max_drawdown_estimate": round(self.max_drawdown_estimate * 100, 2),
            "sector_allocation": {k: round(v * 100, 2) for k, v in self.sector_allocation.items()},
            "risk_metrics": self.risk_metrics,
            "rebalance_suggestions": self.rebalance_suggestions,
        }


@dataclass
class PositionSizeResult:
    """Result of position sizing calculation."""
    symbol: str
    recommended_shares: int
    recommended_value: float
    max_shares: int
    max_value: float
    risk_per_share: float
    position_risk_pct: float
    kelly_fraction: float
    notes: List[str]


class PortfolioOptimizer:
    """
    Portfolio optimization engine.

    Provides various optimization methods and position sizing algorithms
    for building diversified, risk-adjusted portfolios.
    """

    RISK_FREE_RATE = 0.035  # 3.5% (한국 기준금리)
    TRADING_DAYS = 252

    def __init__(
        self,
        risk_level: RiskLevel = RiskLevel.MODERATE,
        max_position_size: float = 0.20,  # Max 20% in single position
        min_position_size: float = 0.02,  # Min 2% position
        max_sector_exposure: float = 0.40,  # Max 40% in single sector
    ):
        self.risk_level = risk_level
        self.max_position_size = max_position_size
        self.min_position_size = min_position_size
        self.max_sector_exposure = max_sector_exposure

        # Risk level parameters
        self.risk_params = {
            RiskLevel.CONSERVATIVE: {"target_vol": 0.10, "max_dd": 0.10},
            RiskLevel.MODERATE: {"target_vol": 0.15, "max_dd": 0.20},
            RiskLevel.AGGRESSIVE: {"target_vol": 0.25, "max_dd": 0.30},
        }

    def optimize(
        self,
        assets: List[AssetInfo],
        returns_data: pd.DataFrame,
        total_capital: float,
        method: OptimizationMethod = OptimizationMethod.MAX_SHARPE,
        constraints: Optional[Dict[str, Any]] = None,
    ) -> OptimizationResult:
        """
        Optimize portfolio allocation.

        Args:
            assets: List of assets to include
            returns_data: DataFrame with historical returns (columns = symbols)
            total_capital: Total capital to allocate
            method: Optimization method to use
            constraints: Additional constraints

        Returns:
            OptimizationResult with optimized allocations
        """
        n_assets = len(assets)
        if n_assets == 0:
            raise ValueError("At least one asset is required")

        symbols = [a.symbol for a in assets]

        # Calculate expected returns and covariance
        if returns_data.empty or len(returns_data) < 30:
            # Use provided expected returns if no data
            expected_returns = np.array([a.expected_return for a in assets])
            # Assume diagonal covariance with individual volatilities
            volatilities = np.array([a.volatility for a in assets])
            cov_matrix = np.diag(volatilities ** 2)
        else:
            # Calculate from historical data
            aligned_returns = returns_data[symbols].dropna()
            expected_returns = aligned_returns.mean().values * self.TRADING_DAYS
            cov_matrix = aligned_returns.cov().values * self.TRADING_DAYS

        # Optimize based on method
        if method == OptimizationMethod.EQUAL_WEIGHT:
            weights = self._equal_weight(n_assets)
        elif method == OptimizationMethod.MIN_VOLATILITY:
            weights = self._min_volatility(expected_returns, cov_matrix)
        elif method == OptimizationMethod.MAX_SHARPE:
            weights = self._max_sharpe(expected_returns, cov_matrix)
        elif method == OptimizationMethod.RISK_PARITY:
            weights = self._risk_parity(cov_matrix)
        elif method == OptimizationMethod.MEAN_VARIANCE:
            target_return = self.risk_params[self.risk_level]["target_vol"] * 0.8
            weights = self._mean_variance(expected_returns, cov_matrix, target_return)
        elif method == OptimizationMethod.KELLY:
            weights = self._kelly_criterion(expected_returns, cov_matrix)
        else:
            weights = self._equal_weight(n_assets)

        # Apply constraints
        weights = self._apply_constraints(weights, assets)

        # Calculate portfolio metrics
        portfolio_return = np.dot(weights, expected_returns)
        portfolio_vol = np.sqrt(np.dot(weights.T, np.dot(cov_matrix, weights)))
        sharpe = (portfolio_return - self.RISK_FREE_RATE) / portfolio_vol if portfolio_vol > 0 else 0

        # Calculate risk contributions
        marginal_risk = np.dot(cov_matrix, weights)
        risk_contributions = weights * marginal_risk / portfolio_vol if portfolio_vol > 0 else weights

        # Calculate diversification ratio
        weighted_vol = np.dot(weights, np.sqrt(np.diag(cov_matrix)))
        diversification_ratio = weighted_vol / portfolio_vol if portfolio_vol > 0 else 1

        # Estimate max drawdown (simplified)
        max_dd_estimate = portfolio_vol * 2.5  # Rule of thumb

        # Build allocations
        allocations = []
        sector_totals: Dict[str, float] = {}

        for i, asset in enumerate(assets):
            weight = weights[i]
            if weight < 0.001:  # Skip very small allocations
                continue

            value = total_capital * weight
            shares = int(value / asset.current_price)
            actual_value = shares * asset.current_price

            allocation = PortfolioAllocation(
                symbol=asset.symbol,
                name=asset.name,
                weight=weight,
                shares=shares,
                value=actual_value,
                sector=asset.sector,
                expected_return=expected_returns[i],
                volatility=np.sqrt(cov_matrix[i, i]),
                contribution_to_risk=risk_contributions[i],
            )
            allocations.append(allocation)

            sector_totals[asset.sector] = sector_totals.get(asset.sector, 0) + weight

        # Generate rebalance suggestions
        rebalance_suggestions = self._generate_rebalance_suggestions(
            allocations, sector_totals
        )

        return OptimizationResult(
            method=method.value,
            allocations=allocations,
            total_value=sum(a.value for a in allocations),
            expected_return=portfolio_return,
            expected_volatility=portfolio_vol,
            sharpe_ratio=sharpe,
            diversification_ratio=diversification_ratio,
            max_drawdown_estimate=max_dd_estimate,
            sector_allocation=sector_totals,
            risk_metrics={
                "var_95": round(-portfolio_vol * 1.645 * 100, 2),
                "cvar_95": round(-portfolio_vol * 2.06 * 100, 2),
                "beta": round(np.mean([a.beta for a in assets]), 2),
            },
            rebalance_suggestions=rebalance_suggestions,
        )

    def calculate_position_size(
        self,
        symbol: str,
        entry_price: float,
        stop_loss_price: float,
        total_capital: float,
        current_portfolio_value: float,
        win_rate: float = 0.5,
        avg_win_loss_ratio: float = 1.5,
        max_risk_per_trade: float = 0.02,
    ) -> PositionSizeResult:
        """
        Calculate optimal position size using multiple methods.

        Args:
            symbol: Stock symbol
            entry_price: Entry price
            stop_loss_price: Stop loss price
            total_capital: Total trading capital
            current_portfolio_value: Current portfolio value
            win_rate: Historical win rate
            avg_win_loss_ratio: Average win/loss ratio
            max_risk_per_trade: Maximum risk per trade (default 2%)

        Returns:
            PositionSizeResult with recommended position size
        """
        notes = []

        # Calculate risk per share
        risk_per_share = abs(entry_price - stop_loss_price)
        risk_pct = risk_per_share / entry_price

        if risk_pct > 0.10:
            notes.append("경고: 손절가가 진입가 대비 10% 이상 떨어져 있습니다")

        # Fixed fractional position sizing
        max_risk_amount = total_capital * max_risk_per_trade
        fixed_fractional_shares = int(max_risk_amount / risk_per_share) if risk_per_share > 0 else 0

        # Kelly Criterion
        if win_rate > 0 and avg_win_loss_ratio > 0:
            kelly_f = (win_rate * avg_win_loss_ratio - (1 - win_rate)) / avg_win_loss_ratio
            kelly_f = max(0, min(kelly_f, 0.25))  # Cap at 25%
        else:
            kelly_f = 0.10

        kelly_position_value = total_capital * kelly_f
        kelly_shares = int(kelly_position_value / entry_price)

        # Maximum position based on portfolio constraints
        max_position_value = total_capital * self.max_position_size
        max_shares = int(max_position_value / entry_price)

        # Recommended shares (more conservative of fixed fractional and kelly)
        recommended_shares = min(fixed_fractional_shares, kelly_shares, max_shares)
        recommended_value = recommended_shares * entry_price

        # Position risk as percentage of portfolio
        position_risk_pct = (recommended_shares * risk_per_share) / total_capital

        if recommended_shares == 0:
            notes.append("추천 포지션 크기가 0입니다. 손절가를 조정하거나 자본금을 확인하세요")

        if position_risk_pct > max_risk_per_trade:
            notes.append(f"포지션 리스크가 {max_risk_per_trade*100}%를 초과합니다")

        return PositionSizeResult(
            symbol=symbol,
            recommended_shares=recommended_shares,
            recommended_value=recommended_value,
            max_shares=max_shares,
            max_value=max_position_value,
            risk_per_share=risk_per_share,
            position_risk_pct=position_risk_pct,
            kelly_fraction=kelly_f,
            notes=notes,
        )

    def suggest_diversification(
        self,
        current_holdings: List[Dict[str, Any]],
        available_assets: List[AssetInfo],
        total_capital: float,
    ) -> Dict[str, Any]:
        """
        Suggest diversification improvements for current portfolio.

        Args:
            current_holdings: Current portfolio holdings
            available_assets: Available assets to consider
            total_capital: Total portfolio value

        Returns:
            Diversification suggestions
        """
        suggestions = []
        warnings = []

        # Analyze current allocation
        sector_exposure: Dict[str, float] = {}
        total_value = sum(h.get("value", 0) for h in current_holdings)

        for holding in current_holdings:
            sector = holding.get("sector", "Unknown")
            value = holding.get("value", 0)
            weight = value / total_value if total_value > 0 else 0

            sector_exposure[sector] = sector_exposure.get(sector, 0) + weight

            # Check position concentration
            if weight > self.max_position_size:
                warnings.append({
                    "type": "concentration",
                    "symbol": holding.get("symbol"),
                    "message": f"{holding.get('symbol')}이(가) 포트폴리오의 {weight*100:.1f}%를 차지합니다. 분산을 고려하세요.",
                    "current_weight": weight,
                    "recommended_weight": self.max_position_size,
                })

        # Check sector concentration
        for sector, exposure in sector_exposure.items():
            if exposure > self.max_sector_exposure:
                warnings.append({
                    "type": "sector_concentration",
                    "sector": sector,
                    "message": f"{sector} 섹터 비중이 {exposure*100:.1f}%입니다. 다른 섹터로 분산을 고려하세요.",
                    "current_exposure": exposure,
                    "recommended_max": self.max_sector_exposure,
                })

        # Find underrepresented sectors
        current_sectors = set(sector_exposure.keys())
        available_sectors = set(a.sector for a in available_assets)
        missing_sectors = available_sectors - current_sectors

        for sector in missing_sectors:
            sector_assets = [a for a in available_assets if a.sector == sector]
            if sector_assets:
                best_asset = max(sector_assets, key=lambda x: x.expected_return / x.volatility if x.volatility > 0 else 0)
                suggestions.append({
                    "type": "add_sector",
                    "sector": sector,
                    "symbol": best_asset.symbol,
                    "name": best_asset.name,
                    "message": f"{sector} 섹터 노출을 위해 {best_asset.name} 추가를 고려하세요.",
                    "expected_return": best_asset.expected_return,
                })

        # Calculate diversification score
        n_positions = len(current_holdings)
        n_sectors = len(sector_exposure)
        herfindahl = sum(w**2 for w in sector_exposure.values())
        diversification_score = min(100, (1 - herfindahl) * 100 * (n_sectors / max(n_sectors, 5)))

        return {
            "diversification_score": round(diversification_score, 1),
            "sector_exposure": {k: round(v * 100, 1) for k, v in sector_exposure.items()},
            "num_positions": n_positions,
            "num_sectors": n_sectors,
            "warnings": warnings,
            "suggestions": suggestions,
            "recommended_actions": self._get_recommended_actions(warnings, suggestions),
        }

    def _equal_weight(self, n_assets: int) -> np.ndarray:
        """Equal weight allocation."""
        return np.ones(n_assets) / n_assets

    def _min_volatility(
        self, expected_returns: np.ndarray, cov_matrix: np.ndarray
    ) -> np.ndarray:
        """Minimum volatility portfolio."""
        n = len(expected_returns)

        def portfolio_volatility(weights):
            return np.sqrt(np.dot(weights.T, np.dot(cov_matrix, weights)))

        constraints = [{"type": "eq", "fun": lambda x: np.sum(x) - 1}]
        bounds = tuple((0, self.max_position_size) for _ in range(n))
        initial = np.ones(n) / n

        result = minimize(
            portfolio_volatility,
            initial,
            method="SLSQP",
            bounds=bounds,
            constraints=constraints,
        )

        return result.x if result.success else initial

    def _max_sharpe(
        self, expected_returns: np.ndarray, cov_matrix: np.ndarray
    ) -> np.ndarray:
        """Maximum Sharpe ratio portfolio."""
        n = len(expected_returns)

        def neg_sharpe(weights):
            port_return = np.dot(weights, expected_returns)
            port_vol = np.sqrt(np.dot(weights.T, np.dot(cov_matrix, weights)))
            return -(port_return - self.RISK_FREE_RATE) / port_vol if port_vol > 0 else 0

        constraints = [{"type": "eq", "fun": lambda x: np.sum(x) - 1}]
        bounds = tuple((0, self.max_position_size) for _ in range(n))
        initial = np.ones(n) / n

        result = minimize(
            neg_sharpe,
            initial,
            method="SLSQP",
            bounds=bounds,
            constraints=constraints,
        )

        return result.x if result.success else initial

    def _risk_parity(self, cov_matrix: np.ndarray) -> np.ndarray:
        """Risk parity portfolio."""
        n = cov_matrix.shape[0]

        def risk_budget_objective(weights):
            port_vol = np.sqrt(np.dot(weights.T, np.dot(cov_matrix, weights)))
            marginal_risk = np.dot(cov_matrix, weights)
            risk_contributions = weights * marginal_risk / port_vol
            target_risk = port_vol / n
            return np.sum((risk_contributions - target_risk) ** 2)

        constraints = [{"type": "eq", "fun": lambda x: np.sum(x) - 1}]
        bounds = tuple((0.01, self.max_position_size) for _ in range(n))
        initial = np.ones(n) / n

        result = minimize(
            risk_budget_objective,
            initial,
            method="SLSQP",
            bounds=bounds,
            constraints=constraints,
        )

        return result.x if result.success else initial

    def _mean_variance(
        self,
        expected_returns: np.ndarray,
        cov_matrix: np.ndarray,
        target_return: float,
    ) -> np.ndarray:
        """Mean-variance optimization with target return."""
        n = len(expected_returns)

        def portfolio_volatility(weights):
            return np.sqrt(np.dot(weights.T, np.dot(cov_matrix, weights)))

        constraints = [
            {"type": "eq", "fun": lambda x: np.sum(x) - 1},
            {"type": "eq", "fun": lambda x: np.dot(x, expected_returns) - target_return},
        ]
        bounds = tuple((0, self.max_position_size) for _ in range(n))
        initial = np.ones(n) / n

        result = minimize(
            portfolio_volatility,
            initial,
            method="SLSQP",
            bounds=bounds,
            constraints=constraints,
        )

        return result.x if result.success else self._max_sharpe(expected_returns, cov_matrix)

    def _kelly_criterion(
        self, expected_returns: np.ndarray, cov_matrix: np.ndarray
    ) -> np.ndarray:
        """Kelly criterion based allocation (half-Kelly for safety)."""
        try:
            inv_cov = np.linalg.inv(cov_matrix)
            excess_returns = expected_returns - self.RISK_FREE_RATE
            kelly_weights = np.dot(inv_cov, excess_returns)

            # Normalize and apply half-Kelly
            kelly_weights = kelly_weights / np.sum(np.abs(kelly_weights)) * 0.5

            # Ensure non-negative and bounded
            kelly_weights = np.clip(kelly_weights, 0, self.max_position_size)
            kelly_weights = kelly_weights / np.sum(kelly_weights)

            return kelly_weights
        except np.linalg.LinAlgError:
            return self._equal_weight(len(expected_returns))

    def _apply_constraints(
        self, weights: np.ndarray, assets: List[AssetInfo]
    ) -> np.ndarray:
        """Apply position and sector constraints."""
        # Apply max position constraint
        weights = np.clip(weights, 0, self.max_position_size)

        # Apply sector constraints
        sector_weights: Dict[str, List[int]] = {}
        for i, asset in enumerate(assets):
            if asset.sector not in sector_weights:
                sector_weights[asset.sector] = []
            sector_weights[asset.sector].append(i)

        for sector, indices in sector_weights.items():
            sector_total = sum(weights[i] for i in indices)
            if sector_total > self.max_sector_exposure:
                scale = self.max_sector_exposure / sector_total
                for i in indices:
                    weights[i] *= scale

        # Renormalize
        total = np.sum(weights)
        if total > 0:
            weights = weights / total

        # Remove tiny positions
        weights[weights < self.min_position_size] = 0
        total = np.sum(weights)
        if total > 0:
            weights = weights / total

        return weights

    def _generate_rebalance_suggestions(
        self,
        allocations: List[PortfolioAllocation],
        sector_totals: Dict[str, float],
    ) -> List[Dict[str, Any]]:
        """Generate rebalancing suggestions."""
        suggestions = []

        # Check for overweight positions
        for alloc in allocations:
            if alloc.weight > self.max_position_size * 0.9:
                suggestions.append({
                    "action": "reduce",
                    "symbol": alloc.symbol,
                    "reason": f"포지션 비중이 {alloc.weight*100:.1f}%로 상한에 근접",
                    "target_weight": self.max_position_size * 0.8,
                })

        # Check for sector overweight
        for sector, weight in sector_totals.items():
            if weight > self.max_sector_exposure * 0.9:
                suggestions.append({
                    "action": "reduce_sector",
                    "sector": sector,
                    "reason": f"{sector} 섹터 비중이 {weight*100:.1f}%로 상한에 근접",
                    "current_weight": weight,
                })

        return suggestions

    def _get_recommended_actions(
        self, warnings: List[Dict], suggestions: List[Dict]
    ) -> List[str]:
        """Get prioritized recommended actions."""
        actions = []

        # High priority: concentration warnings
        for warning in warnings:
            if warning["type"] == "concentration":
                actions.append(f"⚠️ {warning['symbol']} 비중을 {warning['recommended_weight']*100:.0f}% 이하로 줄이세요")
            elif warning["type"] == "sector_concentration":
                actions.append(f"⚠️ {warning['sector']} 섹터 비중을 분산하세요")

        # Medium priority: diversification suggestions
        for suggestion in suggestions[:3]:
            if suggestion["type"] == "add_sector":
                actions.append(f"💡 {suggestion['sector']} 섹터 추가를 고려하세요: {suggestion['name']}")

        return actions
