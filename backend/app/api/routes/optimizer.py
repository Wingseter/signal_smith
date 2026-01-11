"""
Portfolio Optimization API Endpoints
리스크 조정 포지션 크기 및 분산투자 제안
"""

from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.user import User
from app.models.stock import Stock, StockPrice
from app.models.portfolio import Portfolio, Holding
from app.services.portfolio_optimizer import (
    PortfolioOptimizer,
    OptimizationMethod,
    RiskLevel,
    AssetInfo,
)

import pandas as pd
import numpy as np
import logging

logger = logging.getLogger(__name__)

router = APIRouter()


# Request/Response Models
class OptimizeRequest(BaseModel):
    """Request for portfolio optimization."""
    symbols: List[str] = Field(..., description="List of stock symbols")
    total_capital: float = Field(..., description="Total capital to allocate")
    method: str = Field(default="max_sharpe", description="Optimization method")
    risk_level: str = Field(default="moderate", description="Risk level: conservative, moderate, aggressive")
    max_position_size: float = Field(default=0.20, description="Maximum single position size")
    max_sector_exposure: float = Field(default=0.40, description="Maximum sector exposure")


class PositionSizeRequest(BaseModel):
    """Request for position sizing."""
    symbol: str
    entry_price: float
    stop_loss_price: float
    total_capital: float
    current_portfolio_value: float = 0
    win_rate: float = 0.5
    avg_win_loss_ratio: float = 1.5
    max_risk_per_trade: float = 0.02


class DiversificationRequest(BaseModel):
    """Request for diversification analysis."""
    portfolio_id: Optional[int] = None


# Response Models
class AllocationResponse(BaseModel):
    symbol: str
    name: str
    weight: float
    shares: int
    value: float
    sector: str
    expected_return: float
    volatility: float
    contribution_to_risk: float


class OptimizationResponse(BaseModel):
    method: str
    allocations: List[AllocationResponse]
    total_value: float
    expected_return: float
    expected_volatility: float
    sharpe_ratio: float
    diversification_ratio: float
    max_drawdown_estimate: float
    sector_allocation: Dict[str, float]
    risk_metrics: Dict[str, float]
    rebalance_suggestions: List[Dict[str, Any]]


class PositionSizeResponse(BaseModel):
    symbol: str
    recommended_shares: int
    recommended_value: float
    max_shares: int
    max_value: float
    risk_per_share: float
    position_risk_pct: float
    kelly_fraction: float
    notes: List[str]


# Available methods
OPTIMIZATION_METHODS = {
    "mean_variance": OptimizationMethod.MEAN_VARIANCE,
    "max_sharpe": OptimizationMethod.MAX_SHARPE,
    "min_volatility": OptimizationMethod.MIN_VOLATILITY,
    "risk_parity": OptimizationMethod.RISK_PARITY,
    "equal_weight": OptimizationMethod.EQUAL_WEIGHT,
    "kelly": OptimizationMethod.KELLY,
}

RISK_LEVELS = {
    "conservative": RiskLevel.CONSERVATIVE,
    "moderate": RiskLevel.MODERATE,
    "aggressive": RiskLevel.AGGRESSIVE,
}


@router.get("/methods")
async def get_optimization_methods() -> Dict[str, Any]:
    """Get available optimization methods."""
    return {
        "methods": [
            {
                "id": "max_sharpe",
                "name": "최대 샤프 비율",
                "description": "위험 대비 수익을 최대화하는 포트폴리오",
            },
            {
                "id": "min_volatility",
                "name": "최소 변동성",
                "description": "변동성을 최소화하는 안정적인 포트폴리오",
            },
            {
                "id": "risk_parity",
                "name": "리스크 패리티",
                "description": "각 자산의 리스크 기여도를 동일하게",
            },
            {
                "id": "mean_variance",
                "name": "평균-분산 최적화",
                "description": "목표 수익률에서 리스크 최소화",
            },
            {
                "id": "equal_weight",
                "name": "동일 비중",
                "description": "모든 자산에 동일 비중 배분",
            },
            {
                "id": "kelly",
                "name": "켈리 기준",
                "description": "수학적 최적 베팅 비율 기반",
            },
        ],
        "risk_levels": [
            {"id": "conservative", "name": "보수적", "target_volatility": "10%"},
            {"id": "moderate", "name": "중립적", "target_volatility": "15%"},
            {"id": "aggressive", "name": "공격적", "target_volatility": "25%"},
        ],
    }


