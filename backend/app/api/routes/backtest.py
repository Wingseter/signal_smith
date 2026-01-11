"""
Backtesting API Endpoints
"""

from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from sqlalchemy import desc

from app.core.database import get_db
from app.api.routes.auth import get_current_user
from app.models.user import User
from app.models.backtest import BacktestResult as BacktestResultModel, BacktestComparison
from app.services.backtesting import (
    BacktestEngine,
    MACrossoverStrategy,
    RSIStrategy,
    BollingerBandStrategy,
    MACDStrategy,
)
from app.services.backtesting.engine import BacktestConfig, BacktestResult
from app.services.backtesting.strategies import CombinedStrategy

import pandas as pd
import logging

logger = logging.getLogger(__name__)

router = APIRouter()


# Request/Response Models
class BacktestRequest(BaseModel):
    """Request model for running a backtest."""
    strategy: str = Field(..., description="Strategy name: ma_crossover, rsi, bollinger, macd, combined")
    symbols: List[str] = Field(..., description="List of stock symbols to backtest")
    start_date: str = Field(..., description="Start date (YYYY-MM-DD)")
    end_date: str = Field(..., description="End date (YYYY-MM-DD)")
    initial_capital: float = Field(default=10_000_000, description="Initial capital in KRW")
    parameters: Optional[Dict[str, Any]] = Field(default=None, description="Strategy parameters")
    config: Optional[Dict[str, Any]] = Field(default=None, description="Backtest configuration")
    save_result: bool = Field(default=True, description="Save result to database")


class BacktestResponse(BaseModel):
    """Response model for backtest results."""
    success: bool
    id: Optional[int] = None  # Database ID if saved
    strategy_name: str
    start_date: str
    end_date: str
    initial_capital: float
    final_value: float
    total_return_pct: float
    num_trades: int
    metrics: Dict[str, Any]
    trades: List[Dict[str, Any]]
    equity_curve: List[Dict[str, Any]]
    errors: List[str]


class StrategyInfo(BaseModel):
    """Information about an available strategy."""
    name: str
    description: str
    parameters: Dict[str, Any]


class StrategiesResponse(BaseModel):
    """Response with available strategies."""
    strategies: List[StrategyInfo]


class BacktestHistoryItem(BaseModel):
    """Backtest history item."""
    id: int
    strategy_name: str
    strategy_display_name: Optional[str]
    symbols: List[str]
    start_date: str
    end_date: str
    initial_capital: float
    final_value: float
    total_return_pct: float
    total_trades: int
    sharpe_ratio: Optional[float]
    max_drawdown: Optional[float]
    win_rate: Optional[float]
    is_favorite: bool
    tags: Optional[List[str]]
    notes: Optional[str]
    created_at: str


class UpdateBacktestRequest(BaseModel):
    """Request to update backtest metadata."""
    is_favorite: Optional[bool] = None
    notes: Optional[str] = None
    tags: Optional[List[str]] = None


# Available strategies registry
STRATEGIES = {
    "ma_crossover": {
        "class": MACrossoverStrategy,
        "name": "이동평균 교차",
        "description": "단기/장기 이동평균 교차 전략",
        "default_params": {"short_period": 5, "long_period": 20},
        "param_schema": {
            "short_period": {"type": "int", "min": 2, "max": 50, "default": 5},
            "long_period": {"type": "int", "min": 5, "max": 200, "default": 20},
        },
    },
    "rsi": {
        "class": RSIStrategy,
        "name": "RSI 전략",
        "description": "RSI 과매수/과매도 전략",
        "default_params": {"period": 14, "oversold": 30, "overbought": 70},
        "param_schema": {
            "period": {"type": "int", "min": 5, "max": 50, "default": 14},
            "oversold": {"type": "float", "min": 10, "max": 40, "default": 30},
            "overbought": {"type": "float", "min": 60, "max": 90, "default": 70},
        },
    },
    "bollinger": {
        "class": BollingerBandStrategy,
        "name": "볼린저 밴드",
        "description": "볼린저 밴드 평균회귀 전략",
        "default_params": {"period": 20, "std_dev": 2.0},
        "param_schema": {
            "period": {"type": "int", "min": 10, "max": 50, "default": 20},
            "std_dev": {"type": "float", "min": 1.0, "max": 3.0, "default": 2.0},
        },
    },
    "macd": {
        "class": MACDStrategy,
        "name": "MACD 전략",
        "description": "MACD 시그널 교차 전략",
        "default_params": {"fast_period": 12, "slow_period": 26, "signal_period": 9},
        "param_schema": {
            "fast_period": {"type": "int", "min": 5, "max": 20, "default": 12},
            "slow_period": {"type": "int", "min": 15, "max": 50, "default": 26},
            "signal_period": {"type": "int", "min": 5, "max": 20, "default": 9},
        },
    },
    "combined": {
        "class": CombinedStrategy,
        "name": "복합 전략",
        "description": "MA + RSI 복합 전략",
        "default_params": {
            "ma_short": 5,
            "ma_long": 20,
            "rsi_period": 14,
            "rsi_oversold": 30,
            "rsi_overbought": 70,
            "min_confirmations": 2,
        },
        "param_schema": {
            "ma_short": {"type": "int", "min": 2, "max": 20, "default": 5},
            "ma_long": {"type": "int", "min": 10, "max": 100, "default": 20},
            "rsi_period": {"type": "int", "min": 5, "max": 30, "default": 14},
            "min_confirmations": {"type": "int", "min": 1, "max": 3, "default": 2},
        },
    },
}


