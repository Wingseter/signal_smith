"""
Sector & Theme Analysis API Endpoints
섹터 로테이션, 테마별 종목 그룹핑
"""

from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.database import get_sync_db_dep
from app.api.routes.auth import get_current_user
from app.models.user import User
from app.models.stock import Stock, StockPrice
from app.services.sector_analysis import (
    SectorAnalyzer,
    SectorPerformance,
    ThemePerformance,
    KOREAN_SECTORS,
    INVESTMENT_THEMES,
    MarketCycle,
)

import pandas as pd
import logging

logger = logging.getLogger(__name__)

router = APIRouter()


# Response Models
class SectorResponse(BaseModel):
    sector_id: str
    name: str
    return_1d: float
    return_1w: float
    return_1m: float
    return_3m: float
    return_ytd: float
    relative_strength: float
    strength_rank: int
    strength_level: str
    volume_change: float
    momentum_score: float
    top_gainers: List[Dict[str, Any]]
    top_losers: List[Dict[str, Any]]


class ThemeResponse(BaseModel):
    theme_id: str
    name: str
    description: str
    is_hot: bool
    return_1d: float
    return_1w: float
    return_1m: float
    momentum_score: float
    stock_count: int
    avg_volume_change: float
    top_stocks: List[Dict[str, Any]]


class RotationSignalResponse(BaseModel):
    detected: bool
    from_sectors: List[str]
    to_sectors: List[str]
    confidence: float
    cycle_phase: str
    rationale: str


class SectorDetailResponse(BaseModel):
    sector_id: str
    name: str
    description: str
    symbols: List[str]
    stocks: List[Dict[str, Any]]
    performance: Dict[str, float]
    cycle_preference: List[str]


class ThemeDetailResponse(BaseModel):
    theme_id: str
    name: str
    description: str
    keywords: List[str]
    is_hot: bool
    symbols: List[str]
    stocks: List[Dict[str, Any]]
    performance: Dict[str, float]