@router.post("/optimize", response_model=OptimizationResponse)
async def optimize_portfolio(
    request: OptimizeRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> OptimizationResponse:
    """
    Optimize portfolio allocation.
    """
    # Validate method
    if request.method not in OPTIMIZATION_METHODS:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown method: {request.method}. Available: {list(OPTIMIZATION_METHODS.keys())}",
        )

    if request.risk_level not in RISK_LEVELS:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown risk level: {request.risk_level}. Available: {list(RISK_LEVELS.keys())}",
        )

    # Fetch asset information
    assets = []
    for symbol in request.symbols:
        stock = db.query(Stock).filter(Stock.symbol == symbol).first()
        if not stock:
            logger.warning(f"Stock {symbol} not found, skipping")
            continue

        # Get latest price
        latest_price = (
            db.query(StockPrice)
            .filter(StockPrice.symbol == symbol)
            .order_by(StockPrice.date.desc())
            .first()
        )

        current_price = float(latest_price.close) if latest_price else 50000

        # Calculate expected return and volatility from historical data
        expected_return, volatility = await _calculate_asset_stats(symbol, db)

        assets.append(
            AssetInfo(
                symbol=symbol,
                name=stock.name,
                sector=stock.sector or "Unknown",
                current_price=current_price,
                expected_return=expected_return,
                volatility=volatility,
                beta=1.0,  # Could be calculated from market data
            )
        )

    if not assets:
        raise HTTPException(status_code=404, detail="No valid assets found")

    # Fetch returns data
    returns_data = await _fetch_returns_data([a.symbol for a in assets], db)

    # Create optimizer
    optimizer = PortfolioOptimizer(
        risk_level=RISK_LEVELS[request.risk_level],
        max_position_size=request.max_position_size,
        max_sector_exposure=request.max_sector_exposure,
    )

    # Run optimization
    try:
        result = optimizer.optimize(
            assets=assets,
            returns_data=returns_data,
            total_capital=request.total_capital,
            method=OPTIMIZATION_METHODS[request.method],
        )
    except Exception as e:
        logger.error(f"Optimization error: {e}")
        raise HTTPException(status_code=500, detail=f"Optimization failed: {str(e)}")

    result_dict = result.to_dict()

    return OptimizationResponse(
        method=result_dict["method"],
        allocations=[AllocationResponse(**a) for a in result_dict["allocations"]],
        total_value=result_dict["total_value"],
        expected_return=result_dict["expected_return"],
        expected_volatility=result_dict["expected_volatility"],
        sharpe_ratio=result_dict["sharpe_ratio"],
        diversification_ratio=result_dict["diversification_ratio"],
        max_drawdown_estimate=result_dict["max_drawdown_estimate"],
        sector_allocation=result_dict["sector_allocation"],
        risk_metrics=result_dict["risk_metrics"],
        rebalance_suggestions=result_dict["rebalance_suggestions"],
    )