@router.get("/strategies", response_model=StrategiesResponse)
async def get_strategies(
    current_user: User = Depends(get_current_user),
) -> StrategiesResponse:
    """Get list of available backtesting strategies."""
    strategies = []
    for key, info in STRATEGIES.items():
        strategies.append(
            StrategyInfo(
                name=key,
                description=info["description"],
                parameters=info["param_schema"],
            )
        )
    return StrategiesResponse(strategies=strategies)


@router.post("/run", response_model=BacktestResponse)
async def run_backtest(
    request: BacktestRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> BacktestResponse:
    """
    Run a backtest with the specified strategy and parameters.
    """
    # Validate strategy
    if request.strategy not in STRATEGIES:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown strategy: {request.strategy}. Available: {list(STRATEGIES.keys())}",
        )

    strategy_info = STRATEGIES[request.strategy]

    # Parse dates
    try:
        start_date = datetime.strptime(request.start_date, "%Y-%m-%d")
        end_date = datetime.strptime(request.end_date, "%Y-%m-%d")
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail="Invalid date format. Use YYYY-MM-DD",
        )

    if start_date >= end_date:
        raise HTTPException(
            status_code=400,
            detail="Start date must be before end date",
        )

    # Prepare strategy parameters
    params = strategy_info["default_params"].copy()
    if request.parameters:
        params.update(request.parameters)

    # Create strategy instance
    strategy_class = strategy_info["class"]
    strategy = strategy_class(**params)

    # Configure backtest
    config = BacktestConfig(initial_capital=request.initial_capital)
    if request.config:
        for key, value in request.config.items():
            if hasattr(config, key):
                setattr(config, key, value)

    # Fetch historical data for symbols
    data = await _fetch_historical_data(request.symbols, start_date, end_date, db)

    if not data:
        raise HTTPException(
            status_code=404,
            detail="No historical data found for the specified symbols and date range",
        )

    # Run backtest
    engine = BacktestEngine(config)
    try:
        result = engine.run(strategy, data, start_date, end_date)
    except Exception as e:
        logger.error(f"Backtest error: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Backtest execution error: {str(e)}",
        )

    # Convert result to response
    result_dict = result.to_dict()
    total_return_pct = ((result.final_value - request.initial_capital) / request.initial_capital) * 100

    # Calculate winning/losing trades
    winning_trades = sum(1 for t in result.trades if t.pnl and t.pnl > 0)
    losing_trades = sum(1 for t in result.trades if t.pnl and t.pnl < 0)

    # Save to database if requested
    saved_id = None
    if request.save_result:
        try:
            db_result = BacktestResultModel(
                user_id=current_user.id,
                strategy_name=request.strategy,
                strategy_display_name=strategy_info["name"],
                parameters=params,
                symbols=request.symbols,
                start_date=start_date,
                end_date=end_date,
                initial_capital=Decimal(str(request.initial_capital)),
                final_value=Decimal(str(result.final_value)),
                total_return_pct=Decimal(str(total_return_pct)),
                total_trades=len(result.trades),
                winning_trades=winning_trades,
                losing_trades=losing_trades,
                metrics=result_dict["metrics"],
                trades=result_dict["trades"],
                equity_curve=result_dict["equity_curve"],
            )
            db.add(db_result)
            db.commit()
            db.refresh(db_result)
            saved_id = db_result.id
            logger.info(f"Saved backtest result with ID {saved_id}")
        except Exception as e:
            logger.error(f"Failed to save backtest result: {e}")
            db.rollback()

    return BacktestResponse(
        success=True,
        id=saved_id,
        strategy_name=result.strategy_name,
        start_date=result_dict["start_date"],
        end_date=result_dict["end_date"],
        initial_capital=result.initial_capital,
        final_value=result.final_value,
        total_return_pct=total_return_pct,
        num_trades=len(result.trades),
        metrics=result_dict["metrics"],
        trades=result_dict["trades"],
        equity_curve=result_dict["equity_curve"],
        errors=result.errors,
    )