@router.get("/list")
async def list_sectors(
    db: Session = Depends(get_sync_db_dep),
    current_user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    """Get list of all sectors with basic info."""
    sectors = []
    for sector_id, info in KOREAN_SECTORS.items():
        sectors.append({
            "id": sector_id,
            "name": info["name"],
            "description": info["description"],
            "stock_count": len(info["symbols"]),
        })
    return {"sectors": sectors, "total": len(sectors)}


@router.get("/performance", response_model=List[SectorResponse])
async def get_sector_performance(
    db: Session = Depends(get_sync_db_dep),
    current_user: User = Depends(get_current_user),
) -> List[SectorResponse]:
    """
    Get performance metrics for all sectors.
    """
    analyzer = SectorAnalyzer()

    # Fetch price data for all sector stocks
    all_symbols = set()
    for sector_info in KOREAN_SECTORS.values():
        all_symbols.update(sector_info.get("symbols", []))

    price_data = await _fetch_price_data(list(all_symbols), 90, db)

    # Analyze sectors
    performances = analyzer.analyze_sectors(price_data)

    return [
        SectorResponse(
            sector_id=p.sector_id,
            name=p.name,
            return_1d=p.return_1d,
            return_1w=p.return_1w,
            return_1m=p.return_1m,
            return_3m=p.return_3m,
            return_ytd=p.return_ytd,
            relative_strength=p.relative_strength,
            strength_rank=p.strength_rank,
            strength_level=p.strength_level.value,
            volume_change=p.volume_change,
            momentum_score=p.momentum_score,
            top_gainers=p.top_gainers,
            top_losers=p.top_losers,
        )
        for p in performances
    ]


@router.get("/sector/{sector_id}", response_model=SectorDetailResponse)
async def get_sector_detail(
    sector_id: str,
    db: Session = Depends(get_sync_db_dep),
    current_user: User = Depends(get_current_user),
) -> SectorDetailResponse:
    """
    Get detailed information about a specific sector.
    """
    if sector_id not in KOREAN_SECTORS:
        raise HTTPException(status_code=404, detail=f"Sector {sector_id} not found")

    sector_info = KOREAN_SECTORS[sector_id]
    symbols = sector_info.get("symbols", [])

    # Fetch stock details
    stocks = []
    for symbol in symbols:
        stock = db.query(Stock).filter(Stock.symbol == symbol).first()
        latest_price = (
            db.query(StockPrice)
            .filter(StockPrice.symbol == symbol)
            .order_by(StockPrice.date.desc())
            .first()
        )

        if stock:
            stocks.append({
                "symbol": symbol,
                "name": stock.name,
                "current_price": float(latest_price.close) if latest_price else 0,
                "change_pct": 0,  # Would calculate from price data
            })

    # Calculate sector performance
    price_data = await _fetch_price_data(symbols, 60, db)
    analyzer = SectorAnalyzer()
    performances = analyzer.analyze_sectors(price_data)

    sector_perf = next((p for p in performances if p.sector_id == sector_id), None)

    performance_dict = {}
    if sector_perf:
        performance_dict = {
            "return_1d": sector_perf.return_1d,
            "return_1w": sector_perf.return_1w,
            "return_1m": sector_perf.return_1m,
            "return_3m": sector_perf.return_3m,
            "momentum_score": sector_perf.momentum_score,
        }

    cycle_prefs = [c.value for c in sector_info.get("cycle_preference", [])]

    return SectorDetailResponse(
        sector_id=sector_id,
        name=sector_info["name"],
        description=sector_info["description"],
        symbols=symbols,
        stocks=stocks,
        performance=performance_dict,
        cycle_preference=cycle_prefs,
    )


@router.get("/themes", response_model=List[ThemeResponse])
async def get_themes_performance(
    hot_only: bool = False,
    db: Session = Depends(get_sync_db_dep),
    current_user: User = Depends(get_current_user),
) -> List[ThemeResponse]:
    """
    Get performance metrics for all investment themes.
    """
    analyzer = SectorAnalyzer()

    # Fetch price data for all theme stocks
    all_symbols = set()
    for theme_info in INVESTMENT_THEMES.values():
        all_symbols.update(theme_info.get("symbols", []))

    price_data = await _fetch_price_data(list(all_symbols), 60, db)

    # Analyze themes
    performances = analyzer.analyze_themes(price_data)

    if hot_only:
        performances = [p for p in performances if p.is_hot]

    return [
        ThemeResponse(
            theme_id=p.theme_id,
            name=p.name,
            description=p.description,
            is_hot=p.is_hot,
            return_1d=p.return_1d,
            return_1w=p.return_1w,
            return_1m=p.return_1m,
            momentum_score=p.momentum_score,
            stock_count=p.stock_count,
            avg_volume_change=p.avg_volume_change,
            top_stocks=p.top_stocks,
        )
        for p in performances
    ]


@router.get("/theme/{theme_id}", response_model=ThemeDetailResponse)
async def get_theme_detail(
    theme_id: str,
    db: Session = Depends(get_sync_db_dep),
    current_user: User = Depends(get_current_user),
) -> ThemeDetailResponse:
    """
    Get detailed information about a specific theme.
    """
    if theme_id not in INVESTMENT_THEMES:
        raise HTTPException(status_code=404, detail=f"Theme {theme_id} not found")

    theme_info = INVESTMENT_THEMES[theme_id]
    symbols = theme_info.get("symbols", [])

    # Fetch stock details
    stocks = []
    for symbol in symbols:
        stock = db.query(Stock).filter(Stock.symbol == symbol).first()
        latest_price = (
            db.query(StockPrice)
            .filter(StockPrice.symbol == symbol)
            .order_by(StockPrice.date.desc())
            .first()
        )

        if stock:
            stocks.append({
                "symbol": symbol,
                "name": stock.name,
                "current_price": float(latest_price.close) if latest_price else 0,
            })

    # Calculate theme performance
    price_data = await _fetch_price_data(symbols, 60, db)
    analyzer = SectorAnalyzer()
    performances = analyzer.analyze_themes(price_data)

    theme_perf = next((p for p in performances if p.theme_id == theme_id), None)

    performance_dict = {}
    if theme_perf:
        performance_dict = {
            "return_1d": theme_perf.return_1d,
            "return_1w": theme_perf.return_1w,
            "return_1m": theme_perf.return_1m,
            "momentum_score": theme_perf.momentum_score,
        }

    return ThemeDetailResponse(
        theme_id=theme_id,
        name=theme_info["name"],
        description=theme_info["description"],
        keywords=theme_info.get("keywords", []),
        is_hot=theme_info.get("hot", False),
        symbols=symbols,
        stocks=stocks,
        performance=performance_dict,
    )


@router.get("/rotation")
async def detect_rotation_signal(
    db: Session = Depends(get_sync_db_dep),
    current_user: User = Depends(get_current_user),
) -> RotationSignalResponse:
    """
    Detect sector rotation signals.
    """
    analyzer = SectorAnalyzer()

    # Fetch historical price data
    all_symbols = set()
    for sector_info in KOREAN_SECTORS.values():
        all_symbols.update(sector_info.get("symbols", []))

    price_data = await _fetch_price_data(list(all_symbols), 120, db)

    # Analyze current sectors
    current_performance = analyzer.analyze_sectors(price_data)

    # For proper rotation detection, we'd need historical snapshots
    # Here we simulate with current data
    signal = analyzer.detect_rotation([current_performance], lookback_periods=1)

    if signal:
        return RotationSignalResponse(
            detected=True,
            from_sectors=signal.from_sectors,
            to_sectors=signal.to_sectors,
            confidence=signal.confidence,
            cycle_phase=signal.cycle_phase.value,
            rationale=signal.rationale,
        )

    # Return cycle estimate even without rotation signal
    cycle = analyzer._estimate_cycle_phase(current_performance)

    return RotationSignalResponse(
        detected=False,
        from_sectors=[],
        to_sectors=[],
        confidence=0,
        cycle_phase=cycle.value,
        rationale="현재 명확한 섹터 로테이션 신호가 감지되지 않았습니다.",
    )


@router.get("/recommended")
async def get_recommended_sectors(
    cycle_phase: Optional[str] = None,
    db: Session = Depends(get_sync_db_dep),
    current_user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    """
    Get recommended sectors based on market cycle.
    """
    analyzer = SectorAnalyzer()

    # Determine cycle if not provided
    if not cycle_phase:
        all_symbols = set()
        for sector_info in KOREAN_SECTORS.values():
            all_symbols.update(sector_info.get("symbols", []))

        price_data = await _fetch_price_data(list(all_symbols), 60, db)
        performances = analyzer.analyze_sectors(price_data)
        cycle = analyzer._estimate_cycle_phase(performances)
    else:
        try:
            cycle = MarketCycle(cycle_phase)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid cycle phase: {cycle_phase}")

    recommendations = analyzer.get_recommended_sectors(cycle)

    cycle_names = {
        MarketCycle.EARLY_EXPANSION: "초기 확장",
        MarketCycle.MID_EXPANSION: "중기 확장",
        MarketCycle.LATE_EXPANSION: "후기 확장",
        MarketCycle.EARLY_RECESSION: "초기 침체",
        MarketCycle.MID_RECESSION: "중기 침체",
        MarketCycle.LATE_RECESSION: "후기 침체",
    }

    return {
        "cycle_phase": cycle.value,
        "cycle_name": cycle_names[cycle],
        "recommended_sectors": recommendations,
    }


@router.get("/correlation")
async def get_sector_correlation(
    period_days: int = Query(60, ge=20, le=252),
    db: Session = Depends(get_sync_db_dep),
    current_user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    """
    Get correlation matrix between sectors.
    """
    analyzer = SectorAnalyzer()

    all_symbols = set()
    for sector_info in KOREAN_SECTORS.values():
        all_symbols.update(sector_info.get("symbols", []))

    price_data = await _fetch_price_data(list(all_symbols), period_days, db)

    correlation_df = analyzer.calculate_sector_correlation(price_data, period_days)

    if correlation_df.empty:
        return {"correlation": {}, "sectors": []}

    # Convert to dict format
    correlation = {}
    sectors = list(correlation_df.columns)

    for sector in sectors:
        correlation[sector] = {
            other: round(correlation_df.loc[sector, other], 3)
            for other in sectors
        }

    return {
        "correlation": correlation,
        "sectors": sectors,
        "period_days": period_days,
    }


@router.get("/search")
async def search_by_keyword(
    keyword: str,
    db: Session = Depends(get_sync_db_dep),
    current_user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    """
    Search themes and stocks by keyword.
    """
    analyzer = SectorAnalyzer()
    results = analyzer.find_stocks_by_keyword(keyword)

    return {
        "keyword": keyword,
        "results": results,
        "count": len(results),
    }


@router.get("/heatmap")
async def get_sector_heatmap(
    db: Session = Depends(get_sync_db_dep),
    current_user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    """
    Get sector performance heatmap data.
    """
    analyzer = SectorAnalyzer()

    all_symbols = set()
    for sector_info in KOREAN_SECTORS.values():
        all_symbols.update(sector_info.get("symbols", []))

    price_data = await _fetch_price_data(list(all_symbols), 60, db)
    performances = analyzer.analyze_sectors(price_data)

    heatmap_data = []
    for p in performances:
        heatmap_data.append({
            "sector_id": p.sector_id,
            "name": p.name,
            "return_1d": p.return_1d,
            "return_1w": p.return_1w,
            "return_1m": p.return_1m,
            "momentum": p.momentum_score,
            "volume": p.volume_change,
        })

    return {"data": heatmap_data}


async def _fetch_price_data(
    symbols: List[str],
    days: int,
    db: Session,
) -> Dict[str, pd.DataFrame]:
    """Fetch price data for multiple symbols."""
    end_date = datetime.now()
    start_date = end_date - timedelta(days=days)

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