@router.post("/position-size", response_model=PositionSizeResponse)
async def calculate_position_size(
    request: PositionSizeRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> PositionSizeResponse:
    """
    Calculate optimal position size for a trade.
    """
    if request.entry_price <= 0:
        raise HTTPException(status_code=400, detail="Entry price must be positive")

    if request.stop_loss_price <= 0:
        raise HTTPException(status_code=400, detail="Stop loss price must be positive")

    if request.total_capital <= 0:
        raise HTTPException(status_code=400, detail="Total capital must be positive")

    optimizer = PortfolioOptimizer()

    result = optimizer.calculate_position_size(
        symbol=request.symbol,
        entry_price=request.entry_price,
        stop_loss_price=request.stop_loss_price,
        total_capital=request.total_capital,
        current_portfolio_value=request.current_portfolio_value,
        win_rate=request.win_rate,
        avg_win_loss_ratio=request.avg_win_loss_ratio,
        max_risk_per_trade=request.max_risk_per_trade,
    )

    return PositionSizeResponse(
        symbol=result.symbol,
        recommended_shares=result.recommended_shares,
        recommended_value=result.recommended_value,
        max_shares=result.max_shares,
        max_value=result.max_value,
        risk_per_share=result.risk_per_share,
        position_risk_pct=result.position_risk_pct,
        kelly_fraction=result.kelly_fraction,
        notes=result.notes,
    )


@router.get("/diversification")
async def analyze_diversification(
    portfolio_id: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    """
    Analyze portfolio diversification and suggest improvements.
    """
    # Get portfolio
    if portfolio_id:
        portfolio = (
            db.query(Portfolio)
            .filter(Portfolio.id == portfolio_id, Portfolio.user_id == current_user.id)
            .first()
        )
    else:
        portfolio = (
            db.query(Portfolio)
            .filter(Portfolio.user_id == current_user.id, Portfolio.is_default == True)
            .first()
        )

    if not portfolio:
        return {
            "diversification_score": 0,
            "sector_exposure": {},
            "num_positions": 0,
            "num_sectors": 0,
            "warnings": [],
            "suggestions": [
                {
                    "type": "empty_portfolio",
                    "message": "포트폴리오에 보유 종목이 없습니다. 종목을 추가하세요.",
                }
            ],
            "recommended_actions": ["포트폴리오에 종목을 추가하세요"],
        }

    # Get holdings
    holdings = db.query(Holding).filter(Holding.portfolio_id == portfolio.id).all()

    if not holdings:
        return {
            "diversification_score": 0,
            "sector_exposure": {},
            "num_positions": 0,
            "num_sectors": 0,
            "warnings": [],
            "suggestions": [],
            "recommended_actions": ["포트폴리오에 종목을 추가하세요"],
        }

    # Build current holdings data
    current_holdings = []
    for holding in holdings:
        stock = db.query(Stock).filter(Stock.symbol == holding.symbol).first()

        # Get current price
        latest_price = (
            db.query(StockPrice)
            .filter(StockPrice.symbol == holding.symbol)
            .order_by(StockPrice.date.desc())
            .first()
        )
        current_price = float(latest_price.close) if latest_price else float(holding.avg_buy_price)
        value = current_price * holding.quantity

        current_holdings.append({
            "symbol": holding.symbol,
            "name": stock.name if stock else holding.symbol,
            "sector": stock.sector if stock else "Unknown",
            "quantity": holding.quantity,
            "value": value,
        })

    total_value = sum(h["value"] for h in current_holdings)

    # Get available assets for suggestions
    available_assets = []
    stocks = db.query(Stock).limit(50).all()
    for stock in stocks:
        if stock.symbol not in [h["symbol"] for h in current_holdings]:
            exp_ret, vol = await _calculate_asset_stats(stock.symbol, db)
            latest_price = (
                db.query(StockPrice)
                .filter(StockPrice.symbol == stock.symbol)
                .order_by(StockPrice.date.desc())
                .first()
            )
            available_assets.append(
                AssetInfo(
                    symbol=stock.symbol,
                    name=stock.name,
                    sector=stock.sector or "Unknown",
                    current_price=float(latest_price.close) if latest_price else 50000,
                    expected_return=exp_ret,
                    volatility=vol,
                )
            )

    optimizer = PortfolioOptimizer()
    result = optimizer.suggest_diversification(
        current_holdings=current_holdings,
        available_assets=available_assets,
        total_capital=total_value,
    )

    return result


@router.post("/rebalance")
async def suggest_rebalancing(
    portfolio_id: Optional[int] = None,
    target_method: str = "max_sharpe",
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    """
    Suggest trades to rebalance portfolio to target allocation.
    """
    # Get portfolio
    if portfolio_id:
        portfolio = (
            db.query(Portfolio)
            .filter(Portfolio.id == portfolio_id, Portfolio.user_id == current_user.id)
            .first()
        )
    else:
        portfolio = (
            db.query(Portfolio)
            .filter(Portfolio.user_id == current_user.id, Portfolio.is_default == True)
            .first()
        )

    if not portfolio:
        raise HTTPException(status_code=404, detail="Portfolio not found")

    holdings = db.query(Holding).filter(Holding.portfolio_id == portfolio.id).all()

    if not holdings:
        return {"trades": [], "message": "포트폴리오가 비어 있습니다"}

    # Calculate current values
    current_holdings = {}
    total_value = 0

    for holding in holdings:
        latest_price = (
            db.query(StockPrice)
            .filter(StockPrice.symbol == holding.symbol)
            .order_by(StockPrice.date.desc())
            .first()
        )
        price = float(latest_price.close) if latest_price else float(holding.avg_buy_price)
        value = price * holding.quantity
        current_holdings[holding.symbol] = {
            "quantity": holding.quantity,
            "price": price,
            "value": value,
            "current_weight": 0,
        }
        total_value += value

    # Calculate current weights
    for symbol in current_holdings:
        current_holdings[symbol]["current_weight"] = current_holdings[symbol]["value"] / total_value

    # Get optimized allocation
    symbols = list(current_holdings.keys())
    assets = []
    for symbol in symbols:
        stock = db.query(Stock).filter(Stock.symbol == symbol).first()
        exp_ret, vol = await _calculate_asset_stats(symbol, db)
        assets.append(
            AssetInfo(
                symbol=symbol,
                name=stock.name if stock else symbol,
                sector=stock.sector if stock else "Unknown",
                current_price=current_holdings[symbol]["price"],
                expected_return=exp_ret,
                volatility=vol,
            )
        )

    returns_data = await _fetch_returns_data(symbols, db)

    optimizer = PortfolioOptimizer()
    method = OPTIMIZATION_METHODS.get(target_method, OptimizationMethod.MAX_SHARPE)
    result = optimizer.optimize(assets, returns_data, total_value, method)

    # Calculate trades needed
    trades = []
    target_weights = {a.symbol: a.weight for a in result.allocations}

    for symbol, current in current_holdings.items():
        target_weight = target_weights.get(symbol, 0)
        current_weight = current["current_weight"]
        weight_diff = target_weight - current_weight

        if abs(weight_diff) > 0.02:  # Only suggest if difference > 2%
            value_diff = weight_diff * total_value
            shares_diff = int(value_diff / current["price"])

            if shares_diff != 0:
                trades.append({
                    "symbol": symbol,
                    "action": "buy" if shares_diff > 0 else "sell",
                    "shares": abs(shares_diff),
                    "value": abs(value_diff),
                    "current_weight": round(current_weight * 100, 2),
                    "target_weight": round(target_weight * 100, 2),
                })

    return {
        "trades": trades,
        "current_sharpe": round(
            sum(current_holdings[s]["current_weight"] * a.expected_return for s, a in zip(symbols, assets))
            / (result.expected_volatility if result.expected_volatility > 0 else 1),
            4,
        ),
        "target_sharpe": result.sharpe_ratio,
        "improvement": "리밸런싱으로 샤프 비율 개선 가능" if trades else "현재 배분이 최적에 가깝습니다",
    }


async def _calculate_asset_stats(symbol: str, db: Session) -> tuple[float, float]:
    """Calculate expected return and volatility for an asset."""
    # Get price history
    end_date = datetime.now()
    start_date = end_date - timedelta(days=365)

    prices = (
        db.query(StockPrice)
        .filter(
            StockPrice.symbol == symbol,
            StockPrice.date >= start_date,
        )
        .order_by(StockPrice.date)
        .all()
    )

    if len(prices) < 30:
        return 0.10, 0.25  # Default values

    closes = [float(p.close) for p in prices]
    returns = np.diff(closes) / closes[:-1]

    expected_return = np.mean(returns) * 252  # Annualized
    volatility = np.std(returns) * np.sqrt(252)  # Annualized

    return expected_return, volatility


async def _fetch_returns_data(symbols: List[str], db: Session) -> pd.DataFrame:
    """Fetch historical returns data for multiple symbols."""
    end_date = datetime.now()
    start_date = end_date - timedelta(days=365)

    data = {}
    for symbol in symbols:
        prices = (
            db.query(StockPrice)
            .filter(
                StockPrice.symbol == symbol,
                StockPrice.date >= start_date,
            )
            .order_by(StockPrice.date)
            .all()
        )

        if prices:
            df = pd.DataFrame([
                {"date": p.date, "close": float(p.close)}
                for p in prices
            ])
            df.set_index("date", inplace=True)
            df["return"] = df["close"].pct_change()
            data[symbol] = df["return"]

    if data:
        returns_df = pd.DataFrame(data)
        return returns_df.dropna()

    return pd.DataFrame()