@router.post("/compare")
async def compare_strategies(
    symbols: List[str],
    start_date: str,
    end_date: str,
    strategies: Optional[List[str]] = None,
    initial_capital: float = 10_000_000,
    save_result: bool = True,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    """
    Compare multiple strategies on the same data.
    """
    # Parse dates
    try:
        start = datetime.strptime(start_date, "%Y-%m-%d")
        end = datetime.strptime(end_date, "%Y-%m-%d")
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format")

    # Use all strategies if not specified
    strategy_names = strategies or list(STRATEGIES.keys())

    # Fetch data once
    data = await _fetch_historical_data(symbols, start, end, db)
    if not data:
        raise HTTPException(status_code=404, detail="No data found")

    config = BacktestConfig(initial_capital=initial_capital)
    engine = BacktestEngine(config)

    results = {}
    for name in strategy_names:
        if name not in STRATEGIES:
            continue

        info = STRATEGIES[name]
        strategy = info["class"](**info["default_params"])

        try:
            result = engine.run(strategy, data, start, end)
            results[name] = {
                "strategy_name": result.strategy_name,
                "total_return_pct": ((result.final_value - initial_capital) / initial_capital) * 100,
                "sharpe_ratio": result.metrics.sharpe_ratio if result.metrics else 0,
                "max_drawdown": result.metrics.max_drawdown if result.metrics else 0,
                "win_rate": result.metrics.win_rate if result.metrics else 0,
                "total_trades": len(result.trades),
                "final_value": result.final_value,
            }
        except Exception as e:
            logger.warning(f"Strategy {name} failed: {e}")
            results[name] = {"error": str(e)}

    # Rank by Sharpe ratio
    ranking = sorted(
        [(k, v.get("sharpe_ratio", 0)) for k, v in results.items() if "error" not in v],
        key=lambda x: x[1],
        reverse=True,
    )

    response = {
        "results": results,
        "ranking": [{"strategy": k, "sharpe_ratio": v} for k, v in ranking],
        "best_strategy": ranking[0][0] if ranking else None,
    }

    # Save comparison to database
    if save_result:
        try:
            comparison = BacktestComparison(
                user_id=current_user.id,
                name=f"Comparison {datetime.now().strftime('%Y-%m-%d %H:%M')}",
                symbols=symbols,
                start_date=start,
                end_date=end,
                initial_capital=Decimal(str(initial_capital)),
                strategies=strategy_names,
                results=results,
                best_strategy=response["best_strategy"],
                ranking=response["ranking"],
            )
            db.add(comparison)
            db.commit()
            db.refresh(comparison)
            response["comparison_id"] = comparison.id
        except Exception as e:
            logger.error(f"Failed to save comparison: {e}")
            db.rollback()

    return response


@router.get("/history")
async def get_backtest_history(
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    strategy: Optional[str] = None,
    favorites_only: bool = False,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    """
    Get user's backtest history.
    """
    query = db.query(BacktestResultModel).filter(
        BacktestResultModel.user_id == current_user.id
    )

    if strategy:
        query = query.filter(BacktestResultModel.strategy_name == strategy)

    if favorites_only:
        query = query.filter(BacktestResultModel.is_favorite == True)

    # Get total count
    total = query.count()

    # Get paginated results
    results = (
        query
        .order_by(desc(BacktestResultModel.created_at))
        .offset(offset)
        .limit(limit)
        .all()
    )

    history = []
    for r in results:
        metrics = r.metrics or {}
        history.append(BacktestHistoryItem(
            id=r.id,
            strategy_name=r.strategy_name,
            strategy_display_name=r.strategy_display_name,
            symbols=r.symbols,
            start_date=r.start_date.strftime("%Y-%m-%d"),
            end_date=r.end_date.strftime("%Y-%m-%d"),
            initial_capital=float(r.initial_capital),
            final_value=float(r.final_value),
            total_return_pct=float(r.total_return_pct),
            total_trades=r.total_trades,
            sharpe_ratio=metrics.get("sharpe_ratio"),
            max_drawdown=metrics.get("max_drawdown"),
            win_rate=metrics.get("win_rate"),
            is_favorite=r.is_favorite,
            tags=r.tags,
            notes=r.notes,
            created_at=r.created_at.isoformat(),
        ).model_dump())

    return {
        "history": history,
        "total": total,
        "limit": limit,
        "offset": offset,
    }


@router.get("/history/{backtest_id}")
async def get_backtest_detail(
    backtest_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    """
    Get detailed backtest result by ID.
    """
    result = (
        db.query(BacktestResultModel)
        .filter(
            BacktestResultModel.id == backtest_id,
            BacktestResultModel.user_id == current_user.id,
        )
        .first()
    )

    if not result:
        raise HTTPException(status_code=404, detail="Backtest result not found")

    return {
        "id": result.id,
        "strategy_name": result.strategy_name,
        "strategy_display_name": result.strategy_display_name,
        "parameters": result.parameters,
        "symbols": result.symbols,
        "start_date": result.start_date.strftime("%Y-%m-%d"),
        "end_date": result.end_date.strftime("%Y-%m-%d"),
        "initial_capital": float(result.initial_capital),
        "final_value": float(result.final_value),
        "total_return_pct": float(result.total_return_pct),
        "total_trades": result.total_trades,
        "winning_trades": result.winning_trades,
        "losing_trades": result.losing_trades,
        "metrics": result.metrics,
        "trades": result.trades,
        "equity_curve": result.equity_curve,
        "is_favorite": result.is_favorite,
        "notes": result.notes,
        "tags": result.tags,
        "created_at": result.created_at.isoformat(),
    }


@router.patch("/history/{backtest_id}")
async def update_backtest(
    backtest_id: int,
    request: UpdateBacktestRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    """
    Update backtest metadata (favorite, notes, tags).
    """
    result = (
        db.query(BacktestResultModel)
        .filter(
            BacktestResultModel.id == backtest_id,
            BacktestResultModel.user_id == current_user.id,
        )
        .first()
    )

    if not result:
        raise HTTPException(status_code=404, detail="Backtest result not found")

    if request.is_favorite is not None:
        result.is_favorite = request.is_favorite

    if request.notes is not None:
        result.notes = request.notes

    if request.tags is not None:
        result.tags = request.tags

    db.commit()
    db.refresh(result)

    return {"message": "Updated successfully", "id": result.id}


@router.delete("/history/{backtest_id}")
async def delete_backtest(
    backtest_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Dict[str, str]:
    """
    Delete a backtest result.
    """
    result = (
        db.query(BacktestResultModel)
        .filter(
            BacktestResultModel.id == backtest_id,
            BacktestResultModel.user_id == current_user.id,
        )
        .first()
    )

    if not result:
        raise HTTPException(status_code=404, detail="Backtest result not found")

    db.delete(result)
    db.commit()

    return {"message": "Deleted successfully"}


@router.get("/comparisons")
async def get_comparison_history(
    limit: int = Query(default=10, ge=1, le=50),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    """
    Get user's strategy comparison history.
    """
    comparisons = (
        db.query(BacktestComparison)
        .filter(BacktestComparison.user_id == current_user.id)
        .order_by(desc(BacktestComparison.created_at))
        .limit(limit)
        .all()
    )

    return {
        "comparisons": [
            {
                "id": c.id,
                "name": c.name,
                "description": c.description,
                "symbols": c.symbols,
                "start_date": c.start_date.strftime("%Y-%m-%d"),
                "end_date": c.end_date.strftime("%Y-%m-%d"),
                "initial_capital": float(c.initial_capital),
                "strategies": c.strategies,
                "best_strategy": c.best_strategy,
                "ranking": c.ranking,
                "created_at": c.created_at.isoformat(),
            }
            for c in comparisons
        ]
    }


async def _fetch_historical_data(
    symbols: List[str],
    start_date: datetime,
    end_date: datetime,
    db: Session,
) -> Dict[str, pd.DataFrame]:
    """
    Fetch historical OHLCV data for backtesting.
    """
    from app.models.stock import StockPrice

    data = {}

    for symbol in symbols:
        # Query price data from database
        prices = (
            db.query(StockPrice)
            .filter(
                StockPrice.symbol == symbol,
                StockPrice.date >= start_date,
                StockPrice.date <= end_date,
            )
            .order_by(StockPrice.date)
            .all()
        )

        if not prices:
            logger.warning(f"No price data found for {symbol}")
            continue

        # Convert to DataFrame
        df = pd.DataFrame([
            {
                "date": p.date,
                "open": float(p.open),
                "high": float(p.high),
                "low": float(p.low),
                "close": float(p.close),
                "volume": int(p.volume),
            }
            for p in prices
        ])

        df["date"] = pd.to_datetime(df["date"])
        df.set_index("date", inplace=True)

        data[symbol] = df

    return data
